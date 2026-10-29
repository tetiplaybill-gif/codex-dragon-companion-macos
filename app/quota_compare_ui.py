"""Quota history, styled like the existing data panel."""
from datetime import datetime
from PySide6.QtCore import Qt,QRectF,QPointF,Signal,QTimer,QAbstractAnimation
from PySide6.QtGui import QPainter,QColor,QPen,QFontMetrics
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QSizePolicy,QToolButton
from typography import ui_font as font,FONT_CSS
from ui_theme import INK,MUTED,PRIMARY,ACCENT,PANEL,SELECTED,BORDER
from token_calendar import compact_tokens
from chart_reveal import RasterChart,ChartReveal
from choice_controls import ChoiceCombo
from settings_controls import motion_enabled


def date_text(stamp):
    return datetime.fromtimestamp(stamp).strftime('%m/%d')


def text_label(text='',size=11,primary=False):
    label=QLabel(text);label.setTextFormat(Qt.TextFormat.PlainText);label.setFont(font(size))
    label.setStyleSheet(FONT_CSS+f'font-size:{size}px;color:{INK if primary else MUTED};background:transparent;')
    return label


class CyclePlot(QWidget,RasterChart):
    selected=Signal(str);hoverText=Signal(str)
    def __init__(self):
        super().__init__();self.setFixedHeight(94);self.setMouseTracking(True)
        self.cycles=[];self.selected_id=None;self.hits=[];self.points=[];self._resume_time=None
        self.reveal=ChartReveal(self);self._left=38;self._max=1
    def set_data(self,cycles,selected):
        ordered=list(reversed(cycles));index=next((i for i,c in enumerate(ordered) if c['id']==selected),len(ordered)-1)
        start=max(0,min(index-4,len(ordered)-8));shown=ordered[start:start+8]
        if self.cycles==shown and self.selected_id==selected:return
        self.cycles=shown;self.selected_id=selected
        self._max=max([max(c['used'],c.get('estimated_total') or 0) for c in shown]+[1])
        fm=QFontMetrics(font(11));self._left=max(37,max(fm.horizontalAdvance(compact_tokens(round(self._max*f))) for f in (0,.5,1))+6)
        self.invalidate_layers();self.update()
    def chart_mode(self):return 'bars'
    def chart_rect(self):return QRectF(self._left,10,max(1,self.width()-self._left-4),65)
    def paintEvent(self,event):self.paint_layers()
    def render_layers(self,p,dynamic):
        chart=self.chart_rect();p.setFont(font(11));fm=QFontMetrics(p.font());self.hits=[]
        for f in (0,.5,1):
            y=chart.bottom()-chart.height()*f;p.setPen(QPen(QColor(BORDER),.7));p.drawLine(QPointF(chart.left(),y),QPointF(chart.right(),y))
            p.setPen(QColor(MUTED));value=compact_tokens(round(self._max*f))
            p.drawText(QPointF(chart.left()-5-fm.horizontalAdvance(value),y+(fm.ascent()-fm.descent())/2),value)
        slot=chart.width()/max(1,len(self.cycles))
        for i,c in enumerate(self.cycles):
            x=chart.left()+i*slot+2;width=max(2,slot-4)
            estimate=c.get('estimated_total') or 0
            if estimate:
                height=chart.height()*estimate/self._max
                dynamic.fillRect(QRectF(x,chart.bottom()-height,width,height),QColor(SELECTED))
            height=chart.height()*c['used']/self._max
            dynamic.fillRect(QRectF(x,chart.bottom()-height,max(2,width*.55),height),QColor(ACCENT))
            if c['id']==self.selected_id:
                dynamic.setPen(QPen(QColor(PRIMARY),1.2));dynamic.drawLine(QPointF(x,chart.bottom()),QPointF(x+width,chart.bottom()))
            self.hits.append((QRectF(x,chart.top(),width,chart.height()),c))
        p.setPen(QColor(MUTED))
        if self.cycles:
            p.drawText(QRectF(chart.left(),77,48,16),Qt.AlignmentFlag.AlignLeft,date_text(self.cycles[0]['start']))
            p.drawText(QRectF(chart.right()-48,77,48,16),Qt.AlignmentFlag.AlignRight,date_text(self.cycles[-1]['start']))
        else:p.drawText(chart,Qt.AlignmentFlag.AlignCenter,'暂无历史额度记录')
    def mouseMoveEvent(self,event):
        for rect,c in self.hits:
            if rect.contains(event.position()):
                self.hoverText.emit(date_text(c['start'])+' 已用 '+compact_tokens(c['used'])+' / 推测 '+(compact_tokens(c['estimated_total']) if c.get('estimated_total') else '—'));return
        self.hoverText.emit('')
    def leaveEvent(self,event):self.hoverText.emit('');super().leaveEvent(event)
    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            for rect,c in self.hits:
                if rect.contains(event.position()):self.selected.emit(c['id']);break
        super().mouseReleaseEvent(event)
    def begin_reveal(self):
        self.ensure_layers();self._resume_time=None
        if motion_enabled():self.reveal.prepare()
    def freeze_reveal(self):
        self._resume_time=self.reveal.animation.currentTime() if self.reveal.animation.state()==QAbstractAnimation.State.Running else None
        self.reveal.stop()
    def start_reveal(self):
        if self._resume_time is not None and self.isVisible():
            value=self._resume_time;self._resume_time=None;self.reveal.animation.start();self.reveal.animation.setCurrentTime(value)
        else:self.reveal.start()
    def showEvent(self,event):
        super().showEvent(event)
        if self.reveal.pending or self._resume_time is not None:QTimer.singleShot(0,self,self.start_reveal)
    def hideEvent(self,event):self.reveal.stop();super().hideEvent(event)


