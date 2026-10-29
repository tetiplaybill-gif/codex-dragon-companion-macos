import unittest
from datetime import datetime
from ring_metrics import dashboard_metrics

class MetricTests(unittest.TestCase):
    def setUp(self):self.now=datetime(2026,10,18,12).timestamp()
    def test_pro_one_real_quota_plus_clock_and_daily_tokens(self):
        metrics=dashboard_metrics([dict(name='一周',remaining=70,resetsAt=self.now+3.5*86400)],dict(month='2026-10',days={'2026-10-17':200,'2026-10-18':100}),self.now)
        self.assertEqual([m['kind'] for m in metrics],['quota','time','tokens'])
        self.assertEqual([m['progress'] for m in metrics],[.7,.5,.5]);self.assertEqual([m['icon'] for m in metrics],['calendar','clock','tokens'])
        self.assertIn('不表示套餐额度',metrics[-1]['description'])
    def test_two_real_windows_retained_and_nearest_reset_selected(self):
        metrics=dashboard_metrics([dict(name='一周',remaining=70,resetsAt=self.now+86400),dict(name='5小时',remaining=50,resetsAt=self.now+9000)],now=self.now)
        self.assertEqual(len(metrics),4);self.assertEqual([m['label'] for m in metrics[:2]],['5小时','一周']);self.assertEqual(metrics[0]['icon'],'bolt')
        self.assertAlmostEqual(metrics[2]['progress'],.5);self.assertIn('5小时',metrics[2]['description'])
    def test_unknown_fields_never_become_zero(self):
        metrics=dashboard_metrics([dict(name='一周',remaining=None,resetsAt=None)],now=self.now)
        self.assertTrue(all(m['progress'] is None for m in metrics));self.assertIn('未提供',metrics[0]['display'])
    def test_expired_reset_not_fulfilled_and_clock_clamped(self):
        metrics=dashboard_metrics([dict(name='一周',remaining=70,resetsAt=self.now-30)],now=self.now)
        self.assertEqual(metrics[1]['progress'],0);self.assertIn('待刷新',metrics[1]['display'])
        metrics=dashboard_metrics([dict(name='一周',remaining=70,resetsAt=self.now+20*86400)],now=self.now)
        self.assertEqual(metrics[1]['progress'],1)
    def test_zero_daily_usage_is_known_zero_without_divide_by_zero(self):
        metric=dashboard_metrics([],dict(month='2026-10',days={'2026-10-18':0}),self.now)[-1]
        self.assertEqual(metric['progress'],0);self.assertEqual(metric['display'],'0')
    def test_previous_month_and_unavailable_usage_do_not_fabricate_today(self):
        for snapshot in [dict(month='2026-09',days={}),dict(month='2026-10',unavailable=True)]:
            self.assertIsNone(dashboard_metrics([],snapshot,self.now)[-1]['progress'])
    def test_future_daily_values_excluded_from_reference_peak(self):
        metric=dashboard_metrics([],dict(month='2026-10',days={'2026-10-18':100,'2026-10-19':100000}),self.now)[-1]
        self.assertEqual(metric['progress'],1)

if __name__=='__main__':unittest.main()
