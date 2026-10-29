"""Isolated native interaction acceptance for source and frozen builds.

Uses Win32 messages against this process's test HWND only. Does not move the
cursor, alter display scaling, start monitors, open Codex, or join its singleton.
"""
import ctypes,json,os,time
from pathlib import Path
from ctypes import wintypes as w

def run(output):
    from PIL import Image
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt,QPointF,QRectF,QEvent
    from PySide6.QtGui import QPixmap,QImage,QPainter
    from desktop import DesktopPet
    from desktop_services import all_items
    from desktop_core import VERSION
    from native_coordinates import client_position
    app=QApplication.instance() or QApplication([]);app.setQuitOnLastWindowClosed(False)
    class ProbePet(DesktopPet):
        def context_menu(self,point):self.probe_menus+=1
    pet=ProbePet(monitor=False);pet.probe_menus=0;pet.tick.stop();pet.motion_timer.stop()
    pet.apply_settings(dict(wandering=False,random_actions=False,on_top=False,sound=False,drag_physics=False,no_move=False,mouse_through=False),save=False)
    pet.show();pet.bubble.hide();app.processEvents()
    u=ctypes.WinDLL('user32',use_last_error=True)
    u.ClientToScreen.argtypes=[w.HWND,ctypes.POINTER(w.POINT)];u.ClientToScreen.restype=w.BOOL
    u.GetClientRect.argtypes=[w.HWND,ctypes.POINTER(w.RECT)];u.GetClientRect.restype=w.BOOL
    u.SendMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM];u.SendMessageW.restype=ctypes.c_ssize_t
    hwnd=int(pet.winId());rect=w.RECT();assert u.GetClientRect(hwnd,ctypes.byref(rect))
    pw,ph=rect.right,rect.bottom
    records=[];painted=0;body=0;clear=0
    def packed(x,y):return (x&0xffff)|((y&0xffff)<<16)
    def native_hit(x,y):
        p=w.POINT(round(x*pw/pet.width()),round(y*ph/pet.height()));assert u.ClientToScreen(hwnd,ctypes.byref(p))
        logical=client_position(hwnd,p.x,p.y,pet.width(),pet.height())
        result=u.SendMessageW(hwnd,0x84,0,packed(p.x,p.y))
        expected=pet.alpha_hit(*logical)
        assert (result!=-1)==expected,(logical,result,expected)
        return expected
    try:
        items=all_items(pet.manifest)
        # Every installed action's first frame, plus middle/end samples of idle,
        # drag and landing; retain the real manifest's scale and offset.
        for item in items:
            with Image.open(pet.asset_path(item)) as image:
                frames=[0]
                if item['id'] in {pet.idles[0]['id'],pet.manifest.get('dragAnimation',{}).get('id'),pet.manifest.get('landingAnimation',{}).get('id')}:
                    frames=sorted({0,image.n_frames//2,image.n_frames-1})
                for index in frames:
                    image.seek(index);rgba=image.convert('RGBA').resize((256,256))
                    frame=QImage(rgba.tobytes(),256,256,1024,QImage.Format.Format_RGBA8888).copy()
                    pet.frames=[QPixmap.fromImage(frame)];pet.index=0;pet._hit_image=frame;pet.current=item;pet.press_feedback=0
                    for facing in (1,-1):
                        pet.walk_direction=facing
                        for position in ((40,40),(420,180),(-80,-40)):
                            pet.move(*position);app.processEvents()
                            for y in range(8,256,24):
                                for x in range(8,256,24):
                                    if native_hit(x,y):body+=1
                                    else:clear+=1
                            records.append(dict(action=item['id'],frame=index,facing=facing,position=list(position)))
                    painted+=1
        # Real native press/move/release messages: Qt must receive a drag and
        # finish it. No QTest direct call bypasses the native adapter here.
        pet.gate.state='idle';pet.idle();pet.walk_direction=1;pet.press_feedback=0;pet.move(120,100);app.processEvents()
        point=next((QPointF(x,y) for y in range(40,220,12) for x in range(40,220,12) if pet.alpha_hit(x,y)),None)
        assert point is not None
        px,py=round(point.x()*pw/pet.width()),round(point.y()*ph/pet.height())
        u.SendMessageW(hwnd,0x201,1,packed(px,py))
        app.processEvents()
        assert pet._pointer_pressed
        u.SendMessageW(hwnd,0x200,1,packed(px+round(40*pw/256),py+round(30*ph/256)))
        app.processEvents()
        assert pet.dragging,'Native move did not enter drag'
        u.SendMessageW(hwnd,0x202,0,packed(px+round(40*pw/256),py+round(30*ph/256)))
        app.processEvents();assert not pet.dragging and pet.mode=='landing'
        u.SendMessageW(hwnd,0x204,2,packed(px,py));app.processEvents();u.SendMessageW(hwnd,0x205,0,packed(px,py));app.processEvents()
        assert pet.probe_menus==1
        pet.gate.state='idle';pet.idle()
        u.SendMessageW(hwnd,0x201,1,packed(px,py));app.processEvents();u.SendMessageW(hwnd,0x202,0,packed(px,py));app.processEvents()
        assert pet.click_timer.isActive();pet.click_timer.stop()
        pet.dragging=True;pet.gate.state='drag';pet.mode='drag'
        app.sendEvent(pet,QEvent(QEvent.Type.UngrabMouse));app.processEvents()
        assert not pet.dragging and pet.gate.state=='idle'
        u.SendMessageW(hwnd,0x202,0,packed(px,py));app.processEvents()
        assert not pet.click_timer.isActive(),'Late release after cancellation became a click'
        pet.switch_character('builtin');assert not pet.codex_navigation.closed
        proof=dict(passed=True,version=VERSION,dpr=pet.devicePixelRatioF(),clientPixels=[pw,ph],
            realWin32HitTests=True,nativePressDragRelease=True,nativeClickAndContextMenu=True,
            lostCaptureRecovered=True,characterNavigationAlive=True,actions=len(items),sampledFrames=painted,
            bodyPoints=body,transparentPoints=clear,records=records,osDisplaySettingsChanged=False,
            cursorMoved=False,syntheticProcessScale=os.environ.get('QT_SCALE_FACTOR','1'))
        Path(output).write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
        return 0
    finally:pet.close();app.processEvents()
