import unittest,json,struct
import msgspec
from codex_live_status import DECODER,Frames,LifecycleProjection,LiveStatusReader,compaction_state
from enhanced_core import ActivityReducer

SID='11111111-1111-4111-8111-111111111111'
OTHER='22222222-2222-4222-8222-222222222222'

def turn(compact=False,completed=False,status='inProgress'):
    return dict(turnId='turn-one',status=status,items=[dict(type='reasoning',text='PRIVATE HIDDEN CANARY'),dict(type='contextCompaction',id='compact-one',completed=completed)] if compact else [])

def snapshot(canonical=False,compact=False):
    t=turn(compact)
    state=dict(turns=[] if canonical else [t],threadRuntimeStatus=dict(type='active',activeFlags=[]),title='PRIVATE TITLE',cwd='PRIVATE PATH')
    if canonical:state['turnHistory']=dict(kind='canonical',history=dict(entitiesByKey={'turn:one':t},islands=[dict(entries=[dict(value='turn:one')])]))
    return dict(type='broadcast',method='thread-stream-state-changed',version=11,params=dict(conversationId=SID,hostId='local',change=dict(type='snapshot',revision=1,conversationState=state)))

def patches(path,value,base=1,revision=2,op='replace'):
    return dict(type='broadcast',method='thread-stream-state-changed',version=11,params=dict(conversationId=SID,hostId='local',change=dict(type='patches',baseRevision=base,revision=revision,patches=[dict(op=op,path=path,value=value)])))

def decode(value):return DECODER.decode(msgspec.json.encode(value))

class ProjectionTests(unittest.TestCase):
    def setUp(self):self.events=[];self.p=LifecycleProjection(lambda *args:self.events.append(args))
    def accept(self,value):return self.p.accept(decode(value),{SID})
    def test_canonical_and_legacy_compaction_start_finish_without_private_content(self):
        for canonical in (False,True):
            self.setUp();self.accept(snapshot(canonical,True))
            self.assertEqual(self.events,[(SID,True,'turn-one')])
            self.assertNotIn('PRIVATE',json.dumps(self.p.states))
            root=['turnHistory','history','entitiesByKey','turn:one'] if canonical else ['turns',0]
            self.accept(patches(root+['items',1,'completed'],True))
            self.assertEqual(self.events[-1],(SID,False,'turn-one'))
            self.accept(patches(root+['items',1,'completed'],True,2,3));self.assertEqual(len(self.events),2)
    def test_only_explicit_incomplete_item_in_active_turn_is_ongoing(self):
        for status,completed,expected in [('inProgress',False,True),('inProgress',True,False),('inProgress',None,False),('completed',False,False),('failed',False,False)]:
            state=dict(turns=[turn(True,completed,status)])
            self.assertEqual(compaction_state(state)[0],expected)
    def test_text_and_hidden_reasoning_patches_do_not_emit_or_get_retained(self):
        self.accept(snapshot())
        self.accept(patches(['turns',0,'items'],[dict(type='reasoning',text='PRIVATE NEW CANARY'),dict(type='agentMessage',text='正在压缩上下文')]))
        self.assertEqual(self.events,[]);self.assertNotIn('PRIVATE',json.dumps(self.p.states))
        self.accept(patches(['turns',0,'items',0,'text'],'PRIVATE OTHER',2,3));self.assertEqual(self.events,[])
        self.assertNotIn('PRIVATE',json.dumps(self.p.states))
    def test_adding_compaction_and_then_finishing_turn_clears_phase(self):
        self.accept(snapshot())
        self.accept(patches(['turns',0,'items',0],dict(type='contextCompaction',id='c',completed=False),op='add'))
        self.assertEqual(self.events[-1],(SID,True,'turn-one'))
        self.accept(patches(['turns',0,'status'],'completed',2,3));self.assertEqual(self.events[-1],(SID,False,'turn-one'))
    def test_untracked_remote_and_incompatible_streams_are_ignored(self):
        for field,value in [('conversationId',OTHER),('hostId','ssh-other')]:
            m=snapshot(compact=True);m['params'][field]=value;self.accept(m)
        m=snapshot(compact=True);m['version']=10;self.accept(m)
        self.assertEqual(self.events,[]);self.assertEqual(self.p.states,{})
    def test_revision_gap_cannot_apply_completion_to_wrong_snapshot(self):
        self.accept(snapshot(compact=True))
        self.accept(patches(['turns',0,'items',1,'completed'],True,base=20,revision=21))
        self.assertEqual(self.events,[(SID,True,'turn-one')])
        m=snapshot(compact=False);m['params']['change']['revision']=22;self.accept(m)
        self.assertEqual(self.events[-1],(SID,False,'turn-one'))
    def test_disconnect_clears_only_its_tracked_compaction(self):
        self.accept(snapshot(compact=True));self.p.forget(SID)
        self.assertEqual(self.events,[(SID,True,'turn-one'),(SID,False,'turn-one')]);self.assertEqual(self.p.states,{})
    def test_targets_are_valid_unique_bounded_ids(self):
        import threading
        r=LiveStatusReader(threading.Event(),lambda *x:None)
        r.set_targets([SID,SID,'bad; codex --exec',OTHER]+[f'00000000-0000-4000-8000-{i:012d}' for i in range(10)])
        self.assertEqual(len(r.targets()),4);self.assertEqual(r.targets()[:2],(SID,OTHER))

