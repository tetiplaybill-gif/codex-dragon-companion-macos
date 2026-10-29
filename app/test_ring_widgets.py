import os,math,unittest
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from ring_widgets import QuotaRings,ring_geometry,AXIS_X,AXIS_Y,TILT,ARC_START,ARC_SWEEP,CENTER_Y,ellipse_point

app=QApplication.instance() or QApplication([])
def sample():return [dict(id=str(i),label=['一周','距重置','今日 Token'][i],display='70%',kind=['quota','time','tokens'][i],icon=['calendar','clock','tokens'][i],progress=.7,description='测试指标',low=False) for i in range(3)]

class RingWidgetTests(unittest.TestCase):
    def setUp(self):self.rings=QuotaRings([],metrics=sample());self.rings.setFixedWidth(121);self.rings.show();app.processEvents()
    def tearDown(self):self.rings.close();self.rings.deleteLater();app.processEvents()
    def test_three_readable_head_icons_have_clearance_even_when_progress_matches(self):
        radii,stroke,badge=ring_geometry(3);points=self.rings.badge_points()
        self.assertGreaterEqual(badge,16)
        for a,b in zip(points,points[1:]):self.assertGreater(math.hypot(a.x()-b.x(),a.y()-b.y()),badge)
        self.assertLess(ring_geometry(5)[2],10)
    def test_icons_are_exactly_at_the_moving_arc_head(self):
        radius=ring_geometry(3)[0][0];center=QPointF(self.rings.width()/2,CENTER_Y);a=math.radians(TILT)
        for fraction in [0,.25,.5,.75,1]:
            angle=math.radians(ARC_START+ARC_SWEEP*fraction);x=radius*AXIS_X*math.sin(angle);y=-radius*AXIS_Y*math.cos(angle)
            point=self.rings.head_point(0,fraction);self.assertAlmostEqual(point.x(),center.x()+x*math.cos(a)-y*math.sin(a));self.assertAlmostEqual(point.y(),center.y()+x*math.sin(a)+y*math.cos(a))
    def test_solid_ring_progress_uses_arc_length_and_badges_stay_inside_card(self):
        samples=[ellipse_point(ring_geometry(3)[0][0],i/160) for i in range(161)]
        lengths=[math.hypot(b.x()-a.x(),b.y()-a.y()) for a,b in zip(samples,samples[1:])]
        self.assertLess(max(lengths)/min(lengths),1.01)
        for i in range(3):
            for step in range(41):
                point=self.rings.head_point(i,step/40)
                self.assertGreaterEqual(point.x()-6,0);self.assertGreaterEqual(point.y()-6,0)
                self.assertLessEqual(point.x()+6,self.rings.width());self.assertLessEqual(point.y()+6,86)
    def test_progress_animation_and_redraw_cache_preserve_position(self):
        self.rings.close();cache={'0':.1};self.rings=QuotaRings([],metrics=sample(),progress_cache=cache);self.rings.setFixedWidth(121)
        self.rings.animation.setCurrentTime(210);self.assertGreater(self.rings.values['0'],.1);self.assertLess(self.rings.values['0'],.7)
        self.rings.animation.setCurrentTime(420);self.assertAlmostEqual(cache['0'],.7)
        other=QuotaRings([],metrics=sample(),progress_cache=cache);self.assertAlmostEqual(other.values['0'],.7);other.close();other.deleteLater()
    def test_unknown_metric_never_reuses_a_previous_known_position(self):
        metrics=sample();metrics[0]['progress']=None
        other=QuotaRings([],metrics=metrics,progress_cache={'0':.8});self.assertEqual(other.values['0'],0);other.close();other.deleteLater()
    def test_hovering_each_moving_icon_selects_its_own_value(self):
        for index in range(3):
            point=self.rings.badge_points()[index].toPoint();QTest.mouseMove(self.rings,point);app.processEvents();self.assertEqual(self.rings.active,index)
    def test_solid_tracks_have_continuous_remainder_and_a_thicker_fill(self):
        image=self.rings.grab().toImage();scale=image.devicePixelRatio()
        def pixel(x,y):return image.pixelColor(round(x*scale),round(y*scale))
        background=pixel(10,50);top=self.rings.head_point(0,.5)
        for dy in range(-5,6):self.assertNotEqual(pixel(top.x(),top.y()+dy),background)
        for step in range(80,97):
            point=self.rings.head_point(0,step/100);self.assertNotEqual(pixel(point.x(),point.y()),background)
    def test_lower_opening_is_not_a_track_and_caption_stays_inside_ring(self):
        self.assertGreater(ARC_SWEEP,180);self.assertLess(ARC_SWEEP,250)
        for radius in ring_geometry(3)[0]:
            self.assertIsNone(self.rings.nearest(QPointF(self.rings.width()/2,CENTER_Y+radius)))
        image=self.rings.grab().toImage();scale=image.devicePixelRatio()
        def pixel(x,y):return image.pixelColor(round(x*scale),round(y*scale))
        background=pixel(10,50)
        # Real text pixels now occupy the former empty interior below the center.
        ink=[(x,y) for y in range(CENTER_Y+10,CENTER_Y+27) for x in range(48,73)
             if pixel(x,y)!=background and pixel(x,y).lightness()<150]
        self.assertTrue(ink)

if __name__=='__main__':unittest.main()
