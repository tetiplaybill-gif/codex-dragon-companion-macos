"""Silent Windows notification, separate from the interactive Qt tray icon."""
import ctypes
from ctypes import wintypes as w


class GUID(ctypes.Structure):
    _fields_=[('a',w.DWORD),('b',w.WORD),('c',w.WORD),('d',ctypes.c_ubyte*8)]


class NotifyData(ctypes.Structure):
    _fields_=[('cbSize',w.DWORD),('hWnd',w.HWND),('uID',w.UINT),('uFlags',w.UINT),
              ('uCallbackMessage',w.UINT),('hIcon',w.HICON),('szTip',w.WCHAR*128),
              ('dwState',w.DWORD),('dwStateMask',w.DWORD),('szInfo',w.WCHAR*256),
              ('uTimeout',w.UINT),('szInfoTitle',w.WCHAR*64),('dwInfoFlags',w.DWORD),
              ('guidItem',GUID),('hBalloonIcon',w.HICON)]


class SilentNotifier:
    def __init__(self,hwnd):
        self.data=NotifyData()
        self.data.cbSize=ctypes.sizeof(NotifyData)
        self.data.hWnd=hwnd
        self.data.uID=0xB410
        self.added=False
        self.shell=ctypes.WinDLL('shell32',use_last_error=True)
        self.shell.Shell_NotifyIconW.argtypes=[w.DWORD,ctypes.POINTER(NotifyData)]
        self.shell.Shell_NotifyIconW.restype=w.BOOL
        user=ctypes.WinDLL('user32',use_last_error=True)
        user.LoadIconW.argtypes=[w.HINSTANCE,ctypes.c_void_p]
        user.LoadIconW.restype=w.HICON
        self.data.hIcon=user.LoadIconW(None,ctypes.c_void_p(32512))

    def show(self,title,text):
        if not self.added:
            self.data.uFlags=0x02|0x04|0x08  # icon, tooltip, state
            self.data.szTip='白龙桌宠 · 静默通知'
            self.data.dwState=self.data.dwStateMask=1  # hidden notification-only icon
            self.added=bool(self.shell.Shell_NotifyIconW(0,ctypes.byref(self.data)))
        if not self.added:return False
        self.data.uFlags=0x10  # NIF_INFO
        self.data.szInfoTitle=title[:63]
        self.data.szInfo=text[:255]
        self.data.dwInfoFlags=0x01|0x10|0x80  # INFO | NOSOUND | RESPECT_QUIET_TIME
        return bool(self.shell.Shell_NotifyIconW(1,ctypes.byref(self.data)))

    def close(self):
        if self.added:
            self.shell.Shell_NotifyIconW(2,ctypes.byref(self.data))
            self.added=False
