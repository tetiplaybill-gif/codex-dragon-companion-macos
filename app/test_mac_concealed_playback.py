"""Full-screen concealment pauses playback without losing frames or action state."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QWidget
import mac_native as native
from desktop import DesktopPet
from stream_player import StreamPlayer
from sustained_player import SustainedPlayback
from decode_runtime import STATS


class PlaybackSurface(QWidget):
    set_full_screen_concealed=DesktopPet.set_full_screen_concealed
    schedule_animation=DesktopPet.schedule_animation
    schedule_movement=DesktopPet.schedule_movement
    sync_full_screen=DesktopPet.sync_full_screen

    def __init__(self):
        super().__init__()
        self._full_screen_concealed=False;self._conceal_motion_active=False
        self._desktop_hidden=False;self._video_yielded=False
        self.settings=dict(character_visible=True,playback_speed=1.25,on_top=True,video_fullscreen_yield=True)
        self.tick=QTimer(self);self.tick.setInterval(40);self.tick.start()
        self.motion_timer=QTimer(self);self.motion_timer.setInterval(1000);self.motion_timer.start()
        self.player=StreamPlayer();self.sustained=SustainedPlayback()
        self.walking=False;self.throwing=False;self.press_feedback=0
        self.gesture_until=20.;self.motion_clock=0.
        self.bubble=SimpleNamespace(status_indicator=SimpleNamespace(unread=set()))
        self.setGeometry(100,100,100,100);self.show()


class ConcealedPlaybackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.pet=PlaybackSurface();self.card=QWidget();self.card.setGeometry(250,100,100,100);self.card.show()
        self.alpha={};self.displays=[]
        native._yield=True;native._full_screen=False;native._overlays.clear();native._concealed.clear()
        native._overlays.update((self.pet,self.card))
        def conceal(widget,hidden):
            self.alpha[widget]=0. if hidden else 1.
            (native._concealed.add if hidden else native._concealed.discard)(widget)
        self.patches=[patch.object(native,'_conceal',side_effect=conceal),
                      patch.object(native,'full_screen_displays',side_effect=lambda pid:self.displays)]
        for item in self.patches:item.start()
        self.guard=native.FullScreenGuard(self.pet)

    def tearDown(self):
        self.pet.tick.stop();self.pet.motion_timer.stop();self.guard.timer.stop()
        self.pet.sustained.cancel();self.pet.player.close()
        self.assertTrue(STATS.drain())
        for item in reversed(self.patches):item.stop()
        native._guard=None;native._yield=True;native._full_screen=False
        native._overlays.clear();native._concealed.clear()
        self.pet.close();self.card.close()

    def conceal_character(self):
        self.displays=[(0,0,800,600)];self.guard.check()

    def test_hidden_character_stops_clocks_and_stale_callbacks(self):
        self.conceal_character()
        self.assertEqual(self.alpha[self.pet],0.)
        self.assertTrue(self.pet.isVisible()) # native alpha must not change Qt visibility
        self.assertFalse(self.pet.tick.isActive());self.assertFalse(self.pet.motion_timer.isActive())
        with patch.object(self.pet.player,'advance',side_effect=AssertionError('invisible playback')):
            DesktopPet._animate_frame(self.pet)
            DesktopPet._move_frame(self.pet)
        self.pet.tick.start();self.pet.schedule_animation()
        self.assertFalse(self.pet.tick.isActive())

    def test_card_on_other_screen_does_not_pause_visible_character(self):
        self.pet.move(1200,100);self.conceal_character()
        self.assertEqual(self.alpha[self.card],0.)
        self.assertTrue(self.pet._video_yielded)
        self.assertFalse(self.pet._full_screen_concealed)
        self.assertTrue(self.pet.tick.isActive());self.assertTrue(self.pet.motion_timer.isActive())

    def test_resume_keeps_frame_phase_remaining_time_and_original_speed(self):
        player=self.pet.player
        player.playhead=.05;player.next_time=.2;player.last_clock=10.;player.frame_index=4
        self.pet.sustained.phase='exit';owner=object();self.pet.sustained.owner=owner
        self.pet.walking=True
        with patch('desktop.time.monotonic',return_value=100.):self.conceal_character()
        with patch('desktop.time.monotonic',return_value=200.),patch('desktop.time.perf_counter',return_value=110.):
            self.displays=[];self.guard.check()
        self.assertTrue(self.pet.tick.isActive());self.assertTrue(self.pet.motion_timer.isActive())
        self.assertEqual(player.frame_index,4);self.assertEqual(player.playhead,.05)
        self.assertEqual(player.next_time,.2);self.assertEqual(player.last_clock,110.)
        self.assertAlmostEqual(player.deadline,110.+.15/1.25)
        self.assertEqual(self.pet.sustained.phase,'exit');self.assertIs(self.pet.sustained.owner,owner)
        self.assertEqual(self.pet.gesture_until,120.)
        with patch('stream_player.time.perf_counter',return_value=110.01):
            frame,ended=player.advance(32,self.pet.settings['playback_speed'])
        self.assertIsNone(frame);self.assertFalse(ended)
        self.assertAlmostEqual(player.playhead,.0625)

    def test_unread_completion_restores_character_and_clocks_immediately(self):
        self.conceal_character();self.pet.bubble.status_indicator.unread.add(('session','turn'))
        self.pet.sync_full_screen()
        self.assertEqual(self.alpha[self.pet],1.)
        self.assertFalse(self.pet._full_screen_concealed);self.assertTrue(self.pet.tick.isActive())
        self.pet.bubble.status_indicator.unread.clear();self.pet.sync_full_screen()
        self.assertEqual(self.alpha[self.pet],0.);self.assertFalse(self.pet.tick.isActive())

    def test_manual_hidden_character_is_not_restarted_on_full_screen_exit(self):
        self.conceal_character();self.pet._desktop_hidden=True;self.pet.hide()
        self.displays=[];self.guard.check()
        self.assertFalse(self.pet.tick.isActive());self.assertFalse(self.pet._full_screen_concealed)

    def test_real_decoder_stops_producing_after_bounded_prefetch(self):
        # The current frame/queue survives yielding. No GUI-thread joins or
        # re-decoding are needed on resume; the producer naturally backpressures.
        with tempfile.TemporaryDirectory(prefix='bailong-conceal-') as directory:
            path=Path(directory)/'frames.webp'
            frames=[Image.new('RGBA',(16,16),(i*8,40,80,255)) for i in range(20)]
            frames[0].save(path,save_all=True,append_images=frames[1:],duration=100,lossless=True)
            player=self.pet.player;first=player.start(path,16)
            self.conceal_character()
            deadline=time.monotonic()+2
            while player.frames.qsize()<6 and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(player.frames.qsize(),6)
            time.sleep(.03);before=STATS.snapshot().get('decoded_frames',0)
            time.sleep(.12);after=STATS.snapshot().get('decoded_frames',0)
            self.assertEqual(before,after);self.assertEqual(player.frame_index,0)
            self.displays=[];self.guard.check()
            raw,delay,index=player.frames.get(timeout=1)
            self.assertEqual(index,1);self.assertEqual(raw[0],8)
            self.assertEqual(first.toImage().pixelColor(0,0).red(),0)
            player.close();self.assertTrue(STATS.drain())


if __name__=='__main__':unittest.main()
