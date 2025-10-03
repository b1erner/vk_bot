import os
import sqlite3
import threading
from typing import List, Tuple

class DB:
    def __init__(self, path: str):
        if not os.path.isabs(path):
            path = os.path.join("/data", path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self.lock = threading.RLock()
        need_init = not os.path.exists(self.path)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        if need_init:
            self._init_db()

    def _init_db(self):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_settings (
                chat_id INTEGER PRIMARY KEY,
                silence INTEGER DEFAULT 0
            )
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS muted_users (
                chat_id INTEGER,
                user_id INTEGER,
                until_ts INTEGER DEFAULT 0,
                PRIMARY KEY(chat_id, user_id)
            )
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY,
                reason TEXT
            )
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS known_chats (
                chat_id INTEGER PRIMARY KEY
            )
            """)
            self.conn.commit()

    def register_chat(self, chat_id: int):
        with self.lock:
            self.conn.execute("INSERT OR IGNORE INTO known_chats(chat_id) VALUES(?)", (chat_id,))
            self.conn.commit()

    def list_chats(self) -> List[int]:
        with self.lock:
            cur = self.conn.execute("SELECT chat_id FROM known_chats")
            return [row[0] for row in cur.fetchall()]

    def set_silence(self, chat_id: int, enabled: bool):
        with self.lock:
            self.conn.execute("""
                INSERT INTO chat_settings(chat_id, silence)
                VALUES (?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET silence=excluded.silence
            """, (chat_id, 1 if enabled else 0))
            self.conn.commit()

    def get_silence(self, chat_id: int) -> bool:
        with self.lock:
            cur = self.conn.execute("SELECT silence FROM chat_settings WHERE chat_id = ?", (chat_id,))
            row = cur.fetchone()
            return bool(row[0]) if row else False

    # muted users
    def set_muted(self, chat_id: int, user_id: int, until_ts: int = 0):
        with self.lock:
            self.conn.execute("""
                INSERT INTO muted_users(chat_id, user_id, until_ts)
                VALUES (?, ?, ?)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET until_ts=excluded.until_ts
            """, (chat_id, user_id, until_ts))
            self.conn.commit()

    def unset_muted(self, chat_id: int, user_id: int):
        with self.lock:
            self.conn.execute("DELETE FROM muted_users WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
            self.conn.commit()

    def get_mute_until(self, chat_id: int, user_id: int) -> int:
        with self.lock:
            cur = self.conn.execute("SELECT until_ts FROM muted_users WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def is_muted(self, chat_id: int, user_id: int) -> bool:
        with self.lock:
            cur = self.conn.execute("SELECT until_ts FROM muted_users WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
            row = cur.fetchone()
            if not row:
                return False
            until = int(row[0])
            if until == 0:
                return True
            import time
            return time.time() < until

    def list_expired_mutes(self) -> List[Tuple[int,int]]:
        import time
        now = int(time.time())
        with self.lock:
            cur = self.conn.execute("SELECT chat_id, user_id FROM muted_users WHERE until_ts > 0 AND until_ts < ?", (now,))
            return [(row[0], row[1]) for row in cur.fetchall()]

    # banned users (global)
    def add_banned(self, user_id: int, reason: str = ''):
        with self.lock:
            self.conn.execute("INSERT OR REPLACE INTO banned_users(user_id, reason) VALUES(?, ?)", (user_id, reason))
            self.conn.commit()

    def is_banned(self, user_id: int) -> bool:
        with self.lock:
            cur = self.conn.execute("SELECT user_id FROM banned_users WHERE user_id = ?", (user_id,))
            return True if cur.fetchone() else False
