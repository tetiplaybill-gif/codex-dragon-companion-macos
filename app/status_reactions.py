"""Sample only the newest public activity at safe animation boundaries.

No network, model calls, hidden reasoning, tool arguments or FIFO of old states.
Observers replace snapshots cheaply; semantic classification runs only on poll.
"""
from collections import OrderedDict,deque
from dataclasses import dataclass
import re

ACTIVE={'thinking','working','responding'}

@dataclass(frozen=True)
class Reaction:
    kind:str
    action_id:str
    session:str=''
    turn:str=''

def classify(event,available=()):
    def action(preferred,legacy):return preferred if preferred in available else legacy
    state=event.get('state','idle');activity=event.get('activity','')
    if state in ('idle','offline','complete'):return None
    if state=='interrupted':return Reaction('paused','idle2')
    # Explicit lifecycle state wins over incidental words such as "completed"
    # in commentary or a final answer. Celebration needs a completion event.
    if state=='responding':return Reaction('reply',action('work03','01'))
    if state=='thinking':return Reaction('thinking',action('work04','quota'))
    if state!='working':return None
    if activity in ('verify','retry'):return Reaction('review',action('work05','quota'))
    if activity in ('research','read'):return Reaction('review',action('work04','quota'))
    if activity=='compact':return Reaction('review',action('work03','quota'))
    if activity in ('edit','create'):return Reaction('working',action('work03','22'))
    if activity=='execute':return Reaction('working',action('work02','22'))
    text=(str(event.get('display',''))[:180]+' '+str(event.get('text',''))[:1000]).lower()
    if re.search(r'失败|报错|未通过|暂未成功|failed|error|retry',text):return Reaction('review',action('work05','quota'))
    if re.search(r'找到.{0,8}(原因|办法|问题|思路)|定位.{0,6}(原因|问题)|思路.{0,4}(明确|确定)|方案.{0,4}(确定|确认)|关键在于',text):return Reaction('insight','04')
    if re.search(r'检查|核对|验证|测试|排查|inspect|test|verif',text):return Reaction('review',action('work05','quota'))
    if re.search(r'查找|搜索|阅读|读取|分析|研究|查阅|search|read',text):return Reaction('review',action('work04','quota'))
    if re.search(r'编辑|修改|写入|整理|edit|write',text):return Reaction('working',action('work03','22'))
    return Reaction('working',action('work02','22'))

def tool_activity(name):
    name=str(name).lower()
    if any(v in name for v in ('search','browse','web__','fetch','view_image','read_file','read_mcp','list_','get_')):return 'research'
    if any(v in name for v in ('apply_patch','write_file','edit_file','update_file')):return 'edit'
    if any(v in name for v in ('exec_command','write_stdin','shell','terminal')):return 'execute'
    if any(v in name for v in ('imagegen','image_gen','generate')):return 'create'
    return 'tool'

