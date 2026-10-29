"""Real Qt clock, production materials and safe switching; synthetic Codex events."""
import json,time
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

def run(destination):
    from desktop import DesktopPet
    from desktop_core import VERSION
    from PIL import Image
    app=QApplication.instance() or QApplication([]);app.setQuitOnLastWindowClosed(False)
    p=DesktopPet(monitor=False);p.notify=lambda *a:None;p.refresh_quota=lambda *a:None
    p.apply_settings(dict(wandering=False,random_actions=False,self_talk=False,video_fullscreen_yield=False,update_checks=False))
    p.show();p.open_settings();started=time.monotonic();stage=0;checks={};records=[];original_geometry=p.geometry();navigation=p.codex_navigation;last=None
    def record():
        nonlocal last
        key=(p.material_store.current,p.materials.state['phase'],p.mode,p.sustained.phase)
        if key!=last:records.append(dict(at=round(time.monotonic()-started,3),tier=key[0],phase=key[1],mode=key[2],sustained=key[3]));last=key
    def finish(error=None):
        timer.stop();p.record_state()
        result=dict(version=VERSION,passed=not error and all(checks.values()),error=error,checks=checks,records=records,dpr=p.screen().devicePixelRatio(),realQtClock=True,syntheticCodexEvents=True,downloadTransportVerifiedSeparately=True)
        Path(destination).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');p.close();app.exit(0 if result['passed'] else 1)
    def sample():
        nonlocal stage
        try:
            record();elapsed=time.monotonic()-started
            if elapsed>55:finish('timeout');return
            if stage==0 and elapsed>1 and not p.bubble.size_transition.active:
                p.settings_dialog.tabs.setCurrentIndex(3)
                p.bubble.grab().save(str(Path(destination).with_suffix('.png')))
                checks['freshDefaultLight']=p.material_store.current=='light'
                checks['embeddedSettings']=not p.settings_dialog.isWindow() and hasattr(p.settings_dialog,'material_panel')
                with Image.open(p.asset_path(p.manifest['idle'])) as im:checks['actualLight512']=im.size==(512,512)
                checks['hdCacheReady']=p.material_store.available('hd')
                p.bubble.collapse_to_normal();p.on_activity(dict(kind='status',session='material-probe',turn='probe-turn',state='thinking',text='测试思考',active=1))
                stage=1
            elif stage==1 and p.sustained.active and p.sustained.cycles>=1:
                checks['lightCodexContinuous']=p.sustained.owner.action_id=='work04';p.materials.request('hd');stage=2
            elif stage==2 and p._pending_material:
                checks['switchWaitsForBoundary']=p.material_store.current=='light' and p.sustained.active
                p.on_activity(dict(kind='complete',session='material-probe',turn='probe-turn',title='验收完成'))
                checks['completionIconImmediate']=bool(p.bubble.status_indicator.unread);stage=3
            elif stage==3 and p.material_store.current=='hd' and p.mode=='task':
                checks['naturalTailBeforeSwitch']=any(r['sustained']=='exit' and r['tier']=='light' for r in records)
                checks['completionPreserved']=p.current['id']=='18' and bool(p.bubble.status_indicator.unread)
                with Image.open(p.asset_path(p.manifest['idle'])) as im:checks['actualHd720']=im.size==(720,720)
                checks['geometryUnchanged']=p.geometry()==original_geometry
                checks['navigationPreserved']=p.codex_navigation is navigation
                p.apply_settings(dict(character_visible=False));p.materials.request('light');stage=4
            elif stage==4 and p.material_store.current=='light' and not p.materials.job:
                checks['hiddenSwitchWorks']=not p.tick.isActive() and not p.isVisible()
                checks['hdKeptAfterLightSwitch']=p.material_store.available('hd')
                p.apply_settings(dict(character_visible=True));stage=5
            elif stage==5 and p.player and not p.player.ended and p.current:
                checks['visibleAgain']=p.isVisible() and p.tick.isActive()
                checks['decoderHealthy']=p.decode_error is None
                finish()
        except Exception as exc:finish(type(exc).__name__+': '+str(exc))
    timer=QTimer();timer.timeout.connect(sample);timer.start(16)
    return app.exec()
