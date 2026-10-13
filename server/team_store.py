"""Kho nhóm chat team (`team.sqlite3`): nhóm, thành viên, sự kiện, bước nội bộ của việc nhóm, sổ lượt, khoá bận theo agent.

Thiết kế: docs/superpowers/specs/2026-10-13-team-chat-design.md mục 5.2. Việc cấp nhóm (hàng đợi, thứ tự, Ưu tiên) nằm ở
làn `team` của bảng `tasks` trong `kanban.sqlite3` (task_store.py), KHÔNG ở đây: CAS hàng đợi và bước nhận việc cần
cùng một giao dịch. Kho này giữ phần còn lại.

- Danh tính thành viên là `agent_key` bền do host cấp (sổ danh tính của resonance_store, `agent_register`), không phải
  slug: agent mới cùng tên không là thành viên và không nhận việc cũ.
- Bước (`team_steps`) là bước NỘI BỘ của một việc nhóm (lập kế hoạch, làm, hỗ trợ, tổng hợp, trả lời), không phải việc
  cấp nhóm. Nhận bước bằng CAS `queued -> running`, mỗi bước chạy tối đa một lần.
- Sổ lượt (`team_turns`) có một dòng cho MỖI lời gọi model: giữ chỗ trước khi dựng engine, ghi mốc gọi engine ngay
  trước lời gọi; trước mốc thì hoàn được, sau mốc thì luôn tính (kể cả lỗi, hết giờ, huỷ, restart).
- Khoá bận (`agent_busy`) đảm bảo một agent chạy tối đa một lượt nhóm cùng lúc trên cả máy (D3), có hạn để tự nhả khi
  tiến trình chết.
"""
from __future__ import annotations

import json
import secrets
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Optional

import config as cfgmod

