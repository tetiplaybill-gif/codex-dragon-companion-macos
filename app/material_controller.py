"""Explicit background material operations and embedded settings controls."""
import threading,time
from PySide6.QtCore import QObject,QThread,QTimer,Signal
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QPushButton,QProgressBar
from material_store import MaterialError
from app_updates import UpdateCancelled

class MaterialJob(QThread):
    result=Signal(str,object);failed=Signal(str);progress=Signal(int,int,str)
    def __init__(self,store,tier,parent=None):
        super().__init__(parent);self.store=store;self.tier=tier;self.cancel=threading.Event()
    def run(self):
        last=[0.]
        def progress(n,t,p):
            now=time.monotonic()
            if now-last[0]>=.12 or n==t:
                last[0]=now;self.progress.emit(n,t,p)
        try:
            root=self.store.ensure(self.tier,self.cancel.is_set,progress)
            if not self.cancel.is_set():self.result.emit(self.tier,root)
        except (MaterialError,UpdateCancelled,OSError,ValueError) as exc:self.failed.emit(str(exc)[:220])
        except Exception:self.failed.emit('素材准备失败，继续使用原画质')

class MaterialController(QObject):
    changed=Signal(object);ready=Signal(str,object);idle=Signal();removeRequested=Signal();rollbackRequested=Signal()
    def __init__(self,store,parent=None):
        super().__init__(parent);self.store=store;self.job=None;self.closing=False
        self.state=dict(phase='idle',message='',downloaded=0,total=0)
    def snapshot(self):
        return dict(self.state,current=self.store.current,lightCached=self.store.known_available('light'),hdCached=self.store.known_available('hd'),supported=bool(self.store.catalog),busy=self.job is not None,canRollback=bool(self.store.patch_previous))
    def publish(self,**changes):self.state.update(changes);self.changed.emit(self.snapshot())
    def request(self,tier):
        updates=getattr(self.parent(),'updates',None)
        if updates and (updates.job or updates.state['phase']=='pending'):self.publish(message='请先完成当前更新');return False
        if self.closing or self.job or self.state['phase']=='pending' or tier not in ('light','hd'):return False
        if tier==self.store.current and self.store.known_available(tier):self.publish(message='当前已使用所选画质');return False
        self.publish(phase='verifying' if self.store.known_available(tier) else 'downloading',message='正在准备素材…',downloaded=0,total=0)
        job=self.job=MaterialJob(self.store,tier,self);job.result.connect(self._result);job.failed.connect(lambda text:self.publish(phase='error',message=text));job.progress.connect(self._progress);job.finished.connect(self._finished);self.changed.emit(self.snapshot());job.start();return True
    def _progress(self,n,total,phase):
        if not self.closing:self.publish(phase=phase,downloaded=n,total=total,message='正在下载动画资源…' if phase=='downloading' else '正在校验素材…')
    def _result(self,tier,root):
        if self.closing or self.job.cancel.is_set():return
        self.publish(phase='pending',message='素材已就绪，等待当前动作自然结束后切换…');self.ready.emit(tier,root)
    def applied(self):self.publish(phase='idle',message='画质已切换，原动画与 Codex 联动继续保留')
    def remove(self,plan):
        if self.job:return False
        job=self.job=RemovalJob(self.store,plan,self)
        job.done.connect(lambda:self.publish(phase='idle',message='动画资源已移除，仅保留卡片'))
        job.failed.connect(self.failed);job.finished.connect(self._finished)
        self.publish(phase='removing',message='正在移除动画资源…');job.start();return True
    def failed(self,text):self.publish(phase='error',message=str(text)[:220])
    def _finished(self):
        job=self.job;self.job=None
        if job:
            if job.cancel.is_set() and not self.closing:self.publish(phase='idle',message='已取消，继续使用原画质')
            job.deleteLater()
        self.changed.emit(self.snapshot());self.idle.emit()
    def cancel(self):
        if self.job:self.job.cancel.set();self.publish(message='正在取消素材操作…')
    def shutdown(self):
        self.closing=True
        if self.job:self.job.cancel.set();return False
        return True

class RemovalJob(QThread):
    done=Signal();failed=Signal(str)
    def __init__(self,store,plan,parent=None):
        super().__init__(parent);self.store=store;self.plan=plan;self.cancel=threading.Event()
    def run(self):
        from material_removal import remove_animations
        try:remove_animations(self.store,self.plan);self.done.emit()
        except (OSError,ValueError) as exc:self.failed.emit('移除未完成，卡片继续可用：'+str(exc)[:150])

class MaterialPanel(QWidget):
    def __init__(self,controller,parent=None):
        super().__init__(parent);self.controller=controller
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        self.summary=QLabel();self.summary.setWordWrap(True);layout.addWidget(self.summary)
        self.rollback=QPushButton('回退动画补丁');self.rollback.clicked.connect(controller.rollbackRequested.emit);layout.addWidget(self.rollback)
        from settings_controls import SlidingSegments
        row=QHBoxLayout();self.choice=SlidingSegments([('轻量 512px','light'),('高清 720px','hd')]);row.addWidget(self.choice,1)
        self.action=QPushButton();row.addWidget(self.action);self.cancel_button=QPushButton('取消');row.addWidget(self.cancel_button);layout.addLayout(row)
        self.progress=QProgressBar();self.progress.setRange(0,1000);layout.addWidget(self.progress)
        self.message=QLabel();self.message.setWordWrap(True);layout.addWidget(self.message)
        self.remove_button=QPushButton('移除动画资源，仅保留卡片');self.remove_button.setProperty('role','danger');layout.addWidget(self.remove_button)
        self.remove_button.clicked.connect(controller.removeRequested.emit)
        note=QLabel('动画按需下载，升级可复用；移除后可重新下载。');note.setWordWrap(True);note.setStyleSheet('font-size:11px;font-weight:500;color:#706879;');layout.addWidget(note)
        self.choice.setCurrentIndex(max(0,self.choice.findData(controller.store.current)))
        self.choice.currentIndexChanged.connect(lambda:self.refresh(controller.snapshot()));self.action.clicked.connect(lambda:controller.request(self.choice.currentData()));self.cancel_button.clicked.connect(controller.cancel)
        controller.changed.connect(self.refresh);self.refresh(controller.snapshot())
    def refresh(self,s):
        self.rollback.setVisible(bool(s.get('canRollback')));self.rollback.setEnabled(not s['busy'])
        self.summary.setText('当前：'+({'hd':'高清 720px','light':'轻量 512px'}.get(s['current'],'仅卡片')))
        tier=self.choice.currentData();busy=s['busy'] or s['phase']=='pending'
        self.choice.setEnabled(not busy);self.action.setEnabled(s['supported'] and not busy and tier!=s['current'])
        cached=s.get('hdCached' if tier=='hd' else 'lightCached',False)
        self.action.setText('下载并启用' if not cached else '启用动画' if s['current'] is None else '切换画质')
        self.remove_button.setEnabled(s['supported'] and not busy)
        self.cancel_button.setVisible(s['busy'] and s['phase'] not in ('pending','removing'));self.cancel_button.setEnabled(s['busy']);self.message.setText(s['message'])
        self.progress.setVisible(s['busy'])
        total=s['total'];self.progress.setRange(0,1000 if total else 0)
        if total:self.progress.setValue(min(1000,round(s['downloaded']*1000/total)));self.progress.setFormat(f"{s['downloaded']/1048576:.1f} / {total/1048576:.1f} MB")
