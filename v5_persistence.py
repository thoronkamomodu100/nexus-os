"""
NEXUS OS v5 — Persistent SQLite Store
======================================
All state persists across sessions: tasks, knowledge, archive, evolution history, metrics.

Tables:
  - tasks: id, name, description, status, priority, result, created_at, updated_at
  - knowledge_nodes: id, title, content, tags, source, importance, created_at
  - archive_patterns: id, type, task_name, approach, success, details, timestamp
  - evolution_log: id, cycle, type, target, improvements, score_before, score_after, timestamp
  - metrics: id, metric_name, value, delta, timestamp
  - skills: id, name, description, code, tags, success_rate, created_at, updated_at
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from enum import Enum

NEXUS_V5_DB = Path.home() / ".hermes" / "nexus_v5.db"


# ─── Enums ────────────────────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Priority(int, Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


# ─── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class PersistedTask:
    id: str
    name: str
    description: str = ""
    status: str = "pending"
    priority: int = 2
    result: str = ""
    error: str = ""
    agent: str = ""
    depends_on: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: float = 0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["depends_on"] = json.dumps(d["depends_on"]) if isinstance(d["depends_on"], list) else d["depends_on"]
        return d

    @classmethod
    def from_row(cls, row: tuple) -> "PersistedTask":
        keys = ["id", "name", "description", "status", "priority", "result",
                "error", "agent", "depends_on", "created_at", "updated_at", "completed_at"]
        d = dict(zip(keys, row))
        if isinstance(d["depends_on"], str):
            d["depends_on"] = json.loads(d["depends_on"]) if d["depends_on"] else []
        return cls(**d)


@dataclass
class PersistedKnowledge:
    id: str
    title: str
    content: str
    tags: List[str] = field(default_factory=list)
    source: str = ""
    importance: float = 0.5
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["tags"] = json.dumps(d["tags"]) if isinstance(d["tags"], list) else d["tags"]
        return d

    @classmethod
    def from_row(cls, row: tuple) -> "PersistedKnowledge":
        keys = ["id", "title", "content", "tags", "source", "importance", "created_at"]
        d = dict(zip(keys, row))
        if isinstance(d["tags"], str):
            d["tags"] = json.loads(d["tags"]) if d["tags"] else []
        return cls(**d)


@dataclass
class PersistedPattern:
    id: str
    type: str  # "success" or "failure"
    task_name: str
    approach: str
    details: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: tuple) -> "PersistedPattern":
        keys = ["id", "type", "task_name", "approach", "details", "timestamp"]
        return cls(**dict(zip(keys, row)))


@dataclass
class EvolutionLog:
    id: str
    cycle: int
    type: str
    target: str
    improvements: str
    score_before: float
    score_after: float
    timestamp: float = field(default_factory=time.time)

    @property
    def delta(self) -> float:
        return self.score_after - self.score_before

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["delta"] = self.delta
        return d


@dataclass
class Metric:
    id: str
    name: str
    value: float
    delta: float = 0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─── PersistentStore ──────────────────────────────────────────────────────────

class PersistentStore:
    """
    SQLite-backed persistent storage for NEXUS OS v5.
    All state survives across sessions.
    """

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or NEXUS_V5_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT,
                status TEXT DEFAULT 'pending', priority INTEGER DEFAULT 2,
                result TEXT DEFAULT '', error TEXT DEFAULT '',
                agent TEXT DEFAULT '', depends_on TEXT DEFAULT '[]',
                created_at REAL, updated_at REAL, completed_at REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS knowledge_nodes (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT,
                tags TEXT DEFAULT '[]', source TEXT DEFAULT '',
                importance REAL DEFAULT 0.5, created_at REAL
            );
            CREATE TABLE IF NOT EXISTS archive_patterns (
                id TEXT PRIMARY KEY, type TEXT, task_name TEXT,
                approach TEXT, details TEXT DEFAULT '', timestamp REAL
            );
            CREATE TABLE IF NOT EXISTS evolution_log (
                id TEXT PRIMARY KEY, cycle INTEGER, type TEXT,
                target TEXT, improvements TEXT,
                score_before REAL, score_after REAL, timestamp REAL
            );
            CREATE TABLE IF NOT EXISTS metrics (
                id TEXT PRIMARY KEY, name TEXT, value REAL,
                delta REAL DEFAULT 0, timestamp REAL
            );
            CREATE TABLE IF NOT EXISTS skills (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT DEFAULT '',
                code TEXT DEFAULT '', tags TEXT DEFAULT '[]',
                success_rate REAL DEFAULT 0.5, created_at REAL, updated_at REAL
            );
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY, value TEXT, updated_at REAL
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
            CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at);
            CREATE INDEX IF NOT EXISTS idx_kn_importance ON knowledge_nodes(importance);
            CREATE INDEX IF NOT EXISTS idx_ev_cycle ON evolution_log(cycle);
            CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(name);
        """)
        conn.commit()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # ─── Tasks ───────────────────────────────────────────────────────────────

    def create_task(self, task: PersistedTask) -> PersistedTask:
        conn = self._get_conn()
        d = task.to_dict()
        conn.execute("""
            INSERT OR REPLACE INTO tasks
            (id, name, description, status, priority, result, error, agent,
             depends_on, created_at, updated_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (d["id"], d["name"], d["description"], d["status"], d["priority"],
              d["result"], d["error"], d["agent"], d["depends_on"],
              d["created_at"], d["updated_at"], d["completed_at"]))
        conn.commit()
        return task

    def get_task(self, task_id: str) -> Optional[PersistedTask]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return PersistedTask.from_row(row) if row else None

    def update_task(self, task_id: str, **kwargs) -> Optional[PersistedTask]:
        conn = self._get_conn()
        kwargs["updated_at"] = time.time()
        if "status" in kwargs and kwargs["status"] in ("done", "failed"):
            kwargs["completed_at"] = time.time()
        set_clause = ", ".join(f"{k} = ?" for k in kwargs)
        conn.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?",
                     tuple(kwargs.values()) + (task_id,))
        conn.commit()
        return self.get_task(task_id)

    def list_tasks(self, status: str = None, limit: int = 50) -> List[PersistedTask]:
        conn = self._get_conn()
        if status:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
                (limit,)).fetchall()
        return [PersistedTask.from_row(r) for r in rows]

    def get_pending_tasks(self) -> List[PersistedTask]:
        """Tasks that are pending and have no unmet dependencies."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM tasks WHERE status = 'pending' ORDER BY priority DESC, created_at ASC"
        ).fetchall()
        pending = [PersistedTask.from_row(r) for r in rows]

        # Filter by dependencies
        result = []
        for task in pending:
            deps = json.loads(task.depends_on) if isinstance(task.depends_on, str) else task.depends_on
            deps_met = all(
                self.get_task(d) and self.get_task(d).status in ("done",)
                for d in deps
            )
            if deps_met:
                result.append(task)
        return result

    # ─── Knowledge ───────────────────────────────────────────────────────────

    def add_knowledge(self, kn: PersistedKnowledge) -> PersistedKnowledge:
        conn = self._get_conn()
        d = kn.to_dict()
        conn.execute("""
            INSERT OR REPLACE INTO knowledge_nodes
            (id, title, content, tags, source, importance, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (d["id"], d["title"], d["content"], d["tags"], d["source"],
              d["importance"], d["created_at"]))
        conn.commit()
        return kn

    def get_knowledge(self, kn_id: str) -> Optional[PersistedKnowledge]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM knowledge_nodes WHERE id = ?",
                          (kn_id,)).fetchone()
        return PersistedKnowledge.from_row(row) if row else None

    def search_knowledge(self, query: str, limit: int = 10) -> List[PersistedKnowledge]:
        conn = self._get_conn()
        q = f"%{query}%"
        rows = conn.execute("""
            SELECT * FROM knowledge_nodes
            WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?
            ORDER BY importance DESC, created_at DESC LIMIT ?
        """, (q, q, q, limit)).fetchall()
        return [PersistedKnowledge.from_row(r) for r in rows]

    def get_all_knowledge(self, limit: int = 100) -> List[PersistedKnowledge]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM knowledge_nodes ORDER BY importance DESC, created_at DESC LIMIT ?",
            (limit,)).fetchall()
        return [PersistedKnowledge.from_row(r) for r in rows]

    # ─── Archive ─────────────────────────────────────────────────────────────

    def add_pattern(self, p: PersistedPattern) -> PersistedPattern:
        conn = self._get_conn()
        d = p.to_dict()
        conn.execute("""
            INSERT INTO archive_patterns (id, type, task_name, approach, details, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (d["id"], d["type"], d["task_name"], d["approach"], d["details"], d["timestamp"]))
        conn.commit()
        return p

    def get_patterns(self, type: str = None, task_name: str = None,
                     limit: int = 100) -> List[PersistedPattern]:
        conn = self._get_conn()
        if type and task_name:
            rows = conn.execute("""
                SELECT * FROM archive_patterns
                WHERE type = ? AND task_name = ?
                ORDER BY timestamp DESC LIMIT ?
            """, (type, task_name, limit)).fetchall()
        elif type:
            rows = conn.execute(
                "SELECT * FROM archive_patterns WHERE type = ? ORDER BY timestamp DESC LIMIT ?",
                (type, limit)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM archive_patterns ORDER BY timestamp DESC LIMIT ?",
                (limit,)).fetchall()
        return [PersistedPattern.from_row(r) for r in rows]

    def get_archive_stats(self) -> Dict[str, Any]:
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) FROM archive_patterns").fetchone()[0]
        successes = conn.execute(
            "SELECT COUNT(*) FROM archive_patterns WHERE type = 'success'").fetchone()[0]
        failures = conn.execute(
            "SELECT COUNT(*) FROM archive_patterns WHERE type = 'failure'").fetchone()[0]
        return {
            "total": total,
            "successes": successes,
            "failures": failures,
            "rate": successes / total if total > 0 else 0.0,
        }

    # ─── Evolution Log ───────────────────────────────────────────────────────

    def log_evolution(self, entry: EvolutionLog) -> EvolutionLog:
        conn = self._get_conn()
        d = entry.to_dict()
        conn.execute("""
            INSERT INTO evolution_log
            (id, cycle, type, target, improvements, score_before, score_after, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (d["id"], d["cycle"], d["type"], d["target"], d["improvements"],
              d["score_before"], d["score_after"], d["timestamp"]))
        conn.commit()
        return entry

    def get_evolution_history(self, limit: int = 50) -> List[EvolutionLog]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM evolution_log ORDER BY cycle DESC LIMIT ?", (limit,)).fetchall()
        return [EvolutionLog(**dict(zip(
            ["id", "cycle", "type", "target", "improvements",
             "score_before", "score_after", "timestamp"], r))) for r in rows]

    def get_evolution_trend(self, metric: str = "score", limit: int = 30) -> List[float]:
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT score_after FROM evolution_log
            ORDER BY cycle DESC LIMIT ?
        """, (limit,)).fetchall()
        return [r[0] for r in reversed(rows)]

    # ─── Metrics ─────────────────────────────────────────────────────────────

    def record_metric(self, metric: Metric) -> Metric:
        conn = self._get_conn()
        d = metric.to_dict()
        conn.execute("""
            INSERT INTO metrics (id, name, value, delta, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (d["id"], d["name"], d["value"], d["delta"], d["timestamp"]))
        conn.commit()
        return metric

    def get_metrics(self, name: str = None, limit: int = 100) -> List[Metric]:
        conn = self._get_conn()
        if name:
            rows = conn.execute(
                "SELECT * FROM metrics WHERE name = ? ORDER BY timestamp DESC LIMIT ?",
                (name, limit)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM metrics ORDER BY timestamp DESC LIMIT ?",
                (limit,)).fetchall()
        return [Metric(**dict(zip(["id", "name", "value", "delta", "timestamp"], r)))
                for r in rows]

    def get_latest_metric(self, name: str) -> Optional[Metric]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM metrics WHERE name = ? ORDER BY timestamp DESC LIMIT 1",
            (name,)).fetchone()
        return Metric(**dict(zip(["id", "name", "value", "delta", "timestamp"], row))) if row else None

    # ─── Meta ────────────────────────────────────────────────────────────────

    def set_meta(self, key: str, value: str):
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, time.time()))
        conn.commit()

    def get_meta(self, key: str) -> Optional[str]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def get_cycle(self) -> int:
        v = self.get_meta("evolution_cycle")
        return int(v) if v else 0

    def increment_cycle(self) -> int:
        c = self.get_cycle() + 1
        self.set_meta("evolution_cycle", str(c))
        return c

    # ─── Full State ──────────────────────────────────────────────────────────

    def get_full_state(self) -> Dict[str, Any]:
        """Get complete system state for dashboarding."""
        archive_stats = self.get_archive_stats()
        ev_history = self.get_evolution_history(limit=20)
        metrics = self.get_metrics(limit=50)
        pending = self.list_tasks(status="pending")
        running = self.list_tasks(status="running")

        ev_trend = self.get_evolution_trend()
        avg_score = sum(ev_trend) / len(ev_trend) if ev_trend else 0.0

        return {
            "cycle": self.get_cycle(),
            "archive": archive_stats,
            "evolution_trend": ev_trend[-10:] if len(ev_trend) > 10 else ev_trend,
            "avg_evolution_score": avg_score,
            "pending_tasks": len(pending),
            "running_tasks": len(running),
            "knowledge_nodes": len(self.get_all_knowledge(limit=1000)),
            "recent_metrics": [{"name": m.name, "value": m.value, "delta": m.delta}
                             for m in metrics[:10]],
        }


# ─── Singleton ────────────────────────────────────────────────────────────────
_store: Optional[PersistentStore] = None

def get_store() -> PersistentStore:
    global _store
    if _store is None:
        _store = PersistentStore()
    return _store


if __name__ == "__main__":
    # Quick test
    store = PersistentStore()
    print(f"DB: {store.db_path}")
    print(f"Cycle: {store.get_cycle()}")
    state = store.get_full_state()
    print(f"State: {json.dumps(state, indent=2, default=str)}")
    store.close()
