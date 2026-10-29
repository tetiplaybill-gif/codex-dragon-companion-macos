"""Minimal AppKit calls for macOS through libobjc; no PyObjC dependency."""
import ctypes,ctypes.util,sys,weakref
from full_screen_geometry import full_screen_coverage,MAX_SCAN_WINDOWS,MAX_WINDOWS_PER_OWNER
from PySide6.QtCore import Qt,QObject,QEvent,QTimer
from PySide6.QtGui import QGuiApplication

# NSWindowCollectionBehavior bits.
CAN_JOIN_ALL_SPACES=1<<0
MOVE_TO_ACTIVE_SPACE=1<<1
MANAGED=1<<2
TRANSIENT=1<<3
STATIONARY=1<<4
PARTICIPATES_IN_CYCLE=1<<5
IGNORES_CYCLE=1<<6
FULL_SCREEN_PRIMARY=1<<7
FULL_SCREEN_AUXILIARY=1<<8
FULL_SCREEN_NONE=1<<9
NORMAL_LEVEL=0
_objc=None
_full_screen=False;_overlays=weakref.WeakSet();_watcher=None;_guard=None;_yield=True

def cocoa():
    # Offscreen/minimal winId() values are counters, not NSViews; never message them.
    return sys.platform=='darwin' and QGuiApplication.platformName()=='cocoa'

def _runtime():
    global _objc
    if _objc is None:
        ctypes.cdll.LoadLibrary('/System/Library/Frameworks/AppKit.framework/AppKit')
        lib=ctypes.cdll.LoadLibrary(ctypes.util.find_library('objc'))
        lib.objc_getClass.restype=ctypes.c_void_p;lib.objc_getClass.argtypes=[ctypes.c_char_p]
        lib.sel_registerName.restype=ctypes.c_void_p;lib.sel_registerName.argtypes=[ctypes.c_char_p]
        _objc=lib
    return _objc

def _send(target,selector,restype=ctypes.c_void_p,argtypes=(),*args):
    # arm64 requires an exact, non-variadic prototype for every objc_msgSend call.
    lib=_runtime();send=ctypes.CFUNCTYPE(restype,ctypes.c_void_p,ctypes.c_void_p,*argtypes)(('objc_msgSend',lib))
    return send(target,lib.sel_registerName(selector.encode()),*args)

def set_accessory_app():
    """Hide the Dock icon and app switcher entry, as LSUIElement does for a bundle."""
    if not cocoa():return False
    try:
        app=_send(_runtime().objc_getClass(b'NSApplication'),'sharedApplication')
        return bool(app) and bool(_send(app,'setActivationPolicy:',ctypes.c_bool,(ctypes.c_long,),1))
    except (OSError,AttributeError):return False

def reduce_motion():
    """System Settings > Accessibility > Display > Reduce motion."""
    if sys.platform!='darwin':return False
    try:
        workspace=_send(_runtime().objc_getClass(b'NSWorkspace'),'sharedWorkspace')
        return bool(workspace) and bool(_send(workspace,'accessibilityDisplayShouldReduceMotion',ctypes.c_bool))
    except (OSError,AttributeError):return False

def ns_window(widget):
    if not cocoa():return None
    view=ctypes.c_void_p(int(widget.winId()))
    return _send(view,'window') if view.value else None

def join_all_spaces(widget,full_screen=False):
    """Keep an overlay on every desktop Space; full-screen Spaces only when asked."""
    if sys.platform!='darwin':return None
    try:
        window=ns_window(widget)
        if not window:return None
        behavior=_send(window,'collectionBehavior',ctypes.c_ulong)
        # AppKit raises (and aborts the process) on mutually exclusive bits.
        behavior&=~(MOVE_TO_ACTIVE_SPACE|MANAGED|TRANSIENT|PARTICIPATES_IN_CYCLE|FULL_SCREEN_PRIMARY|FULL_SCREEN_AUXILIARY|FULL_SCREEN_NONE)
        behavior|=CAN_JOIN_ALL_SPACES|STATIONARY|IGNORES_CYCLE|(FULL_SCREEN_AUXILIARY if full_screen else FULL_SCREEN_NONE)
        _send(window,'setCollectionBehavior:',None,(ctypes.c_ulong,),behavior)
        return _send(window,'collectionBehavior',ctypes.c_ulong)
    except (OSError,AttributeError,ValueError):return None

