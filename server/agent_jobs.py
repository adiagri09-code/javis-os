"""Tab Công việc của một trợ lý ở trang Cộng sự (0.142.0).

Gom việc của MỘT trợ lý (theo `agent_key` bền, trong đúng một brain) từ ba nguồn, đọc thẳng bản ghi gốc, không sao chép:
- **Nhóm** (`kanban.sqlite3` làn `team` + bước trong `team.sqlite3`): việc giao thẳng cho trợ lý, việc trợ lý điều phối,
  và việc trợ lý chỉ làm một bước con, hỗ trợ hay tổng hợp (người làm bước con cũng thấy việc liên quan).
- **Chat riêng** (Kanban thường): việc xếp hàng từ cuộc chat riêng với trợ lý (`chat_id` là phiên `agent:<slug>` đã ghim
  đúng mã), và việc giao bằng nút Giao việc ở chính tab này (`metadata.agent_key`).
- **Auto** (mục tiêu Cộng hưởng, `resonance.sqlite3`): mục tiêu của trợ lý, cùng mục tiêu cũ trợ lý đang là người review.

Mỗi việc rơi vào đúng một trong bốn ngăn: `running` (Đang làm), `waiting` (Đang chờ), `needs_you` (Cần bạn), `done`
(Đã xong). Không có phần trăm giả: tiến độ là số bước thật của việc nhóm.

Hàng chờ phải trung thực: việc Kanban khi brain tắt "AI tự vận hành" chỉ nằm chờ, nên ghi rõ `board_off`; việc nhóm ghi
vị trí trong hàng của nhóm.

Giao việc (`assign`) tạo MỘT việc Kanban gắn mã trợ lý, báo kết quả về cuộc chat riêng với trợ lý. Không tạo gì khi chỉ
đọc; chat thường không tự sinh việc.
"""
from __future__ import annotations

import re
import time
from typing import Any, Optional

BUCKETS = ("running", "waiting", "needs_you", "done")
RESULT_CHARS = 280
TEAM_HISTORY = 30
KANBAN_LIMIT = 500
GOAL_LIMIT = 40

_TEAM_BUCKET = {"team_running": "running", "team_queued": "waiting", "team_blocked": "needs_you", "done": "done",
                "cancelled": "done"}
_KANBAN_BUCKET = {"running": "running", "triage": "waiting", "todo": "waiting", "ready": "waiting",
                  "review": "needs_you", "blocked": "needs_you", "done": "done", "cancelled": "done"}


def _excerpt(text: Any, n: int = RESULT_CHARS) -> str:
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def _team_jobs(agent_key: str, root: str, teams, tasks) -> list:
    out = []
    if teams is None:
        return out
    for team in teams.teams_of_agent(agent_key):
        if team.get("brain_id") != root:
            continue
        q = tasks.team_queue(team["team_id"])
        waiting_pos = {t["id"]: i + 1 for i, t in enumerate(q.get("waiting") or [])}
        rows = list(q.get("running") or []) + list(q.get("waiting") or []) + list(q.get("blocked") or []) + \
            list(tasks.team_history(team["team_id"], TEAM_HISTORY))
        for task in rows:
            steps = teams.steps(task["id"])
            mine = [s for s in steps if s.get("agent_key") == agent_key]
            roles = []
            if task.get("assignee_key") == agent_key:
                roles.append("assignee")
            if task.get("coordinator_key") == agent_key or any(s["kind"] in ("plan", "synthesize") for s in mine):
                roles.append("coordinator")
            if any(s["kind"] == "work" for s in mine) and "assignee" not in roles:
                roles.append("worker")
            if any(s["kind"] == "help" for s in mine):
                roles.append("helper")
            if not roles:
                continue
            live_steps = [s for s in steps if s.get("status") != "cancelled"]
            st = str(task.get("status") or "")
            out.append({
                "id": f"team:{task['id']}", "source": "team", "source_id": team["team_id"],
                "source_label": team.get("name") or "", "title": task.get("title") or "", "status": st,
                "bucket": _TEAM_BUCKET.get(st, "waiting"), "roles": roles,
                "progress": {"done": sum(1 for s in live_steps if s.get("status") == "done"), "total": len(live_steps)},
                "my_steps": [{"kind": s["kind"], "status": s["status"]} for s in mine],
                "result": _excerpt(task.get("result")) if st == "done" else "",
                "reason": _excerpt(task.get("block_reason"), 200) if st == "team_blocked" else "",
                "queue_pos": waiting_pos.get(task["id"]), "cancelled": st == "cancelled",
                "updated_at": float(task.get("updated_at") or 0),
                "open": {"kind": "team", "team_id": team["team_id"], "task_id": task["id"]},
                "cancel": {"kind": "team", "team_id": team["team_id"], "task_id": task["id"]}
                if st in ("team_queued", "team_running", "team_blocked") else None,
            })
    return out


