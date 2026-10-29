"""Short, isolated repeated-action memory and thread check."""
import json,tempfile,time,threading
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from desktop import DesktopPet
from pet import ROOT
def main():
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder);patches=[patch('enhanced.CONFIG',root/'settings.json'),patch('enhanced.STATE_DIR',root),patch('desktop.CONFIG',root/'settings.json'),patch('desktop.STATE_DIR',root)]
        for p in patches:p.start()
        pet=DesktopPet(monitor=False);pet.apply_settings(dict(wandering=False,random_actions=False));pet.show()
        items=pet.idles+pet.variants+[pet.manifest['dragAnimation'],pet.manifest['landingAnimation'],pet.manifest['quotaAnimation']]
        values=[];index=0;timer=QTimer()
        def step():
            nonlocal index
            import psutil
            pet.gate.state='idle';pet.play(items[index%len(items)],'variant');index+=1
            values.append(dict(action=index,rss_mb=round(psutil.Process().memory_info().rss/1048576,1),queue=pet.player.frames.qsize(),reader_threads=sum(t.name=='pet-frame-reader' for t in threading.enumerate()),first_cache=len(pet.player.first)))
            if index>=60:
                timer.stop();pet.close()
                (ROOT/'验收截图/压力测试.json').write_text(json.dumps(values,ensure_ascii=False,indent=2),encoding='utf-8');app.quit()
        timer.timeout.connect(step);timer.start(500);app.exec()
        for p in reversed(patches):p.stop()
if __name__=='__main__':main()
