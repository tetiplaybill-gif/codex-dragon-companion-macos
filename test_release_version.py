import unittest
from release_version import next_version,validate_new_version,validate_public_successor

class NumberingTests(unittest.TestCase):
    def test_patch_and_minor_both_carry_after_nine(self):
        self.assertEqual(next_version('0.7.8'),'0.7.9')
        self.assertEqual(next_version('0.7.9'),'0.8.0')
        self.assertEqual(next_version('0.9.9'),'1.0.0')
        self.assertEqual(next_version('1.9.9'),'2.0.0')
        self.assertEqual(next_version('1.0.9'),'1.1.0')
    def test_new_policy_does_not_reinterpret_legacy_installations(self):
        self.assertEqual(next_version('0.6.50'),'0.7.0')
        self.assertEqual(next_version('0.10.0'),'1.0.1')
        self.assertEqual(validate_new_version('0.7.0'),'0.7.0')
        with self.assertRaises(ValueError):validate_new_version('0.7.10')
        with self.assertRaises(ValueError):validate_new_version('0.10.0')

    def test_public_release_uses_previous_public_not_local_version(self):
        self.assertEqual(validate_public_successor('0.9.9','1.0.0'),'1.0.0')
        self.assertEqual(validate_public_successor('1.0.0','1.0.1'),'1.0.1')
        for candidate in ('1.0.1','1.1.0','0.9.9'):
            with self.assertRaises(ValueError):validate_public_successor('0.9.9',candidate)