def refresh(widget):
    """Re-assert Spaces, deactivation and stacking; Qt resets the level on every flag change."""
    if not cocoa() or not widget.isWindow() or not widget.testAttribute(Qt.WidgetAttribute.WA_WState_Created):return
    try:
        window=ns_window(widget)
        if not window:return
        join_all_spaces(widget,_full_screen)
        _send(window,'setHidesOnDeactivate:',None,(ctypes.c_bool,),False)
        # Qt puts a Tool window without StaysOnTop at the floating level; Windows keeps normal z-order.
        if not widget.windowFlags()&Qt.WindowType.WindowStaysOnTopHint:_send(window,'setLevel:',None,(ctypes.c_long,),NORMAL_LEVEL)
    except (OSError,AttributeError,ValueError):pass

class _Watcher(QObject):
    def eventFilter(self,obj,event):
        # At Show the NSWindow exists but is not ordered in; the deferred pass follows showEvent's own flag changes.
        if event.type()==QEvent.Type.Show:
            refresh(obj);QTimer.singleShot(0,obj,lambda:refresh(obj))
            if _guard is not None:QTimer.singleShot(0,_guard,_guard.check) # no flash over a full-screen Space
        return False

def overlay(widget):
    """Call right after a Qt.Tool overlay's QWidget.__init__, before its first show or winId."""
    global _watcher
    if sys.platform!='darwin':return
    widget.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow) # honoured only before native creation
    widget.setWindowFlag(Qt.WindowType.NoDropShadowWindowHint,True) # Windows layered windows have no system shadow
    if _watcher is None:_watcher=_Watcher()
    widget.installEventFilter(_watcher);_overlays.add(widget)

def set_full_screen(value):
    """Allow overlays into other apps' full-screen Spaces (yield off, or an unread completion)."""
    global _full_screen
    if _full_screen==bool(value):return
    _full_screen=bool(value)
    for widget in list(_overlays):
        refresh(widget)
        if _full_screen and widget.isVisible():widget.raise_()

_cg=None
class _Rect(ctypes.Structure):
    _fields_=[('x',ctypes.c_double),('y',ctypes.c_double),('w',ctypes.c_double),('h',ctypes.c_double)]

def _quartz():
    global _cg
    if _cg is None:
        cg=ctypes.cdll.LoadLibrary('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
        cf=ctypes.cdll.LoadLibrary('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        for lib,name,res,args in [(cg,'CGGetActiveDisplayList',ctypes.c_int32,[ctypes.c_uint32,ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint32)]),
                (cg,'CGDisplayBounds',_Rect,[ctypes.c_uint32]),(cg,'CGWindowListCopyWindowInfo',ctypes.c_void_p,[ctypes.c_uint32,ctypes.c_uint32]),
                (cg,'CGRectMakeWithDictionaryRepresentation',ctypes.c_bool,[ctypes.c_void_p,ctypes.POINTER(_Rect)]),
                (cf,'CFArrayGetCount',ctypes.c_long,[ctypes.c_void_p]),(cf,'CFArrayGetValueAtIndex',ctypes.c_void_p,[ctypes.c_void_p,ctypes.c_long]),
                (cf,'CFDictionaryGetValue',ctypes.c_void_p,[ctypes.c_void_p,ctypes.c_void_p]),
                (cf,'CFNumberGetValue',ctypes.c_bool,[ctypes.c_void_p,ctypes.c_long,ctypes.c_void_p]),(cf,'CFRelease',None,[ctypes.c_void_p])]:
            f=getattr(lib,name);f.restype=res;f.argtypes=args
        keys={k:ctypes.c_void_p.in_dll(cg,'kCGWindow'+k).value for k in ('Layer','Bounds','OwnerPID')}
        _cg=(cg,cf,keys)
    return _cg

_owners={}
def _owner_path(pid):
    lib=ctypes.CDLL('/usr/lib/libSystem.B.dylib')
    lib.proc_pidpath.restype=ctypes.c_int;lib.proc_pidpath.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_uint32]
    buffer=ctypes.create_string_buffer(4096)
    return buffer.value.decode('utf-8','replace') if lib.proc_pidpath(int(pid),buffer,4096)>0 else ''

