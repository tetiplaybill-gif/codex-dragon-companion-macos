"""One local sound per verified announcement batch; no network or speech."""
import subprocess
import sys
from pathlib import Path

def play_reset_sound():
    if sys.platform == 'win32':
        # Use an existing Windows system sound, asynchronously and once. There
        # is no downloaded audio, shell command, loop, or second fallback beep.
        try:
            import winsound
            winsound.PlaySound('SystemAsterisk',
                winsound.SND_ALIAS | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            return True
        except (ImportError, OSError, RuntimeError):
            return False
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
    try:
        from PySide6.QtWidgets import QApplication
        if QApplication.instance() is None:
            return False
        QApplication.beep()
        return True
    except (ImportError, OSError, RuntimeError):
        return False