def _chat_sessions(agent_key: str, slug: str, brain_keys: Any, sessions, goals) -> dict:
    """{session_id: tiêu đề} các phiên chat riêng thuộc ĐÚNG mã này: phiên đã ghim mã khác (trợ lý cũ cùng slug) bị
    loại; phiên chưa ghim thì nhận theo slug (chưa có lượt nào gắn mã)."""
    out = {}
    if sessions is None or not slug:
        return out
    for s in sessions.list_sessions(limit=200, brain=brain_keys, include_archived=True, channel=f"agent:{slug}"):
        pin = None
        if goals is not None:
            try:
                pin = goals.session_pin(s["id"])
            except Exception:  # noqa: BLE001
                pin = None
        if pin and pin.get("agent_key") != agent_key:
            continue
        out[s["id"]] = s.get("title") or ""
    return out


def _kanban_jobs(agent_key: str, slug: str, root: str, brain_keys: Any, tasks, sessions, goals) -> list:
    out = []
    chats = _chat_sessions(agent_key, slug, brain_keys, sessions, goals)
    board_off = False
    try:
        board_off = tasks.board_mode(root) == "off"
    except Exception:  # noqa: BLE001
        pass
    for task in tasks.list_tasks(root, include_archived=False, limit=KANBAN_LIMIT):
        chat = str(task.get("chat_id") or "")
        sid = chat[4:] if chat.startswith("web:") else ""
        owner = assigned_key(task)
        # Việc giao bằng nút Giao việc mang mã trợ lý trong khoá idempotency (metadata bị ghi đè khi việc chạy xong);
        # việc xếp từ chat riêng nhận theo phiên đã ghim đúng mã.
        if owner is not None:
            if owner != agent_key:
                continue
        elif not (sid and sid in chats):
            continue
        st = str(task.get("status") or "")
        bucket = _KANBAN_BUCKET.get(st, "waiting")
        if st == "done" and "[[NEEDS_INPUT]]" in str(task.get("result") or ""):
            bucket = "needs_you"
        out.append({
            "id": f"kanban:{task['id']}", "source": "chat", "source_id": sid,
            "source_label": chats.get(sid, ""), "title": task.get("title") or "", "status": st, "bucket": bucket,
            "roles": ["assignee"], "progress": None, "my_steps": [],
            "result": _excerpt(task.get("result")) if st in ("done", "review") else "",
            "reason": _excerpt(task.get("block_reason"), 200) if bucket == "needs_you" else "",
            "queue_pos": None, "board_off": bool(board_off and bucket == "waiting"), "cancelled": st == "cancelled",
            "updated_at": float(task.get("updated_at") or 0),
            "open": {"kind": "chat", "session_id": sid} if sid else {"kind": "work", "task_id": task["id"]},
            "cancel": {"kind": "kanban", "task_id": task["id"]} if st not in ("done", "cancelled", "archived") else None,
        })
    return out


_GOAL_DONE = {"succeeded": "succeeded", "failed": "failed", "cancelled": "cancelled"}


