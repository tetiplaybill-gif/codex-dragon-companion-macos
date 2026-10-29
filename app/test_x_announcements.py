"""Offline fixtures only: no X requests, credentials, audio or real app data."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import x_announcements as x

NOW = 1793255000.


def post(ident=10001, text='We just reset Codex rate limits for everyone.', published=None, **fields):
    return dict(id=str(ident), text=text, created_at=NOW-10 if published is None else published,
                author='thsottiaux', **fields)


class Provider:
    available = True
    def __init__(self, posts=None): self.posts=posts or []; self.calls=[]; self.error=None
    def fetch(self, **kwargs):
        self.calls.append(kwargs)
        if self.error: raise self.error
        return self.posts


class ClassificationTests(unittest.TestCase):
    def test_explicit_reset_english_and_chinese(self):
        for text in ('We just reset Codex rate limits for everyone.',
                     'ChatGPT usage limits have been reset.',
                     'We are resetting Codex quotas now.', 'Codex 额度已经重置。',
                     'We have reset weekly Codex usage limits.'):
            with self.subTest(text=text): self.assertEqual(x.classify(text), 'reset')

    def test_future_ambiguous_negative_and_recurring_never_confirm(self):
        cases = {'We will reset Codex limits tomorrow.': 'upcoming',
                 'Codex limits reset': 'uncertain',
                 'We have not reset Codex limits.': 'uncertain',
                 'Did we reset ChatGPT limits?': 'uncertain',
                 'If we reset Codex limits now it would help.': 'uncertain',
                 'We reset Codex limits every five hours.': 'uncertain',
                 'We reset Codex rate limits every week': 'uncertain',
                 'You can reset your Codex limits now': 'uncertain',
                 'Reset Codex limits now': 'uncertain',
                 'Sam said we reset Codex limits now.': 'uncertain',
                 '\"We just reset Codex limits\"': 'uncertain',
                 "Someone said 'we reset Codex limits'": 'uncertain',
                 'Imagine we reset Codex limits now.': 'uncertain',
                 'We reset Codex rate limits next Tuesday.': 'upcoming',
                 'We reset Codex rate limits in two hours.': 'upcoming',
                 'We reset Codex rate limits weekly.': 'uncertain',
                 'We reset Codex rate limits daily.': 'uncertain',
                 'Someone wrote:\nWe just reset Codex rate limits.': 'uncertain',
                 'The example text is:\nWe just reset Codex rate limits.': 'uncertain',
                 'We reset Codex rate limits.': 'uncertain',
                 'Codex is great. We just reset database connection limits.': 'uncertain',
                 'We reset Codex limits yesterday.': 'uncertain',
                 'Codex limits might reset soon.': 'upcoming'}
        for text, expected in cases.items():
            with self.subTest(text=text): self.assertEqual(x.classify(text), expected)

    def test_updates_and_unrelated(self):
        self.assertEqual(x.classify('New Codex desktop features are available today.'), 'update')
        self.assertEqual(x.classify('ChatGPT now supports a new model.'), 'update')
        for text in ('Lunch was great.', 'We just reset the database.', 'Done!',
                     'Look at https://example.test/codex-limits-reset-now'):
            self.assertIsNone(x.classify(text))

    def test_author_id_date_and_text_validation(self):
        bad = [dict(post(), author='someone_else'), dict(post(), id='../../evil'),
               dict(post(), created_at='2026-01-01'), dict(post(), text='x'*(x.MAX_TEXT+1))]
        for value in bad:
            with self.subTest(value=str(value)[:100]):
                with self.assertRaises(ValueError): x.normalize_post(value)

    def test_url_is_canonical_and_text_is_data(self):
        value = x.normalize_post(dict(post(text='We just reset Codex limits. <script>evil()</script>'),
                                     url='javascript:alert(1)'))
        self.assertEqual(value['url'], 'https://x.com/thsottiaux/status/10001')
        self.assertIn('<script>', value['text'])  # UI must render plain text.

    def test_retweets_excluded_but_contextual_reply_supported(self):
        self.assertIsNone(x.normalize_post(post(referenced_tweets=[{'type':'retweeted','id':'10000'}])))
        parent = post(text='We will reset Codex limits tomorrow.', published=NOW-100)
        reply = post(10002, 'Done!', parent=parent, in_reply_to_id='10001',
                     referenced_tweets=[{'type':'replied_to','id':'10001'}])
        result = x.normalize_post(reply)
        self.assertEqual(result['kind'], 'reset')
        self.assertEqual(result['context_url'], 'https://x.com/thsottiaux/status/10001')
        self.assertEqual(result['text'], 'Done!')
        for broken in (dict(reply, in_reply_to_id='10000'),
                       dict(reply, referenced_tweets=[]),
                       dict(reply, parent=post(text='Could we reset Codex limits tomorrow?'))):
            self.assertEqual(x.normalize_post(broken)['kind'], 'other')

    def test_official_parser_requires_resolved_author(self):
        payload={'data':[dict(post(), author_id='99')], 'includes':{'users':[{'id':'99','username':'thsottiaux'}]}}
        self.assertEqual(x.parse_official_response(payload)[0]['author'], 'thsottiaux')
        for broken in (dict(payload, includes={}), dict(payload, errors=[{}]),
                       dict(payload, includes={'users':[{'id':'99','username':'other'}]})):
            with self.assertRaises(ValueError): x.parse_official_response(broken)

    def test_official_parser_preserves_long_post_text(self):
        payload={'data':[dict(post(), author_id='99', note_tweet={'text':'New Codex feature. Full original content.'})],
                 'includes':{'users':[{'id':'99','username':'thsottiaux'}]}}
        self.assertEqual(x.parse_official_response(payload)[0]['text'], payload['data'][0]['note_tweet']['text'])


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='bailong-x-tests-')
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'x-announcements-state.json'
        self.provider=Provider([post()])
        self.monitor=x.AnnouncementMonitor(self.path, self.provider)

    def test_unavailable_makes_no_request_and_no_success_claim(self):
        provider=x.UnavailableProvider()
        with patch.object(provider, 'fetch', side_effect=AssertionError('must not fetch')):
            m=x.AnnouncementMonitor(self.path, provider)
            snapshot,alerts=m.poll(NOW, force=True)
        self.assertEqual(snapshot['state'], 'unconfigured')
        self.assertEqual(snapshot['error_code'], 'free_source_unavailable')
        self.assertEqual(snapshot['message'], '免费自动读取尚未接通；可在 X 官方页面登录查看。')
        self.assertIsNone(snapshot['last_success'])
        self.assertIsNone(snapshot['next_check'])
        self.assertTrue(snapshot['stale']); self.assertEqual(alerts, [])
        self.assertFalse(self.path.exists())

    def test_visible_post_records_manual_origin_without_automatic_success(self):
        monitor=x.AnnouncementMonitor(self.path)
        raw=post(10004, 'A freshly visible public post.', published=NOW-20)
        with patch.object(monitor.provider, 'fetch', side_effect=AssertionError('no network')):
            snapshot,alerts=monitor.record_visible_post(raw, observed_at=NOW)
            polled,poll_alerts=monitor.poll(NOW+1, force=True)
        self.assertEqual(snapshot['state'], 'unconfigured')
        self.assertEqual(snapshot['error_code'], 'free_source_unavailable')
        self.assertIsNone(snapshot['last_success']); self.assertIsNone(snapshot['checked'])
        self.assertEqual(snapshot['last_manual_read'], NOW)
        self.assertEqual(snapshot['display_origin'], 'official_visible_page')
        self.assertEqual(snapshot['items'][0]['text'], raw['text'])
        self.assertEqual(snapshot['items'][0]['url'], 'https://x.com/thsottiaux/status/10004')
        self.assertEqual(alerts, []); self.assertEqual(poll_alerts, [])
        self.assertEqual(polled['display_origin'], 'official_visible_page')
        loaded=x.AnnouncementMonitor(self.path)
        self.assertEqual(loaded.snapshot(NOW)['last_manual_read'], NOW)
        self.assertEqual(loaded.snapshot(NOW)['display_origin'], 'official_visible_page')
        self.assertTrue(loaded.state['initialized']); self.assertEqual(loaded.state['high_water'], '10004')

    def test_visible_reset_is_silent_and_not_replayed_after_provider_connects(self):
        monitor=x.AnnouncementMonitor(self.path)
        snapshot,alerts=monitor.record_visible_post(post(10004), observed_at=NOW)
        self.assertEqual(snapshot['items'][0]['kind'], 'reset'); self.assertEqual(alerts, [])
        provider=Provider([post(10004), post(10005, published=NOW-100)])
        connected=x.AnnouncementMonitor(self.path, provider)
        self.assertEqual(connected.poll(NOW+900)[1], [])
        provider.posts=[post(10006, published=NOW+1800)]
        self.assertEqual([a['id'] for a in connected.poll(NOW+1800)[1]], ['10006'])
        self.assertEqual(connected.snapshot(NOW+1800)['last_manual_read'], NOW)

    def test_first_fetch_silent_new_reset_once_and_restart_dedup(self):
        snapshot,alerts=self.monitor.poll(NOW)
        self.assertEqual(alerts, []); self.assertEqual(snapshot['state'], 'ok')
        self.provider.posts=[post(10002, published=NOW+900)]*2
        snapshot,alerts=self.monitor.poll(NOW+900)
        self.assertEqual([a['id'] for a in alerts], ['10002'])
        self.assertTrue(self.path.is_file())
        m=x.AnnouncementMonitor(self.path, self.provider)
        self.assertEqual(m.poll(NOW+1800)[1], [])
        self.assertEqual(len(m.snapshot(NOW+1800)['items']), 1)
        self.assertEqual(m.snapshot(NOW+1800)['items'][0]['id'], '10002')

    def test_cadence_and_bounded_provider_arguments(self):
        self.monitor.poll(NOW)
        self.monitor.poll(NOW+899)
        self.assertEqual(len(self.provider.calls), 1)
        self.monitor.poll(NOW+900)
        self.assertEqual(self.provider.calls[-1], dict(since_id='10001', limit=100, timeout=10))
        self.monitor.configure(interval_minutes=1)
        self.assertEqual(self.monitor.snapshot(NOW)['interval_minutes'], 5)
        self.monitor.configure(interval_minutes=99999)
        self.assertEqual(self.monitor.snapshot(NOW)['interval_minutes'], 1440)

    def test_nonreset_updates_display_without_sound(self):
        self.monitor.poll(NOW)
        self.provider.posts=[post(10002, 'New Codex features are available.', NOW+900),
                             post(10003, 'We will reset Codex limits tomorrow.', NOW+900),
                             post(10004, 'Codex limits reset?', NOW+900),
                             post(10005, 'Lovely weather.', NOW+900)]
        snapshot,alerts=self.monitor.poll(NOW+900)
        self.assertEqual(alerts, [])
        self.assertEqual([i['id'] for i in snapshot['items']], ['10005'])
        self.assertEqual(snapshot['items'][0]['kind'], 'other')

    def test_mute_consumes_seen_and_unmute_does_not_replay(self):
        self.monitor.poll(NOW)
        self.monitor.configure(sound_enabled=False)
        self.provider.posts=[post(10002, published=NOW+900)]
        self.assertEqual(self.monitor.poll(NOW+900)[1], [])
        self.monitor.configure(sound_enabled=True)
        self.assertEqual(self.monitor.poll(NOW+1800)[1], [])

    def test_disable_reenable_has_silent_baseline(self):
        self.monitor.poll(NOW)
        self.monitor.configure(enabled=False)
        self.provider.posts=[post(10002, published=NOW+900)]
        self.assertEqual(self.monitor.poll(NOW+900)[0]['state'], 'disabled')
        self.assertEqual(len(self.provider.calls), 1)
        self.monitor.configure(enabled=True)
        self.assertEqual(self.monitor.poll(NOW+1800)[1], [])

    def test_network_errors_keep_cache_backoff_and_hide_exception(self):
        self.monitor.poll(NOW)
        self.provider.error=OSError('sensitive request value must not leak')
        snapshot,alerts=self.monitor.poll(NOW+900)
        self.assertEqual(snapshot['state'], 'error'); self.assertTrue(snapshot['stale'])
        self.assertEqual(snapshot['items'][0]['id'], '10001')
        self.assertEqual(snapshot['next_check'], NOW+1800)
        self.assertNotIn('sensitive', json.dumps(snapshot)); self.assertEqual(alerts, [])
        self.monitor.poll(NOW+1000, force=True)
        self.assertEqual(len(self.provider.calls), 2)
        snapshot,_=self.monitor.poll(NOW+1800)
        self.assertEqual(snapshot['next_check'], NOW+3600)
        m=x.AnnouncementMonitor(self.path, self.provider)
        m.poll(NOW+1801, force=True)
        self.assertEqual(len(self.provider.calls), 3)

    def test_write_failure_suppresses_sound(self):
        self.monitor.poll(NOW)
        self.provider.posts=[post(10002, published=NOW+900)]
        with patch.object(x, '_atomic_json', side_effect=OSError('disk full')):
            snapshot,alerts=self.monitor.poll(NOW+900)
        self.assertEqual(snapshot['error_code'], 'cache_write')
        self.assertEqual(alerts, [])

    def test_old_or_future_posts_do_not_ring(self):
        self.monitor.poll(NOW)
        self.provider.posts=[post(10002, published=NOW-1000), post(10003, published=NOW+100000)]
        snapshot,alerts=self.monitor.poll(NOW+900)
        self.assertEqual(alerts, [])
        self.assertEqual(snapshot['items'][0]['kind'], 'uncertain')

    def test_invalid_batch_keeps_last_good_and_size_is_bounded(self):
        self.monitor.poll(NOW)
        for posts in ([dict(post(), author='other')], [post()]*101):
            self.provider.posts=posts
            snapshot,alerts=self.monitor.poll(self.monitor.state['next_check'])
            self.assertEqual(snapshot['error_code'], 'invalid_response')
            self.assertEqual(snapshot['items'][0]['id'], '10001'); self.assertEqual(alerts, [])

    def test_high_water_prevents_realert_after_seen_eviction(self):
        self.monitor.poll(NOW)
        self.monitor.state.update(high_water='20000', seen=[])
        self.provider.posts=[post(19000, published=NOW+900)]
        self.assertEqual(self.monitor.poll(NOW+900)[1], [])

    def test_forced_refresh_dedup_and_late_old_timestamp(self):
        self.monitor.poll(NOW)
        self.provider.posts=[post(10002, published=NOW+5)]
        self.assertEqual(len(self.monitor.poll(NOW+10, force=True)[1]), 1)
        self.assertEqual(self.monitor.poll(NOW+11, force=True)[1], [])
        self.provider.posts=[post(10003, published=NOW+1)]
        self.assertEqual(self.monitor.poll(NOW+12, force=True)[1], [])

    def test_done_context_survives_restart(self):
        parent=post(text='We will reset Codex limits tomorrow.', published=NOW-100)
        self.provider.posts=[post(10002, 'Done!', parent=parent, in_reply_to_id='10001',
                                  referenced_tweets=[{'type':'replied_to','id':'10001'}])]
        self.monitor.poll(NOW)
        m=x.AnnouncementMonitor(self.path, self.provider)
        self.assertEqual(m.snapshot(NOW)['items'][0]['kind'], 'reset')
        self.assertEqual(m.snapshot(NOW)['items'][0]['context_text'], parent['text'])

    def test_corrupt_cache_recovers_silently(self):
        self.path.write_text('{bad json')
        monitor=x.AnnouncementMonitor(self.path, self.provider)
        self.assertEqual(monitor.poll(NOW)[1], [])

    def test_bad_typed_cache_recovers_silently(self):
        self.monitor.poll(NOW)
        saved=json.loads(self.path.read_text())
        for key, value in (('failures', 'bad'), ('last_success', {}), ('seen', [123]), ('initialized', 'yes')):
            self.path.write_text(json.dumps(dict(saved, **{key:value})))
            monitor=x.AnnouncementMonitor(self.path, self.provider)
            self.assertEqual(monitor.poll(NOW+900)[1], [])

    def test_large_unicode_cache_remains_loadable_and_bounded(self):
        self.provider.posts=[post(10001+i, 'New Codex update. '+('新'*24000)) for i in range(100)]
        self.monitor.poll(NOW)
        self.assertLessEqual(self.path.stat().st_size, x.MAX_CACHE_BYTES)
        loaded=x.AnnouncementMonitor(self.path, self.provider)
        self.assertTrue(loaded.state['initialized'])
        self.assertEqual(loaded.state['high_water'], '10100')
        self.assertEqual(len(loaded.snapshot(NOW)['items']), 1)

    def test_newest_publication_beats_pinned_order_and_id(self):
        self.provider.posts=[dict(post(20000, published=NOW-100), pinned=True),
                             post(10002, 'A nice morning.', published=NOW-1)]
        snapshot,alerts=self.monitor.poll(NOW)
        self.assertEqual([i['id'] for i in snapshot['items']], ['10002'])
        self.assertEqual(snapshot['items'][0]['kind'], 'other')
        self.assertEqual(alerts, [])
        self.assertEqual(len(json.loads(self.path.read_text())['items']), 1)

    def test_retweet_does_not_replace_latest_authored_post(self):
        self.provider.posts=[post(10002, 'A nice morning.', published=NOW-20),
                             post(10003, published=NOW-1, referenced_tweets=[{'type':'retweeted','id':'99999'}])]
        snapshot,alerts=self.monitor.poll(NOW)
        self.assertEqual([i['id'] for i in snapshot['items']], ['10002'])
        self.assertEqual(alerts, [])

    def test_previous_multi_item_cache_preserves_receipts_and_latest_only(self):
        self.monitor.poll(NOW)
        saved=json.loads(self.path.read_text())
        saved['items']=[x.normalize_post(post(10002, 'New Codex update.', published=NOW-1)),
                        x.normalize_post(post(10001, published=NOW-100))]
        saved.update(seen=['10002','10001'], high_water='10002')
        self.path.write_text(json.dumps(saved))
        loaded=x.AnnouncementMonitor(self.path, self.provider)
        self.assertTrue(loaded.state['initialized'])
        self.assertEqual(loaded.state['high_water'], '10002')
        self.assertEqual([i['id'] for i in loaded.snapshot(NOW)['items']], ['10002'])
        self.provider.posts=[post(10002, published=NOW-1)]
        self.assertEqual(loaded.poll(NOW+900)[1], [])

    def test_concurrent_poll_never_duplicates_fetch(self):
        ready=threading.Event(); release=threading.Event()
        def fetch(**kwargs): ready.set(); release.wait(3); return [post()]
        with patch.object(self.provider, 'fetch', side_effect=fetch) as call:
            thread=threading.Thread(target=lambda:self.monitor.poll(NOW)); thread.start()
            self.assertTrue(ready.wait(1))
            self.assertEqual(self.monitor.poll(NOW)[1], [])
            release.set(); thread.join(3)
            self.assertEqual(call.call_count, 1)


if __name__ == '__main__': unittest.main()
