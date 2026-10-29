"""Gecko video detection from IA2 HTML tags; independent of player controls."""
import ctypes,time
from ctypes import wintypes
from comtypes import IUnknown,GUID,COMMETHOD,HRESULT,COMError
from video_fullscreen import video_coverage

class IServiceProvider(IUnknown):
    _iid_=GUID('{6D5140C1-7436-11CE-8034-00AA006009FA}')
    _methods_=[COMMETHOD([],HRESULT,'QueryService',
        (['in'],ctypes.POINTER(GUID),'service'),(['in'],ctypes.POINTER(GUID),'iid'),
        (['out'],ctypes.POINTER(ctypes.POINTER(IUnknown)),'result'))]

class FirefoxVideo:
    IA2=GUID('{E89F726E-C4F4-4c19-BB19-B647D7FA8478}')
    def __init__(self,types):
        self.types=types;self.cached=None;self.detail={}
        self.ole=ctypes.OleDLL('oleacc')
        self.ole.AccessibleObjectFromWindow.argtypes=[wintypes.HWND,wintypes.DWORD,ctypes.POINTER(GUID),ctypes.c_void_p]
        self.free=ctypes.WinDLL('oleaut32').SysFreeString;self.free.argtypes=[ctypes.c_void_p];self.free.restype=None
    def tag(self,node):
        ia=node.QueryInterface(IServiceProvider).QueryService(self.IA2,self.IA2)
        table=ctypes.cast(ia,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        # IAccessible has 28 ABI slots; IA2's attributes accessor follows 17
        # preceding IA2 methods. No other object attributes are retained.
        function=ctypes.WINFUNCTYPE(ctypes.c_long,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p))(table[45])
        value=ctypes.c_void_p();status=function(ia,ctypes.byref(value))
        if status<0:raise OSError('IA2 attributes unavailable')
        if not value.value:return ''
        try:
            for item in ctypes.wstring_at(value.value).split(';'):
                if item.startswith('tag:'):return item[4:].casefold()
            return ''
        finally:self.free(value)
    def visible_rect(self,node):
        if node.accState(0)&(0x8000|0x10000):return None
        x,y,w,h=node.accLocation(0)
        return (x,y,x+w,y+h) if w>0 and h>0 else None
    def video(self,hwnd,monitor):
        self.detail=dict(method='firefox_ia2',video_node=False)
        # Re-check the actual node's visibility and geometry; retaining a COM
        # node handles overlays without treating a stale page as still playing.
        if self.cached and self.cached[0]==hwnd:
            try:
                node=self.cached[1];rect=self.visible_rect(node)
                if self.tag(node)=='video' and rect and video_coverage(rect,monitor):
                    self.detail.update(video_node=True,coverage=True);return True
            except (OSError,AttributeError,COMError):pass
        self.cached=None
        try:
            root=ctypes.POINTER(self.types.IAccessible)()
            self.ole.AccessibleObjectFromWindow(hwnd,0xfffffffc,ctypes.byref(self.types.IAccessible._iid_),ctypes.byref(root))
            began=time.monotonic();seen_video=False
            for fx,fy in ((.5,.5),(.3,.5),(.7,.5)):
                hit=root.accHitTest(round(monitor[0]+(monitor[2]-monitor[0])*fx),round(monitor[1]+(monitor[3]-monitor[1])*fy))
                if hasattr(hit,'QueryInterface'):node=hit.QueryInterface(self.types.IAccessible)
                elif isinstance(hit,int) and hit>0:node=root.accChild(hit).QueryInterface(self.types.IAccessible)
                else:node=root
                for _ in range(14):
                    if time.monotonic()-began>.3:break
                    try:
                        tag=self.tag(node)
                        if tag=='video':
                            seen_video=True;rect=self.visible_rect(node)
                            if rect and video_coverage(rect,monitor):
                                self.cached=(hwnd,node);self.detail.update(video_node=True,coverage=True);return True
                            break
                        parent=node.accParent
                        if not parent:break
                        node=parent.QueryInterface(self.types.IAccessible)
                    except (OSError,AttributeError,COMError):break
            self.detail.update(video_node=seen_video,coverage=False);return False
        except (OSError,AttributeError,COMError):
            self.detail['unavailable']=True;return None
    def clear(self):self.cached=None
