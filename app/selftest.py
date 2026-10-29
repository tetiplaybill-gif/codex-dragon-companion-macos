"""Offline smoke check executed by the shipped EXE, without a Python install."""
import os,json,time,traceback
from pathlib import Path

def run(root):
    os.environ['QT_QPA_PLATFORM']='offscreen'
    report={'passed':False,'checks':[],'frozen':False}
    try:
        import sys
        from version import VERSION
        report.update(version=VERSION,frozen=bool(getattr(sys,'frozen',False)))
        if '--quota-only' in sys.argv:
            from quota import read_quota,quota_windows
            windows=quota_windows(read_quota())
            report['checks'].append(f'EXE只读额度接口成功，返回{len(windows)}个窗口；不记录账号或额度数值')
            report['passed']=True
            (root/'额度接口检查报告.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            return 0
        from pet import Pet,clamp_position
        from quota import quota_windows
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QPoint,QRect,QSize,QPointF
        from types import SimpleNamespace
        report.update(version=VERSION,frozen=bool(getattr(sys,'frozen',False)))
        app=QApplication([]);pet=Pet();pet.tick.stop()
        from desktop_services import all_items
        items=all_items(pet.manifest)
        for item in items:
            frames=pet.load(item);assert len(frames)==round(item['durationMs']*24/1000)
            assert frames[0].width()==pet.frame_size
        assert len(pet.variants)==(15 if pet.manifest.get('upstreamAnimationVersion')=='0.4.1' else 10)
        report['checks'].append(f'{len(items)}段动画可解码，最新14困倦、完整落地主体与音效文件齐全')
        assert (root/'app/sounds/click.wav').is_file()
        assert '最新版' in next(v for v in pet.variants if v['id']=='14')['file']
        for item in items:
            assert 'renderScale' in item and 'renderOffset' in item
        report['checks'].append('全部动作尺寸校准字段齐全')
        pet.play(pet.manifest['quotaAnimation'],'quota');pet.started=time.monotonic()-pet.current['durationMs']/1000-.1;pet.animate();assert pet.mode=='idle'
        report['checks'].append('查询动作只播一次')
        press=SimpleNamespace(button=lambda:__import__('PySide6.QtCore',fromlist=['Qt']).Qt.MouseButton.LeftButton,globalPosition=lambda:QPointF(200,200))
        move=SimpleNamespace(buttons=press.button,globalPosition=lambda:QPointF(240,230))
        pet.mousePressEvent(press);pet.mouseMoveEvent(move);assert pet.mode=='drag'
        pet.mouseReleaseEvent(press);assert pet.mode=='landing' and pet.current.get('originalDurationMs',pet.current['durationMs'])==2000
        report['checks'].append('拖拽与落地切换正常，原落地主体时长2秒')
        for position in [QPoint(-999,-999),QPoint(5000,5000)]:
            area=QRect(0,0,1920,1040);assert area.contains(QRect(clamp_position(position,QSize(256,256),area),QSize(256,256)))
        report['checks'].append('屏幕边界限制正常')
        assert quota_windows({'rateLimits':{'primary':{'usedPercent':25,'windowDurationMins':300}}})[0]['remaining']==75
        report['checks'].append('额度解析正常；未使用或捆绑任何账号')
        pet.play(pet.idles[0],'idle');pet.grab().save(str(root/'检查预览.png'));pet.bubble.close();pet.hide()
        report['passed']=True
    except Exception:report['error']=traceback.format_exc()
    (root/('额度接口检查报告.json' if '--quota-only' in __import__('sys').argv else '检查报告.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if report['passed'] else 1
