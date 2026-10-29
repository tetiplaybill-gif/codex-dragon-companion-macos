"""Dispatch supported Codex links off the GUI thread with a single latest intent."""
import threading,time,os,ctypes
from PySide6.QtCore import QObject,Signal,Slot
from desktop_services import codex_conversation_url

class CodexNavigation(QObject):
    error=Signal(str)
    dispatched=Signal(str)
    def __init__(self,opener,parent=None):
        super().__init__(parent);self.opener=opener;self.busy=False;self.pending=None;self.closed=False
        self.active_key=None;self.last_key=None;self.last_request=-1e9
        self.dispatched.connect(self._done)
    def open(self,session=None):
        if self.closed:return False
        key=codex_conversation_url(session) if session is not None else ''
        now=time.monotonic()
        if self.busy:
            self.pending=(key,session) if key!=self.active_key else None
            return False
        if key==self.last_key and now-self.last_request<.6:return False
        self.last_key=key;self.last_request=now;self._start(key,session);return True
    def _start(self,key,session):
        self.busy=True;self.active_key=key;self.last_key=key;self.last_request=time.monotonic()
        def run():
            error='';com_ready=False
            try:
                if os.name=='nt':com_ready=ctypes.windll.ole32.CoInitializeEx(None,2) in (0,1)
                self.opener(session)
            except OSError as exc:error=str(exc)
            except Exception:error='无法唤起 Codex，请重试'
            finally:
                if com_ready:ctypes.windll.ole32.CoUninitialize()
            try:self.dispatched.emit(error)
            except RuntimeError:pass  # Parent may have been destroyed while the OS handled its link.
        threading.Thread(target=run,name='BailongCodexNavigation',daemon=True).start()
    @Slot(str)
    def _done(self,error):
        self.busy=False;pending=self.pending;self.pending=None
        if self.closed:return
        if pending:self._start(*pending)
        elif error:self.error.emit(error)
    def close(self):self.closed=True;self.pending=None
