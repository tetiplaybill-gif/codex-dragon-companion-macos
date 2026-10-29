"""Render this application's own windows and report bounded-memory behavior."""
import json,os,tempfile,time
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtWidgets import QApplication
from desktop import DesktopPet
from pet import ROOT

def main():
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    font=QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
    families=QFontDatabase.applicationFontFamilies(font)
    if families:app.setFont(QFont(families[0],10))
    with tempfile.TemporaryDirectory() as folder:
        tmp=Path(folder);patches=[patch('enhanced.CONFIG',tmp/'settings.json'),patch('enhanced.STATE_DIR',tmp),patch('desktop.CONFIG',tmp/'settings.json'),patch('desktop.STATE_DIR',tmp),patch('desktop_settings.autostart_enabled',return_value=False)]
        for p in patches:p.start()
        started=time.monotonic();pet=DesktopPet(monitor=False);elapsed=time.monotonic()-started
        pet.apply_settings(dict(wandering=False,random_actions=False));pet.show();pet.reset_position()
        pet.update_quota([dict(name='一周',remaining=87,resetsAt=time.time()+86400)],time.time(),'live')
        pet.bubble.quota_caption='界面测试示例 · 非实时账户读数';pet.bubble.status='正在验证桌面控制、静音和气泡布局…';pet.bubble.redraw();pet.position_bubble()
        pet.open_settings();pet.open_chat()
        qa=ROOT/'验收截图';qa.mkdir(exist_ok=True)
        measurements=[]
        def sample():
            import psutil
            measurements.append(round(psutil.Process().memory_info().rss/1048576,1))
        timer=QTimer();timer.timeout.connect(sample);timer.start(500)
        def capture():
            pet.grab().save(str(qa/'角色.png'));pet.bubble.grab().save(str(qa/'气泡.png'))
            pet.settings_dialog.grab().save(str(qa/'设置.png'))
            pet.settings_dialog.tabs.setCurrentIndex(1)
            pet.chat_window.grab().save(str(qa/'聊天.png'))
            pet.record_state();result=json.loads((tmp/'runtime.json').read_text(encoding='utf-8'));result.update(startup_seconds=round(elapsed,3),rss_samples=measurements)
            (qa/'性能.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            pet.close();app.quit()
        QTimer.singleShot(5000,capture);app.exec()
        for p in reversed(patches):p.stop()
if __name__=='__main__':main()
