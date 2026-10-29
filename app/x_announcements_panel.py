"""Local X announcement display and preferences; this UI never fetches posts."""
import json,re
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt,QUrl,Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget,QLabel,QVBoxLayout,QHBoxLayout,QPushButton,QCheckBox,QSpinBox,QFrame,QSizePolicy
from typography import FONT_CSS
from ui_theme import editor_stylesheet,INK,MUTED,DANGER
from reset_presentation import latest_x_item

SOURCE_URL='https://x.com/thsottiaux'
ACCOUNT_NOTICE='X 公告不代表本机账户额度已到账；实际余额与重置时间请查看“额度”页。'
DEFAULT_OPTIONS=dict(enabled=True,interval_minutes=15,sound_enabled=True)


def options_path():
    from platform_paths import data_dir
    return data_dir()/'x-announcements-options.json'


def load_options(path=None):
    result=dict(DEFAULT_OPTIONS)
    try:value=json.loads(Path(path or options_path()).read_text(encoding='utf-8'))
    except (OSError,ValueError,TypeError):value={}
    if not isinstance(value,dict):return result
    for key in ('enabled','sound_enabled'):
        if isinstance(value.get(key),bool):result[key]=value[key]
    minutes=value.get('interval_minutes')
    if isinstance(minutes,(int,float)) and not isinstance(minutes,bool):
        try:result['interval_minutes']=max(5,min(1440,int(minutes)))
        except (ValueError,OverflowError):pass
    return result


def display_snapshot(snapshot):
    if isinstance(snapshot,dict) and snapshot.get('source')=='x':return snapshot
    # Never turn an old codex-resets cache into X content.
    return dict(source='x',account='thsottiaux',source_url=SOURCE_URL,state='unconfigured',
                message='免费自动读取尚未接通；可在 X 官方页面登录查看。',items=[],
                checked=None,last_success=None,next_check=None,stale=False,account_notice=ACCOUNT_NOTICE)


def display_time(value):
    try:
        if value is None or isinstance(value,bool):return '暂无'
        return datetime.fromtimestamp(float(value)).astimezone().strftime('%Y-%m-%d %H:%M %Z')
    except (ValueError,OverflowError,OSError,TypeError):return '时间未知'


def post_url(item):
    value=str(item.get('url') or '')
    return value if re.fullmatch(r'https://x\.com/thsottiaux/status/[0-9]+',value) else None


