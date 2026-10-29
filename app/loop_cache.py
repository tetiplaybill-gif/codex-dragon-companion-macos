"""Bounded, process-local, lossless decoded idle loops; never caches partial clips."""
import threading
from collections import OrderedDict


class DecodedLoopCache:
    def __init__(self,limit=24*1024*1024):
        self.limit=limit;self.entry_limit=limit//2;self.entries=OrderedDict();self.skipped=OrderedDict()
        self.bytes=0;self.hits=0;self.lock=threading.Lock()
    def get(self,key):
        with self.lock:
            value=self.entries.get(key)
            if value is None:return None
            self.entries.move_to_end(key);self.hits+=1;return value[0]
    def begin(self,key,reserve=None,cancel=lambda:False):
        with self.lock:
            if cancel():return False
            if key in self.skipped:return False
            # Reserve one entry's build space. Stored + in-progress compressed
            # bytes stay inside the same budget, instead of doubling it.
            reserve=self.entry_limit if reserve is None else min(self.limit,max(0,reserve))
            while self.entries and self.bytes>self.limit-reserve:
                _,(_,size)=self.entries.popitem(last=False);self.bytes-=size
            return True
    def skip(self,key):
        with self.lock:
            self.skipped[key]=True
            while len(self.skipped)>16:self.skipped.popitem(last=False)
    def put(self,key,frames,size,entry_limit=None,cancel=lambda:False):
        entry_limit=self.entry_limit if entry_limit is None else min(self.limit,entry_limit)
        if size>entry_limit:return
        with self.lock:
            if cancel():return
            old=self.entries.pop(key,None)
            if old:self.bytes-=old[1]
            while self.entries and self.bytes+size>self.limit:
                _,(_,cost)=self.entries.popitem(last=False);self.bytes-=cost
            self.entries[key]=(tuple(frames),size);self.bytes+=size
    def stats(self):
        with self.lock:return dict(bytes=self.bytes,entries=len(self.entries),hits=self.hits,limit=self.limit)
