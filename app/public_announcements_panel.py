"""Independent, attributed public-source views; no network or account access."""
from pathlib import Path
from PySide6.QtCore import Qt,QUrl,Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget,QLabel,QVBoxLayout,QHBoxLayout,QPushButton,QCheckBox,QSpinBox,QFrame,QSizePolicy
from typography import FONT_CSS
from ui_theme import editor_stylesheet,INK,MUTED,DANGER
from reset_presentation import PUBLIC_SOURCE_POLICIES,public_source_url,public_source_snapshots,latest_x_item
from x_announcements_panel import display_time,load_options

ACCOUNT_NOTICE='重置公告不代表本机账户额度已到账；实际余额与重置时间请查看“额度”页。'

def options_path():
    from platform_paths import data_dir
    return data_dir()/'public-announcements-options.json'

def display_snapshot(snapshot):
    if isinstance(snapshot,dict) and snapshot.get('source')=='public_announcements':return snapshot
    # Old third-party and X caches keep their original identities. Only the
    # worker may explicitly attach an independent, labelled source snapshot.
    return dict(source='public_announcements',state='loading',sources=[])

def source_state(source):
    if source.get('id') not in PUBLIC_SOURCE_POLICIES:return '未验证来源'
    state=source.get('state')
    if state=='disabled':return '已暂停'
    if state=='unconfigured':return '手动缓存，自动读取未接通' if source.get('id')=='x' else '未接通'
    if state=='error':return '不可用，保留缓存' if latest_x_item(source) else '暂不可用'
    if source.get('stale'):return '已过期，显示缓存'
    return '正常' if state=='ok' else '等待首次读取'