class XAnnouncementsPanel(QWidget):
    refreshRequested=Signal()
    optionsSaved=Signal(dict)
    def __init__(self,snapshot=None,parent=None,settings_path=None):
        super().__init__(parent)
        self.setObjectName('x_announcements_panel');self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        self.setStyleSheet(editor_stylesheet(FONT_CSS))
        self.snapshot=display_snapshot(snapshot);self.settings_path=Path(settings_path or options_path())
        self.body=QVBoxLayout(self);self.body.setContentsMargins(0,0,0,0);self.body.setSpacing(8)
        state=self.snapshot.get('state','unconfigured')
        title={'unconfigured':'免费自动读取尚未接通；可在 X 官方页面登录查看。','disabled':'自动关注已暂停',
               'error':'读取失败 · 保留上次推文','ok':'最新推文'}.get(state,'读取状态未知')
        self.status_label=self.label(title,strong=True,warning=state in ('unconfigured','error'))
        self.status_label.setObjectName('x_connection_state')
        message=str(self.snapshot.get('message') or '')
        if state=='unconfigured':message='浏览器登录不等于后台自动读取已接通。'
        if message and message!=title:self.label(message,muted=True)
        self.label(ACCOUNT_NOTICE,muted=True).setObjectName('x_account_notice')
        self.label('来源：X @thsottiaux',strong=True)
        row=QHBoxLayout();row.setSpacing(6)
        source=QPushButton('打开 X 主页');source.setObjectName('x_account_source')
        source.clicked.connect(lambda:QDesktopServices.openUrl(QUrl(SOURCE_URL)));row.addWidget(source)
        refresh=QPushButton('检查公告');refresh.setObjectName('x_refresh')
        refresh.clicked.connect(self.refreshRequested.emit);row.addWidget(refresh)
        self.body.addLayout(row)
        success=self.snapshot.get('last_success')
        self.label('上次自动读取：'+display_time(success),muted=True).setObjectName('x_last_success')
        if self.snapshot.get('display_origin')=='official_visible_page' and self.snapshot.get('last_manual_read') is not None:
            self.label('最近从 X 官方页面读取：'+display_time(self.snapshot['last_manual_read']),muted=True).setObjectName('x_last_manual_read')
        next_check=self.snapshot.get('next_check')
        if next_check is not None:self.label('下次检查：'+display_time(next_check),muted=True)
        if self.snapshot.get('stale'):self.label('以下是缓存公告，尚未确认有没有新内容。',warning=True)
        item=latest_x_item(self.snapshot)
        if item is None:
            self.label('尚无可显示的最新推文。' if state!='unconfigured' else '仅显示最新一条推文；不使用旧的第三方缓存代替。',muted=True)
        else:self.add_item(item)
        self.add_options()

    def label(self,text,strong=False,muted=False,warning=False,layout=None):
        label=QLabel(str(text));label.setTextFormat(Qt.TextFormat.PlainText);label.setWordWrap(True)
        label.setMinimumWidth(0);label.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        color=DANGER if warning else MUTED if muted else INK
        label.setStyleSheet(FONT_CSS+f'font-size:12px;font-weight:{600 if strong else 500};color:{color};background:transparent;')
        (layout or self.body).addWidget(label);return label

    def add_item(self,item):
        box=QFrame();box.setObjectName('x_post');box.setMinimumWidth(0)
        box.setStyleSheet('QFrame#x_post{background:#f5f2f7;border-radius:8px;}')
        layout=QVBoxLayout(box);layout.setContentsMargins(9,9,9,9);layout.setSpacing(6)
        names={'reset':'已公布重置','upcoming':'未来重置安排','uncertain':'重置尚未确认','update':'功能更新','other':'最新推文'}
        kind=item.get('kind');self.label(names.get(kind,'公告'),strong=True,layout=layout)
        self.label('发布时间：'+display_time(item.get('published')),muted=True,layout=layout)
        self.label(item.get('text') or item.get('summary') or '原文暂不可用',layout=layout).setObjectName('x_post_original')
        if kind=='reset':self.label('公告称重置已发生；到账仍以账户实际读数为准。',muted=True,layout=layout)
        url=post_url(item)
        if url:
            button=QPushButton('查看 X 原文');button.setObjectName('x_post_source');button.setToolTip(url)
            button.clicked.connect(lambda checked=False,u=url:QDesktopServices.openUrl(QUrl(u)));layout.addWidget(button)
        context_url=post_url({'url':item.get('context_url')})
        if context_url and isinstance(item.get('context_text'),str):
            self.label('回复上下文（'+display_time(item.get('context_published'))+'）',muted=True,layout=layout)
            self.label(item['context_text'],layout=layout).setObjectName('x_post_context')
            button=QPushButton('查看上下文原文');button.setObjectName('x_context_source');button.setToolTip(context_url)
            button.clicked.connect(lambda checked=False,u=context_url:QDesktopServices.openUrl(QUrl(u)));layout.addWidget(button)
        self.body.addWidget(box)

    def add_options(self):
        self.label('公告与声音',strong=True)
        self.enabled=QCheckBox('接通后自动检查最新推文');self.enabled.setObjectName('x_enabled');self.body.addWidget(self.enabled)
        row=QHBoxLayout();row.setSpacing(6)
        row.addWidget(QLabel('检查间隔'))
        self.interval=QSpinBox();self.interval.setObjectName('x_interval');self.interval.setRange(5,1440)
        self.interval.setSuffix(' 分钟');self.interval.setAccessibleName('X 公告检查间隔（分钟）');row.addWidget(self.interval,1)
        self.body.addLayout(row)
        self.sound=QCheckBox('明确重置公告响铃');self.sound.setObjectName('x_sound');self.body.addWidget(self.sound)
        self.label('间隔与响铃接通后生效。明确重置才响铃；功能更新和其他推文只显示。首次读取、重复、未来安排或不确定信息不响铃。',muted=True)
        options=load_options(self.settings_path)
        self.enabled.setChecked(options['enabled']);self.interval.setValue(options['interval_minutes']);self.sound.setChecked(options['sound_enabled'])
        row=QHBoxLayout();row.setSpacing(6)
        self.mute_button=QPushButton('立即静音');self.mute_button.setObjectName('x_mute')
        self.mute_button.clicked.connect(self.mute);row.addWidget(self.mute_button)
        self.save_button=QPushButton('保存公告设置');self.save_button.setObjectName('x_save')
        self.save_button.clicked.connect(self.save_options);row.addWidget(self.save_button)
        self.body.addLayout(row)
        self.save_status=self.label('设置在本页单独保存，接通后生效。',muted=True);self.save_status.setObjectName('x_options_status')

    def save_options(self):
        from desktop_core import atomic_json
        values=dict(enabled=self.enabled.isChecked(),interval_minutes=self.interval.value(),sound_enabled=self.sound.isChecked())
        try:atomic_json(self.settings_path,values)
        except OSError:
            self.save_status.setText('保存失败，请重试；当前草稿保留。');return
        self.save_status.setText('公告设置已保存。' if values['sound_enabled'] else '公告设置已保存，重置公告已静音。')
        self.optionsSaved.emit(values);self.refreshRequested.emit()

    def mute(self):
        self.sound.setChecked(False);self.save_options()