def system_owner(pid):
    """True for macOS helper processes such as AquaAppearanceHelper, whose light/dark crossfade
    briefly covers every display at layer 0; a real full-screen Space belongs to an app."""
    if pid not in _owners:
        if len(_owners)>256:_owners.clear() # pids are reused; keep the cache small and fresh
        try:_owners[pid]=_owner_path(pid).startswith('/System/Library/')
        except (OSError,AttributeError):_owners[pid]=False
    return _owners[pid]

def full_screen_displays(own_pid):
    """Quartz bounds of displays covered by one app's native full-screen windows."""
    cg,cf,keys=_quartz()
    ids=(ctypes.c_uint32*16)();count=ctypes.c_uint32()
    if cg.CGGetActiveDisplayList(16,ids,ctypes.byref(count)):return []
    displays=[]
    for i in range(count.value):
        d=cg.CGDisplayBounds(ids[i]);displays.append((d.x,d.y,d.w,d.h))
    # On-screen windows of the current Spaces only; bounds, layer and pid need no screen-recording permission.
    windows=cg.CGWindowListCopyWindowInfo(1|16,0)
    if not windows:return []
    by_owner={}
    try:
        for i in range(min(cf.CFArrayGetCount(windows),MAX_SCAN_WINDOWS)):
            info=cf.CFArrayGetValueAtIndex(windows,i);layer=ctypes.c_int64();pid=ctypes.c_int64();rect=_Rect()
            if not (cf.CFNumberGetValue(cf.CFDictionaryGetValue(info,keys['Layer']),4,ctypes.byref(layer)) and layer.value==0):continue
            if not cf.CFNumberGetValue(cf.CFDictionaryGetValue(info,keys['OwnerPID']),4,ctypes.byref(pid)) or pid.value==own_pid:continue
            if not cg.CGRectMakeWithDictionaryRepresentation(cf.CFDictionaryGetValue(info,keys['Bounds']),ctypes.byref(rect)):continue
            if system_owner(pid.value):continue
            # Chrome can expose its full-screen toolbar and content as separate
            # layer-zero windows. Require their actual union to cover a display;
            # never merge unrelated apps or fill gaps with a bounding box.
            owner=by_owner.setdefault(pid.value,[])
            if len(owner)<MAX_WINDOWS_PER_OWNER:owner.append((rect.x,rect.y,rect.w,rect.h))
    finally:cf.CFRelease(windows)
    return full_screen_coverage(displays,by_owner)

_concealed=weakref.WeakSet()
def _conceal(widget,hidden):
    window=ns_window(widget)
    if not window:return
    # Alpha and input only: Qt keeps its own visibility, geometry and flags untouched.
    _send(window,'setAlphaValue:',None,(ctypes.c_double,),0. if hidden else widget.windowOpacity())
    # Panels toggle input transparency on the QWindow, which QWidget.windowFlags() does not mirror.
    handle=widget.windowHandle();flags=handle.flags() if handle else widget.windowFlags()
    _send(window,'setIgnoresMouseEvents:',None,(ctypes.c_bool,),hidden or bool(flags&Qt.WindowType.WindowTransparentForInput))
    (_concealed.add if hidden else _concealed.discard)(widget)

