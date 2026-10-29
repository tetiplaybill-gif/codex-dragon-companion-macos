"""Native Windows Z-order regression, operating only on this test's own Qt UI."""
import ctypes,json,tempfile,time
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt,QTimer,QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialog
from desktop import DesktopPet
from pet import ROOT

def above(first,second):
    user=ctypes.windll.user32;user.GetWindow.argtypes=[ctypes.c_void_p,ctypes.c_uint];user.GetWindow.restype=ctypes.c_void_p
    current=int(second.winId());target=int(first.winId())
    for _ in range(2048):
        current=user.GetWindow(current,3) # GW_HWNDPREV: preceding top-level window
        if not current:return False
        if current==target:return True
    raise RuntimeError('Windows Z-order list unexpectedly long')

def main():
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    with tempfile.TemporaryDirectory() as folder:
        data=Path(folder);patches=[patch('enhanced.CONFIG',data/'settings.json'),patch('enhanced.STATE_DIR',data),patch('desktop.CONFIG',data/'settings.json'),patch('desktop.STATE_DIR',data),patch('desktop_settings.autostart_enabled',return_value=False)]
        for p in patches:p.start()
        pet=DesktopPet(monitor=False);pet.apply_settings({'on_top':True,'wandering':False,'random_actions':False});pet.show();pet.move(600,500);pet.bubble.redraw();pet.position_bubble()
        # Reproduce the previous construction: an unowned, ordinary settings dialog.
        legacy=QDialog();legacy.show();legacy.raise_();legacy.activateWindow();QTest.qWait(100)
        evidence={'old_unowned_dialog_below_pet':above(pet,legacy)};legacy.close();legacy.deleteLater()
        def click_settings():
            menu=app.activePopupWidget()
            if menu:
                action=next(a for a in menu.actions() if a.text()=='桌宠设置…')
                QTest.mouseClick(menu,Qt.MouseButton.LeftButton,pos=menu.actionGeometry(action).center())
        def inspect_open_menu():
            menu=app.activePopupWidget();pet.flush_status();pet.position_bubble()
            evidence['menu_above_pet_after_refresh']=bool(menu and above(menu,pet))
            evidence['menu_above_bubble_after_refresh']=bool(menu and above(menu,pet.bubble))
        QTimer.singleShot(800,inspect_open_menu)
        QTimer.singleShot(1100,click_settings);pet.context_menu(QPoint(650,550));QTest.qWait(200)
        panel=pet.settings_dialog
        evidence.update(settings_owned=panel.parentWidget() is pet,settings_above_pet_after_menu=above(panel,pet))
        for _ in range(4):pet.flush_status();pet.position_bubble();QTest.qWait(200)
        evidence['settings_above_bubble_after_updates']=above(panel,pet.bubble)
        # Also exercise applying the topmost checkbox while the dialog is open.
        pet.apply_settings({'on_top':False});QTest.qWait(100);pet.apply_settings({'on_top':True});QTest.qWait(150)
        evidence['settings_above_pet_after_toggle']=above(panel,pet)
        panel.hide();pet.open_settings();QTest.qWait(100);evidence['reopen_above_pet']=above(panel,pet)
        for index in range(2):
            QTimer.singleShot(150,click_settings);pet.context_menu(QPoint(650,550));QTest.qWait(150)
            evidence['repeat_menu_'+str(index+1)]=above(panel,pet) and above(panel,pet.bubble)
        out=ROOT/'验收截图/窗口层级.json';out.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
        pet.close();app.processEvents()
        for p in reversed(patches):p.stop()
        print(json.dumps(evidence));return 0 if all(evidence.values()) else 1
if __name__=='__main__':raise SystemExit(main())
