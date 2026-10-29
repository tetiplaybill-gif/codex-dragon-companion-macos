import os,sys,unittest
os.environ['QT_QPA_PLATFORM']='offscreen'
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt,QPoint,QPointF,QEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from compact_bubble import CompactBubble
from desktop_services import codex_conversation_url,open_codex
from test_live_compaction import SID,OTHER
APP=QApplication.instance() or QApplication([])

class NameNavigationTests(unittest.TestCase):
    def setUp(self):
        self.b=CompactBubble();self.b.show();APP.processEvents()
        for sid,title in [(SID,'白龙桌宠状态'),(OTHER,'其他会话')]:self.b.roster.observe(dict(session=sid,title=title,state='working',display='正在编辑文件'))
        self.b.redraw();APP.processEvents()
    def tearDown(self):self.b.close();self.b.deleteLater();APP.processEvents()
    def test_clicking_each_name_emits_exact_id_without_expanding_or_marking_read(self):
        self.b.status_indicator.unread=[(SID,'turn-one')]
        opened=[];self.b.conversationRequested.connect(opened.append)
        for sid in (SID,OTHER):
            row=self.b.status_view.rows[sid]
            QTest.mouseClick(row,Qt.MouseButton.LeftButton,pos=QPoint(7,row.height()//2))
        self.assertEqual(opened,[SID,OTHER]);self.assertFalse(self.b.expanded)
        self.assertEqual(self.b.status_indicator.unread,[(SID,'turn-one')])
    def test_name_survives_row_reorder_and_rename_and_text_still_opens_details(self):
        view=self.b.status_view;opened=[];view.conversationRequested.connect(opened.append)
        view.set_conversations([(OTHER,'执行中'),(SID,'思考中')],metadata={SID:dict(title='新会话名'),OTHER:dict(title='另一个会话')})
        row=view.rows[OTHER];QTest.mouseClick(row,Qt.MouseButton.LeftButton,pos=QPoint(6,9))
        self.assertEqual(opened,[OTHER])
        QTest.mouseClick(row,Qt.MouseButton.LeftButton,pos=QPoint(row.text_left()+10,9));self.b.size_transition.complete()
        self.assertTrue(self.b.expanded)
    @unittest.skipUnless(sys.platform=='win32','Windows Codex layout')
    def test_opening_conversation_uses_registered_deeplink_with_no_shell_or_fallback(self):
        self.assertEqual(codex_conversation_url('rollout-2026-10-18-'+SID),'codex://threads/'+SID)
        with patch('desktop_services.os.startfile') as launch:
            open_codex(SID);launch.assert_called_once_with('codex://threads/'+SID)
        for value in ('bad','../escape','codex://threads/'+SID,SID+'?prompt=run'):
            with self.assertRaises(OSError):codex_conversation_url(value)
    @unittest.skipUnless(sys.platform=='win32','Windows Codex layout')
    def test_unknown_protocol_failure_is_reported_without_opening_wrong_conversation(self):
        with patch('desktop_services.os.startfile',side_effect=OSError('no protocol')) as launch:
            with self.assertRaisesRegex(OSError,'对应会话'):open_codex(SID)
            self.assertEqual(launch.call_count,1)
    def test_name_hover_and_press_change_pixels_and_dragging_out_does_not_navigate(self):
        row=self.b.status_view.rows[SID];opened=[];self.b.conversationRequested.connect(opened.append)
        row.name_hovered=False;normal=row.grab().toImage()
        point=QPointF(7,row.height()/2)
        APP.sendEvent(row,QMouseEvent(QEvent.Type.MouseMove,point,point,Qt.MouseButton.NoButton,Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier))
        self.assertTrue(row.name_hovered);hover=row.grab().toImage();self.assertNotEqual(normal,hover)
        QTest.mousePress(row,Qt.MouseButton.LeftButton,pos=point.toPoint());self.assertTrue(row.name_pressed)
        self.assertNotEqual(hover,row.grab().toImage())
        QTest.mouseRelease(row,Qt.MouseButton.LeftButton,pos=QPoint(row.text_left()+5,9))
        self.assertFalse(row.name_pressed);self.assertEqual(opened,[]);self.assertFalse(self.b.expanded)

if __name__=='__main__':unittest.main()