# Trần mặc định ở chế độ Quyền giới hạn (spec 12.3, D7). Toàn quyền (T3) đọc và ghi đè theo nhóm.
DEFAULT_CAPS = {
    "task_turns": 12,          # lượt model mỗi việc
    "task_steps": 8,           # bước mỗi việc
    "help_depth": 2,           # độ sâu nhờ hỗ trợ
    "no_progress": 2,          # lượt không tiến triển liên tiếp của một bước
    "mentions": 3,             # @ mỗi tin
    "daily_turns": 100,        # lượt mỗi nhóm mỗi ngày
    "running_jobs": 1,         # việc chạy cùng lúc mỗi nhóm
    "busy_wait_s": 1800,       # chờ khoá bận trước khi báo chặn
}
TEAM_STATUS = ("active", "paused", "archived")
STEP_KINDS = ("plan", "work", "help", "synthesize", "reply")
TURN_ROLES = ("leader_reply", "member_reply", "plan", "work", "help", "synthesize")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS teams(
  team_id TEXT PRIMARY KEY, brain_id TEXT NOT NULL, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
  session_id TEXT NOT NULL, leader_key TEXT, leader_mode TEXT NOT NULL DEFAULT 'limited',
  status TEXT NOT NULL DEFAULT 'active', caps_json TEXT NOT NULL DEFAULT '{}',
  created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS teams_brain ON teams(brain_id, updated_at);
CREATE TABLE IF NOT EXISTS team_members(
  team_id TEXT NOT NULL, agent_key TEXT NOT NULL, slug_at_join TEXT NOT NULL DEFAULT '',
  role TEXT NOT NULL DEFAULT 'member', status TEXT NOT NULL DEFAULT 'active',
  managed_by_team INTEGER NOT NULL DEFAULT 0, joined_at REAL NOT NULL, left_at REAL,
  PRIMARY KEY(team_id, agent_key));
CREATE INDEX IF NOT EXISTS team_members_agent ON team_members(agent_key, status);
CREATE TABLE IF NOT EXISTS team_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, team_id TEXT NOT NULL, kind TEXT NOT NULL, by TEXT NOT NULL DEFAULT '',
  before_json TEXT NOT NULL DEFAULT '{}', after_json TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS team_events_team ON team_events(team_id, id);
CREATE TABLE IF NOT EXISTS team_steps(
  step_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, team_id TEXT NOT NULL, seq INTEGER NOT NULL, kind TEXT NOT NULL,
  agent_key TEXT NOT NULL, job_revision INTEGER NOT NULL, brief TEXT NOT NULL DEFAULT '',
  input_refs_json TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT 'queued', parent_step TEXT,
  result_msg_id INTEGER, applied INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '',
  created_at REAL NOT NULL, updated_at REAL NOT NULL, UNIQUE(task_id, seq));
CREATE TABLE IF NOT EXISTS team_turns(
  turn_id TEXT PRIMARY KEY, team_id TEXT NOT NULL, task_id TEXT, step_id TEXT, agent_key TEXT NOT NULL,
  role TEXT NOT NULL, engine TEXT NOT NULL DEFAULT '', model TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'reserved', engine_at REAL, tokens_in INTEGER, tokens_out INTEGER, cost_usd REAL,
  created_at REAL NOT NULL, settled_at REAL);
CREATE INDEX IF NOT EXISTS team_turns_team ON team_turns(team_id, created_at);
CREATE INDEX IF NOT EXISTS team_turns_task ON team_turns(task_id);
CREATE TABLE IF NOT EXISTS agent_busy(
  agent_key TEXT PRIMARY KEY, team_id TEXT NOT NULL, turn_id TEXT NOT NULL, lease_until REAL NOT NULL);
"""


class TeamError(Exception):
    """Thao tác không hợp lệ với trạng thái hiện tại của nhóm (route trả 409 hay 400)."""


def _j(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True)


class TeamStore:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else Path(cfgmod.STATE_DIR) / "team.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._conn()) as c:
            c.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.path), timeout=10, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        return c

    class _Tx:
        """BEGIN IMMEDIATE ... COMMIT; lỗi thì ROLLBACK."""

        def __init__(self, store):
            self.c = store._conn()

        def __enter__(self):
            self.c.execute("BEGIN IMMEDIATE")
            return self.c

        def __exit__(self, et, ev, tb):
            try:
                self.c.execute("ROLLBACK" if et else "COMMIT")
            finally:
                self.c.close()
            return False

    # ───────────── nhóm ─────────────

    @staticmethod
    def _team(r) -> dict:
        caps = dict(DEFAULT_CAPS)
        caps.update(json.loads(r["caps_json"] or "{}"))
        return {"team_id": r["team_id"], "brain_id": r["brain_id"], "name": r["name"], "description": r["description"],
                "session_id": r["session_id"], "leader_key": r["leader_key"], "leader_mode": r["leader_mode"],
                "status": r["status"], "caps": caps, "created_at": r["created_at"], "updated_at": r["updated_at"]}

    def _event(self, c, team_id: str, kind: str, by: str, before: Any = None, after: Any = None) -> None:
        c.execute("INSERT INTO team_events(team_id,kind,by,before_json,after_json,created_at) VALUES(?,?,?,?,?,?)",
                  (team_id, kind, by, _j(before or {}), _j(after or {}), time.time()))

    def create_team(self, brain_id: str, name: str, description: str, session_id: str, by: str = "owner") -> dict:
        name = str(name or "").strip()
        if not name:
            raise TeamError("thiếu tên nhóm")
        tid = "tm_" + secrets.token_hex(8)
        now = time.time()
        with self._Tx(self) as c:
            c.execute("INSERT INTO teams(team_id,brain_id,name,description,session_id,created_at,updated_at) "
                      "VALUES(?,?,?,?,?,?,?)", (tid, brain_id, name[:120], str(description or "")[:2000],
                                                 session_id, now, now))
            self._event(c, tid, "created", by, None, {"name": name})
        return self.get(tid)

    def get(self, team_id: str) -> Optional[dict]:
        with closing(self._conn()) as c:
            r = c.execute("SELECT * FROM teams WHERE team_id=?", (str(team_id or ""),)).fetchone()
            return self._team(r) if r else None

    def list_teams(self, brain_id: str, limit: int = 50, before: Optional[float] = None,
                   include_archived: bool = False) -> list:
        q = "SELECT * FROM teams WHERE brain_id=?"
        args: list = [brain_id]
        if not include_archived:
            q += " AND status != 'archived'"
        if before is not None:
            q += " AND updated_at < ?"
            args.append(float(before))
        q += " ORDER BY updated_at DESC LIMIT ?"
        args.append(max(1, min(int(limit), 200)))
        with closing(self._conn()) as c:
            return [self._team(r) for r in c.execute(q, args).fetchall()]

    def update(self, team_id: str, by: str = "owner", **fields) -> dict:
        allowed = {"name", "description", "status"}
        bad = set(fields) - allowed
        if bad:
            raise TeamError(f"trường không đổi được: {sorted(bad)}")
        if "status" in fields and fields["status"] not in TEAM_STATUS:
            raise TeamError("trạng thái nhóm không hợp lệ")
        if "name" in fields and not str(fields["name"] or "").strip():
            raise TeamError("thiếu tên nhóm")
        with self._Tx(self) as c:
            r = c.execute("SELECT * FROM teams WHERE team_id=?", (team_id,)).fetchone()
            if r is None:
                raise TeamError("không có nhóm này")
            before = {k: r[k] for k in fields}
            sets = ", ".join(f"{k}=?" for k in fields)
            c.execute(f"UPDATE teams SET {sets}, updated_at=? WHERE team_id=?",
                      (*[str(v) for v in fields.values()], time.time(), team_id))
            self._event(c, team_id, "updated", by, before, fields)
        return self.get(team_id)

    def touch(self, team_id: str) -> None:
        with self._Tx(self) as c:
            c.execute("UPDATE teams SET updated_at=? WHERE team_id=?", (time.time(), team_id))

    # ───────────── thành viên và trưởng nhóm ─────────────

    @staticmethod
    def _member(r) -> dict:
        return {"team_id": r["team_id"], "agent_key": r["agent_key"], "slug_at_join": r["slug_at_join"],
                "role": r["role"], "status": r["status"], "managed_by_team": bool(r["managed_by_team"]),
                "joined_at": r["joined_at"], "left_at": r["left_at"]}

    def add_member(self, team_id: str, agent_key: str, slug: str, by: str = "owner") -> dict:
        now = time.time()
        with self._Tx(self) as c:
            if c.execute("SELECT 1 FROM teams WHERE team_id=?", (team_id,)).fetchone() is None:
                raise TeamError("không có nhóm này")
            r = c.execute("SELECT * FROM team_members WHERE team_id=? AND agent_key=?", (team_id, agent_key)).fetchone()
            if r is not None and r["status"] == "active":
                return self._member(r)
            if r is None:
                c.execute("INSERT INTO team_members(team_id,agent_key,slug_at_join,role,status,joined_at) "
                          "VALUES(?,?,?,?,?,?)", (team_id, agent_key, slug, "member", "active", now))
            else:
                c.execute("UPDATE team_members SET status='active', role='member', slug_at_join=?, joined_at=?, "
                          "left_at=NULL WHERE team_id=? AND agent_key=?", (slug, now, team_id, agent_key))
            c.execute("UPDATE teams SET updated_at=? WHERE team_id=?", (now, team_id))
            self._event(c, team_id, "member_added", by, None, {"agent_key": agent_key, "slug": slug})
            return self._member(c.execute("SELECT * FROM team_members WHERE team_id=? AND agent_key=?",
                                          (team_id, agent_key)).fetchone())

    def _drop_member(self, c, team_id: str, agent_key: str, status: str, by: str, now: float) -> bool:
        r = c.execute("SELECT * FROM team_members WHERE team_id=? AND agent_key=? AND status='active'",
                      (team_id, agent_key)).fetchone()
        if r is None:
            return False
        c.execute("UPDATE team_members SET status=?, role='member', left_at=? WHERE team_id=? AND agent_key=?",
                  (status, now, team_id, agent_key))
        t = c.execute("SELECT leader_key FROM teams WHERE team_id=?", (team_id,)).fetchone()
        if t is not None and t["leader_key"] == agent_key:
            # Không âm thầm mất điều phối (spec 6.3): nhóm thành "chưa có trưởng nhóm", ghi sự kiện, giao diện báo.
            c.execute("UPDATE teams SET leader_key=NULL, leader_mode='limited', updated_at=? WHERE team_id=?",
                      (now, team_id))
            self._event(c, team_id, "leader_removed", by, {"leader_key": agent_key}, {"leader_key": None})
        self._event(c, team_id, "member_" + status, by, {"agent_key": agent_key}, None)
        return True

    def remove_member(self, team_id: str, agent_key: str, by: str = "owner") -> bool:
        with self._Tx(self) as c:
            return self._drop_member(c, team_id, agent_key, "removed", by, time.time())

    def mark_agent_gone(self, brain_id: str, agent_key: str) -> list:
        """Agent bị xoá khỏi Javis (mã nghỉ): mọi nhóm của brain đánh dấu `agent_gone`. Trả danh sách nhóm bị ảnh hưởng."""
        out = []
        now = time.time()
        with self._Tx(self) as c:
            rows = c.execute("SELECT m.team_id FROM team_members m JOIN teams t ON t.team_id=m.team_id "
                             "WHERE t.brain_id=? AND m.agent_key=? AND m.status='active'",
                             (brain_id, agent_key)).fetchall()
            for r in rows:
                if self._drop_member(c, r["team_id"], agent_key, "agent_gone", "host", now):
                    out.append(r["team_id"])
        return out

    def set_leader(self, team_id: str, agent_key: Optional[str], by: str = "owner") -> dict:
        now = time.time()
        with self._Tx(self) as c:
            t = c.execute("SELECT * FROM teams WHERE team_id=?", (team_id,)).fetchone()
            if t is None:
                raise TeamError("không có nhóm này")
            if agent_key is not None and c.execute(
                    "SELECT 1 FROM team_members WHERE team_id=? AND agent_key=? AND status='active'",
                    (team_id, agent_key)).fetchone() is None:
                raise TeamError("trưởng nhóm phải là thành viên đang hoạt động của nhóm")
            c.execute("UPDATE team_members SET role='member' WHERE team_id=? AND role='leader'", (team_id,))
            if agent_key is not None:
                c.execute("UPDATE team_members SET role='leader' WHERE team_id=? AND agent_key=?", (team_id, agent_key))
            # Đổi trưởng nhóm thì chế độ quyền về giới hạn (Toàn quyền gắn người, không gắn chức danh; spec 13.1, M11).
            c.execute("UPDATE teams SET leader_key=?, leader_mode='limited', updated_at=? WHERE team_id=?",
                      (agent_key, now, team_id))
            self._event(c, team_id, "leader_set", by, {"leader_key": t["leader_key"]}, {"leader_key": agent_key})
        return self.get(team_id)

    def members(self, team_id: str, include_removed: bool = False) -> list:
        q = "SELECT * FROM team_members WHERE team_id=?"
        if not include_removed:
            q += " AND status='active'"
        with closing(self._conn()) as c:
            return [self._member(r) for r in c.execute(q + " ORDER BY joined_at", (team_id,)).fetchall()]

    def member(self, team_id: str, agent_key: str) -> Optional[dict]:
        with closing(self._conn()) as c:
            r = c.execute("SELECT * FROM team_members WHERE team_id=? AND agent_key=?", (team_id, agent_key)).fetchone()
            return self._member(r) if r else None

    def is_active_member(self, team_id: str, agent_key: str) -> bool:
        m = self.member(team_id, agent_key)
        return bool(m and m["status"] == "active")

    def teams_of_agent(self, agent_key: str) -> list:
        with closing(self._conn()) as c:
            return [r["team_id"] for r in c.execute(
                "SELECT team_id FROM team_members WHERE agent_key=? AND status='active'", (agent_key,)).fetchall()]

    def events(self, team_id: str, limit: int = 200) -> list:
        with closing(self._conn()) as c:
            return [{"id": r["id"], "kind": r["kind"], "by": r["by"], "before": json.loads(r["before_json"]),
                     "after": json.loads(r["after_json"]), "created_at": r["created_at"]}
                    for r in c.execute("SELECT * FROM team_events WHERE team_id=? ORDER BY id DESC LIMIT ?",
                                       (team_id, int(limit))).fetchall()]

    # ───────────── bước nội bộ của việc nhóm ─────────────

    @staticmethod
    def _step(r) -> dict:
        return {"step_id": r["step_id"], "task_id": r["task_id"], "team_id": r["team_id"], "seq": r["seq"],
                "kind": r["kind"], "agent_key": r["agent_key"], "job_revision": r["job_revision"], "brief": r["brief"],
                "input_refs": json.loads(r["input_refs_json"] or "[]"), "status": r["status"],
                "parent_step": r["parent_step"], "result_msg_id": r["result_msg_id"], "applied": bool(r["applied"]),
                "note": r["note"], "created_at": r["created_at"], "updated_at": r["updated_at"]}

    def add_step(self, task_id: str, team_id: str, kind: str, agent_key: str, job_revision: int, brief: str,
                 input_refs: list, parent_step: Optional[str] = None) -> dict:
        if kind not in STEP_KINDS:
            raise TeamError("loại bước không hợp lệ")
        now = time.time()
        with self._Tx(self) as c:
            seq = int(c.execute("SELECT COALESCE(MAX(seq),0)+1 FROM team_steps WHERE task_id=?",
                                (task_id,)).fetchone()[0])
            sid = "st_" + secrets.token_hex(8)
            c.execute("INSERT INTO team_steps(step_id,task_id,team_id,seq,kind,agent_key,job_revision,brief,"
                      "input_refs_json,parent_step,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                      (sid, task_id, team_id, seq, kind, agent_key, int(job_revision), str(brief or "")[:8000],
                       _j(list(input_refs or [])), parent_step, now, now))
            return self._step(c.execute("SELECT * FROM team_steps WHERE step_id=?", (sid,)).fetchone())

    def steps(self, task_id: str) -> list:
        with closing(self._conn()) as c:
            return [self._step(r) for r in c.execute("SELECT * FROM team_steps WHERE task_id=? ORDER BY seq",
                                                     (task_id,)).fetchall()]

    def step(self, step_id: str) -> Optional[dict]:
        with closing(self._conn()) as c:
            r = c.execute("SELECT * FROM team_steps WHERE step_id=?", (step_id,)).fetchone()
            return self._step(r) if r else None

    def next_queued_step(self, task_id: str) -> Optional[dict]:
        with closing(self._conn()) as c:
            r = c.execute("SELECT * FROM team_steps WHERE task_id=? AND status='queued' ORDER BY seq LIMIT 1",
                          (task_id,)).fetchone()
            return self._step(r) if r else None

    def claim_step(self, step_id: str) -> bool:
        with self._Tx(self) as c:
            cur = c.execute("UPDATE team_steps SET status='running', updated_at=? WHERE step_id=? AND status='queued'",
                            (time.time(), step_id))
            return cur.rowcount == 1

    def finish_step(self, step_id: str, status: str, result_msg_id: Optional[int] = None, applied: bool = False,
                    note: str = "") -> None:
        with self._Tx(self) as c:
            c.execute("UPDATE team_steps SET status=?, result_msg_id=?, applied=?, note=?, updated_at=? "
                      "WHERE step_id=?", (status, result_msg_id, 1 if applied else 0, str(note or "")[:500],
                                          time.time(), step_id))

    def requeue_step(self, step_id: str) -> None:
        """Bước chưa tới mốc gọi engine (restart, khoá bận): về hàng chờ, không mất chỗ."""
        with self._Tx(self) as c:
            c.execute("UPDATE team_steps SET status='queued', updated_at=? WHERE step_id=? AND status='running'",
                      (time.time(), step_id))

    def cancel_open_steps(self, task_id: str, note: str) -> int:
        with self._Tx(self) as c:
            return c.execute("UPDATE team_steps SET status='cancelled', note=?, updated_at=? "
                             "WHERE task_id=? AND status IN ('queued','waiting')", (note, time.time(), task_id)).rowcount

    def set_step_status(self, step_id: str, status: str, note: str = "") -> None:
        with self._Tx(self) as c:
            c.execute("UPDATE team_steps SET status=?, note=?, updated_at=? WHERE step_id=?",
                      (status, note, time.time(), step_id))

    # ───────────── sổ lượt ─────────────

    def reserve_turn(self, team_id: str, task_id: Optional[str], step_id: Optional[str], agent_key: str,
                     role: str) -> str:
        if role not in TURN_ROLES:
            raise TeamError("vai lượt không hợp lệ")
        tid = "tu_" + secrets.token_hex(8)
        with self._Tx(self) as c:
            c.execute("INSERT INTO team_turns(turn_id,team_id,task_id,step_id,agent_key,role,created_at) "
                      "VALUES(?,?,?,?,?,?,?)", (tid, team_id, task_id, step_id, agent_key, role, time.time()))
        return tid

    def mark_engine(self, turn_id: str, engine: str, model: str) -> None:
        with self._Tx(self) as c:
            c.execute("UPDATE team_turns SET status='running', engine=?, model=?, engine_at=? "
                      "WHERE turn_id=? AND status='reserved'", (engine, model, time.time(), turn_id))

    def settle_turn(self, turn_id: str, status: str, tokens_in: Optional[int] = None, tokens_out: Optional[int] = None,
                    cost_usd: Optional[float] = None) -> None:
        if status not in ("ok", "error", "interrupted"):
            raise TeamError("kết cục lượt không hợp lệ")
        with self._Tx(self) as c:
            c.execute("UPDATE team_turns SET status=?, tokens_in=?, tokens_out=?, cost_usd=?, settled_at=? "
                      "WHERE turn_id=? AND status IN ('running','reserved')",
                      (status, tokens_in, tokens_out, cost_usd, time.time(), turn_id))

    def refund_turn(self, turn_id: str) -> None:
        """Lượt chưa tới mốc gọi engine: hoàn, không tính. Đã qua mốc thì không hoàn được."""
        with self._Tx(self) as c:
            r = c.execute("SELECT status, engine_at FROM team_turns WHERE turn_id=?", (turn_id,)).fetchone()
            if r is None:
                raise TeamError("không có lượt này")
            if r["engine_at"] is not None:
                raise TeamError("lượt đã gọi engine, không hoàn được")
            c.execute("UPDATE team_turns SET status='refunded', settled_at=? WHERE turn_id=?", (time.time(), turn_id))

    def turn(self, turn_id: str) -> Optional[dict]:
        with closing(self._conn()) as c:
            r = c.execute("SELECT * FROM team_turns WHERE turn_id=?", (turn_id,)).fetchone()
            return dict(r) if r else None

    def count_task_turns(self, task_id: str) -> int:
        with closing(self._conn()) as c:
            return int(c.execute("SELECT COUNT(*) FROM team_turns WHERE task_id=? AND status != 'refunded'",
                                 (task_id,)).fetchone()[0])

    def count_team_turns(self, team_id: str, since: float) -> int:
        with closing(self._conn()) as c:
            return int(c.execute("SELECT COUNT(*) FROM team_turns WHERE team_id=? AND status != 'refunded' "
                                 "AND created_at >= ?", (team_id, float(since))).fetchone()[0])

    def turns(self, team_id: str, since: float = 0, limit: int = 500) -> list:
        with closing(self._conn()) as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM team_turns WHERE team_id=? AND created_at >= ? ORDER BY created_at DESC LIMIT ?",
                (team_id, float(since), int(limit))).fetchall()]

    def open_turns(self) -> list:
        """Lượt còn `reserved` hay `running` (dùng khi khởi động lại để chốt `interrupted` hay hoàn)."""
        with closing(self._conn()) as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM team_turns WHERE status IN ('reserved','running')").fetchall()]

    # ───────────── khoá bận theo agent (D3) ─────────────

    def acquire_busy(self, agent_key: str, team_id: str, turn_id: str, lease_s: float = 300,
                     now: Optional[float] = None) -> bool:
        t = time.time() if now is None else float(now)
        with self._Tx(self) as c:
            r = c.execute("SELECT * FROM agent_busy WHERE agent_key=?", (agent_key,)).fetchone()
            if r is not None and r["turn_id"] != turn_id and float(r["lease_until"]) > t:
                return False
            c.execute("INSERT INTO agent_busy(agent_key,team_id,turn_id,lease_until) VALUES(?,?,?,?) "
                      "ON CONFLICT(agent_key) DO UPDATE SET team_id=excluded.team_id, turn_id=excluded.turn_id, "
                      "lease_until=excluded.lease_until", (agent_key, team_id, turn_id, t + float(lease_s)))
            return True

    def release_busy(self, agent_key: str, turn_id: str) -> None:
        with self._Tx(self) as c:
            c.execute("DELETE FROM agent_busy WHERE agent_key=? AND turn_id=?", (agent_key, turn_id))

    def busy_of(self, agent_key: str, now: Optional[float] = None) -> Optional[dict]:
        t = time.time() if now is None else float(now)
        with closing(self._conn()) as c:
            r = c.execute("SELECT * FROM agent_busy WHERE agent_key=? AND lease_until > ?", (agent_key, t)).fetchone()
            return dict(r) if r else None
