import math
import unittest
from datetime import datetime, timedelta

from quota_summary_data import quota_items, today_tokens
from reset_watch import BEIJING


class QuotaSummaryDataTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 19, 12, 0, 0, tzinfo=BEIJING).timestamp()

    def quota(self, remaining=70, reset=None, name='5小时'):
        return {'name': name, 'remaining': remaining,
                'resetsAt': self.now + 9000 if reset is None else reset}

    def test_orders_account_windows_and_keeps_only_two(self):
        rows = quota_items([self.quota(name='每日额外额度'), self.quota(name='一周'), self.quota()], self.now)
        self.assertEqual([r['name'] for r in rows], ['5小时', '一周'])
        self.assertEqual([r['label'] for r in rows], ['5h剩余', '周剩余'])
        self.assertEqual(rows[0]['id'], 'quota:5小时')
        self.assertEqual(rows[0]['remaining'], 70.0)
        self.assertEqual(rows[0]['progress'], .7)
        self.assertEqual(rows[0]['display'], '70%')
        self.assertEqual(rows[0]['reset_text'], '2时30分后重置')
        self.assertIn('2026-10-19 14:30:00（北京时间）', rows[0]['description'])

    def test_real_zero_is_distinct_from_unknown(self):
        zero = quota_items([self.quota(0)], self.now)[0]
        self.assertEqual((zero['progress'], zero['display'], zero['low']), (0, '0%', True))
        for bad in [None, True, False, math.nan, math.inf, -1, 101, '70', [], {}, 10**400]:
            with self.subTest(bad=repr(bad)):
                row = quota_items([self.quota(bad)], self.now)[0]
                self.assertIsNone(row['remaining'])
                self.assertIsNone(row['progress'])
                self.assertEqual(row['display'], '—')
                self.assertFalse(row['low'])

    def test_decimal_percentages_fit_without_rounding_to_false_zero_or_full(self):
        for value, expected in [(0, '0%'), (.123456, '<1%'), (.99999, '<1%'),
                                (1, '1%'), (12.3456, '12.3%'), (70, '70%'),
                                (98.95, '99%'), (99, '99%'), (99.9999, '>99%'), (100, '100%')]:
            with self.subTest(value=value):
                row = quota_items([self.quota(value)], self.now)[0]
                self.assertEqual(row['display'], expected)
                self.assertIn(f'{value:g}%', row['description'])
                self.assertEqual(row['progress'], value / 100)

    def test_elapsed_reset_never_reuses_stale_percentage(self):
        for reset in [self.now - 1, self.now]:
            for remaining in [0, 70, 100]:
                row = quota_items([self.quota(remaining, reset)], self.now)[0]
                self.assertTrue(row['expired'])
                self.assertEqual(row['reset_text'], '待刷新')
                self.assertEqual(row['display'], '—')
                self.assertIsNone(row['progress'])
                self.assertFalse(row['low'])
        self.assertEqual(quota_items([self.quota(reset=self.now + 1)], self.now)[0]['reset_text'], '1分后重置')

    def test_week_countdown_and_unknown_timestamp(self):
        row = quota_items([self.quota(reset=self.now + timedelta(days=3, hours=12).total_seconds())], self.now)[0]
        self.assertEqual(row['reset_text'], '3天12时后重置')
        for reset in [True, False, -1, 0, math.nan, math.inf, 'invalid', '2026-10-19T12:00:00']:
            row = quota_items([self.quota(reset=reset)], self.now)[0]
            self.assertEqual(row['reset_text'], '重置时间未知')
            self.assertIsNone(row['reset_at'])
            self.assertEqual(row['display'], '70%')
        row = quota_items([self.quota(reset='2026-10-19T06:30:00Z')], self.now)[0]
        self.assertEqual(row['reset_text'], '2时30分后重置')

    def test_bad_window_containers_missing_names_and_duplicate_rows(self):
        for source in [None, {}, 'invalid', [], [None, True, 7]]:
            rows = quota_items(source, self.now)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['id'], 'quota:unknown')
            self.assertIsNone(rows[0]['progress'])
        rows = quota_items([self.quota(), self.quota(), self.quota(name='一周')], self.now)
        self.assertEqual(len(rows), 2)
        row = quota_items([dict(name=[], remaining=50)], self.now)[0]
        self.assertEqual(row['name'], '额度')
        row = quota_items([self.quota(name='较长的自定义额度名称')], self.now)[0]
        self.assertLessEqual(len(row['label']), 5)
        self.assertIn('较长的自定义额度名称', row['description'])


class TodayTokenSummaryTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 19, 12).timestamp()
        self.snapshot = dict(month='2026-10', days={'2026-10-19': 120_000})

    def test_known_count_has_exact_amount_and_local_scope(self):
        row = today_tokens(self.snapshot, self.now)
        self.assertTrue(row['known'])
        self.assertEqual(row['display'], '120.0K')
        self.assertIn('120,000', row['description'])
        self.assertIn('本机 Codex 日志', row['description'])
        self.assertIn('输入含缓存', row['description'])
        self.assertNotIn('progress', row)

    def test_arbitrary_precision_integer_cannot_overflow_compact_format(self):
        self.snapshot['days']['2026-10-19'] = 10**400
        row = today_tokens(self.snapshot, self.now)
        self.assertTrue(row['known'])
        self.assertEqual(row['display'], '>999T')
        self.assertIn(f'{10**400:,}', row['description'])

    def test_missing_today_is_legitimate_zero_but_bad_today_is_unknown(self):
        row = today_tokens(dict(month='2026-10', days={}), self.now)
        self.assertEqual((row['known'], row['display']), (True, '0'))
        for bad in [None, True, False, -1, 1.2, math.nan, math.inf, '120', {}, []]:
            row = today_tokens(dict(month='2026-10', days={'2026-10-19': bad}), self.now)
            self.assertEqual((row['known'], row['display']), (False, '待统计'))

    def test_future_invalid_and_outside_month_records_do_not_change_today(self):
        self.snapshot['days'].update({'2026-10-20': 99_000_000, '2026-10-32': 99_000_000,
                                     '2026-09-19': 99_000_000, '2026-10-18': 'bad',
                                     '20261019': 99_000_000, 19: 99_000_000})
        self.assertEqual(today_tokens(self.snapshot, self.now)['display'], '120.0K')

    def test_month_change_and_calendar_day_rollover_never_reuse_yesterday(self):
        now = datetime(2026, 10, 31, 23, 59).timestamp()
        snapshot = dict(month='2026-10', days={'2026-10-31': 1000})
        self.assertEqual(today_tokens(snapshot, now)['display'], '1.0K')
        after = now + 120
        self.assertFalse(today_tokens(snapshot, after)['known'])
        self.assertEqual(today_tokens(dict(month='2026-11', days={}), after)['display'], '0')
        after = datetime(2026, 10, 20, 0, 1).timestamp()
        self.assertEqual(today_tokens(self.snapshot, after)['display'], '0')

    def test_partial_and_unavailable_data_keep_truthful_status(self):
        self.snapshot['partial'] = True
        row = today_tokens(self.snapshot, self.now)
        self.assertTrue(row['known'])
        self.assertTrue(row['partial'])
        self.assertIn('部分日志暂不可读', row['description'])
        self.snapshot['unavailable'] = True
        row = today_tokens(self.snapshot, self.now)
        self.assertFalse(row['known'])
        self.assertTrue(row['partial'])
        for invalid in [None, [], True, 'bad', {}, dict(month='2026-10'), dict(month='2026-10', days=[])]:
            self.assertEqual(today_tokens(invalid, self.now)['display'], '待统计')


if __name__ == '__main__':
    unittest.main()