def _auto_jobs(agent_key: str, goals, principal) -> list:
    out = []
    if goals is None:
        return out
    for g in goals.agent_goal_rows(principal, agent_key, GOAL_LIMIT):
        st, rs = str(g.get("status") or ""), str(g.get("run_state") or "")
        if st == "active":
            bucket = "needs_you" if (rs == "blocked" or g.get("paused")) else "running" if rs == "running" else "waiting"
        else:
            bucket = "done"
        out.append({
            "id": f"goal:{g['id']}", "source": "auto", "source_id": g.get("session_id") or "",
            "source_label": "", "title": _excerpt(g.get("understanding") or g.get("request_ref") or g["id"], 140),
            "status": st, "run_state": rs, "bucket": bucket, "roles": [g.get("role") or "owner"], "progress": None,
            "my_steps": [], "result": "", "reason": str(g.get("block_reason") or "") if bucket == "needs_you" else "",
            "reason_code": str(g.get("reason_code") or ""),
            "queue_pos": None, "cancelled": st == "cancelled", "failed": st == "failed",
            "updated_at": float(g.get("updated_at") or 0),
            "open": {"kind": "chat", "session_id": g.get("session_id") or "", "goal_id": g["id"]},
            "cancel": {"kind": "goal", "goal_id": g["id"]} if st == "active" and g.get("role") != "reviewer" else None,
        })
    return out


def collect(agent_key: str, slug: str, root: str, *, brain_keys: Any = None, teams=None, tasks=None, sessions=None,
            goals=None, principal=None, now: Optional[float] = None) -> dict:
    """{"jobs": [...], "counts": {ngăn: số}} của một trợ lý. Mỗi nguồn hỏng không làm mất nguồn khác: nguồn lỗi được
    ghi trong `errors` để giao diện nói rõ thiếu phần nào thay vì im lặng."""
    jobs, errors = [], []
    for name, fn in (("team", lambda: _team_jobs(agent_key, root, teams, tasks)),
                     ("chat", lambda: _kanban_jobs(agent_key, slug, root, brain_keys, tasks, sessions, goals)),
                     ("auto", lambda: _auto_jobs(agent_key, goals, principal))):
        try:
            jobs += fn()
        except Exception as ex:  # noqa: BLE001
            errors.append({"source": name, "error": f"{type(ex).__name__}: {str(ex)[:200]}"})
    order = {b: i for i, b in enumerate(("needs_you", "running", "waiting", "done"))}
    jobs.sort(key=lambda j: (order.get(j["bucket"], 9), -(j.get("updated_at") or 0)))
    counts = {b: sum(1 for j in jobs if j["bucket"] == b) for b in BUCKETS}
    return {"jobs": jobs, "counts": counts, "errors": errors, "at": now if now is not None else time.time()}


ASSIGN_PREFIX = "agent:"


def assign_key(agent_key: str, slug: str, nonce: str) -> str:
    """Khoá idempotency của việc giao cho trợ lý: `agent:<mã>:<slug>:<nonce>`. Bền suốt đời việc (metadata thì bị ghi đè
    khi việc chạy xong), nên vừa là dấu "việc của ai" vừa chống gửi trùng khi bấm hai lần hay gửi lại sau rớt mạng."""
    return f"{ASSIGN_PREFIX}{agent_key}:{slug}:{re.sub(r'[^A-Za-z0-9_-]', '', str(nonce or ''))[:64]}"


def parse_assign_key(key: Any) -> Optional[tuple]:
    """(agent_key, slug) từ khoá của việc giao cho trợ lý, None nếu không phải."""
    k = str(key or "")
    if not k.startswith(ASSIGN_PREFIX):
        return None
    parts = k[len(ASSIGN_PREFIX):].split(":")
    if len(parts) < 3 or not parts[0] or not parts[1]:
        return None
    return parts[0], parts[1]


def assigned_key(task: dict) -> Optional[str]:
    got = parse_assign_key(task.get("idempotency_key"))
    return got[0] if got else None


def assign_title(agent_name: str, text: str) -> str:
    """Tiêu đề việc giao cho trợ lý. Kanban gộp việc đang mở CÙNG tiêu đề trong một brain, nên tên trợ lý đi kèm để
    "Viết bài" giao cho hai trợ lý khác nhau vẫn là hai việc (trên bảng Việc cũng đọc ra ngay ai làm)."""
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    return f"{t[:120]} · {str(agent_name or '').strip()[:40]}".strip(" ·")
