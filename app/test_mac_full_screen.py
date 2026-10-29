"""macOS full-screen yield guard state transitions (native calls mocked) and Reduce Motion."""
import os,sys,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QWidget
import mac_native as m

class Pet(QWidget):_video_yielded=None

class FullScreenGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.alpha={}
        def conceal(widget,hidden):
            self.alpha[widget]=0. if hidden else 1.;(m._concealed.add if hidden else m._concealed.discard)(widget)
        self.patches=[patch.object(m,'_conceal',side_effect=conceal),patch.object(m,'full_screen_displays',side_effect=lambda pid:self.displays)]
        for p in self.patches:p.start()
        self.displays=[];m._yield=True;m._overlays.clear();m._concealed.clear()
        self.widget=QWidget();self.widget.setGeometry(100,100,50,50);self.widget.show();m._overlays.add(self.widget)
        self.pet=Pet();self.guard=m.FullScreenGuard(self.pet)
    def tearDown(self):
        for p in self.patches:p.stop()
        m._yield=True;m._guard=None;self.widget.close()
    def test_hidden_while_yielding_is_restored_before_next_show(self):
        self.displays=[(0,0,800,600)];self.guard.check()
        self.assertEqual(self.alpha[self.widget],0.);self.assertTrue(self.pet._video_yielded)
        self.widget.hide();self.guard.check()
        self.assertEqual(self.alpha[self.widget],1.);self.assertNotIn(self.widget,m._concealed)
        self.displays=[];self.widget.show();self.guard.check();self.assertEqual(self.alpha[self.widget],1.)
    def test_yield_off_never_hides_and_restores(self):
        self.displays=[(0,0,800,600)];self.guard.check();self.assertEqual(self.alpha[self.widget],0.)
        m.set_yield(False);self.assertEqual(self.alpha[self.widget],1.);self.assertFalse(self.pet._video_yielded)
        self.guard.check();self.assertEqual(self.alpha[self.widget],1.)

class ConcealTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_restore_reads_input_transparency_from_qwindow(self):
        from PySide6.QtCore import Qt
        widget=QWidget();widget.show();widget.windowHandle().setFlag(Qt.WindowType.WindowTransparentForInput,True)
        calls={}
        with patch.object(m,'ns_window',return_value=1),patch.object(m,'_send',side_effect=lambda w,sel,r,a,v:calls.__setitem__(sel,v)):
            m._conceal(widget,True);m._conceal(widget,False)
        self.assertIs(calls['setIgnoresMouseEvents:'],True);widget.close()

if __name__=='__main__':unittest.main()


@unittest.skipUnless(sys.platform=='darwin','macOS accessibility setting')
class ReduceMotionTests(unittest.TestCase):
    def tearDown(self):
        import settings_controls;settings_controls.motion_enabled.cache_clear()
    def test_system_reduce_motion_disables_control_animation(self):
        import settings_controls
        for reduced in (True,False):
            settings_controls.motion_enabled.cache_clear()
            with patch('mac_native.reduce_motion',return_value=reduced):self.assertIs(settings_controls.motion_enabled(),not reduced)
    def test_reading_the_real_setting_returns_a_bool(self):
        from mac_native import reduce_motion
        self.assertIsInstance(reduce_motion(),bool)


class SystemOwnerTests(unittest.TestCase):
    def setUp(self):m._owners.clear();self.addCleanup(m._owners.clear)
    def test_system_helpers_are_not_full_screen_apps(self):
        paths={1:'/System/Library/CoreServices/AquaAppearanceHelper.app/Contents/MacOS/AquaAppearanceHelper',
               2:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
               3:'/System/Applications/QuickTime Player.app/Contents/MacOS/QuickTime Player',4:''}
        with patch.object(m,'_owner_path',side_effect=paths.get) as lookup:
            self.assertEqual([m.system_owner(p) for p in (1,2,3,4,1)],[True,False,False,False,True])
            self.assertEqual(lookup.call_count,4) # cached per pid
    def test_lookup_failure_keeps_yielding(self):
        with patch.object(m,'_owner_path',side_effect=OSError('gone')):self.assertFalse(m.system_owner(5))
