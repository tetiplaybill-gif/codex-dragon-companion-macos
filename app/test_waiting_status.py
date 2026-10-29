"""Explicit desktop waiting flags, lifecycle clearing and two-slot priority."""
import json
import unittest
from codex_live_status import LifecycleProjection,waiting_state
from conversation_roster import ConversationRoster
from enhanced_core import ActivityReducer
from test_live_compaction import SID,OTHER,decode,snapshot,patches

def waiting_snapshot(flag='waitingOnUserInput',canonical=False):
    value=snapshot(canonical)
    state=value['params']['change']['conversationState']
    state['threadRuntimeStatus']['activeFlags']=[flag] if flag else []
    return value

def event(typ,**fields):
    return dict(type='event_msg',payload=dict(type=typ,**fields))

class WaitingProjectionTests(unittest.TestCase):
    def setUp(self):
        self.events=[];self.compactions=[]
        self.p=LifecycleProjection(lambda *args:self.compactions.append(args),lambda *args:self.events.append(args))
    def accept(self,value):
        return self.p.accept(decode(value),{SID})
    def test_actual_runtime_flags_enter_waiting_and_clear_on_resume(self):
        for canonical in (False,True):
            self.setUp();self.accept(waiting_snapshot(canonical=canonical))
            self.assertEqual(self.events,[(SID,'input','turn-one')])
            self.accept(patches(['threadRuntimeStatus','activeFlags'],['waitingOnApproval']))
            self.assertEqual(self.events[-1],(SID,'approval','turn-one'))
            self.accept(patches(['threadRuntimeStatus','activeFlags'],[],2,3))
            self.assertEqual(self.events[-1],(SID,'','turn-one'))
            self.assertEqual(self.compactions,[])
            self.assertNotIn('PRIVATE',json.dumps(self.p.states))
    def test_array_item_patches_are_not_lost(self):
        self.accept(waiting_snapshot(''))
        self.accept(patches(['threadRuntimeStatus','activeFlags',0],'waitingOnApproval',op='add'))
        self.assertEqual(self.events[-1],(SID,'approval','turn-one'))
        self.accept(patches(['threadRuntimeStatus','activeFlags',0],None,2,3,op='remove'))
        self.assertEqual(self.events[-1],(SID,'','turn-one'))
    def test_no_inference_from_message_text_unknown_flags_or_inactivity(self):
        value=waiting_snapshot('unrecognizedFlag')
        state=value['params']['change']['conversationState']
        state['turns'][0]['items']=[dict(type='agentMessage',text='等待你的输入')]
        self.accept(value)
        self.assertEqual(self.events,[])
        state['threadRuntimeStatus'].update(type='idle',activeFlags=['waitingOnUserInput'])
        self.assertEqual(waiting_state(state),('','turn-one'))
    def test_terminal_turn_and_inactive_runtime_clear_waiting(self):
        for status in ('completed','failed','interrupted'):
            self.setUp();self.accept(waiting_snapshot())
            self.accept(patches(['turns',0,'status'],status))
            self.assertEqual(self.events[-1],(SID,'','turn-one'))
        self.setUp();self.accept(waiting_snapshot())
        self.accept(patches(['threadRuntimeStatus','type'],'idle'))
        self.assertEqual(self.events[-1],(SID,'','turn-one'))
    def test_resync_rotation_and_disconnect_do_not_leave_waiting_stuck(self):
        self.accept(waiting_snapshot())
        self.assertEqual(self.accept(patches(['threadRuntimeStatus','activeFlags'],[],base=6,revision=7)),'resync')
        self.assertEqual(len(self.events),1)
        self.p.forget(SID,clear=False)
        self.assertEqual(len(self.events),1)
        self.accept(waiting_snapshot(''))
        self.assertEqual(self.events[-1],(SID,'','turn-one'))
        self.accept(waiting_snapshot('waitingOnApproval'))
        self.p.forget(SID)
        self.assertEqual(self.events[-1],(SID,'','turn-one'))
        self.assertEqual(self.p.waiting,{})