class CycleChoice(ChoiceCombo):
    title='选择额度周期'
    def display_text(self):return self.title


class QuotaCompareView(QWidget):
    def __init__(self):
        super().__init__();self.cycles=[];self.selected_id=None;self.history={}
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(5)
        navigation=QWidget();nav=QHBoxLayout(navigation);nav.setContentsMargins(0,0,0,0);nav.setSpacing(4)
        self.previous=QToolButton();self.next=QToolButton()
        for button,text,title in [(self.previous,'‹','查看更早一轮额度'),(self.next,'›','查看更新一轮额度')]:
            button.setText(text);button.setAccessibleName(title);button.setFixedSize(28,30);button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet('QToolButton{'+FONT_CSS+f'font-size:18px;color:{PRIMARY};border:0;background:{PANEL};border-radius:7px;}}'
                f'QToolButton:hover{{background:{SELECTED};}}QToolButton:pressed{{background:{BORDER};}}QToolButton:disabled{{color:{BORDER};}}')
        self.choice=CycleChoice();self.choice.setObjectName('quota_cycle_choice');self.choice.setAccessibleName('选择哪一轮额度')
        nav.addWidget(self.previous);nav.addWidget(self.choice,1);nav.addWidget(self.next);layout.addWidget(navigation)
        self.period_line=text_label();self.period_line.setWordWrap(True);layout.addWidget(self.period_line)
        self.previous.clicked.connect(lambda:self.choice.setCurrentIndex(self.choice.currentIndex()+1))
        self.next.clicked.connect(lambda:self.choice.setCurrentIndex(self.choice.currentIndex()-1))
        self.choice.currentIndexChanged.connect(self.select_current)
        metrics=QWidget();row=QHBoxLayout(metrics);row.setContentsMargins(0,0,0,0);row.setSpacing(4)
        for title,name in [('本机已用','used'),('推测总量','estimate')]:
            card=QWidget();card.setObjectName('cycle_metric');card.setStyleSheet('QWidget#cycle_metric{background:#f5f0f8;border-radius:7px;}')
            box=QVBoxLayout(card);box.setContentsMargins(7,5,7,5);box.setSpacing(1);box.addWidget(text_label(title))
            value=text_label('—',14,True);value.setObjectName('quota_cycle_'+name);setattr(self,name,value);box.addWidget(value);row.addWidget(card,1)
        layout.addWidget(metrics)
        self.detail=text_label();self.detail.setWordWrap(True);layout.addWidget(self.detail)
        self.comparison=text_label('',12,True);self.comparison.setWordWrap(True);layout.addWidget(self.comparison)
        self.plot=CyclePlot();self.plot.selected.connect(self.select_id);layout.addWidget(self.plot)
        self.readout=text_label('深色已用 / 浅色推测总量');self.readout.setWordWrap(True)
        self.readout.setMinimumHeight(28);layout.addWidget(self.readout)
        self.plot.hoverText.connect(lambda value:self.readout.setText(value or '深色已用 / 浅色推测总量'))
        self.quality=text_label();self.quality.setWordWrap(True);layout.addWidget(self.quality)
        self.note=text_label('已记录额度下降至少 5 个百分点后推测总量；两轮均达到 20 个百分点，且套餐、主模型等条件相近时对比。缓存及其他设备使用会影响估算。');self.note.setWordWrap(True);layout.addWidget(self.note)
    def set_snapshot(self,snapshot):
        self.history=snapshot.get('quota_history') or {};self.cycles=self.history.get('cycles') or []
        if self.selected_id not in {c['id'] for c in self.cycles}:self.selected_id=self.cycles[0]['id'] if self.cycles else None
        labels=[(self.caption(c),c['id']) for c in self.cycles]
        if labels!=[(self.choice.itemText(i),self.choice.itemData(i)) for i in range(self.choice.count())]:
            blocked=self.choice.blockSignals(True);self.choice.clear()
            for title,key in labels:self.choice.addItem(title,key)
            self.choice.setCurrentIndex(self.choice.findData(self.selected_id));self.choice.blockSignals(blocked)
        self.update_selected()
    def caption(self,c):
        return self.cycle_title(c)+'  '+datetime.fromtimestamp(c['start']).strftime('%m/%d %H:%M')
    def cycle_title(self,c):
        if not c['closed']:return '本轮额度'
        index=next((i for i,x in enumerate(self.cycles) if x['id']==c['id']),0)
        rank=index+(1 if self.cycles and self.cycles[0]['closed'] else 0)
        return '上一轮额度' if rank<=1 else f'前{rank}轮额度'
    def select_current(self,*args):
        self.selected_id=self.choice.currentData();self.update_selected()
    def select_id(self,key):self.choice.setCurrentIndex(self.choice.findData(key))
    def update_selected(self):
        c=next((c for c in self.cycles if c['id']==self.selected_id),None)
        self.choice.setEnabled(bool(self.cycles));self.plot.set_data(self.cycles,self.selected_id)
        index=self.choice.currentIndex();self.previous.setEnabled(index>=0 and index<len(self.cycles)-1);self.next.setEnabled(index>0)
        if not c:
            self.choice.title='暂无额度周期';self.choice.update();self.period_line.setText('重置后开始记录新一轮')
            self.used.setText('—');self.estimate.setText('—');self.detail.setText('等待周额度记录')
            self.comparison.setText('历史额度整理中' if self.history.get('pending') else '暂无可对比周期')
            self.quality.setText('已有 Token 日志会保留；缺少额度记录时无法还原总量。');return
        self.choice.title=self.cycle_title(c);self.choice.update()
        begin=datetime.fromtimestamp(c['start']).strftime('%m/%d %H:%M')
        end=datetime.fromtimestamp(c['end']).strftime('%m/%d %H:%M') if c['closed'] else '至今'
        kind={'natural':'自然重置','extra':'额外补充','inferred':'起点推定','changed':'套餐或窗口变化'}.get(c['kind'],'起点推定')
        self.period_line.setText(begin+' — '+end+'\n'+kind)
        self.used.setText(compact_tokens(c['used']));self.estimate.setText(compact_tokens(c['estimated_total']) if c['estimated_total'] else '—')
        each=compact_tokens(round(c['per_percent'])) if c.get('per_percent') else '—'
        self.detail.setText(f"每 1% ≈ {each} Token    剩余 {c['remaining']:g}%")
        change=c.get('change')
        self.comparison.setText(c['comparison_reason']+(f' {change:+.1f}%' if change is not None else ''))
        parts=[]
        if self.history.get('pending'):parts.append('正在补齐历史记录')
        elif not c['complete']:parts.append('部分记录受限')
        elif c.get('cached'):parts.append('保留上次完整统计')
        elif not c['fresh']:parts.append('额度待刷新')
        elif c.get('corrected'):parts.append('额度曾回调，本轮不推测')
        else:parts.append(f"已观察 {c['drop']:g}% 额度变化")
        if c.get('model'):parts.append(c['model']+f" {c['model_share']:.0%}")
        self.quality.setText('\n'.join(parts))
