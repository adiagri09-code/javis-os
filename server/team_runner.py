"""Bộ chạy nhóm chat team (T1, Quyền giới hạn). Spec: docs/superpowers/specs/2026-10-13-team-chat-design.md mục 7 tới 12.

Ba việc:
- `submit`: ghi tin của chủ nhóm (chống trùng bằng `client_msg_id`), định tuyến (D1: tin không @ thì trưởng nhóm trả
  lời), hay tạo một việc nhóm khi bật "Giao việc" (D2). `run_replies` chạy các lượt trả lời theo thứ tự @.
- `dispatch_once` / `run_job`: nhận việc đầu hàng của từng nhóm (làn `team` của Kanban, task_store) và chạy các bước
  nội bộ `plan`, `work`, `help`, `synthesize` (team_store) tới khi xong hay bị chặn.
- `recover`: sau restart, lượt chưa tới mốc gọi engine thì hoàn và chạy tiếp; đã qua mốc thì tính một lần
  (`interrupted`) và chặn việc, không tự chạy lại.

Engine đi qua phụ thuộc tiêm vào (`engine_for`), nên test chạy hoàn toàn bằng engine giả. Lượt nhóm ở T1 chỉ chữ
(phán quyết R3): request mang `tools=[]`.

Agent điều phối bằng khối chỉ dẫn do host đọc ở cuối câu trả lời (phán quyết R1), cùng kiểu JAVIS_ASK:
    <!-- JAVIS_TEAM: {"op": "assign", "agent": "<mã hay slug>", "brief": "..."} -->
Host kiểm từng op theo vai của lượt; op sai bị bỏ kèm ghi chú trên tin, không gọi thêm lượt ngoài trần.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from typing import Any, Awaitable, Callable, Optional

from team_store import TeamError

DIRECTIVE_RE = re.compile(r"<!--\s*JAVIS_TEAM:\s*(.*?)-->", re.S)
# Op được phép theo vai của lượt (spec 15.2, Quyền giới hạn). Lượt trò chuyện không mở việc, không nhờ ai.
OPS_BY_ROLE = {
    "leader_reply": {"propose_job"},
    "member_reply": set(),
    "plan": {"assign"},
    "work": {"request_help"},
    "help": {"request_help"},
    "synthesize": set(),
}
LEADER_ROLES = ("leader_reply", "plan", "synthesize")
ROLE_LABEL = {
    "leader_reply": "Trưởng nhóm trả lời trò chuyện",
    "member_reply": "Thành viên trả lời trò chuyện",
    "plan": "Lập kế hoạch",
    "work": "Làm",
    "help": "Hỗ trợ",
    "synthesize": "Tổng hợp",
}
BUSY_LEASE_S = 900.0          # hạn khoá bận một lượt; tiến trình chết thì tự nhả
NEW_MSG_LIMIT = 20            # tin mới trong khối nhóm (spec 11.2)
NEW_MSG_CHARS = 8000
INPUT_CHARS = 4000            # mỗi đầu vào của bước
DECISION_LIMIT = 20           # sổ quyết định (spec 11.2)
DECISION_CHARS = 500
REMIND_AFTER_S = 24 * 3600    # nhắc việc bị chặn quá 24 giờ (spec 8.4)

EngineFn = Callable[[dict], Awaitable[dict]]


def parse_directives(text: str) -> tuple[str, list, list]:
    """Tách khối JAVIS_TEAM khỏi câu trả lời. Trả (chữ sạch, danh sách op, ghi chú lỗi)."""
    ops: list = []
    notes: list = []

    def take(m: re.Match) -> str:
        raw = m.group(1).strip()
        try:
            obj = json.loads(raw)
        except Exception:
            notes.append("Khối JAVIS_TEAM hỏng (không đọc được JSON), đã bỏ")
            return ""
        if not isinstance(obj, dict) or not isinstance(obj.get("op"), str):
            notes.append("Khối JAVIS_TEAM thiếu op, đã bỏ")
            return ""
        ops.append(obj)
        return ""

    clean = DIRECTIVE_RE.sub(take, text or "")
    return clean.strip(), ops, notes


def _sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


class TeamRunner:
    def __init__(self, *, teams, tasks, sessions, engine_for: Callable[[dict, str, str], tuple],
                 agent_info: Callable[[str, str], Optional[dict]], publish: Optional[Callable[[dict], Any]] = None,
                 notify: Optional[Callable[[str, str], Any]] = None, worker_id: str = "team-runner",
                 max_parallel_teams: int = 2, clock: Callable[[], float] = time.time):
        self.teams = teams
        self.tasks = tasks
        self.sessions = sessions
        self.engine_for = engine_for
        self.agent_info = agent_info
        self._publish_fn = publish
        self._notify_fn = notify
        self.worker_id = worker_id
        self.max_parallel_teams = max(1, int(max_parallel_teams))
        self.clock = clock
        self._jobs: dict[str, asyncio.Task] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._locks_loop: Any = None

    # ───────────── tiện ích ─────────────

    def _publish(self, event: dict) -> None:
        if self._publish_fn:
            try:
                self._publish_fn(event)
            except Exception:
                pass

    def _notify(self, team_id: str, text: str) -> None:
        if self._notify_fn:
            try:
                self._notify_fn(team_id, text)
            except Exception:
                pass

    def _team(self, team_id: str) -> dict:
        team = self.teams.get(team_id)
        if not team:
            raise TeamError("không có nhóm này")
        return team

    def _name(self, team: dict, agent_key: str) -> str:
        info = self.agent_info(team["brain_id"], agent_key) or {}
        return str(info.get("name") or info.get("slug") or agent_key)

    def _resolve(self, team: dict, ref: Any) -> Optional[str]:
        """Mã agent từ `agent_key`, slug lúc vào nhóm hay slug hiện tại; chỉ thành viên đang hoạt động."""
        ref = str(ref or "").strip().lstrip("@")
        if not ref:
            return None
        for m in self.teams.members(team["team_id"]):
            info = self.agent_info(team["brain_id"], m["agent_key"]) or {}
            if ref in (m["agent_key"], m["slug_at_join"], info.get("slug")):
                return m["agent_key"]
        return None

    def _day_start(self) -> float:
        lt = time.localtime(self.clock())
        return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))

    def _daily_left(self, team: dict) -> bool:
        return self.teams.count_team_turns(team["team_id"], self._day_start()) < int(team["caps"]["daily_turns"])

    def _post(self, team: dict, text: str, *, author_kind: str, author_ref: str = "", reply_to=None,
              task_id=None, step_id=None, meta=None, role: str = "assistant") -> int:
        mid, _ = self.sessions.append_team_message(team["session_id"], role, text, author_kind=author_kind,
                                                   author_ref=author_ref, reply_to=reply_to, task_id=task_id,
                                                   step_id=step_id, meta=meta)
        self.teams.touch(team["team_id"])
        self._publish({"type": "team_message", "team_id": team["team_id"],
                       "message": self.sessions.team_message(team["session_id"], mid)})
        return mid

    def _state(self, team_id: str) -> None:
        self._publish({"type": "team_state", "team_id": team_id})

    def _lock_for(self, agent_key: str) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        if self._locks_loop is not loop:
            self._locks, self._locks_loop = {}, loop
        return self._locks.setdefault(agent_key, asyncio.Lock())

    def busy_view(self, team_id: str) -> dict:
        """{agent_key: team_id khác đang giữ agent} cho các thành viên của nhóm (hiện "X đang làm ở nhóm Y")."""
        out = {}
        for m in self.teams.members(team_id):
            b = self.teams.busy_of(m["agent_key"])
            if b and b["team_id"] != team_id:
                out[m["agent_key"]] = b["team_id"]
        return out

    # ───────────── tin của chủ nhóm ─────────────

    def submit(self, team_id: str, text: str, *, mentions: Optional[list] = None, as_job: bool = False,
               client_msg_id: str = "") -> dict:
        """Ghi tin của chủ nhóm rồi định tuyến (spec 7.1 tới 7.3). Không gọi model ở đây."""
        team = self._team(team_id)
        if team["status"] == "archived":
            raise TeamError("nhóm đã lưu trữ, không gửi tin được")
        text = str(text or "").strip()
        if not text:
            raise TeamError("tin trống")
        cmid = str(client_msg_id or "").strip()
        if not cmid:
            raise TeamError("thiếu client_msg_id")
        sid = team["session_id"]
        out = {"team_id": team_id, "session_id": sid, "text": text, "task_id": None, "replies": [], "notes": []}
        old = self.sessions.message_by_client_id(sid, cmid)
        if old is not None:
            # Gửi lại sau rớt mạng: trả đúng tin cũ (và việc cũ), không thêm lượt.
            out.update(message_id=old["id"], created=False)
            if (old.get("meta") or {}).get("as_job"):
                out["task_id"] = self._enqueue_for(team, old["id"], old["content"], old["meta"].get("mentions") or [])[0]
            return out
        wanted = list(dict.fromkeys(str(m) for m in (mentions or []) if str(m or "").strip()))
        cap = int(team["caps"]["mentions"])
        if len(wanted) > cap:
            raise TeamError(f"Mỗi tin gắn tối đa {cap} người (@)")
        valid = []
        for key in wanted:
            if self.teams.is_active_member(team_id, key) and self.agent_info(team["brain_id"], key):
                valid.append(key)
            else:
                out["notes"].append(f"{self._name(team, key)} ({key}) không còn trong nhóm")
        mid, created = self.sessions.append_team_message(
            sid, "user", text, author_kind="owner", client_msg_id=cmid,
            meta={"mentions": valid, "as_job": bool(as_job), "notes": list(out["notes"])})
        self.teams.touch(team_id)
        out.update(message_id=mid, created=created)
        self._publish({"type": "team_message", "team_id": team_id, "message": self.sessions.team_message(sid, mid)})
        if as_job:
            out["task_id"] = self._enqueue_for(team, mid, text, valid)[0]
            self._state(team_id)
            return out
        if not created:
            return out
        if team["status"] != "active":
            out["notes"].append("team_paused")
        elif not self._daily_left(team):
            out["notes"].append("daily_cap")
        elif wanted:
            out["replies"] = valid
        elif team["leader_key"]:
            out["replies"] = [team["leader_key"]]
        else:
            out["notes"].append("no_leader")
        return out

    def _enqueue_for(self, team: dict, mid: int, text: str, assignees: list) -> tuple:
        title = re.sub(r"\s+", " ", text)[:80]
        return self.tasks.enqueue_team(
            team["brain_id"], team["team_id"], title, text, source_ref=f"msg:{team['session_id']}:{mid}",
            assignee_key=assignees[0] if assignees else "", coordinator_key=team["leader_key"] or "",
            chat_id=f"team:{team['team_id']}")

    async def run_replies(self, submitted: dict) -> list:
        """Lượt trả lời trò chuyện, tuần tự theo thứ tự @: người sau thấy câu trả lời của người trước."""
        outcomes = []
        for key in submitted.get("replies") or []:
            team = self._team(submitted["team_id"])
            role = "leader_reply" if key == team["leader_key"] else "member_reply"
            body = (f"Chủ nhóm vừa nhắn (tin #{submitted['message_id']}):\n{submitted['text']}\n\n"
                    "Trả lời ngắn gọn, đúng vai của bạn trong nhóm.")
            if role == "leader_reply":
                body += ("\nNếu trao đổi này nên thành một việc nhóm, bạn có thể ĐỀ XUẤT (chủ nhóm bấm mới thành việc): "
                         '<!-- JAVIS_TEAM: {"op": "propose_job", "title": "...", "brief": "..."} -->')
            outcomes.append(await self._turn(team, key, role, body, reply_to=submitted["message_id"],
                                             vet=self._vet_reply))
        return outcomes

    def _vet_reply(self, team, role, ops, notes, task=None, step=None) -> tuple:
        meta: dict = {}
        for op in ops:
            if op["op"] == "propose_job" and role == "leader_reply" and not meta.get("proposal"):
                title = str(op.get("title") or "").strip()[:120]
                brief = str(op.get("brief") or title).strip()[:4000]
                if title:
                    meta["proposal"] = {"title": title, "brief": brief}
                    continue
                notes.append("Đề xuất việc thiếu tiêu đề, đã bỏ")
            else:
                notes.append(f"Lệnh '{op['op']}' không dùng được ở lượt trò chuyện, đã bỏ")
        return [], meta

    def accept_proposal(self, team_id: str, message_id: int) -> str:
        """Chủ nhóm bấm "Tạo việc" trên thẻ đề xuất của trưởng nhóm (D2). Bấm lại trả đúng việc cũ."""
        team = self._team(team_id)
        msg = self.sessions.team_message(team["session_id"], int(message_id))
        prop = ((msg or {}).get("meta") or {}).get("proposal")
        if not msg or msg.get("author_kind") != "agent" or not prop:
            raise TeamError("tin này không phải đề xuất việc")
        tid, _ = self.tasks.enqueue_team(
            team["brain_id"], team_id, prop["title"], prop.get("brief") or prop["title"],
            source_ref=f"proposal:{team['session_id']}:{int(message_id)}", coordinator_key=team["leader_key"] or "",
            chat_id=f"team:{team_id}")
        self._state(team_id)
        return tid

    # ───────────── một lượt ─────────────

    def _context(self, team: dict, agent_key: str, role: str, task: Optional[dict], step: Optional[dict]) -> str:
        """Khối nhóm do code dựng (spec 11.2). Chỉ dữ liệu của CHÍNH nhóm này."""
        lines = [f"# NHÓM: {team['name']}"]
        if team.get("description"):
            lines.append(f"Mô tả: {team['description']}")
        lines.append("Thành viên:")
        for m in self.teams.members(team["team_id"]):
            tag = " - trưởng nhóm" if m["agent_key"] == team["leader_key"] else ""
            me = " (bạn)" if m["agent_key"] == agent_key else ""
            lines.append(f"- {self._name(team, m['agent_key'])} [{m['agent_key']}]{tag}{me}")
        lines.append(f"Vai của bạn trong lượt này: {ROLE_LABEL.get(role, role)}")
        sid = team["session_id"]
        decisions = self.sessions.team_decisions(sid, DECISION_LIMIT)
        if decisions:
            lines.append("\n## Sổ quyết định (chủ nhóm ghim, luôn theo)")
            lines.extend(f"- [#{m['id']}] {m['content'][:DECISION_CHARS]}" for m in decisions)
        after = self.sessions.last_message_id_by(sid, agent_key)
        fresh = self.sessions.team_messages_after(sid, after, NEW_MSG_LIMIT)
        rendered, size = [], 0
        for m in reversed(fresh):
            who = ("Chủ nhóm" if m["author_kind"] == "owner" else
                   self._name(team, m["author_ref"]) if m["author_kind"] == "agent" else "Hệ thống")
            row = f"[#{m['id']} {who}] {m['content']}"
            if size + len(row) > NEW_MSG_CHARS:
                break
            rendered.append(row)
            size += len(row)
        if rendered:
            lines.append("\n## Tin mới trong nhóm (kể từ lượt trước của bạn)")
            lines.extend(reversed(rendered))
        if task:
            lines.append(f"\n## Việc hiện tại: {task['title']} (bản {task['team_rev']})")
            lines.append(f"Yêu cầu: {task['intent']}")
            if step:
                lines.append(f"Bước của bạn: {ROLE_LABEL.get(step['kind'], step['kind'])}")
                if step.get("brief"):
                    lines.append(f"Nội dung bước: {step['brief']}")
                inputs = []
                for ref in step.get("input_refs") or []:
                    m = self.sessions.team_message(sid, int(ref)) if str(ref).isdigit() else None
                    if m:
                        who = "Chủ nhóm" if m["author_kind"] == "owner" else self._name(team, m["author_ref"])
                        inputs.append(f"[#{m['id']} {who}] {m['content'][:INPUT_CHARS]}")
                if inputs:
                    lines.append("Đầu vào:")
                    lines.extend(inputs)
        return "\n".join(lines)

    async def _acquire(self, team: dict, agent_key: str, turn_id: str) -> bool:
        """Khoá bận theo agent (D3): một lượt nhóm mỗi agent trên cả máy, chờ theo thứ tự xin (FIFO)."""
        wait = float(team["caps"]["busy_wait_s"])
        lock = self._lock_for(agent_key)
        holder = self.teams.busy_of(agent_key)
        if holder and holder["team_id"] != team["team_id"]:
            self._state(team["team_id"])
        try:
            await asyncio.wait_for(lock.acquire(), timeout=wait)
        except (asyncio.TimeoutError, TimeoutError):
            return False
        deadline = time.monotonic() + wait
        while not self.teams.acquire_busy(agent_key, team["team_id"], turn_id, lease_s=BUSY_LEASE_S):
            if time.monotonic() > deadline:
                lock.release()
                return False
            await asyncio.sleep(0.2)
        return True

    def _release(self, agent_key: str, turn_id: str) -> None:
        self.teams.release_busy(agent_key, turn_id)
        lock = self._locks.get(agent_key)
        if lock is not None and lock.locked():
            lock.release()

    async def _turn(self, team: dict, agent_key: str, role: str, body: str, *, task: Optional[dict] = None,
                    step: Optional[dict] = None, reply_to=None, vet=None) -> dict:
        """Một lượt của thành viên (spec 9.1): giữ chỗ, khoá bận, kiểm, mốc engine, gọi, kiểm muộn, đăng tin."""
        team_id = team["team_id"]
        task_id = task["id"] if task else None
        step_id = step["step_id"] if step else None
        if not self._daily_left(team):
            return {"status": "cap", "cap": "daily_turns"}
        if task and self.teams.count_task_turns(task_id) >= int(team["caps"]["task_turns"]):
            return {"status": "cap", "cap": "task_turns"}
        turn_id = self.teams.reserve_turn(team_id, task_id, step_id, agent_key, role)
        try:
            got = await self._acquire(team, agent_key, turn_id)
        except asyncio.CancelledError:
            self.teams.refund_turn(turn_id)
            raise
        if not got:
            self.teams.refund_turn(turn_id)
            return {"status": "busy_long", "turn_id": turn_id}
        try:
            pre = self._still_valid(team_id, agent_key, role, task, step)
            info = self.agent_info(team["brain_id"], agent_key)
            if pre == "done" and info is None:
                pre = "member_left"
            if pre != "done":
                self.teams.refund_turn(turn_id)
                return {"status": pre, "before_engine": True, "turn_id": turn_id}
            team = self._team(team_id)
            engine, model, fn = self.engine_for(team, agent_key, role)
            req = {"team_id": team_id, "brain": team["brain_id"], "agent_key": agent_key, "role": role,
                   "system": str(info.get("system") or ""), "prompt": self._context(team, agent_key, role, task, step)
                   + "\n\n" + body, "thread": f"teammate:{team_id}:{agent_key}", "task_id": task_id,
                   "step_id": step_id, "turn_id": turn_id, "tools": []}
            self.teams.mark_engine(turn_id, str(engine or ""), str(model or ""))
            try:
                res = await fn(req)
            except asyncio.CancelledError:
                self.teams.settle_turn(turn_id, "interrupted")
                raise
            except Exception as ex:
                self.teams.settle_turn(turn_id, "error")
                return {"status": "error", "error": str(ex)[:500], "turn_id": turn_id}
            res = res or {}
            self.teams.settle_turn(turn_id, "ok", res.get("tokens_in"), res.get("tokens_out"), res.get("cost_usd"))
        finally:
            self._release(agent_key, turn_id)
        raw = str(res.get("text") or "")
        clean, ops, notes = parse_directives(raw)
        status = self._still_valid(team_id, agent_key, role, task, step)
        applied = status == "done"
        allowed = OPS_BY_ROLE.get(role, set())
        kept = []
        for op in ops:
            if op["op"] not in allowed:
                notes.append(f"Lệnh '{op['op']}' không dùng được ở lượt này, đã bỏ")
            else:
                kept.append(op)
        extra: dict = {}
        if applied and vet:
            kept, extra = vet(self._team(team_id), role, kept, notes, task, step)
        elif not applied:
            kept = []
        meta = {"role": role, "status": status, "applied": applied, "turn_id": turn_id, "notes": notes,
                "sha": _sha(raw)}
        if task:
            meta["revision"] = step["job_revision"] if step else task["team_rev"]
        meta.update(extra)
        mid = self._post(self._team(team_id), clean or "(không có nội dung)", author_kind="agent", author_ref=agent_key,
                         reply_to=reply_to, task_id=task_id, step_id=step_id, meta=meta)
        return {"status": status, "applied": applied, "ops": kept, "notes": notes, "message_id": mid,
                "text": clean, "sha": meta["sha"], "turn_id": turn_id}

    def _still_valid(self, team_id: str, agent_key: str, role: str, task: Optional[dict],
                     step: Optional[dict]) -> str:
        """Kết quả còn được áp dụng không (spec 9.1 bước 6, 12.4). Trả "done" hay nhãn đến muộn."""
        if not self.teams.is_active_member(team_id, agent_key):
            return "member_left"
        if task:
            cur = self.tasks.get_task(task["id"])
            if not cur or cur["status"] == "cancelled":
                return "late_cancelled"
            if cur["status"] != "team_running":
                return "late"
            if step and int(cur["team_rev"]) != int(step["job_revision"]):
                return "old_revision"
        if role in LEADER_ROLES:
            team = self.teams.get(team_id) or {}
            if team.get("leader_key") != agent_key:
                return "leader_changed"
        return "done"

    # ───────────── việc nhóm ─────────────

    def _assignees(self, task: dict) -> list:
        src = str(task.get("source_ref") or "")
        if src.startswith("msg:"):
            _, sid, mid = src.split(":", 2)
            msg = self.sessions.team_message(sid, int(mid)) if mid.isdigit() else None
            got = list(((msg or {}).get("meta") or {}).get("mentions") or [])
            if got:
                return got
        return [task["assignee_key"]] if task.get("assignee_key") else []

    def _source_id(self, task: dict) -> list:
        parts = str(task.get("source_ref") or "").split(":")
        return [int(parts[-1])] if parts and parts[-1].isdigit() else []

    def start_job_steps(self, task_id: str) -> str:
        """Tạo bước đầu cho việc vừa nhận nếu chưa có bước nào. Trả "ok", "no_leader" hay "assignee_removed"."""
        if self.teams.steps(task_id):
            return "ok"
        task = self.tasks.get_task(task_id)
        team = self._team(task["team_id"])
        assignees = self._assignees(task)
        rev = int(task["team_rev"])
        if assignees:
            live = [a for a in assignees if self.teams.is_active_member(team["team_id"], a)]
            if not live:
                return "assignee_removed"
            for a in live:
                self.teams.add_step(task_id, team["team_id"], "work", a, rev, task["intent"], self._source_id(task))
            return "ok"
        if not team["leader_key"]:
            return "no_leader"
        if task.get("coordinator_key") != team["leader_key"]:
            self._coordinator_changed(team, task, team["leader_key"])
        self.teams.add_step(task_id, team["team_id"], "plan", team["leader_key"], rev, task["intent"],
                            self._source_id(task))
        return "ok"

    def _coordinator_changed(self, team: dict, task: dict, new_key: Optional[str]) -> None:
        self.tasks.team_set_coordinator(task["id"], new_key or "")
        self.teams.log_event(team["team_id"], "coordinator_changed", "host",
                             {"task_id": task["id"], "coordinator_key": task.get("coordinator_key")},
                             {"task_id": task["id"], "coordinator_key": new_key})

    def _block(self, task_id: str, kind: str, reason: str) -> str:
        task = self.tasks.get_task(task_id)
        if self.tasks.team_block(task_id, kind, reason) is not None and task:
            self._notify(task["team_id"], f"Việc nhóm \"{task['title']}\" bị chặn: {reason}")
            self._state(task["team_id"])
        return "team_blocked"

    def _add_steps(self, team: dict, task: dict, specs: list) -> bool:
        """Thêm bước nếu không vượt trần bước mỗi việc; vượt thì chặn `cap_reached`, không thêm bước nào."""
        cap = int(team["caps"]["task_steps"])
        if len(self.teams.steps(task["id"])) + len(specs) > cap:
            self._block(task["id"], "cap_reached", f"Đã chạm trần {cap} bước mỗi việc")
            return False
        for s in specs:
            self.teams.add_step(task["id"], team["team_id"], s["kind"], s["agent"], int(s.get("rev") or task["team_rev"]),
                                s.get("brief", ""), s.get("inputs", []), s.get("parent"))
        return True

    def _recoordinate(self, team: dict, task: dict, step: dict, reason: str) -> Optional[str]:
        """Về điểm điều phối (spec 6.4, 7.6): việc chung thì trưởng nhóm lập lại kế hoạch; việc trực tiếp thì người được
        giao làm lại theo bản mới, hay chặn `assignee_removed` nếu người đó đã rời."""
        task = self.tasks.get_task(task["id"])
        self.teams.cancel_open_steps(task["id"], reason)
        direct = bool(self._assignees(task))
        if direct:
            if not self.teams.is_active_member(team["team_id"], step["agent_key"]):
                return self._block(task["id"], "assignee_removed", "Người được giao đã rời nhóm")
            ok = self._add_steps(team, task, [{"kind": step["kind"], "agent": step["agent_key"], "brief": task["intent"],
                                               "inputs": step["input_refs"], "parent": step["parent_step"]}])
            return None if ok else "team_blocked"
        team = self._team(team["team_id"])
        if not team["leader_key"]:
            return self._block(task["id"], "no_leader", "Nhóm chưa có trưởng nhóm")
        ok = self._add_steps(team, task, [{"kind": "plan", "agent": team["leader_key"],
                                           "brief": f"Lập lại kế hoạch ({reason}). {task['intent']}",
                                           "inputs": self._done_results(task) or self._source_id(task)}])
        return None if ok else "team_blocked"

    def _done_results(self, task: dict) -> list:
        return [s["result_msg_id"] for s in self.teams.steps(task["id"])
                if s["kind"] == "work" and s["status"] == "done" and s["applied"]
                and int(s["job_revision"]) == int(task["team_rev"]) and s["result_msg_id"]]

    def _finish(self, team: dict, task_id: str, msg_id: int, text: str) -> str:
        if self.tasks.team_finish(task_id, text) is not None:
            self.sessions.update_team_message_meta(team["session_id"], msg_id, {"job_result": True})
            self._publish({"type": "team_message", "team_id": team["team_id"],
                           "message": self.sessions.team_message(team["session_id"], msg_id)})
            self._state(team["team_id"])
        return "done"

    def _chain(self, step: dict) -> list:
        """Các bước đang chờ câu trả lời phía trên `step` (theo parent_step), gần nhất trước."""
        out, cur = [], step
        while cur and cur.get("parent_step"):
            cur = self.teams.step(cur["parent_step"])
            if cur:
                out.append(cur)
        return out

    def _body(self, step: dict, task: dict) -> str:
        if step["kind"] == "plan":
            return ("Bạn là trưởng nhóm, lập kế hoạch cho việc trên. Giao từng phần cho thành viên phù hợp, mỗi phần một "
                    'khối: <!-- JAVIS_TEAM: {"op": "assign", "agent": "<mã thành viên>", "brief": "..."} -->\n'
                    "Việc nhỏ thì tự làm luôn và trả kết quả, không cần giao.")
        if step["kind"] == "synthesize":
            return "Tổng hợp kết quả các bước (ở phần Đầu vào) thành một kết quả cuối cho chủ nhóm."
        return ("Làm phần việc của bạn và trả kết quả. Cần hỏi thành viên khác thì dùng: "
                '<!-- JAVIS_TEAM: {"op": "request_help", "agent": "<mã thành viên>", "question": "..."} -->')

    def _vet_step(self, team, role, ops, notes, task=None, step=None) -> tuple:
        kept = []
        if role == "plan":
            for op in ops:
                key = self._resolve(team, op.get("agent"))
                if not key:
                    notes.append(f"'{op.get('agent')}' không phải thành viên đang hoạt động của nhóm, đã bỏ")
                    continue
                kept.append({"op": "assign", "agent": key, "brief": str(op.get("brief") or "")[:4000]})
            return kept, {}
        # work, help: nhờ hỗ trợ (spec 7.4) với trần độ sâu và chặn nhờ ngược
        for op in ops:
            if kept:
                notes.append("Mỗi lượt chỉ nhờ được một người, đã bỏ lời nhờ thêm")
                continue
            key = self._resolve(team, op.get("agent"))
            if not key or key == step["agent_key"]:
                notes.append(f"'{op.get('agent')}' không nhờ được (không phải thành viên khác đang hoạt động), đã bỏ")
                continue
            chain = self._chain(step)
            if key in {s["agent_key"] for s in chain}:
                notes.append(f"Không nhờ ngược trong cùng một việc: {self._name(team, key)} đang chờ bạn, đã bỏ")
                continue
            depth = 1 + sum(1 for s in [step] + chain if s["kind"] == "help")
            cap = int(team["caps"]["help_depth"])
            if depth > cap:
                notes.append(f"Đã tới độ sâu nhờ hỗ trợ tối đa ({cap}), không nhờ tiếp được")
                continue
            kept.append({"op": "request_help", "agent": key, "question": str(op.get("question") or "")[:4000]})
        return kept, {}

    async def run_job(self, task_id: str) -> str:
        """Chạy các bước của một việc `team_running` tới khi xong, bị chặn, bị huỷ hay nhóm tạm dừng."""
        while True:
            task = self.tasks.get_task(task_id)
            if not task or task["status"] != "team_running":
                if task and task["status"] == "cancelled":
                    self.teams.cancel_open_steps(task_id, "việc đã huỷ")
                return task["status"] if task else "missing"
            team = self._team(task["team_id"])
            if team["status"] == "archived":
                # Lưu trữ = tạm dừng + huỷ việc (spec 11.4): việc đang chạy dừng ở điểm điều phối này.
                self.cancel_job(task_id, "nhóm đã lưu trữ")
                return "cancelled"
            if team["status"] != "active":
                return "paused"
            self.tasks.team_heartbeat(task_id, self.worker_id)
            step = self.teams.next_queued_step(task_id)
            if step is None:
                res = self._after_steps(team, task)
                if res:
                    return res
                continue
            if step["kind"] in ("plan", "synthesize") and step["agent_key"] != team["leader_key"]:
                self.teams.set_step_status(step["step_id"], "cancelled", "trưởng nhóm đã đổi")
                if not team["leader_key"]:
                    return self._block(task_id, "no_leader", "Nhóm chưa có trưởng nhóm")
                self._coordinator_changed(team, task, team["leader_key"])
                if not self._add_steps(team, task, [{"kind": step["kind"], "agent": team["leader_key"],
                                                     "brief": step["brief"], "inputs": step["input_refs"]}]):
                    return "team_blocked"
                continue
            if not self.teams.claim_step(step["step_id"]):
                continue
            res = await self._run_step(team, task, step)
            if res:
                return res

    def _after_steps(self, team: dict, task: dict) -> Optional[str]:
        """Hết bước chờ: một kết quả thì xong; nhiều kết quả thì trưởng nhóm tổng hợp; không có gì thì chặn."""
        steps = self.teams.steps(task["id"])
        results = [s for s in steps if s["kind"] == "work" and s["status"] == "done" and s["applied"]
                   and int(s["job_revision"]) == int(task["team_rev"])]
        if len(results) == 1:
            m = self.sessions.team_message(team["session_id"], results[0]["result_msg_id"])
            return self._finish(team, task["id"], results[0]["result_msg_id"], (m or {}).get("content", ""))
        if len(results) > 1:
            if not team["leader_key"]:
                return self._block(task["id"], "no_leader", "Nhóm chưa có trưởng nhóm để tổng hợp")
            ok = self._add_steps(team, task, [{"kind": "synthesize", "agent": team["leader_key"], "brief": "",
                                               "inputs": [s["result_msg_id"] for s in results]}])
            return None if ok else "team_blocked"
        return self._block(task["id"], "failed", "Không còn bước nào để chạy")

    async def _run_step(self, team: dict, task: dict, step: dict) -> Optional[str]:
        sid = step["step_id"]
        out = await self._turn(team, step["agent_key"], step["kind"], self._body(step, task), task=task, step=step,
                               reply_to=(self._source_id(task) or [None])[0], vet=self._vet_step)
        st = out["status"]
        if st == "cap":
            self.teams.requeue_step(sid)
            what = "lượt mỗi ngày của nhóm" if out["cap"] == "daily_turns" else "lượt mỗi việc"
            return self._block(task["id"], "cap_reached", f"Đã chạm trần {what}")
        if st == "busy_long":
            self.teams.requeue_step(sid)
            return self._block(task["id"], "agent_busy_long",
                               f"{self._name(team, step['agent_key'])} bận ở nhóm khác quá lâu")
        if st == "error":
            self.teams.finish_step(sid, "failed", note=out["error"])
            return self._block(task["id"], "failed", f"Lượt lỗi: {out['error']}")
        mid = out.get("message_id")
        if st in ("late_cancelled", "late"):
            self.teams.finish_step(sid, "cancelled", mid, False, "đến sau khi huỷ, không áp dụng")
            return None  # vòng run_job đọc lại trạng thái việc rồi dừng
        if st == "member_left":
            self.teams.finish_step(sid, "cancelled", mid, False, "thành viên đã rời nhóm")
            return self._recoordinate(team, task, step, "thành viên đã rời nhóm")
        if st == "old_revision":
            self.teams.finish_step(sid, "cancelled", mid, False, "theo yêu cầu cũ")
            return self._recoordinate(team, task, step, "yêu cầu đã sửa")
        if st == "leader_changed":
            self.teams.finish_step(sid, "cancelled", mid, False, "trưởng nhóm đã đổi")
            team = self._team(team["team_id"])
            if not team["leader_key"]:
                return self._block(task["id"], "no_leader", "Nhóm chưa có trưởng nhóm")
            self._coordinator_changed(team, task, team["leader_key"])
            ok = self._add_steps(team, task, [{"kind": step["kind"], "agent": team["leader_key"],
                                               "brief": step["brief"], "inputs": step["input_refs"]}])
            return None if ok else "team_blocked"
        # Đã áp dụng
        note = step.get("note") or ""
        if note.startswith("continues:"):
            prev = self.teams.step(note.split(":", 1)[1])
            prev_msg = self.sessions.team_message(team["session_id"], prev["result_msg_id"]) if prev and \
                prev.get("result_msg_id") else None
            if prev_msg and (prev_msg.get("meta") or {}).get("sha") == out["sha"]:
                self.teams.finish_step(sid, "done", mid, True, "không tiến triển")
                return self._block(task["id"], "no_progress", "Hai lượt liền nhau không có kết quả mới")
        kind = step["kind"]
        if kind == "plan":
            assigns = out["ops"]
            self.teams.finish_step(sid, "done", mid, True)
            if not assigns:
                return self._finish(team, task["id"], mid, out["text"])
            ok = self._add_steps(team, task, [{"kind": "work", "agent": a["agent"], "brief": a["brief"],
                                               "inputs": [mid]} for a in assigns])
            return None if ok else "team_blocked"
        if kind == "synthesize":
            self.teams.finish_step(sid, "done", mid, True)
            return self._finish(team, task["id"], mid, out["text"])
        # work, help
        helps = out["ops"]
        if helps:
            h = helps[0]
            ok = self._add_steps(team, task, [{"kind": "help", "agent": h["agent"], "brief": h["question"],
                                               "inputs": [mid], "parent": sid, "rev": step["job_revision"]}])
            self.teams.finish_step(sid, "waiting", mid, True)
            return None if ok else "team_blocked"
        self.teams.finish_step(sid, "done", mid, True)
        if step.get("parent_step"):
            parent = self.teams.step(step["parent_step"])
            if parent:
                ok = self._add_steps(team, task, [{"kind": parent["kind"], "agent": parent["agent_key"],
                                                   "brief": parent["brief"], "inputs": list(parent["input_refs"]) + [mid],
                                                   "parent": parent["parent_step"], "rev": parent["job_revision"]}])
                if not ok:
                    return "team_blocked"
                cont = self.teams.steps(task["id"])[-1]
                self.teams.set_step_status(parent["step_id"], "continued", "")
                self.teams.set_step_status(cont["step_id"], "queued", f"continues:{parent['step_id']}")
        return None

    async def dispatch_once(self, wait: bool = True) -> list:
        """Nhận việc đầu hàng của các nhóm còn chỗ chạy (spec 8.3). Pool riêng `max_parallel_teams` nhóm."""
        started = []
        self._jobs = {k: v for k, v in self._jobs.items() if not v.done()}
        busy_teams = {(self.tasks.get_task(k) or {}).get("team_id") for k in self._jobs}
        for team_id in self.tasks.teams_with_waiting():
            if len(self._jobs) >= self.max_parallel_teams:
                break
            if team_id in busy_teams:
                continue
            team = self.teams.get(team_id)
            if not team or team["status"] != "active":
                continue
            task = self.tasks.claim_team_next(team_id, self.worker_id,
                                              max_running=int(team["caps"]["running_jobs"]))
            if not task:
                continue
            first = self.start_job_steps(task["id"])
            if first == "no_leader":
                self._block(task["id"], "no_leader", "Nhóm chưa có trưởng nhóm")
                continue
            if first == "assignee_removed":
                self._block(task["id"], "assignee_removed", "Người được giao đã rời nhóm")
                continue
            started.append(task["id"])
            self._jobs[task["id"]] = asyncio.ensure_future(self.run_job(task["id"]))
            self._state(team_id)
        if wait:
            await self.wait_jobs()
        return started

    async def wait_jobs(self) -> None:
        """Chờ mọi việc đang chạy trong tiến trình này. Việc nào văng lỗi thì ném lại lỗi đầu tiên (không nuốt)."""
        errors = []
        while True:
            pending = [t for t in self._jobs.values() if not t.done()]
            if not pending:
                break
            for res in await asyncio.gather(*pending, return_exceptions=True):
                # Việc bị chủ huỷ giữa lượt (cancel_job) kết thúc bằng CancelledError: đó là kết cục đúng, không phải lỗi.
                if isinstance(res, BaseException) and not isinstance(res, asyncio.CancelledError):
                    errors.append(res)
        self._jobs = {}
        if errors:
            raise errors[0]

    async def resume_jobs(self, task_ids: list) -> None:
        for tid in task_ids:
            self._jobs[tid] = asyncio.ensure_future(self.run_job(tid))
        await self.wait_jobs()

    # ───────────── lệnh của chủ, phục hồi ─────────────

    def cancel_job(self, task_id: str, reason: str = "chủ nhóm huỷ") -> Optional[str]:
        """Huỷ việc (spec 7.6). Lượt đang gọi engine bị ngắt (tính một lần, `interrupted`); bước chưa chạy huỷ theo.
        Trả trạng thái trước khi huỷ, None nếu việc đã kết thúc hay không thuộc làn team."""
        prev = self.tasks.team_cancel(task_id, reason)
        if prev is None:
            return None
        job = self._jobs.get(task_id)
        try:
            me = asyncio.current_task()
        except RuntimeError:
            me = None
        if job is not None and not job.done() and job is not me:
            job.cancel()
        self.teams.cancel_open_steps(task_id, "việc đã huỷ")
        for s in self.teams.steps(task_id):
            if s["status"] == "running":
                self.teams.set_step_status(s["step_id"], "cancelled", "việc đã huỷ")
        task = self.tasks.get_task(task_id)
        if task:
            self._state(task["team_id"])
        return prev

    async def resume_team(self, team_id: str) -> None:
        """Nhóm tiếp tục sau tạm dừng: việc đang `team_running` của nhóm chạy tiếp từ điểm điều phối."""
        ids = [t["id"] for t in self.tasks.team_queue(team_id)["running"] if t["id"] not in self._jobs]
        for tid in ids:
            self._jobs[tid] = asyncio.ensure_future(self.run_job(tid))

    def unblock(self, task_id: str, action: str = "resume") -> bool:
        """Gỡ chặn: `retry` chạy lại bước lỗi hay bị ngắt (bước mới, lượt mới); `resume` cho chạy tiếp như cũ."""
        task = self.tasks.get_task(task_id)
        if not task or task["status"] != "team_blocked":
            return False
        if action == "retry":
            steps = self.teams.steps(task_id)
            last = next((s for s in reversed(steps) if s["status"] in ("failed", "interrupted")), None)
            if last:
                self.teams.add_step(task_id, task["team_id"], last["kind"], last["agent_key"], int(task["team_rev"]),
                                    last["brief"], last["input_refs"], last["parent_step"])
        return self.tasks.team_unblock(task_id) is not None

    def resume_no_leader(self, team_id: str) -> int:
        """Nhóm vừa có trưởng nhóm: các việc bị chặn `no_leader` về hàng chờ, đúng chỗ cũ."""
        n = 0
        for t in self.tasks.team_queue(team_id)["blocked"]:
            if t["block_kind"] == "no_leader" and self.tasks.team_unblock(t["id"]) is not None:
                n += 1
        if n:
            self._state(team_id)
        return n

    def remind_blocked(self, now: Optional[float] = None) -> int:
        """Việc bị chặn quá 24 giờ: một tin nhắc vào hộp thư cho mỗi lần bị chặn. Không gọi model."""
        now = self.clock() if now is None else float(now)
        sent = 0
        for t in self.tasks.team_tasks_by_status("team_blocked"):
            if now - float(t["updated_at"]) < REMIND_AFTER_S:
                continue
            mark = {"task_id": t["id"], "blocked_at": t["updated_at"]}
            if any(e["kind"] == "blocked_reminder" and e["after"] == mark for e in self.teams.events(t["team_id"], 500)):
                continue
            self.teams.log_event(t["team_id"], "blocked_reminder", "host", None, mark)
            self._notify(t["team_id"], f"Việc nhóm \"{t['title']}\" vẫn đang chờ anh xử lý: {t['block_reason']}")
            sent += 1
        return sent

    def recover(self) -> dict:
        """Sau restart (spec 8.6): lượt chưa tới mốc engine thì hoàn, bước về chờ, việc chạy tiếp; lượt đã qua mốc thì
        `interrupted` (tính một lần), bước `interrupted`, việc chặn với nút "Chạy lại bước". Không tự chạy lại."""
        interrupted_tasks = set()
        for t in self.teams.open_turns():
            self.teams.release_busy(t["agent_key"], t["turn_id"])
            if t["engine_at"] is None:
                self.teams.refund_turn(t["turn_id"])
                if t["step_id"]:
                    self.teams.requeue_step(t["step_id"])
            else:
                self.teams.settle_turn(t["turn_id"], "interrupted")
                if t["step_id"]:
                    self.teams.set_step_status(t["step_id"], "interrupted", "server khởi động lại giữa lượt")
                if t["task_id"]:
                    interrupted_tasks.add(t["task_id"])
        resumed, blocked = [], []
        for task in self.tasks.team_running_tasks():
            self.tasks.team_take_over(task["id"], self.worker_id)
            if task["id"] in interrupted_tasks:
                self._block(task["id"], "interrupted", "Server khởi động lại khi bước đang chạy")
                blocked.append(task["id"])
            else:
                resumed.append(task["id"])
        return {"resumed": resumed, "blocked": blocked}
