"""Capture our own compact UI in real Qt rendering, including edge cases."""
import json,time,os
import calendar
from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont,QFontDatabase
from compact_bubble import CompactBubble
from ring_widgets import QuotaRings
from pet import ROOT
def main():
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    ident=QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc');families=QFontDatabase.applicationFontFamilies(ident)
    if families:app.setFont(QFont(families[0],10))
    now=time.time();out=ROOT/'验收截图/简洁气泡';out.mkdir(parents=True,exist_ok=True)
    if os.environ.get('QT_SCALE_FACTOR'):
        out=out/('DPI-'+os.environ['QT_SCALE_FACTOR']);out.mkdir(exist_ok=True)
    pending=dict(id='preview-reset',announced=now-3600,reset_type='regular',scheduled=now+3600*12,text='今天内完成本轮额外重置，正在陆续落实。')
    cases={
        '单额度':dict(windows=[dict(name='一周',remaining=87,resetsAt=now+86400*6)],heading='Codex · 处理中',status='正在调整气泡布局，检查额度和重置时间…',reset_snapshot=dict(pending=pending,scheduled=pending)),
        '双额度':dict(windows=[dict(name='5小时',remaining=68,resetsAt=now+7200),dict(name='一周',remaining=87,resetsAt=now+86400*6)],heading='Codex · 思考中 · 2 个任务',status='正在检查代码，并核对桌宠的交互行为。'),
        '低额度':dict(windows=[dict(name='5小时',remaining=8,resetsAt=now+900),dict(name='一周',remaining=0,resetsAt=now-30)],heading='Codex · 已完成',status='任务完成啦！所有修改已通过回归测试。',reset_snapshot=dict(pending=dict(pending,scheduled=now-60))),
        '未知额度':dict(windows=[dict(name='一周',remaining=None,resetsAt=None)],heading='Codex · 待命',status='已连接本地 Codex，等待新消息'),
        '长消息展开':dict(windows=[dict(name='一周',remaining=87,resetsAt=now+86400)],heading='Codex · 正在回复',status='正在检查气泡位置和文字换行，自动动作与任务完成提醒都应保持安静。完整的工作摘要、来源和重置说明可以在展开后查看，收起后恢复紧凑布局。',expanded=True),
        '六行月历':dict(windows=[dict(name='5小时',remaining=68,resetsAt=now+7200),dict(name='一周',remaining=87,resetsAt=now+86400*6)],status='六月历行数边界检查。',token_snapshot=dict(month='2026-08',days={f'2026-08-{d:02}':(d%5)*100000 for d in range(1,32)},total=6000000)),
        '满额度':dict(windows=[dict(name='5小时',remaining=100,resetsAt=now+7200),dict(name='一周',remaining=100,resetsAt=now+86400*6)],status='两种额度均为100%，检查圆头与数值。'),
        '两行摘要':dict(windows=[dict(name='5小时',remaining=68.5,resetsAt=now+7200),dict(name='一周',remaining=87.5,resetsAt=now+86400*6)],status='正在检查完整月份的用量统计、公告切换与额度刷新，所有自动动作仍然保持静音。'),
        '长公告':dict(windows=[dict(name='5小时',remaining=68,resetsAt=now+7200),dict(name='一周',remaining=87,resetsAt=now+86400*6)],status='公告原文可悬停查看，或点击详情展开。',reset_feed_error=True,reset_snapshot=dict(pending=dict(pending,scheduled=None,text='这是完整公告，时间尚未公布，后续会陆续落实。'*5))),
        'Pro三环':dict(windows=[dict(name='一周',remaining=70,resetsAt=now+3.5*86400)],heading='Codex · 处理中',status='三环：额度 / 重置 / 今日Token'),
    }
    sizes={}
    for name,values in cases.items():
        bubble=CompactBubble();bubble.quota_caption='演示数据';bubble.reset_snapshot=dict(pending=None,scheduled=None)
        current=datetime.now();days={f'{current:%Y-%m}-{d:02}':((d*31)%7)*275000 if d<=current.day else 0 for d in range(1,calendar.monthrange(current.year,current.month)[1]+1)}
        bubble.token_snapshot=dict(month=current.strftime('%Y-%m'),days=days,total=sum(days.values()))
        for key,value in values.items():setattr(bubble,key,value)
        bubble.redraw();bubble.show();app.processEvents()
        for rings in bubble.findChildren(QuotaRings):
            if rings.isVisible():rings.animation.setCurrentTime(rings.animation.duration())
        app.processEvents()
        bubble.grab().save(str(out/(name+'.png')));sizes[name]=[bubble.width(),bubble.height()]
        if name=='Pro三环':
            for rings in bubble.findChildren(QuotaRings):
                if rings.isVisible():
                    for index in [1,2]:
                        rings.active=index;rings.update();app.processEvents()
                        bubble.grab().save(str(out/('三环悬停-'+rings.metrics[index]['kind']+'.png')))
        bubble.close();bubble.deleteLater();app.processEvents()
    (out/'尺寸.json').write_text(json.dumps(sizes,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(sizes,ensure_ascii=False))
if __name__=='__main__':main()
