"""Pure geometry regressions for Chrome's split full-screen toolbar/content."""
import unittest
from full_screen_geometry import rectangles_cover, full_screen_coverage, MAX_WINDOWS_PER_OWNER


class FullScreenCoverageTests(unittest.TestCase):
    DISPLAY = (0, 0, 2560, 1440)
    CHROME = [(0, 0, 2560, 41), (0, 41, 2560, 47),
              (0, 0, 2560, 124), (0, 88, 2560, 1352)]

    def test_observed_chrome_toolbar_and_content_cover_the_display(self):
        self.assertEqual(full_screen_coverage([self.DISPLAY], {1118: self.CHROME}), [self.DISPLAY])

    def test_single_window_previous_behavior(self):
        self.assertTrue(rectangles_cover(self.DISPLAY, [self.DISPLAY]))
        self.assertFalse(rectangles_cover(self.DISPLAY, [(0, 24, 2560, 1416)]))

    def test_one_pixel_gap_in_either_axis_prevents_yield(self):
        for rectangles in ([(0, 0, 2560, 88), (0, 89, 2560, 1351)],
                           [(0, 0, 1279, 1440), (1280, 0, 1280, 1440)]):
            with self.subTest(rectangles=rectangles):
                self.assertFalse(rectangles_cover(self.DISPLAY, rectangles))

    def test_different_processes_must_not_be_combined(self):
        owners = {1: [(0, 0, 2560, 88)], 2: [(0, 88, 2560, 1352)]}
        self.assertEqual(full_screen_coverage([self.DISPLAY], owners), [])

    def test_bounding_box_with_interior_hole_does_not_cover(self):
        frame = [(0, 0, 2560, 88), (0, 88, 100, 1352), (2460, 88, 100, 1352), (0, 1340, 2560, 100)]
        self.assertFalse(rectangles_cover(self.DISPLAY, frame))

    def test_partial_screen_and_unrelated_windows_do_not_cover(self):
        self.assertFalse(rectangles_cover(self.DISPLAY, [(0, 0, 2560, 124), (3000, 0, 2560, 1440)]))

    def test_multiple_displays_are_evaluated_independently(self):
        left = (-1920, 0, 1920, 1080)
        owners = {1: self.CHROME, 2: [(-1920, 24, 1920, 1056)]}
        self.assertEqual(full_screen_coverage([left, self.DISPLAY], owners), [self.DISPLAY])
        owners[2] = [left]
        self.assertEqual(full_screen_coverage([left, self.DISPLAY], owners), [left, self.DISPLAY])

    def test_clipped_overlap_can_cover_without_exactly_matching_edges(self):
        self.assertTrue(rectangles_cover(self.DISPLAY, [(-100, -100, 2700, 200), (-100, 88, 2700, 1500)]))

    def test_invalid_rectangles_fail_closed(self):
        for rect in ((0, 0, 0, 1440), (0, 0, 2560, -1), (0, 0, float('inf'), 1440), (float('nan'), 0, 2560, 1440)):
            with self.subTest(rect=rect):
                self.assertFalse(rectangles_cover(self.DISPLAY, [rect]))

    def test_rectangle_cap_does_not_use_unbounded_extra_coverage(self):
        rectangles = [(0, 0, 2560, 88)] * MAX_WINDOWS_PER_OWNER + [self.DISPLAY]
        self.assertFalse(rectangles_cover(self.DISPLAY, rectangles))


if __name__ == '__main__':
    unittest.main()
