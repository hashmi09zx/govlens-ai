import sqlite3
from typing import Optional
from langgraph.checkpoint.sqlite import SqliteSaver

# Singleton checkpointer instance
_checkpointer: Optional[SqliteSaver] = None


def get_checkpointer(db_path: str = "checkpoints.db") -> SqliteSaver:
    global _checkpointer
    if _checkpointer is None:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        _checkpointer = SqliteSaver(conn)
    return _checkpointer
