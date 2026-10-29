import os,socket,struct,sys,tempfile,threading,time,unittest,json
from pathlib import Path
from unittest.mock import patch
import msgspec
import codex_live_status as live

SID='11111111-1111-4111-8111-111111111111'

def frame(value):raw=msgspec.json.encode(value);return struct.pack('<I',len(raw))+raw

def read_frame(conn):
    data=b''
    while len(data)<4:data+=conn.recv(4-len(data))
    size=struct.unpack('<I',data)[0];data=b''
    while len(data)<size:data+=conn.recv(size-len(data))
    return json.loads(data)

def snapshot(pad=0):
    turn=dict(turnId='turn-one',status='inProgress',items=[dict(type='contextCompaction',id='c',completed=False)])
    state=dict(turns=[turn],threadRuntimeStatus=dict(type='active',activeFlags=[]),ignored='X'*pad)
    return dict(type='broadcast',method='thread-stream-state-changed',version=11,params=dict(conversationId=SID,hostId='local',change=dict(type='snapshot',revision=1,conversationState=state)))

@unittest.skipUnless(sys.platform=='darwin','macOS unix socket transport')
class UnixTransportTests(unittest.TestCase):
    def setUp(self):
        self.root=tempfile.mkdtemp();self.path=os.path.join(self.root,'ipc.sock')
    def test_explicit_profile_never_falls_back_to_default_or_legacy(self):
        expected=Path(self.root).resolve()/'ipc/ipc.sock'
        for values in ({'BAILONG_CODEX_HOME':self.root,'CODEX_HOME':''},
                       {'BAILONG_CODEX_HOME':'','CODEX_HOME':self.root},
                       {'BAILONG_CODEX_HOME':self.root,'CODEX_HOME':'/different-profile'}):
            with self.subTest(values=values),patch.dict(os.environ,values),\
                    patch('codex_connection.data_home',return_value=Path(self.root).resolve()),\
                    patch('pathlib.Path.home',side_effect=AssertionError('default home must not be consulted')),\
                    patch('tempfile.gettempdir',side_effect=AssertionError('legacy IPC must not be consulted')):
                self.assertEqual(live.unix_sockets(),[expected])
    def test_default_profile_retains_legacy_discovery(self):
        with patch.dict(os.environ,{'BAILONG_CODEX_HOME':'','CODEX_HOME':''}),\
                patch('codex_connection.data_home',return_value=Path(self.root).resolve()):
            paths=live.unix_sockets()
        self.assertEqual(paths[0],Path(self.root).resolve()/'ipc/ipc.sock')
        self.assertEqual(paths[-1].name,f'ipc-{os.getuid()}.sock')
        self.assertIn((Path.home()/'.codex').resolve()/'ipc/ipc.sock',paths)
    def test_non_socket_missing_and_stale_paths_are_rejected(self):
        plain=os.path.join(self.root,'plain');Path(plain).write_text('x')
        stale=socket.socket(socket.AF_UNIX);stale.bind(os.path.join(self.root,'stale'));stale.close()
        with self.assertRaises(OSError):live.connect_unix([plain,os.path.join(self.root,'missing'),os.path.join(self.root,'stale')])
    def test_follow_large_snapshot_and_disconnect(self):
        server=socket.socket(socket.AF_UNIX);server.bind(self.path);server.listen(1);seen=[]
        def router():
            conn,_=server.accept()
            with conn:
                init=read_frame(conn);seen.append(init)
                conn.sendall(frame(dict(type='response',requestId=init['requestId'],resultType='success',method='initialize',result=dict(clientId='cid'))))
                seen.append(read_frame(conn));conn.sendall(frame(snapshot(4*1024*1024)));time.sleep(.3)
        threading.Thread(target=router,daemon=True).start()
        stop=threading.Event();events=[];reader=live.LiveStatusReader(stop,lambda *v:events.append(v));reader.set_targets([SID])
        with patch('codex_live_status.unix_sockets',return_value=[os.path.join(self.root,'missing'),self.path]):
            reader.start();deadline=time.monotonic()+5
            while time.monotonic()<deadline and reader.health_snapshot()['code']!='ipc_disconnected':time.sleep(.02)
            stop.set();reader.join(3);server.close()
        self.assertEqual(seen[0]['params'],dict(clientType='bailong-desktop-pet'))
        self.assertEqual((seen[1]['method'],seen[1]['params']['following'],seen[1]['sourceClientId']),('thread-stream-following-changed',True,'cid'))
        self.assertEqual(events,[(SID,True,'turn-one'),(SID,False,'turn-one')])
        self.assertEqual(reader.health_snapshot()['code'],'ipc_disconnected');self.assertFalse(reader.connected)

if __name__=='__main__':unittest.main()