class PublicAnnouncementsPanel(QWidget):
    refreshRequested=Signal()
    optionsSaved=Signal(dict)
    def __init__(self,snapshot=None,parent=None,settings_path=None):
        super().__init__(parent)
        self.setObjectName('public_announcements_panel');self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        self.setStyleSheet(editor_stylesheet(FONT_CSS))
        self.snapshot=display_snapshot(snapshot);self.settings_path=Path(settings_path or options_path())
        self.body=QVBoxLayout(self);self.body.setContentsMargins(0,0,0,0);self.body.setSpacing(8)
        sources=[s for s in public_source_snapshots(self.snapshot) if s['id']!='x' or latest_x_item(s)]
        sources.sort(key=lambda s:{'codex_resets':0,'codex_changelog':1,'x':3}.get(s['id'],2))
        public=[s for s in sources if s['id'] in PUBLIC_SOURCE_POLICIES and s['id']!='x']
        normal=[s for s in public if s.get('state')=='ok' and not s.get('stale')]
        title='公开公告正在检查'
        if self.snapshot.get('state')=='disabled':title='公开公告自动读取已暂停'
        elif normal:
            title=f'{len(normal)} 个公开来源正常'
            if len(normal)<len(public):title+=f'，{len(public)-len(normal)} 个待更新'
        elif any(s.get('state')=='error' for s in public):title='公开来源暂不可用'
        elif public and any(s.get('stale') for s in public):title='正在显示缓存公告'
        self.status_label=self.label(title,strong=True);self.status_label.setObjectName('public_status')
        self.label('免费公开来源，无需 X 账号。每个来源只显示最新一条，状态分别更新。',muted=True)
        self.label(ACCOUNT_NOTICE,muted=True).setObjectName('public_account_notice')
        refresh=QPushButton('立即检查公告');refresh.setObjectName('public_refresh')
        refresh.clicked.connect(self.refreshRequested.emit);self.body.addWidget(refresh)
        self.source_blocks={}
        if not sources:self.label('等待首次读取结果；尚未获取公告。',muted=True)
        for source in sources:self.add_source(source)
        self.add_options()

    def label(self,text,strong=False,muted=False,warning=False,layout=None):
        label=QLabel(str(text));label.setTextFormat(Qt.TextFormat.PlainText);label.setWordWrap(True)
        label.setMinimumWidth(0);label.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        color=DANGER if warning else MUTED if muted else INK
        label.setStyleSheet(FONT_CSS+f'font-size:12px;font-weight:{600 if strong else 500};color:{color};background:transparent;')
        (layout or self.body).addWidget(label);return label

    def link_button(self,text,url,layout,name):
        button=QPushButton(text);button.setObjectName(name);button.setToolTip(url)
        button.clicked.connect(lambda checked=False,u=url:QDesktopServices.openUrl(QUrl(u)))
        layout.addWidget(button);return button

    def add_source(self,source):
        ident=source['id'];policy=PUBLIC_SOURCE_POLICIES.get(ident)
        label=policy['label'] if policy else str(source.get('label') or ident)
        box=QFrame();box.setObjectName('public_source');box.setProperty('source_id',ident);box.setMinimumWidth(0)
        box.setStyleSheet('QFrame#public_source{background:#f5f2f7;border-radius:8px;}')
        layout=QVBoxLayout(box);layout.setContentsMargins(9,9,9,9);layout.setSpacing(6)
        self.source_blocks[ident]=box
        url=public_source_url(ident,source.get('attribution_url'))
        if url is None and policy:url=policy['url']
        if url:self.link_button(label,url,layout,'public_attribution')
        else:self.label(label,strong=True,layout=layout)
        state=source_state(source)
        self.label(state,warning=source.get('state')=='error' or bool(source.get('stale')),layout=layout).setObjectName('public_source_state')
        if policy:self.label(policy['coverage'],muted=True,layout=layout)
        message=str(source.get('message') or '')
        if message:self.label(message,muted=True,layout=layout)
        if ident=='x':
            self.label('手动读取：'+display_time(source.get('last_manual_read')),muted=True,layout=layout)
        else:
            self.label('上次成功：'+display_time(source.get('last_success')),muted=True,layout=layout).setObjectName('public_last_success')
            if source.get('next_check') is not None:self.label('下次检查：'+display_time(source['next_check']),muted=True,layout=layout)
        item=latest_x_item(source)
        if item is None:self.label('尚无可显示的公告。',muted=True,layout=layout)
        else:
            cached=source.get('state')!='ok' or bool(source.get('stale')) or ident=='x'
            self.label('最新一条（缓存）' if cached else '最新一条',strong=True,layout=layout).setObjectName('public_item_origin')
            if ident=='codex_changelog':kind='官方更新，不响铃'
            else:kind={'reset':'已公布重置','upcoming':'未来重置安排','uncertain':'重置尚未确认','update':'功能更新','other':'最新推文'}.get(item.get('kind'),'公告')
            self.label(kind,muted=True,layout=layout)
            self.label('发布时间：'+display_time(item.get('published')),muted=True,layout=layout)
            self.label(item.get('text') or item.get('summary') or '原文暂不可用',layout=layout).setObjectName('public_original')
            item_url=public_source_url(ident,item.get('url'))
            if item_url:self.link_button('查看来源记录',item_url,layout,'public_item_source')
            origin_url=public_source_url(ident,item.get('origin_url'),origin=True)
            if origin_url:
                self.label('原帖引用由 Codex Resets 提供，不代表桌宠直接读取了 X。',muted=True,layout=layout)
                self.link_button('原始公告（X）',origin_url,layout,'public_origin_source')
        self.body.addWidget(box)

    def add_options(self):
        self.label('自动检查与提醒',strong=True)
        self.enabled=QCheckBox('自动检查公开公告');self.enabled.setObjectName('public_enabled');self.body.addWidget(self.enabled)
        row=QHBoxLayout();row.setSpacing(6);row.addWidget(QLabel('检查间隔'))
        self.interval=QSpinBox();self.interval.setObjectName('public_interval');self.interval.setRange(5,1440)
        self.interval.setSuffix(' 分钟');self.interval.setAccessibleName('公开公告检查间隔（分钟）');row.addWidget(self.interval,1)
        self.body.addLayout(row)
        self.sound=QCheckBox('明确重置公告响铃');self.sound.setObjectName('public_sound');self.body.addWidget(self.sound)
        self.label('只有明确已发生的额度重置才响铃。首次读取、重复公告、未来安排和功能更新保持静音。',muted=True)
        options=load_options(self.settings_path)
        self.enabled.setChecked(options['enabled']);self.interval.setValue(options['interval_minutes']);self.sound.setChecked(options['sound_enabled'])
        row=QHBoxLayout();row.setSpacing(6)
        self.mute_button=QPushButton('立即静音');self.mute_button.setObjectName('public_mute');self.mute_button.clicked.connect(self.mute);row.addWidget(self.mute_button)
        self.save_button=QPushButton('保存公告设置');self.save_button.setObjectName('public_save');self.save_button.clicked.connect(self.save_options);row.addWidget(self.save_button)
        self.body.addLayout(row)
        self.save_status=self.label('公开公告设置单独保存。',muted=True);self.save_status.setObjectName('public_options_status')

    def save_options(self):
        from desktop_core import atomic_json
        values=dict(enabled=self.enabled.isChecked(),interval_minutes=self.interval.value(),sound_enabled=self.sound.isChecked())
        try:atomic_json(self.settings_path,values)
        except OSError:self.save_status.setText('保存失败，请重试；草稿保留。');return
        self.save_status.setText('公开公告设置已保存。' if values['sound_enabled'] else '公开公告设置已保存，重置响铃已静音。')
        self.optionsSaved.emit(values);self.refreshRequested.emit()

    def mute(self):
        self.sound.setChecked(False);self.save_options()
