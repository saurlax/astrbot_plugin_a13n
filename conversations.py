import json
import sqlite3
from contextlib import closing
from pathlib import Path

from .a13n_client import AgentError


class Conversations:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "conversations.sqlite3"
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    thread_id TEXT NOT NULL
                )
                """)

    def thread(self, conversation_id: str, scope: tuple[str, ...]) -> str:
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute(
                "SELECT thread_id FROM conversations WHERE id = ? AND scope = ?",
                (conversation_id, json.dumps(scope)),
            ).fetchone()
        if row is None:
            raise AgentError(
                "Conversation unavailable. Use AstrBot's /reset to start a new chat."
            )
        return row[0]

    def save(
        self, conversation_id: str, scope: tuple[str, ...], thread_id: str
    ) -> None:
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "INSERT INTO conversations VALUES (?, ?, ?)",
                (conversation_id, json.dumps(scope), thread_id),
            )
