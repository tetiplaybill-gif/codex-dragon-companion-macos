"""Relative public reset estimates; reaching a date is never confirmation."""
import math
import re
import time
from urllib.parse import urlsplit,unquote
from reset_watch import pending_reset,locally_reset,epoch,local_time,schedule_text

PUBLIC_SOURCE_POLICIES={
    'codex_resets':dict(label='Codex Resets（第三方）',url='https://codex-resets.com/',hosts=('codex-resets.com',),
                        coverage='第三方额度重置汇总，只覆盖重置公告，不代表账号的全部推文。'),
    'codex_changelog':dict(label='Codex 官方更新',url='https://learn.chatgpt.com/docs/changelog',hosts=('learn.chatgpt.com','developers.openai.com'),
                           coverage='OpenAI 官方 Codex 更新记录，不覆盖全部 X 推文；功能更新只显示，不响铃。'),
    'x':dict(label='X 原文（手动缓存）',url='https://x.com/thsottiaux',hosts=('x.com',),
             coverage='独立保存的 X 原文缓存，未接通 X 自动读取，不影响公开来源。'),
}

def public_source_url(source_id,value,origin=False):
    """Only known source HTTPS hosts; no userinfo, alternate ports or shortlinks."""
    if not isinstance(value,str) or any(c.isspace() or ord(c)<32 for c in value) or '\\' in value:return None
    if origin:
        return value if source_id=='codex_resets' and re.fullmatch(r'https://x\.com/thsottiaux/status/[1-9][0-9]{4,29}',value) else None
    policy=PUBLIC_SOURCE_POLICIES.get(source_id)
    if policy is None:return None
    try:
        url=urlsplit(value)
        if url.scheme!='https' or url.hostname not in policy['hosts'] or url.username is not None or url.password is not None or url.port not in (None,443):return None
    except ValueError:return None
    if source_id=='x' and not re.fullmatch(r'https://x\.com/thsottiaux(?:/status/[1-9][0-9]{4,29})?/?',value):return None
    if source_id=='codex_changelog':
        path=unquote(url.path)
        if any(part in ('.','..') for part in path.split('/')):return None
        base='/docs/changelog' if url.hostname=='learn.chatgpt.com' else '/codex/changelog'
        if path!=base and not path.startswith(base+'/'):return None
    return value

def public_source_snapshots(snapshot):
    if not isinstance(snapshot,dict) or snapshot.get('source')!='public_announcements':return []
    sources=snapshot.get('sources')
    if not isinstance(sources,list):return []
    seen=set();result=[]
    for source in sources:
        if not isinstance(source,dict) or not isinstance(source.get('id'),str) or source['id'] in seen:continue
        seen.add(source['id']);result.append(source)
    return result

def public_announcement_view(snapshot,error=False,now=None):
    sources=public_source_snapshots(snapshot)
    public=[s for s in sources if s.get('id') in PUBLIC_SOURCE_POLICIES and s['id']!='x']
    active=[s for s in public if s.get('state')=='ok' and not s.get('stale')]
    data=snapshot if isinstance(snapshot,dict) else {}
    value='等待读取';phase='loading';note='免费公开来源';selected=None;item=None
    choices=[]
    for source in active:
        latest=latest_x_item(source)
        if latest:choices.append(dict(latest,_source=source))
    reset_source=next((s for s in public if s['id']=='codex_resets'),None)
    reset_item=latest_x_item(reset_source) if reset_source else None
    if data.get('state')=='disabled':value='已暂停';phase='disabled';note='公开公告自动读取已暂停'
    elif reset_item:
        item=reset_item;selected=reset_source
        if reset_source in active:
            phase='ok';value={'reset':'已公布重置','upcoming':'未来安排','uncertain':'尚未确认'}.get(item.get('kind'),'最新重置')
            note=str(item.get('summary') or item.get('text') or '查看原文与来源')
        else:value='缓存重置';phase='cached';note='重置来源待更新，保留旧值'
    elif choices:
        item=latest_x_item({'items':choices});selected=item['_source'];phase='ok'
        value='官方更新' if selected['id']=='codex_changelog' else {'reset':'已公布重置','upcoming':'未来安排','uncertain':'尚未确认','update':'功能更新'}.get(item.get('kind'),'最新公告')
        note=str(item.get('summary') or item.get('text') or '查看原文与来源')
    elif active:value='暂无公告';phase='ok';note='来源正常，尚无可显示条目';selected=active[0]
    else:
        cached=[dict(latest_x_item(s),_source=s) for s in public if latest_x_item(s)]
        if cached:item=latest_x_item({'items':cached});selected=item['_source'];value='缓存公告';phase='cached';note='读取未成功，保留上次记录'
        elif any(s.get('state')=='error' for s in public):value='暂不可用';phase='unavailable';note='请查看各来源状态'
    if active and len(public)>1 and phase!='cached':note=f'{len(active)} 个来源正常，{len(public)-len(active)} 个待更新'
    policy=PUBLIC_SOURCE_POLICIES.get((selected or {}).get('id'),PUBLIC_SOURCE_POLICIES['codex_resets'])
    details=[]
    for source in sources:
        meta=PUBLIC_SOURCE_POLICIES.get(source['id'],{})
        label=meta.get('label') or str(source.get('label') or source['id'])
        state='缓存已过期' if source.get('stale') else {'ok':'正常','error':'不可用','disabled':'已暂停','unconfigured':'未接通'}.get(source.get('state'),'等待读取')
        details.append(label+'：'+state)
    description='公开公告；'+value+'；'+note+'\n'+'\n'.join(details)
    if item:description+='\n'+str(item.get('text') or item.get('summary') or '')
    description+='\n重置公告不代表本机账户额度已到账；实际余额请查看额度页。'
    return dict(title='公告',phase=phase,eyebrow=policy['label'] if selected else '公开公告',value=value,unit='',parts=[(value,'')],display=value,note=note,
                description=description,next_change=None,source_url=policy['url'],source_name=policy['label'])