class WaitingReducerTests(unittest.TestCase):
    def setUp(self):
        self.r=ActivityReducer()
        self.r.apply(SID,event('task_started',turn_id='turn-one'))
    def test_waiting_overrides_but_retains_latest_operation_for_resume(self):
        start=self.r.set_waiting(SID,'approval','turn-one')[-1]
        self.assertEqual((start['state'],start['waiting'],start['waiting_reason']),('waiting',1,'approval'))
        self.assertEqual(start['display'],'等待你的批准')
        op=dict(type='response_item',payload=dict(type='function_call',name='exec_command',call_id='call'))
        waiting=self.r.apply(SID,op)[-1]
        self.assertEqual(waiting['state'],'waiting')
        self.assertEqual(waiting['display'],'等待你的批准')
        end=self.r.set_waiting(SID,'','turn-one')[-1]
        self.assertEqual((end['state'],end['waiting']),('working',0))
        self.assertEqual(end['display'],'正在运行命令')
    def test_aggregate_wait_count_survives_another_conversation_updates(self):
        self.r.set_waiting(SID,'input','turn-one')
        other=self.r.apply(OTHER,event('task_started',turn_id='other'))[-1]
        self.assertEqual((other['state'],other['active'],other['waiting']),('thinking',2,1))
        self.r.set_waiting(OTHER,'approval','other')
        end=self.r.set_waiting(SID,'','turn-one')[-1]
        self.assertEqual((end['active'],end['waiting']),(2,1))
    def test_completion_abort_new_turn_clear_and_stale_flags_do_not_resurrect(self):
        for terminal in ('task_complete','turn_aborted','turn_cancelled'):
            self.setUp();self.r.set_waiting(SID,'input','turn-one')
            end=self.r.apply(SID,event(terminal))[-1]
            self.assertEqual(end['waiting'],0)
            self.assertEqual(self.r.set_waiting(SID,'input','turn-one'),[])
        self.setUp();self.r.set_waiting(SID,'approval','turn-one')
        new=self.r.apply(SID,event('task_started',turn_id='turn-two'))[-1]
        self.assertEqual((new['state'],new['waiting']),('thinking',0))
        self.assertEqual(self.r.set_waiting(SID,'input','turn-one'),[])
    def test_wrong_turn_child_or_unknown_reason_never_enters_waiting(self):
        self.assertEqual(self.r.set_waiting(SID,'input','old'),[])
        self.assertEqual(self.r.set_waiting(SID,'uncertain','turn-one'),[])
        self.r.apply(OTHER,dict(type='session_meta',payload=dict(source=dict(subagent='parent'))))
        self.assertEqual(self.r.set_waiting(OTHER,'input'),[])
    def test_queued_message_does_not_assume_approval_was_answered(self):
        self.r.set_waiting(SID,'approval','turn-one')
        value=self.r.apply(SID,event('user_message',message='queued'))[-1]
        self.assertEqual(value['state'],'waiting')
        self.assertEqual(value['display'],'等待你的批准')

class WaitingRosterTests(unittest.TestCase):
    def test_waiting_enters_two_slots_even_when_existing_slots_are_pinned(self):
        roster=ConversationRoster()
        for sid in ('a','b','c'):roster.observe(dict(session=sid,state='working'))
        roster.selection([])
        roster.observe(dict(session='c',state='waiting'))
        selected,extra=roster.selection([])
        self.assertEqual(selected[0]['session'],'c')
        self.assertEqual(selected[0]['text'],'等待你的操作')
        self.assertEqual((len(selected),extra),(2,1))
    def test_unread_and_waiting_take_one_slot_each_then_resume_preserves_task(self):
        roster=ConversationRoster()
        for sid,state in [('a','complete'),('b','working'),('c','waiting')]:
            roster.observe(dict(session=sid,state=state))
        chosen,extra=roster.selection([('a','done')])
        self.assertEqual([v['session'] for v in chosen],['a','c'])
        self.assertEqual(extra,1)
        roster.observe(dict(session='c',state='working'))
        chosen,_=roster.selection([])
        self.assertEqual({v['session'] for v in chosen},{'b','c'})

if __name__=='__main__':unittest.main()
