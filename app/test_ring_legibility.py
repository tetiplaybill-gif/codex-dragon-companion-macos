import os,math,unittest
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtCore import Qt,QRectF,QEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from ring_widgets import QuotaRings,RingLegend,metric_name,metric_color,ring_geometry,CENTER_Y
from ui_theme import contrast
APP=QApplication.instance() or QApplication([])

class RingLegibilityTests(unittest.TestCase):
    def widget(self,count):
        windows=[dict(name='一周',remaining=70,resetsAt=None)]
        if count==4:windows.insert(0,dict(name='5小时',remaining=70,resetsAt=None))
        r=QuotaRings(windows);r.setFixedWidth(121);r.show();APP.processEvents();self.addCleanup(r.deleteLater);self.addCleanup(r.close)
        return r
    def test_badges_do_not_overlap_each_other_or_the_caption_at_matching_progress(self):
        for count in (3,4):
            r=self.widget(count);radius=ring_geometry(count)[2]/2
            for progress in (0,.1,.25,.5,.7,.9,1):
                for key in r.values:r.values[key]=progress
                points=r.badge_points();caption=QRectF(r.width()/2-30,CENTER_Y+8,60,39)
                for i,p in enumerate(points):
                    self.assertGreaterEqual(p.x()-radius,0);self.assertLessEqual(p.x()+radius,r.width())
                    self.assertGreaterEqual(p.y()-radius,0);self.assertLessEqual(p.y()+radius,r.height())
                    self.assertFalse(QRectF(p.x()-radius,p.y()-radius,2*radius,2*radius).intersects(caption))
                    for q in points[i+1:]:self.assertGreaterEqual(math.hypot(p.x()-q.x(),p.y()-q.y()),2*radius)
    def test_standing_legend_names_all_metrics_and_fits_the_normal_bubble(self):
        for count,expected in [(3,['周剩余','距重置','今日Token']),(4,['5h剩余','周剩余','距重置','今日Token'])]:
            r=self.widget(count);legend=RingLegend(r);legend.setFixedWidth(248);legend.show();APP.processEvents();legend.grab()
            self.addCleanup(legend.deleteLater);self.addCleanup(legend.close)
            self.assertEqual([metric_name(m) for m in r.metrics],expected)
            self.assertEqual(len(legend.hits),count)
            for name,rect in zip(expected,legend.hits):
                self.assertIn(name,legend.accessibleName());self.assertGreaterEqual(rect.left(),0);self.assertLessEqual(rect.right(),legend.width()+.1)
    def test_legend_hover_shares_the_corresponding_ring_value_and_click_details(self):
        r=self.widget(4);legend=RingLegend(r);legend.setFixedWidth(248);legend.show();APP.processEvents();legend.grab()
        self.addCleanup(legend.deleteLater);self.addCleanup(legend.close)
        expanded=[];r.expand.connect(lambda:expanded.append(True))
        for i,rect in enumerate(legend.hits):
            APP.sendEvent(legend,QMouseEvent(QEvent.Type.MouseMove,rect.center(),rect.center(),Qt.MouseButton.NoButton,Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier));self.assertEqual(r.active,i)
            self.assertEqual(legend.active,i)
        QTest.mouseClick(legend,Qt.MouseButton.LeftButton,pos=legend.hits[2].center().toPoint());self.assertEqual(expanded,[True])
    def test_palette_and_icon_ink_have_sufficient_contrast_on_their_backgrounds(self):
        r=self.widget(4)
        for i,metric in enumerate(r.metrics):self.assertGreaterEqual(contrast(metric_color(metric,i).name(),'#f5f2f7'),3)
        self.assertGreaterEqual(contrast('#493b5b','#fffdff'),7)
    def test_badge_layout_is_reused_when_no_progress_or_size_changes(self):
        r=self.widget(4);points=r.badge_points();self.assertIs(r.badge_points(),points)
        r.values[r.metrics[0]['id']]=.2;self.assertIsNot(r.badge_points(),points)

if __name__=='__main__':unittest.main()
