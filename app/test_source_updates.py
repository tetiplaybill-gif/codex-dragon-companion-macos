"""A source checkout must not download another project's binary updater."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from update_controller import UpdateController

APP = QApplication.instance() or QApplication([])

class SourceUpdatesTests(unittest.TestCase):
    def test_no_automatic_work_or_manual_binary_install(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch('update_controller.UpdateJob') as job, \
                patch('update_controller.prune_completed') as prune:
            controller = UpdateController('1.0.1', Path(directory) / 'updates')
            controller.configure(True)
            self.assertFalse(controller.enabled)
            self.assertFalse(controller.initial.isActive())
            self.assertFalse(controller.timer.isActive())
            self.assertFalse(controller.cleanup_timer.isActive())
            self.assertFalse(controller.check())
            self.assertFalse(controller.download_install())
            self.assertIn('源码', controller.snapshot()['message'])
            job.assert_not_called()
            prune.assert_not_called()
            self.assertTrue(controller.shutdown())

if __name__ == '__main__':
    unittest.main()
