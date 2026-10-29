"""One local sound per verified announcement batch; no network or speech."""
import subprocess
import sys
from pathlib import Path

def play_reset_sound():
    if sys.platform == 'darwin':
        sound = Path('/System/Library/Sounds/Glass.aiff')
        if not sound.is_file():
            return False
        try:
            subprocess.Popen(['/usr/bin/afplay', str(sound)], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             close_fds=True)
            return True
        except OSError:
            return False
    from PySide6.QtWidgets import QApplication
    QApplication.beep()
    return True
