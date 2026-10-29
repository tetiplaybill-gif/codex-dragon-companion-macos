"""Durable completion IDs, separate from the unread UI list. No message text."""
import sqlite3
from contextlib import closing

class CompletionLedger:
    def __init__(self,path):self.path=path
    def remember(self,keys):
        try:
            with closing(sqlite3.connect(self.path,timeout=.1)) as db,db:
                db.execute('CREATE TABLE IF NOT EXISTS completed (session TEXT,turn TEXT,PRIMARY KEY(session,turn))')
                db.executemany('INSERT OR IGNORE INTO completed VALUES (?,?)',keys)
            return True
        except (OSError,sqlite3.Error):return False
    def contains(self,key):
        try:
            with closing(sqlite3.connect(self.path,timeout=.1)) as db:
                return db.execute('SELECT 1 FROM completed WHERE session=? AND turn=?',key).fetchone() is not None
        except (OSError,sqlite3.Error):return False
