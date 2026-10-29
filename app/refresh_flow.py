"""Join background reads without confusing their busy signal with a result."""
import threading
import time


class RefreshRuns:
    """One running or reserved read, shared safely by UI and worker threads."""
    def __init__(self):
        self._lock = threading.Lock()
        self._serial = 0
        self._active = None

    def reserve(self):
        with self._lock:
            if self._active is not None:
                return self._active, False
            self._serial += 1
            self._active = self._serial
            return self._active, True

    @property
    def active(self):
        with self._lock:
            return self._active

    def complete(self, run):
        with self._lock:
            if self._active == run:
                self._active = None


class RefreshCoordinator:
    """UI-thread batches. Results match the actual source read, not a timer."""
    def __init__(self, finished, clock=time.monotonic, timeout=55):
        self.finished = finished
        self.clock = clock
        self.timeout = timeout
        self.batches = {}

    def active(self, scope):
        return scope in self.batches

    def begin(self, scope, sources):
        if self.active(scope):
            return False
        self.batches[scope] = dict(
            pending=dict(sources), failed=set(), deadline=self.clock()+self.timeout)
        # A missing worker is a real failed source; never leave a spinner waiting.
        for name, run in sources.items():
            if run is None:
                self.batches[scope]['pending'].pop(name, None)
                self.batches[scope]['failed'].add(name)
        self._finish_ready()
        return True

    def result(self, source, run, success):
        if run is None:
            return
        for batch in self.batches.values():
            if batch['pending'].get(source) != run:
                continue
            del batch['pending'][source]
            if not success:
                batch['failed'].add(source)
        self._finish_ready()

    def expire(self):
        now = self.clock()
        for batch in self.batches.values():
            if now >= batch['deadline']:
                batch['failed'].update(batch['pending'])
                batch['pending'].clear()
        self._finish_ready()

    def _finish_ready(self):
        ready = [(scope, sorted(batch['failed']))
                 for scope, batch in self.batches.items() if not batch['pending']]
        for scope, failed in ready:
            del self.batches[scope]
            self.finished(scope, not failed, failed)
