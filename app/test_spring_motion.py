import unittest
from spring_motion import island_response,dismiss_progress,stage


class SpringMotionTests(unittest.TestCase):
    def test_surface_spring_is_bounded_and_settles_exactly(self):
        values=[island_response(i/1000) for i in range(1001)]
        self.assertEqual(values[0],0.);self.assertEqual(values[-1],1.)
        self.assertGreater(max(values),1.01);self.assertLessEqual(max(values),1.02)
        self.assertTrue(all(v>0 for v in values[1:]));self.assertLess(values[1],.001)
        self.assertLess(abs(values[-2]-values[-1]),.00001)
    def test_content_stages_do_not_overlap_and_wait_for_the_body(self):
        self.assertEqual(1-stage(.2,0,.18),0.)
        self.assertEqual(stage(.2,.24,.62),0.)
        self.assertEqual(stage(.62,.24,.62),1.)
    def test_dismiss_never_disappears_before_final_frame(self):
        values=[dismiss_progress(i/1000) for i in range(1001)]
        self.assertEqual(values[0],0.);self.assertEqual(values[-1],1.)
        self.assertTrue(all(-.006<=v<1 for v in values[:-1]))
        self.assertLess(min(values),0.)
        tail=values[120:]
        self.assertTrue(all(b>=a for a,b in zip(tail,tail[1:])))
    def test_surface_has_a_stable_terminal_hold(self):
        self.assertTrue(all(island_response(i/1000)==1. for i in range(820,1001)))


if __name__=='__main__':unittest.main()
