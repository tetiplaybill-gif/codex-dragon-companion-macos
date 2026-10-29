"""Offline Qt checks for independent, attributed public announcement sources."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QFontMetricsF
from PySide6.QtWidgets import QApplication,QLabel,QPushButton,QScrollArea
from public_announcements_panel import PublicAnnouncementsPanel,display_snapshot
from reset_presentation import public_source_url,public_announcement_view
from reset_card import ResetCard
from compact_bubble import CompactBubble

APP=QApplication.instance() or QApplication([])
NOW=1803100000

def item(text='reset notice',published=NOW,kind='reset',**extra):
    return dict(id=str(published),text=text,summary=text,published=published,kind=kind,url='https://codex-resets.com/',**extra)

def source(ident='codex_resets',state='ok',items=None,**extra):
    values=dict(id=ident,label=ident,attribution_url='https://codex-resets.com/',state=state,message='',
                checked=NOW,last_success=NOW,next_check=NOW+900,stale=False,items=[item()] if items is None else items)
    values.update(extra);return values

def snapshot(*sources,state='ok'):
    return dict(source='public_announcements',state=state,sources=list(sources))


class PublicPanelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='bailong-public-ui-');self.root=Path(self.tmp.name)
        self.path=self.root/'public-announcements-options.json';self.widgets=[]
        self.options_patch=patch('public_announcements_panel.options_path',return_value=self.path);self.options_patch.start()

    def tearDown(self):
        for widget in self.widgets:widget.close();widget.deleteLater()
        APP.processEvents();self.options_patch.stop();self.tmp.cleanup()

    def panel(self,data=None):
        panel=PublicAnnouncementsPanel(data,settings_path=self.path);self.widgets.append(panel);return panel

    def text(self,widget):return '\n'.join(label.text() for label in widget.findChildren(QLabel))

    def test_initial_page_has_no_x_gate_or_old_cache_conversion(self):
        for old in (None,{'source':'x','items':[item('old X cache')]},{'pending':{'text':'old reset cache'}}):
            panel=self.panel(old);text=self.text(panel)
            self.assertIn('公开公告正在检查',text);self.assertIn('无需 X 账号',text)
            self.assertNotIn('免费自动读取尚未接通',text);self.assertNotIn('old X cache',text);self.assertNotIn('old reset cache',text)
            self.assertEqual(display_snapshot(old)['sources'],[])
        card=ResetCard(None,False,dense=True,with_refresh=False);self.widgets.append(card)
        self.assertEqual(card.view['title'],'公告');self.assertEqual(card.view['value'],'等待读取')

    def test_sources_fail_independently_and_x_cache_is_last(self):
        official=source('codex_changelog','error',items=[dict(item('old official update'),url='https://developers.openai.com/codex/changelog/#fixture',kind='update')],stale=True)
        manual=source('x','unconfigured',items=[dict(item('manual X',NOW+9999),url='https://x.com/thsottiaux/status/123456',kind='other')],last_success=None,last_manual_read=NOW)
        panel=self.panel(snapshot(manual,official,source(),state='degraded'))
        self.assertIn('1 个公开来源正常',panel.status_label.text())
        self.assertEqual(list(panel.source_blocks),['codex_resets','codex_changelog','x'])
        self.assertEqual(panel.source_blocks['codex_resets'].findChild(QLabel,'public_source_state').text(),'正常')
        self.assertIn('不可用',panel.source_blocks['codex_changelog'].findChild(QLabel,'public_source_state').text())
        self.assertIn('手动缓存',self.text(panel.source_blocks['x']))
        self.assertEqual(panel.source_blocks['codex_changelog'].findChild(QLabel,'public_item_origin').text(),'最新一条（缓存）')
        self.assertIn('上次成功：',self.text(panel.source_blocks['codex_changelog']))

    def test_expired_source_is_not_presented_as_newly_read(self):
        panel=self.panel(snapshot(source(stale=True),state='degraded'));block=panel.source_blocks['codex_resets']
        self.assertIn('已过期',block.findChild(QLabel,'public_source_state').text())
        self.assertEqual(block.findChild(QLabel,'public_item_origin').text(),'最新一条（缓存）')
        self.assertIn('正在显示缓存公告',panel.status_label.text())

    def test_each_source_displays_only_newest_publication_and_original_plain_text(self):
        original='<img src="https://example.com/tracker">\nlatest & original https://t.co/example'
        panel=self.panel(snapshot(source(items=[item('old',NOW),item(original,NOW+900),item('middle',NOW+300)])))
        labels=panel.findChildren(QLabel,'public_original')
        self.assertEqual([label.text() for label in labels],[original])
        self.assertEqual(labels[0].textFormat(),Qt.TextFormat.PlainText)
        self.assertNotIn('old',self.text(panel));self.assertNotIn('middle',self.text(panel))

    def test_attribution_and_origin_links_are_separate_and_safe(self):
        origin='https://x.com/thsottiaux/status/2115330127886463244'
        panel=self.panel(snapshot(source(items=[item(origin_url=origin)])))
        block=panel.source_blocks['codex_resets']
        self.assertEqual(block.findChild(QPushButton,'public_attribution').text(),'Codex Resets（第三方）')
        self.assertIn('不代表桌宠直接读取了 X',self.text(block))
        with patch('public_announcements_panel.QDesktopServices.openUrl',return_value=True) as opened:
            block.findChild(QPushButton,'public_attribution').click();block.findChild(QPushButton,'public_origin_source').click()
            self.assertEqual([call.args[0].toString() for call in opened.call_args_list],['https://codex-resets.com/',origin])
        bad=self.panel(snapshot(source(attribution_url='https://evil.example/',items=[dict(item(),url='https://t.co/example',origin_url='https://x.com/someone/status/123456')]))).source_blocks['codex_resets']
        self.assertIsNone(bad.findChild(QPushButton,'public_item_source'));self.assertIsNone(bad.findChild(QPushButton,'public_origin_source'))
        self.assertEqual(bad.findChild(QPushButton,'public_attribution').toolTip(),'https://codex-resets.com/')

    def test_official_update_links_stay_in_verified_official_scope(self):
        urls=['https://learn.chatgpt.com/docs/changelog','https://learn.chatgpt.com/docs/changelog/rss.xml',
              'https://developers.openai.com/codex/changelog/#october-29']
        for url in urls:self.assertEqual(public_source_url('codex_changelog',url),url)
        bad=['http://codex-resets.com/','https://codex-resets.com.evil.example/','https://user@codex-resets.com/',
             'https://codex-resets.com:444/','https://codex-resets.com/\nattack','https://codex-resets.com\\@evil.example/']
        for url in bad:self.assertIsNone(public_source_url('codex_resets',url),url)
        for url in ['https://learn.chatgpt.com/account','https://developers.openai.com/docs','https://learn.chatgpt.com/docs/changelog/../account',
                    'https://learn.chatgpt.com/docs/changelog/%2e%2e/account','javascript:alert(1)','https://t.co/example']:
            self.assertIsNone(public_source_url('codex_changelog',url),url)
        panel=self.panel(snapshot(source('codex_changelog',items=[dict(item('release notes'),url=urls[2],kind='update')],attribution_url=urls[0])))
        self.assertIn('官方更新，不响铃',self.text(panel))

    def test_compact_summary_prioritizes_reset_channel_not_x_or_official_dates(self):
        resets=source(items=[item('reset channel',NOW,kind='upcoming')])
        updates=source('codex_changelog',items=[item('official update',NOW+1000,kind='update')])
        manual=source('x','unconfigured',items=[item('manual X',NOW+2000,kind='other')])
        view=public_announcement_view(snapshot(updates,manual,resets))
        self.assertEqual(view['value'],'未来安排');self.assertEqual(view['source_name'],'Codex Resets（第三方）')
        resets.update(state='error',stale=True)
        self.assertEqual(public_announcement_view(snapshot(resets,updates,manual,state='degraded'))['value'],'缓存重置')
        resets['items']=[]
        self.assertEqual(public_announcement_view(snapshot(resets,updates,manual,state='degraded'))['value'],'官方更新')

    def test_independent_options_default_to_fifteen_and_mute_persists(self):
        old=self.root/'x-announcements-options.json';old.write_text('{"interval_minutes": 60, "sound_enabled": true}')
        panel=self.panel(snapshot(source()));events=[];panel.optionsSaved.connect(events.append)
        self.assertEqual(panel.interval.value(),15);self.assertTrue(panel.enabled.isChecked());self.assertTrue(panel.sound.isChecked())
        panel.interval.setValue(30);panel.mute()
        self.assertEqual(json.loads(self.path.read_text()),dict(enabled=True,interval_minutes=30,sound_enabled=False))
        self.assertEqual(json.loads(old.read_text())['interval_minutes'],60);self.assertEqual(len(events),1)
        self.assertIn('首次读取',self.text(panel));self.assertIn('功能更新保持静音',self.text(panel))

    def test_fixed_canvas_and_long_content_only_scroll_vertically(self):
        data=snapshot(source(items=[item(('原文 '+('x'*180)+'\n')*12)]),source('codex_changelog','error',items=[],stale=True),state='degraded')
        for width in (244,320,400):
            panel=self.panel(data);area=QScrollArea();self.widgets.append(area);area.setWidgetResizable(True)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);area.setWidget(panel);area.resize(width,244);area.show();APP.processEvents()
            self.assertEqual(area.horizontalScrollBar().maximum(),0);self.assertGreater(area.verticalScrollBar().maximum(),0)
            self.assertEqual(area.height(),244);self.assertLessEqual(panel.width(),area.viewport().width())
            for label in panel.findChildren(QLabel):self.assertLessEqual(label.width(),panel.width())
        bubble=CompactBubble();self.widgets.append(bubble);bubble.reset_snapshot=data;bubble.show_reset_details();bubble.size_transition.complete();APP.processEvents()
        tabs=bubble.details_tabs;self.assertEqual(tabs.height(),244);self.assertEqual(tabs.tabText(2),'公告')
        self.assertIsNotNone(tabs.findChild(PublicAnnouncementsPanel));self.assertEqual(tabs.areas['reset'].horizontalScrollBar().maximum(),0)
        seen=[];bubble.resetRefreshRequested.connect(lambda:seen.append(True))
        tabs.public_panel.findChild(QPushButton,'public_refresh').click();self.assertEqual(seen,[True])
        card=ResetCard(data,False,dense=True,with_refresh=False);self.widgets.append(card);card.resize(106,78)
        for text,font,origin in card.text_runs():
            self.assertTrue(QRectF(card.rect()).contains(QFontMetricsF(font).tightBoundingRect(text).translated(origin)))


if __name__=='__main__':unittest.main()
