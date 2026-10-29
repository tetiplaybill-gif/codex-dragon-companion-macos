"""Offline Qt checks for honest X state, local preferences and bounded layout."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QFontMetricsF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QLabel,QPushButton,QScrollArea,QWidget
from x_announcements_panel import XAnnouncementsPanel,SOURCE_URL,load_options,display_snapshot
from reset_card import ResetCard
from compact_bubble import CompactBubble

APP=QApplication.instance() or QApplication([])


def snapshot(state='ok',items=None,**extra):
    return dict(source='x',account='thsottiaux',source_url=SOURCE_URL,state=state,message='',
                items=items or [],last_success=1803100000,next_check=None,**extra)


class XPanelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='bailong-x-ui-');self.root=Path(self.tmp.name)
        self.path=self.root/'options.json';self.widgets=[]
        self.options_patch=patch('x_announcements_panel.options_path',return_value=self.path);self.options_patch.start()

    def tearDown(self):
        for widget in self.widgets:widget.close();widget.deleteLater()
        APP.processEvents();self.options_patch.stop();self.tmp.cleanup()

    def panel(self,data=None):
        panel=XAnnouncementsPanel(data,settings_path=self.path);self.widgets.append(panel);return panel

    def labels(self,panel):return [label.text() for label in panel.findChildren(QLabel)]

    def test_unconfigured_and_legacy_cache_never_claim_live_x_reading(self):
        for data in (None,{'pending':{'text':'旧站点的重置公告'},'scheduled':{}}):
            panel=self.panel(data);text='\n'.join(self.labels(panel))
            self.assertIn('免费自动读取尚未接通；可在 X 官方页面登录查看。',text)
            self.assertIn('浏览器登录不等于后台自动读取已接通',text)
            self.assertNotIn('官方读取授权',text);self.assertNotIn('付费',text)
            self.assertNotIn('旧站点的重置公告',text)
            self.assertFalse(panel.findChildren(QLabel,'x_post_original'))
            self.assertEqual(panel.interval.value(),15)
            self.assertTrue(panel.enabled.isChecked());self.assertTrue(panel.sound.isChecked())

    def test_old_multi_item_cache_displays_only_the_latest_post(self):
        old=dict(id='123456',text='older post',published=1803100000,url=SOURCE_URL+'/status/123456',kind='update')
        latest=dict(old,id='123459',text='latest post',published=1803100900,kind='other')
        panel=self.panel(snapshot(items=[old,latest,dict(old,id='123457',published=1803100300)]))
        originals=panel.findChildren(QLabel,'x_post_original')
        self.assertEqual([label.text() for label in originals],['latest post'])
        self.assertNotIn('older post','\n'.join(self.labels(panel)))
        card=ResetCard(snapshot(items=[old,latest]),False,dense=True,with_refresh=False);self.widgets.append(card)
        self.assertEqual(card.view['value'],'最新推文');self.assertIn('latest post',card.toolTip())
        self.assertNotIn('older post',card.toolTip())

    def test_visible_page_read_is_distinct_from_background_reading(self):
        data=snapshot('unconfigured',display_origin='official_visible_page',last_manual_read=1803100900)
        data['last_success']=None
        panel=self.panel(data)
        self.assertIn('免费自动读取尚未接通',panel.status_label.text())
        self.assertEqual(panel.findChild(QLabel,'x_last_success').text(),'上次自动读取：暂无')
        self.assertIn('最近从 X 官方页面读取：',panel.findChild(QLabel,'x_last_manual_read').text())

    def test_save_and_immediate_mute_persist_only_local_preferences(self):
        panel=self.panel();events=[];refresh=[]
        panel.optionsSaved.connect(events.append);panel.refreshRequested.connect(lambda:refresh.append(True))
        panel.interval.setValue(30);panel.sound.setChecked(True);panel.save_options()
        self.assertEqual(json.loads(self.path.read_text()),dict(enabled=True,interval_minutes=30,sound_enabled=True))
        panel.mute()
        self.assertEqual(load_options(self.path),dict(enabled=True,interval_minutes=30,sound_enabled=False))
        self.assertEqual(len(events),2);self.assertEqual(len(refresh),2)
        self.assertIn('已静音',panel.save_status.text())

    def test_failed_save_keeps_draft_and_does_not_report_success(self):
        panel=self.panel();panel.interval.setValue(60);seen=[];panel.optionsSaved.connect(seen.append)
        with patch('desktop_core.atomic_json',side_effect=OSError('read only')):panel.save_options()
        self.assertEqual(panel.interval.value(),60);self.assertFalse(seen)
        self.assertIn('保存失败',panel.save_status.text());self.assertFalse(self.path.exists())

    def test_original_text_time_and_canonical_source_links_are_preserved(self):
        original='<b>We have reset Codex usage limits.</b>\nFeature notes & details.'
        item=dict(id='123456',text=original,published=1803100000,url=SOURCE_URL+'/status/123456',kind='reset')
        panel=self.panel(snapshot(items=[item]));labels=self.labels(panel)
        self.assertIn(original,labels);self.assertTrue(any('发布时间：' in text for text in labels))
        label=panel.findChild(QLabel,'x_post_original');self.assertEqual(label.textFormat(),Qt.TextFormat.PlainText)
        self.assertIn('实际余额',panel.findChild(QLabel,'x_account_notice').text())
        with patch('x_announcements_panel.QDesktopServices.openUrl',return_value=True) as opened:
            panel.findChild(QPushButton,'x_account_source').click()
            panel.findChild(QPushButton,'x_post_source').click()
            self.assertEqual([call.args[0].toString() for call in opened.call_args_list],[SOURCE_URL,item['url']])
        bad=self.panel(snapshot(items=[dict(item,url='https://example.com/not-x')]))
        self.assertIsNone(bad.findChild(QPushButton,'x_post_source'))

    def test_dense_card_has_honest_initial_state_and_fixed_geometry(self):
        card=ResetCard(snapshot('unconfigured'),False,dense=True,with_refresh=False);self.widgets.append(card)
        card.resize(106,78);card.show();APP.processEvents()
        self.assertEqual(card.view['value'],'未接通');self.assertFalse(card.timer.isActive())
        for text,font,origin in card.text_runs():
            self.assertTrue(QRectF(card.rect()).contains(QFontMetricsF(font).tightBoundingRect(text).translated(origin)))
        before=card.size()
        with patch('reset_card.QDesktopServices.openUrl',return_value=True) as opened:
            card.source_button.click();self.assertEqual(opened.call_args.args[0].toString(),SOURCE_URL)
        self.assertEqual(card.size(),before)

    def test_reply_context_keeps_original_text_and_official_source(self):
        item=dict(id='123456',text='Done.',published=1803100000,url=SOURCE_URL+'/status/123456',kind='reset',
                  context_text='We will reset Codex usage limits.',context_published=1803099000,context_url=SOURCE_URL+'/status/123450')
        panel=self.panel(snapshot(items=[item]))
        self.assertEqual(panel.findChild(QLabel,'x_post_context').text(),item['context_text'])
        with patch('x_announcements_panel.QDesktopServices.openUrl',return_value=True) as opened:
            panel.findChild(QPushButton,'x_context_source').click()
            self.assertEqual(opened.call_args.args[0].toString(),item['context_url'])

    def test_long_posts_scroll_vertically_without_horizontal_overflow(self):
        item=dict(id='123456',text=('原文内容 '+('x'*180)+'\n')*12,published=1803100000,
                  url=SOURCE_URL+'/status/123456',kind='update')
        for width in (244,320,400):
            panel=self.panel(snapshot(items=[item],stale=True))
            area=QScrollArea();self.widgets.append(area);area.setWidgetResizable(True)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            area.setWidget(panel);area.resize(width,244);area.show();APP.processEvents()
            self.assertEqual(area.horizontalScrollBar().maximum(),0)
            self.assertLessEqual(panel.width(),area.viewport().width())
            self.assertGreater(area.verticalScrollBar().maximum(),0)
            for label in panel.findChildren(QLabel):
                self.assertLessEqual(label.width(),panel.width())
            self.assertEqual(area.height(),244)

    def test_details_keep_fixed_canvas_and_show_x_controls(self):
        bubble=CompactBubble();self.widgets.append(bubble)
        bubble.reset_snapshot=snapshot('unconfigured');bubble.show_reset_details()
        bubble.size_transition.complete();APP.processEvents()
        tabs=bubble.details_tabs;self.assertEqual(tabs.height(),244)
        self.assertEqual(tabs.tabText(2),'公告')
        self.assertIsNotNone(tabs.findChild(QPushButton,'x_mute'))
        self.assertEqual(tabs.areas['reset'].horizontalScrollBar().maximum(),0)
        refresh=[];bubble.resetRefreshRequested.connect(lambda:refresh.append(True))
        tabs.x_panel.findChild(QPushButton,'x_refresh').click();self.assertEqual(refresh,[True])


if __name__=='__main__':unittest.main()
