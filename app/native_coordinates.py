"""Convert Win32 physical screen points through the actual HWND client area.

Never divide a global position by DPR: mixed-DPI monitors have distinct origins.
The client-size ratio also accounts for fractional-DPI rounding by Windows.
"""
import ctypes
from functools import lru_cache
from ctypes import wintypes

@lru_cache(maxsize=1)
def window_api():
    api=ctypes.WinDLL('user32',use_last_error=True)
    api.ScreenToClient.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
    api.ScreenToClient.restype=wintypes.BOOL
    api.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    api.GetClientRect.restype=wintypes.BOOL
    return api

def client_position(hwnd,x,y,width,height,api=None):
    api=window_api() if api is None else api
    point=wintypes.POINT(x,y);rect=wintypes.RECT()
    if not api.ScreenToClient(hwnd,ctypes.byref(point)) or not api.GetClientRect(hwnd,ctypes.byref(rect)):return None
    pixels_x,pixels_y=rect.right-rect.left,rect.bottom-rect.top
    if pixels_x<=0 or pixels_y<=0 or width<=0 or height<=0:return None
    return ((point.x-rect.left)*width/pixels_x,(point.y-rect.top)*height/pixels_y)

def message_position(lparam):
    return ctypes.c_short(lparam&0xffff).value,ctypes.c_short((lparam>>16)&0xffff).value
