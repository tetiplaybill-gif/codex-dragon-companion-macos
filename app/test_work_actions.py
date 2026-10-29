"""Real event-to-animation semantics, queue lifetimes and import compatibility."""
import unittest
from status_reactions import StatusReactions,classify
from enhanced_core import ActivityReducer
from desktop_services import all_items

WORK={'work01','work02','work03','work04','work05'}
def event(**kw):return dict(dict(state='working',session='a',turn='1',activity='execute',active=1),**kw)

class WorkActionTests(unittest.TestCase):
    def scheduler(self):return StatusReactions(0,available=WORK)
    def test_operations_match_the_work_and_only_real_completion_celebrates(self):
        for activity,action in [('execute','work02'),('edit','work03'),('create','work03'),('compact','work03'),('research','work04'),('read','work04'),('verify','work05'),('retry','work05')]:
            self.assertEqual(classify(event(activity=activity),WORK).action_id,action)
        self.assertEqual(classify(event(state='thinking'),WORK).action_id,'work04')
        self.assertEqual(classify(event(state='responding'),WORK).action_id,'work03')
        self.assertIsNone(classify(event(state='waiting'),WORK))
        self.assertEqual(classify(event(activity='commentary',text='测试失败，继续检查'),WORK).action_id,'work05')
        self.assertNotEqual(classify(event(text='已经完成一个文件'),WORK).kind,'complete')
    def test_real_turn_greets_once_at_boundary_not_for_every_status(self):
        s=self.scheduler();s.observe(event(turn_started=True),0)
        for t in range(1,8):s.observe(event(),t)
        self.assertIsNone(s.poll(8,boundary=False))
        self.assertEqual(s.poll(8,boundary=True).action_id,'work01')
        s.observe(event(turn_started=True),9)
        self.assertEqual(s.poll(26,boundary=True).action_id,'work02')
    def test_restored_working_session_never_synthesizes_a_task_arrival(self):
        s=self.scheduler();s.observe(event(),0)
        self.assertEqual(s.poll(8,boundary=True).action_id,'work02')
        self.assertFalse(s.openings)
    def test_completed_or_superseded_turn_drops_its_pending_greeting(self):
        s=self.scheduler();s.observe(event(turn_started=True),0)
        s.observe(event(turn='2',turn_started=True),1)
        self.assertEqual(list(s.openings),[('a','2')])
        s.queue_completion(dict(session='a',turn='2'),2)
        self.assertFalse(s.openings);self.assertFalse(s.busy(3))
        self.assertEqual(s.poll(8,boundary=True).kind,'complete')
        self.assertIsNone(s.poll(26,boundary=True))
    def test_one_completed_session_does_not_stop_the_other(self):
        s=self.scheduler();s.observe(event(),0);s.observe(event(session='b',activity='research'),1)
        s.queue_completion(dict(session='b',turn='1'),2)
        self.assertTrue(s.busy(3));self.assertEqual(s.poll(8,boundary=True).kind,'complete')
        self.assertEqual(s.poll(26,boundary=True).session,'a')
    def test_stale_greeting_cooldown_and_waiting_state(self):
        s=self.scheduler();s.observe(event(turn_started=True),0);s.finished(1,20)
        self.assertIsNone(s.poll(10,boundary=True))
        s.observe(event(state='waiting'),22);self.assertIsNone(s.poll(23,boundary=True));self.assertFalse(s.openings)
        s=self.scheduler();s.observe(event(turn_started=True),0);s.observe(event(),50)
        self.assertEqual(s.poll(50,boundary=True).action_id,'work02')
    def test_storm_keeps_bounded_queues_and_character_switch_uses_legacy_fallback(self):
        s=self.scheduler()
        for i in range(2000):s.observe(event(session=str(i),turn_started=True),i/1000)
        self.assertLessEqual(len(s.openings),8);self.assertLessEqual(len(s.sessions),32);self.assertLessEqual(len(s.opening_seen),128)
        s.set_actions({'22','quota'});self.assertFalse(s.openings)
        self.assertEqual(s.poll(8,boundary=True).action_id,'22')
    def test_reducer_flags_only_live_turn_starts_and_suppresses_subagents(self):
        r=ActivityReducer();data=dict(type='event_msg',timestamp='2026-10-21T12:00:00Z',payload=dict(type='task_started',turn_id='t'))
        result=r.apply('fake-session',data);self.assertTrue(result[-1]['turn_started'])
        self.assertFalse(r.apply('history-session',data,historical=True))
        r.sessions['fake-session'].source_subagent=True;self.assertFalse(r.apply('fake-session',data))
    def test_null_work_slots_enumerated_and_deduplicated(self):
        item=lambda i:dict(id=i,file=i+'.webp')
        m=dict(idle=item('idle'),variants=[item('01')],workAnimations=[item('work01'),None,item('work01'),item('work02')])
        self.assertEqual([v['id'] for v in all_items(m)],['idle','01','work01','work02'])
    def test_wrapped_real_tool_names_use_public_operation_semantics(self):
        r=ActivityReducer()
        for tool,expected in [('apply_patch','work03'),('read_file','work04'),('exec_command','work02')]:
            data=dict(type='response_item',payload=dict(type='function_call',name='functions.exec',call_id=tool,arguments='await tools.'+tool+'({})'))
            status=r.apply('fake-session',data)[-1]
            self.assertEqual(classify(status,WORK).action_id,expected)

if __name__=='__main__':unittest.main()