class FullScreenGuard(QObject):
    """Accessory-app overlays that join all Spaces also appear over other apps' full-screen Spaces;
    collection behaviour cannot exclude them, so overlays on such a display are made invisible instead."""
    def __init__(self,pet,interval=800):
        super().__init__(pet);self.pet=pet;self.displays=[];self.error=None
        import os;self.pid=os.getpid()
        self.timer=QTimer(self);self.timer.setInterval(interval);self.timer.timeout.connect(self.check)
        global _guard
        _guard=self
        if cocoa():self.timer.start()
    def check(self):
        try:self.displays=full_screen_displays(self.pid) if _yield else [];self.error=None
        except (OSError,AttributeError,ValueError) as error:self.displays=[];self.error=type(error).__name__
        yielded=False
        for widget in list(_overlays):
            try:
                if not widget.testAttribute(Qt.WidgetAttribute.WA_WState_Created):
                    _concealed.discard(widget);continue
                if not widget.isVisible():
                    # The NSWindow survives hide(); restore it now or the next show() stays invisible.
                    if widget in _concealed:_conceal(widget,False)
                    continue
                g=widget.frameGeometry()
                hide=any(g.x()<x+w and x<g.x()+g.width() and g.y()<y+h and y<g.y()+g.height() for x,y,w,h in self.displays)
                if hide or widget in _concealed:_conceal(widget,hide)
                yielded|=hide
            except (RuntimeError,OSError,AttributeError):continue
        self.pet._video_yielded=yielded
        # A card can yield on one display while the character remains visible
        # on another. Pause only the character whose native window is hidden.
        pause=getattr(self.pet,'set_full_screen_concealed',None)
        if pause is not None:pause(self.pet in _concealed and self.pet.isVisible())

def set_yield(value):
    """Whether the guard hides overlays over full-screen Spaces; independent of the window level."""
    global _yield
    if _yield==bool(value):return
    _yield=bool(value)
    if _guard is not None:_guard.check()

def activate_app():
    """Bring this app forward for user-opened panels; raise_() alone no longer activates it."""
    if not cocoa():return
    try:_send(_send(_runtime().objc_getClass(b'NSApplication'),'sharedApplication'),'activateIgnoringOtherApps:',None,(ctypes.c_bool,),True)
    except (OSError,AttributeError):pass

_reopen=None
def on_reopen(callback):
    """Run callback when the running app is opened again (Finder, Spotlight, open(1))."""
    global _reopen
    if not cocoa() or _reopen:return False
    try:
        lib=_runtime()
        for name,res,args in [('object_getClass',ctypes.c_void_p,[ctypes.c_void_p]),('class_getInstanceMethod',ctypes.c_void_p,[ctypes.c_void_p,ctypes.c_void_p]),
                ('class_getMethodImplementation',ctypes.c_void_p,[ctypes.c_void_p,ctypes.c_void_p]),('class_replaceMethod',ctypes.c_void_p,[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_char_p])]:
            f=getattr(lib,name);f.restype=res;f.argtypes=args
        delegate=_send(_send(lib.objc_getClass(b'NSApplication'),'sharedApplication'),'delegate')
        if not delegate:return False
        cls=lib.object_getClass(delegate);sel=lib.sel_registerName(b'applicationShouldHandleReopen:hasVisibleWindows:')
        IMP=ctypes.CFUNCTYPE(ctypes.c_bool,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_bool)
        original=IMP(lib.class_getMethodImplementation(cls,sel)) if lib.class_getInstanceMethod(cls,sel) else None
        def reopen(this,cmd,app,flag):
            # Keep Qt's own handling; recovery runs from the event loop, not inside AppKit's callback.
            try:QTimer.singleShot(0,callback)
            except RuntimeError:pass
            return original(this,cmd,app,flag) if original else True
        _reopen=(IMP(reopen),original)
        lib.class_replaceMethod(cls,sel,ctypes.cast(_reopen[0],ctypes.c_void_p),b'B@:@B')
        return True
    except (OSError,AttributeError,ValueError):return False
