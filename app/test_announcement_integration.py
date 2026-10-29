"""No live API, account data or audio is used in these integration checks."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from enhanced import EnhancedPet, ResetThread


class AnnouncementIntegrationTests(unittest.TestCase):
    def test_worker_keeps_partial_source_success_without_any_x_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            worker = ResetThread(state_dir=tmp,providers=[])
            received = []
            def ready(snapshot, alerts, fresh):
                received.append((snapshot, alerts, fresh))
                worker.stop.set()
                worker.wake.set()
            worker.ready.connect(ready)
            result={'source':'public_announcements','state':'degraded','checked':1,
                'sources':[{'id':'codex_resets','state':'ok','items':[]},
                           {'id':'codex_changelog','state':'error','items':[]}],
                'next_check':None}
            with patch.object(worker.monitor,'poll',return_value=(result,[])), \
                    patch('urllib.request.build_opener', side_effect=AssertionError('no network')):
                worker.run()
            self.assertEqual(len(received), 1)
            snapshot, alerts, fresh = received[0]
            self.assertEqual(snapshot['state'], 'degraded')
            self.assertEqual(snapshot['source'], 'public_announcements')
            self.assertEqual(alerts, [])
            self.assertTrue(fresh)
            self.assertIsNone(snapshot['next_check'])

    def test_options_preserve_silent_disabled_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'public-announcements-options.json').write_text(
                '{"interval_minutes":30,"sound_enabled":false,"enabled":false}')
            worker = ResetThread(state_dir=tmp,providers=[])
            worker.read_options()
            snapshot, alerts = worker.monitor.poll()
            self.assertEqual(snapshot['interval_minutes'], 30)
            self.assertFalse(snapshot['sound_enabled'])
            self.assertEqual(snapshot['state'], 'disabled')
            self.assertEqual(alerts, [])

    def pet(self):
        return SimpleNamespace(bubble=SimpleNamespace(redraw=Mock()),
            position_bubble=Mock(), say=Mock(), refresh_quota=Mock(),
            local_reset_evidence=Mock())

    def test_feature_updates_only_render_no_sound_or_account_refresh(self):
        pet = self.pet()
        snapshot = {'source':'x','state':'ok','checked':1,'items':[
            {'id':'123456','kind':'update','text':'New Codex feature'}]}
        with patch('announcement_sound.play_reset_sound') as sound:
            EnhancedPet.on_reset_feed(pet, snapshot, [], True)
        sound.assert_not_called()
        pet.say.assert_not_called()
        pet.refresh_quota.assert_not_called()
        pet.local_reset_evidence.decorate.assert_not_called()
        self.assertIs(pet.bubble.reset_snapshot, snapshot)

    def test_reset_batch_plays_one_sound_and_requests_live_account_read(self):
        pet = self.pet()
        snapshot = {'source':'x','state':'ok','checked':1,'items':[]}
        alerts = [{'kind':'reset','source_id':'codex_resets','title':'额度重置公告','text':'公开公告，不代表账户到账'},
                  {'kind':'reset','source_id':'codex_resets','title':'额度重置公告','text':'第二条'}]
        with patch('announcement_sound.play_reset_sound') as sound:
            EnhancedPet.on_reset_feed(pet, snapshot, alerts, True)
        sound.assert_called_once_with()
        pet.refresh_quota.assert_called_once_with()
        pet.local_reset_evidence.decorate.assert_not_called()

    def test_unexpected_product_or_scheduled_alert_never_plays_sound(self):
        pet=self.pet()
        alerts=[{'kind':'update','source_id':'codex_changelog','title':'update','text':'reset feature'},
                {'kind':'upcoming','source_id':'codex_resets','title':'future','text':'tomorrow'},
                {'kind':'reset','source_id':'unknown','title':'unknown','text':'reset'}]
        with patch('announcement_sound.play_reset_sound') as sound:
            EnhancedPet.on_reset_feed(pet,{'source':'public_announcements','state':'ok'},alerts,True)
        sound.assert_not_called();pet.say.assert_not_called()

    def test_manual_x_cache_remains_separate_and_does_not_change_public_health(self):
        from x_announcements import AnnouncementMonitor
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp,'x-announcements.json')
            monitor=AnnouncementMonitor(path)
            monitor.record_visible_post({'id':'2115622002581188681','author':'thsottiaux',
                'created_at':'2026-10-29T01:49:26Z','text':'New Codex feature'},observed_at=1793256792)
            before=path.read_bytes();worker=ResetThread(state_dir=tmp,providers=[])
            result=worker.with_manual_x_cache({'source':'public_announcements','state':'ok',
                'sources':[{'id':'codex_resets','state':'ok','items':[]}]})
            self.assertEqual(result['state'],'ok')
            self.assertEqual(result['sources'][-1]['id'],'x')
            self.assertEqual(result['sources'][-1]['state'],'unconfigured')
            self.assertEqual(path.read_bytes(),before)

    def test_worker_failure_marks_display_stale_without_faking_a_success(self):
        pet=self.pet()
        before={'source':'public_announcements','state':'ok','last_success':123,
            'sources':[{'id':'codex_resets','state':'ok','last_success':123,'items':[{'id':'old'}]},
                       {'id':'x','state':'unconfigured','last_manual_read':100,'items':[]}]}
        pet.bubble.reset_snapshot=before
        EnhancedPet.on_reset_feed_error(pet)
        after=pet.bubble.reset_snapshot
        self.assertEqual(after['state'],'error');self.assertTrue(after['sources'][0]['stale'])
        self.assertEqual(after['sources'][0]['last_success'],123)
        self.assertEqual(after['sources'][0]['items'],[{'id':'old'}])
        self.assertEqual(after['sources'][1],before['sources'][1])
        self.assertEqual(before['sources'][0]['state'],'ok')


if __name__ == '__main__':
    unittest.main()