def latest_x_item(snapshot):
    items=(snapshot or {}).get('items')
    if not isinstance(items,list):return None
    def key(item):
        try:stamp=float(item.get('published'))
        except (ValueError,TypeError,OverflowError):stamp=-math.inf
        if not math.isfinite(stamp):stamp=-math.inf
        ident=str(item.get('id') or '')
        return stamp,int(ident) if ident.isdigit() else 0
    return max((item for item in items if isinstance(item,dict)),key=key,default=None)

def x_announcement_view(snapshot,error=False,now=None):
    """Compact X state; cached third-party reset estimates are never X posts."""
    data=snapshot if isinstance(snapshot,dict) and snapshot.get('source')=='x' else {}
    state=data.get('state','unconfigured');item=latest_x_item(data)
    value={'unconfigured':'未接通','disabled':'已暂停','error':'读取失败','ok':'暂无公告'}.get(state,'待确认')
    note='免费读取尚未接通' if state=='unconfigured' else 'X @thsottiaux'
    if state=='ok' and item:
        value={'reset':'已公布重置','upcoming':'未来安排','uncertain':'尚未确认','update':'功能更新','other':'最新推文'}.get(item.get('kind'),'最新推文')
        note=str(item.get('summary') or item.get('text') or '点击查看原文')
    if data.get('stale'):note='缓存公告，尚未刷新'
    message='免费自动读取尚未接通；可在 X 官方页面登录查看。' if state=='unconfigured' else str(data.get('message') or '')
    description='X @thsottiaux；'+value+'；'+note+'\n'+message
    description+='\nX 公告不代表本机账户额度已到账；实际余额请查看额度页。'
    if item:description+='\n'+str(item.get('text') or item.get('summary') or '')
    return dict(title='X 公告',phase='unavailable' if state in ('unconfigured','error') else state,
                eyebrow='X @thsottiaux',value=value,unit='',parts=[(value,'')],display=value,note=note,
                description=description,next_change=None,source_url='https://x.com/thsottiaux',source_name='X @thsottiaux')

def reset_view(snapshot,error=False,now=None):
    now=time.time() if now is None else now
    details=error if isinstance(error,dict) else {}
    item=pending_reset(snapshot);stamp=epoch((item or {}).get('scheduled'))
    title='备用重置' if (item or {}).get('reset_type')=='banked' else '额外重置'
    phase='loading';eyebrow=title;value='查询中';unit='';minutes=None;note='正在连接公告';next_change=None
    if snapshot is None:
        if error:phase='unavailable';value='暂不可用';note='稍后重试'
    elif not item:phase='empty';value='暂无安排';note='有新公告会提醒'
    elif stamp is None:phase='undated';eyebrow='已有重置安排';value='时间待定';note='等待公布具体时间'
    elif stamp<=now:phase='pending';eyebrow='预计时间已过';value='待确认';note='等待公告确认'
    else:
        phase='scheduled';eyebrow='预计还有';remaining=stamp-now;note='最晚 '+local_time(stamp)
        total_minutes=math.ceil(remaining/60)
        if total_minutes>=60:
            hours,minute=divmod(total_minutes,60);unit='小时'
            value=str(hours) if hours<=9999 else '9999+'
            if hours<=9999:minutes=f'{minute:02d}'
        else:
            unit='分钟';value='<1' if remaining<60 else str(total_minutes)
        next_change=min(remaining,remaining-(total_minutes-1)*60)
        if remaining==60:next_change=.001  # The next visible value is “<1”.
    if locally_reset(snapshot):
        phase='local_reset';eyebrow='本机额度';value='已重置';unit='';minutes=None;note='公告仍待确认';next_change=None
    if error and snapshot is not None and details.get('code')!='cache_write':
        eyebrow='上次安排 · 预计' if phase=='scheduled' else '上次公告记录'
    if details:
        note={'timeout':'连接超时 · 保留旧值','certificate':'证书验证失败','cache_write':'最新公告 · 缓存未保存','schema':'公告格式变化','network':'网络连接失败 · 保留旧值','runtime_file':'联网组件缺失 · 请更新'}.get(details.get('code'),'公告服务暂不可用')
    parts=[(value,unit)]+([(minutes,'分钟')] if minutes is not None else [])
    main=' '.join(number+(' '+label if label else '') for number,label in parts)
    description=title+'；'+eyebrow+' '+main+'；'+schedule_text(snapshot,now)
    description+='\n北京时间 · Codex Resets（第三方）；预计安排不代表账户额度已到账。'
    if item and item.get('text'):description+='\n'+str(item['text'])
    if error:description+='\n'+details['message'] if details.get('message') else '\n更新失败，保留上次记录。' if snapshot is not None else '\n公告暂不可用，请稍后重试。'
    return dict(title=title,phase=phase,eyebrow=eyebrow,value=value,unit=unit,parts=parts,display=main,note=note,
                description=description,next_change=next_change)