class StatusReactions:
    def __init__(self,now,interval=18,available=()):
        self.interval=interval;self.next_sample=now+8;self.earliest=now
        self.latest=None;self.sessions=OrderedDict();self.completion=None
        self.seen=deque(maxlen=64);self.played=OrderedDict();self.last=None;self.last_at=-1e9;self.sample_count=0
        self.action_ids=set(available);self.openings=OrderedDict();self.opening_seen=deque(maxlen=128)
        self.leases=OrderedDict();self.present=None
    def confirm(self,sid,turn,active,now):
        # A live IPC lease renews lifecycle truth without pretending that text
        # changed, replaying a greeting, or refreshing another turn's snapshot.
        self.leases[str(sid)]=(str(turn),bool(active),now);self.leases.move_to_end(str(sid))
        while len(self.leases)>32:self.leases.popitem(last=False)
    def fresh(self,event,now):
        lease=self.leases.get(str(event.get('session','')))
        if event.get('state') in ACTIVE and lease and lease[0]==str(event.get('turn','')):
            if not lease[1]:return False
            if now-lease[2]<=35:return True
        return now-event['received']<=90
    def set_actions(self,available):
        self.action_ids=set(available)
        if 'work01' not in self.action_ids:self.openings.clear()
    def configure(self,interval,now=None):
        interval=max(8,min(120,float(interval)))
        if now is not None and interval!=self.interval:self.next_sample=now+interval
        self.interval=interval
    def observe(self,event,now):
        snapshot={key:event.get(key,'') for key in ('session','turn','state','activity','text','display','active')}
        snapshot['text']=str(snapshot['text'])[:1000];snapshot['received']=now
        self.latest=snapshot;sid=str(snapshot['session'])
        self.sessions[sid]=snapshot;self.sessions.move_to_end(sid)
        while len(self.sessions)>32:self.sessions.popitem(last=False)
        key=(sid,str(snapshot['turn']))
        # Only an actual new-turn event may queue a greeting; restored working
        # sessions, commentary bursts and subagent history are not new tasks.
        if event.get('turn_started') and all(key) and snapshot['state'] in ACTIVE and 'work01' in self.action_ids and key not in self.opening_seen:
            self.opening_seen.append(key)
            for old in list(self.openings):
                if old[0]==sid:self.openings.pop(old)
            self.openings[key]=dict(snapshot)
            while len(self.openings)>8:self.openings.popitem(last=False)
        if snapshot['state'] in ('complete','interrupted','offline'):
            for old in list(self.openings):
                if old[0]==sid:self.openings.pop(old)
        pending=self.completion
        if pending and snapshot['state'] in ACTIVE and sid==pending.get('session',''):
            # New activity in the completed turn's session supersedes its
            # deferred celebration. Its visual notification was already sent.
            if not snapshot['turn'] or snapshot['turn']!=pending.get('turn',''):self.completion=None
    def queue_completion(self,event,now):
        key=(str(event.get('session','')),str(event.get('turn','')))
        if key!=('','') and key in self.seen:return False
        if key!=('',''):self.seen.append(key)
        self.completion=dict(session=key[0],turn=key[1],received=now)
        self.confirm(*key,False,now)
        self.openings.pop(key,None)
        current=self.sessions.get(key[0])
        if current and (not key[1] or current['turn']==key[1]):
            done=dict(current,state='complete',active=0,received=now)
            self.sessions[key[0]]=done
            if self.latest and self.latest['session']==key[0]:self.latest=done
        return True
    def finished(self,now,gap=8):
        self.earliest=max(self.earliest,now+max(0,gap))
    def busy(self,now):
        return self.present is not False and any(self.fresh(event,now) and event['state'] in ACTIVE
            for event in self.sessions.values())
    def record(self,result,now):
        self.last=result;self.last_at=now;self.next_sample=max(self.next_sample,now+self.interval)
        key=(result.session,result.turn,result.action_id);self.played[key]=now;self.played.move_to_end(key)
        while len(self.played)>64:self.played.popitem(last=False)
        return result
    def take_completion(self,now):
        if self.completion and now-self.completion['received']>120:self.completion=None
        if not self.completion or now<self.earliest:return None
        event=self.completion;self.completion=None
        return self.record(Reaction('complete','18',event['session'],event['turn']),now)
    def take_opening(self,now):
        if self.present is False or now<self.earliest:return None
        for key,event in list(self.openings.items()):
            current=self.sessions.get(key[0],{})
            self.openings.pop(key)
            if now-event['received']<=45 and current.get('turn')==key[1] and current.get('state') in ACTIVE and self.fresh(current,now):
                return self.record(Reaction('received','work01',*key),now)
        return None
    def take_current(self,result,now):
        if result is None or now<self.earliest:return None
        key=(result.session,result.turn,result.action_id)
        repeat=self.interval if result.action_id in {'work02','work03','work04','work05'} else 60
        if now-self.played.get(key,-1e9)<repeat:return None
        self.sample_count+=1
        return self.record(result,now)
    def poll(self,now,*,boundary,allowed=True):
        if not boundary or not allowed or now<self.earliest:return None
        if self.completion and now-self.completion['received']>120:self.completion=None
        # Explicit completion is not a stream of inferred status messages. It
        # may use the next boundary, respecting the last action's quiet gap.
        if self.completion:
            if now-self.last_at<self.interval:return None
            event=self.completion;self.completion=None
            result=Reaction('complete','18',event['session'],event['turn'])
        else:
            if now<self.next_sample:return None
            self.next_sample=now+self.interval;self.sample_count+=1
            if self.present is False:return None
            for key,event in list(self.openings.items()):
                current=self.sessions.get(key[0],{})
                if now-event['received']>45 or current.get('turn')!=key[1] or current.get('state') not in ACTIVE or not self.fresh(current,now):self.openings.pop(key)
            opening=next(iter(self.openings.items()),None)
            if opening:
                key,event=opening;self.openings.pop(key)
                result=Reaction('received','work01',key[0],key[1])
                self.last=result;self.last_at=now;self.next_sample=max(self.next_sample,now+self.interval)
                return result
            event=self.latest
            if event and (event.get('state') not in ACTIVE or not self.fresh(event,now)):
                event=next((e for e in reversed(self.sessions.values()) if e['state'] in ACTIVE and self.fresh(e,now)),event)
            if not event or not self.fresh(event,now):return None
            selected=classify(event,self.action_ids)
            if selected is None:return None
            result=Reaction(selected.kind,selected.action_id,str(event.get('session','')),str(event.get('turn','')))
            key=(result.session,result.turn,result.action_id)
            # Dedicated work clips communicate an ongoing state, rather than
            # occasional decorative reactions. Legacy/custom gestures keep
            # their conservative repeat limit (e.g. quota or an insight).
            repeat=self.interval if result.action_id in {'work02','work03','work04','work05'} else 60
            if now-self.played.get(key,-1e9)<repeat:return None
        self.last=result;self.last_at=now;self.next_sample=max(self.next_sample,now+self.interval)
        key=(result.session,result.turn,result.action_id);self.played[key]=now;self.played.move_to_end(key)
        while len(self.played)>64:self.played.popitem(last=False)
        return result
