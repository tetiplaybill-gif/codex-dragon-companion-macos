"""Truthful dashboard metrics: account quota, cycle time, daily local tokens."""
import math,time
from datetime import datetime
from token_calendar import compact_tokens
from reset_watch import epoch,account_reset_text

def remaining_time(seconds):
    if seconds<=0:return '到期待刷新'
    minutes=max(1,math.ceil(seconds/60));days,hours=divmod(minutes//60,24)
    if days:return f'{days}天{hours}时'
    if hours:return f'{hours}时{minutes%60:02}分'
    return f'{minutes}分'

def dashboard_metrics(windows,tokens=None,now=None):
    now=time.time() if now is None else now
    ordered=sorted(windows,key=lambda w:0 if w.get('name')=='5小时' else 1 if w.get('name')=='一周' else 2)
    result=[]
    for window in ordered:
        name=window.get('name','额度');value=window.get('remaining')
        valid=isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and 0<=value<=100
        display=f'{value:g}%' if valid else '未提供'
        result.append(dict(id='quota:'+name,kind='quota',icon='bolt' if name=='5小时' else 'calendar',label=name,
                           progress=value/100 if valid else None,display=display,low=valid and value<=15,
                           description=f'{name}剩余额度：{display}\n'+account_reset_text(window.get('resetsAt'),now)+'（北京时间）'))
    if not result:
        result.append(dict(id='quota:unknown',kind='quota',icon='calendar',label='额度',progress=None,display='未提供',low=False,description='账户额度尚未提供；空轨道不代表0%。'))
    known=[w for w in ordered if epoch(w.get('resetsAt'))]
    target=min(known,key=lambda w:epoch(w['resetsAt'])) if known else None
    minutes=({'5小时':300,'一周':10080}.get(target.get('name')) or target.get('windowDurationMins')) if target else None
    if target and isinstance(minutes,(int,float)) and minutes>0:
        seconds=epoch(target['resetsAt'])-now;progress=max(0,min(1,seconds/(minutes*60)))
        display=remaining_time(seconds);description=f"距{target['name']}额度重置：{display}\n时间环表示周期剩余时间比例，随时间减少；不表示剩余额度。\n"+account_reset_text(target['resetsAt'],now)+'（北京时间）'
    else:progress=None;display='时间未提供';description='尚未取得账户额度的重置时间，倒计时暂不可用。'
    result.append(dict(id='reset-time',kind='time',icon='clock',label='距重置',progress=progress,display=display,low=False,description=description))
    current=datetime.fromtimestamp(now);today=current.strftime('%Y-%m-%d')
    valid=bool(tokens and not tokens.get('unavailable') and tokens.get('month')==current.strftime('%Y-%m'))
    if valid:
        days={k:v for k,v in (tokens.get('days') or {}).items() if k<=today and isinstance(v,int) and not isinstance(v,bool) and v>=0}
        count=days.get(today,0);peak=max(days.values(),default=0);progress=count/peak if peak else 0
        display=compact_tokens(count);description=f'今日 Token：{count:,}\n相对本月单日峰值 {peak:,} 的活跃度：{progress:.0%}。\n本机日志；输入含缓存、输出含推理。此环不表示套餐额度。'
        if tokens.get('partial'):description+='\n部分日志暂不可读，显示已有记录。'
    else:progress=None;display='待统计';description='今日 Token 尚未统计；统计完成后显示相对本月单日峰值的活跃度，不表示套餐额度。'
    result.append(dict(id='daily-tokens',kind='tokens',icon='tokens',label='今日 Token',progress=progress,display=display,low=False,description=description))
    # Quotas take precedence; up to two real account windows plus both local metrics.
    return result[:2]+result[-2:] if len(result)>4 else result