class FrameTests(unittest.TestCase):
    def test_fragmented_and_adjacent_frames_are_reassembled_once(self):
        a=b'{"one":1}';b=b'{"two":2}';wire=struct.pack('<I',len(a))+a+struct.pack('<I',len(b))+b
        parser=Frames();result=[]
        for byte in wire:result.extend(parser.feed(bytes([byte])))
        self.assertEqual(result,[a,b]);self.assertEqual(parser.buffer,bytearray())
    def test_invalid_or_unbounded_frame_fails_without_allocation(self):
        for size in (0,Frames.MAX_BYTES+1):
            with self.assertRaises(ValueError):list(Frames().feed(struct.pack('<I',size)))
    def test_large_initial_snapshot_is_released_while_idle(self):
        import threading,tracemalloc
        initial=dict(type='response',method='initialize',result=dict(clientId='observer'))
        state=snapshot(compact=True);state['params']['change']['conversationState']['ignoredText']='X'*(8*1024*1024)
        def frame(value):
            raw=msgspec.json.encode(value);return struct.pack('<I',len(raw))+raw
        wire=frame(initial)+frame(state);idle_allocations=[]
        class Stop(threading.Event):
            def wait(self,timeout=None):
                idle_allocations.append(tracemalloc.get_traced_memory()[0]);self.set();return True
        class Pipe:
            offset=0
            def write(self,data):return len(data)
            def read(self,size):
                data=wire[self.offset:self.offset+size];self.offset+=len(data);return data
        stop=Stop();reader=LiveStatusReader(stop,lambda *x:None);reader.set_targets([SID]);pipe=Pipe()
        tracemalloc.start()
        try:reader._listen(pipe,lambda:len(wire)-pipe.offset)
        finally:tracemalloc.stop()
        self.assertTrue(idle_allocations);self.assertLess(idle_allocations[-1],2*1024*1024)

class ReducerCompactionTests(unittest.TestCase):
    def setUp(self):
        self.r=ActivityReducer();self.r.apply(SID,dict(type='event_msg',payload=dict(type='task_started',turn_id='turn-one')))
    def test_compaction_overrides_detail_until_real_end_then_restores_latest_operation(self):
        self.r.apply(SID,dict(type='response_item',payload=dict(type='function_call',name='exec_command',call_id='call')))
        start=self.r.set_compacting(SID,True,'turn-one')[-1]
        self.assertEqual(start['display'],'正在压缩上下文');self.assertEqual(start['activity'],'compact');self.assertEqual(start['state'],'working')
        self.assertEqual(self.r.set_compacting(SID,True,'turn-one'),[])
        event=self.r.apply(SID,dict(type='response_item',payload=dict(type='function_call_output',call_id='call')))[-1]
        self.assertEqual(event['display'],'正在压缩上下文')
        end=self.r.apply(SID,dict(type='compacted',payload=dict(message='PRIVATE SUMMARY')))[-1]
        self.assertFalse(end['compacting']);self.assertEqual(end['display'],'运行了命令')
        self.assertEqual(self.r.set_compacting(SID,False,'turn-one'),[])
    def test_saved_compaction_alone_never_becomes_a_start_or_completion_notification(self):
        self.assertEqual(self.r.apply(SID,dict(type='compacted',payload={})),[])
        self.assertEqual(self.r.set_compacting(SID,True,'old-turn'),[])
        self.r.set_compacting(SID,True,'turn-one')
        self.r.apply(OTHER,dict(type='event_msg',payload=dict(type='task_started',turn_id='other-turn')))
        self.assertFalse(self.r.sessions[OTHER].compacting)
        event=self.r.apply(SID,dict(type='event_msg',payload=dict(type='turn_aborted')))[-1]
        self.assertFalse(event['compacting']);self.assertEqual(event['state'],'interrupted')
    def test_subagent_not_promoted_to_a_user_conversation(self):
        self.r.apply('agent',dict(type='session_meta',payload=dict(source=dict(subagent='parent'))))
        self.assertEqual(self.r.set_compacting('agent',True),[])
    def test_manual_compaction_of_finished_conversation_does_not_notify_new_completion(self):
        self.r.apply(SID,dict(type='event_msg',payload=dict(type='task_complete')))
        event=self.r.set_compacting(SID,True,'manual-turn')[-1]
        self.assertEqual(event['state'],'working');self.assertEqual(event['active'],1)
        events=self.r.set_compacting(SID,False,'manual-turn')
        self.assertEqual([e['kind'] for e in events],['status']);self.assertEqual(events[0]['active'],0)
    def test_queued_user_message_does_not_hide_an_unfinished_compaction(self):
        self.r.set_compacting(SID,True,'turn-one')
        event=self.r.apply(SID,dict(type='event_msg',payload=dict(type='user_message',message='queued')))[-1]
        self.assertEqual(event['display'],'正在压缩上下文')
        event=self.r.apply(SID,dict(type='event_msg',payload=dict(type='task_started',turn_id='turn-two')))[-1]
        self.assertFalse(event['compacting'])

if __name__=='__main__':unittest.main()
