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
import threading
import time
from typing import Any, Awaitable, Callable, Optional

from team_store import REACTION_EMOJI, TeamError, TurnCapReached

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
REPLY_ROLES = ("leader_reply", "member_reply")
ROLE_LABEL = {
    "leader_reply": "Trưởng nhóm trả lời trò chuyện",
    "member_reply": "Thành viên trả lời trò chuyện",
    "plan": "Lập kế hoạch",
    "work": "Làm",
    "help": "Hỗ trợ",
    "synthesize": "Tổng hợp",
}
BUSY_LEASE_S = 900.0          # hạn khoá bận một lượt; tiến trình chết thì tự nhả
NEW_MSG_LIMIT = 20            # cửa sổ lịch sử trong khối nhóm (spec 11.2, review T1 R2)
NEW_MSG_CHARS = 8000
INPUT_CHARS = 4000            # mỗi đầu vào của bước
DECISION_LIMIT = 20           # sổ quyết định (spec 11.2)
DECISION_CHARS = 500
REMIND_AFTER_S = 24 * 3600    # nhắc việc bị chặn quá 24 giờ (spec 8.4)
FEEDBACK_LIMIT = 5            # khối phản hồi ở lượt kế (spec 14.4)
FEEDBACK_DAYS = 30
FEEDBACK_EXCERPT = 160
# Câu dặn cố định đi kèm khối phản hồi (spec 14.4 mục 3), nguyên văn.
FEEDBACK_NOTE = ("Emoji là cảm xúc của chủ nhóm, có thể về sự việc được kể; đừng coi là chấm điểm. Chỉ điều chỉnh theo "
                 "lý do chất lượng và góp ý chữ. Chưa rõ thì giữ cách làm.")
REASON_LABEL = {"on_point": "Đúng ý", "wrong_facts": "Sai dữ kiện", "missing": "Thiếu ý", "too_long": "Quá dài",
                "unclear": "Khó hiểu", "off_topic": "Lạc đề"}

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


async def run_io(fn: Callable, *args, undo: Optional[Callable[[Any], Any]] = None, **kwargs) -> Any:
    """Chạy một đơn vị I/O chặn (SQLite, file) ở luồng phụ, không chặn event loop (review T1, R5).

    Bị huỷ (kể cả huỷ lặp) khi luồng phụ còn đang ghi: KHÔNG bỏ đi giữa chừng. Chờ luồng phụ xong hẳn, chạy `undo(kết
    quả)` nếu có (vd. hoàn lượt vừa giữ chỗ, nhả khoá vừa lấy), rồi mới ném CancelledError. Nhờ vậy không có ghi dở,
    không nhả khoá trước khi việc ghi kết thúc, không có lượt giữ chỗ mồ côi."""
    fut = asyncio.ensure_future(asyncio.to_thread(fn, *args, **kwargs))
    cancelled = False
    while True:
        try:
            res = await asyncio.shield(fut)
            break
        except asyncio.CancelledError:
            if fut.done() and not fut.cancelled():
                try:
                    res = fut.result()
                except BaseException:  # noqa: BLE001
                    raise asyncio.CancelledError()
                cancelled = True
                break
            cancelled = True
        except BaseException:
            if cancelled:
                raise asyncio.CancelledError()
            raise
    if cancelled:
        if undo is not None:
            try:
                await run_io(undo, res)
            except asyncio.CancelledError:
                pass
            except Exception:  # noqa: BLE001
                pass
        raise asyncio.CancelledError()
    return res


class EngineUnavailable(RuntimeError):
    """Không dựng được engine cho lượt (cấu hình, provider chưa sẵn sàng): CHƯA gọi model, lượt được hoàn (R4)."""


class EngineOutcomeError(RuntimeError):
    """Engine đã được gọi nhưng kết cục không phải một câu trả lời chữ hợp lệ (R1). `kind`: final_error, auth,
    error_event, error_after_final, tool_call, no_final, empty. Lượt vẫn tính; bước thành lỗi để chủ Chạy lại."""

    def __init__(self, kind: str, detail: str = ""):
        super().__init__(f"{kind}: {detail}" if detail else kind)
        self.kind = kind
        self.detail = detail


OUTCOME_TEXT = {
    "final_error": "engine báo lỗi khi chạy",
    "auth": "lỗi đăng nhập của engine",
    "error_event": "engine báo lỗi",
    "error_after_final": "engine báo lỗi sau câu trả lời",
    "tool_call": "engine gọi công cụ trong lượt chỉ chữ",
    "no_final": "engine không trả câu trả lời cuối",
    "empty": "engine trả câu trả lời rỗng",
}


class TextOnlyOutcome:
    """Hợp đồng kết cục của một lượt CHỈ CHỮ, cùng luật với `_engine_outcome_pop` của lượt chat (pilot Resonance 4) và
    chặt hơn ở hai chỗ: lượt chỉ chữ không được gọi công cụ, và câu trả lời rỗng không phải sản phẩm.

    `note(ev)` cho từng sự kiện engine; `result()` trả {"text", "tokens_in", "tokens_out"} hay ném EngineOutcomeError.
    Sự kiện `error` có cờ `resume_failed` (mất mạch, engine đã tự mồi lại trong lượt) không tính là lỗi."""

    TOOL_EVENTS = ("tool_call", "tool_use", "tool_result")

    def __init__(self):
        self.final: Optional[dict] = None
        self.error: Optional[tuple] = None
        self.tokens_in: Optional[int] = None
        self.tokens_out: Optional[int] = None

    def note(self, ev: Any) -> None:
        if not isinstance(ev, dict):
            return
        et = ev.get("type")
        if et == "final":
            self.final = {"content": str(ev.get("content") or ""), "is_error": bool(ev.get("is_error")),
                          "subtype": str(ev.get("subtype") or ""),
                          "auth_refresh_race": bool(ev.get("auth_refresh_race"))}
        elif et == "usage":
            self.tokens_in = int(ev.get("input_tokens") or 0)
            self.tokens_out = int(ev.get("output_tokens") or 0)
        elif et in self.TOOL_EVENTS:
            if self.error is None:
                self.error = ("tool_call", str(ev.get("name") or ev.get("tool") or "")[:80])
        elif et == "error" and not ev.get("resume_failed"):
            kind = "error_after_final" if self.final is not None else "error_event"
            if self.error is None:
                self.error = (kind, str(ev.get("content") or "")[:300])

    def result(self) -> dict:
        if self.error is not None:
            raise EngineOutcomeError(*self.error)
        f = self.final
        if f is None:
            raise EngineOutcomeError("no_final")
        if f["auth_refresh_race"]:
            raise EngineOutcomeError("auth", f["subtype"])
        if f["is_error"]:
            raise EngineOutcomeError("final_error", f["subtype"] or f["content"][:200])
        if not f["content"].strip():
            raise EngineOutcomeError("empty")
        return {"text": f["content"], "tokens_in": self.tokens_in, "tokens_out": self.tokens_out}


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
        self._loop: Any = None
        self._loop_thread: Optional[int] = None
        # Pool chung của tiến trình (review T1 R8): task_id -> team_id của việc đang giữ chỗ. Đọc, ghi trong `_pool_lock`.
        self._pool: dict[str, str] = {}
        self._pool_lock = threading.Lock()
        # Khoá chấp nhận đầu ra (R3): kiểm "đầu ra còn hợp lệ" và ghi bài học bền nằm trong cùng một khoá với các thao
        # tác làm đầu ra hết hợp lệ (bỏ thành viên, đổi trưởng nhóm, huỷ, sửa yêu cầu, xoá agent). Không có khe nào giữa
        # lúc kiểm và lúc ghi để một thao tác như vậy chen vào.
        self.accept_lock = threading.RLock()

    # ───────────── tiện ích ─────────────

    async def _io(self, fn: Callable, *args, undo: Optional[Callable[[Any], Any]] = None, **kwargs) -> Any:
        """I/O chặn ra luồng phụ (R5). Nhớ event loop để phần chạy ở luồng phụ đẩy gói WS về đúng loop."""
        self._bind_loop()
        return await run_io(fn, *args, undo=undo, **kwargs)

    def _bind_loop(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._loop, self._loop_thread = loop, threading.get_ident()

    def _on_loop(self, fn: Callable, *args) -> None:
        """Gọi `fn` trên event loop: ngay nếu đang ở luồng của loop (hay chưa có loop), còn từ luồng phụ thì xếp hàng
        bằng call_soon_threadsafe (gói WS, hộp thư, huỷ task asyncio đều là việc của loop)."""
        loop = self._loop
        if loop is None or threading.get_ident() == self._loop_thread or loop.is_closed():
            fn(*args)
            return
        try:
            loop.call_soon_threadsafe(fn, *args)
        except RuntimeError:
            fn(*args)

    def _publish(self, event: dict) -> None:
        if self._publish_fn:
            def go(ev=event):
                try:
                    self._publish_fn(ev)
                except Exception:
                    pass
            self._on_loop(go)

    def _notify(self, team_id: str, text: str) -> None:
        if self._notify_fn:
            def go():
                try:
                    self._notify_fn(team_id, text)
                except Exception:
                    pass
            self._on_loop(go)

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
        ref = str(ref or "").strip().lstrip("@").strip().casefold()
        if not ref:
            return None
        # Model hay gọi thành viên bằng TÊN hiển thị ("Minh") thay vì mã: so cả tên, không phân biệt hoa thường.
        for m in self.teams.members(team["team_id"]):
            info = self.agent_info(team["brain_id"], m["agent_key"]) or {}
            names = (m["agent_key"], m["slug_at_join"], info.get("slug"), info.get("name"))
            if ref in {str(n).strip().casefold() for n in names if n}:
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
        if self.sessions.get_session(sid) is None:
            # Kho phiên đã khôi phục về trước khi có nhóm (R6): không ghi tin vào phiên không còn.
            raise TeamError("phiên trò chuyện của nhóm không còn (kho phiên đã khôi phục về bản cũ)")
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
        if team["status"] == "archived":
            raise TeamError("nhóm đã lưu trữ, không tạo việc mới được")
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

    # ───────────── phản hồi (T2, spec mục 14) ─────────────

    def react(self, team_id: str, message_id: int, value: Optional[str], *, reasons: Optional[list] = None,
              comment: str = "", nonce: str) -> Optional[dict]:
        """Chủ nhóm thả cảm xúc, chọn lý do, viết góp ý trên một tin của agent. CHỈ ghi kho và đẩy gói WS: không đổi
        việc, goal hay hàng đợi, không đánh thức agent, không mở lượt, không gọi model (spec 14.4 mục 2)."""
        team = self._team(team_id)
        sid = team["session_id"]
        msg = self.sessions.team_message(sid, int(message_id))
        if not msg or msg.get("author_kind") != "agent" or not msg.get("author_ref"):
            raise TeamError("chỉ thả cảm xúc được trên tin của trợ lý trong nhóm này")
        state = self.teams.set_reaction(team_id=team_id, session_id=sid, message_id=int(message_id),
                                        agent_key=msg["author_ref"], task_id=msg.get("task_id"),
                                        content_sha=_sha(msg.get("content") or ""), value=value, reasons=reasons,
                                        comment=comment, nonce=nonce)
        self._publish({"type": "team_message", "team_id": team_id, "message": dict(msg, reaction=state)})
        return state

    def _feedback_lines(self, team: dict, agent_key: str) -> list:
        """Khối "Phản hồi gần đây của chủ nhóm" cho lượt kế của CHÍNH agent này trong CHÍNH nhóm này: tối đa 5 mục trong
        30 ngày, emoji gốc kèm tên loại, lý do, góp ý, đoạn trích. Mục đã bỏ không còn trong kho nên tự rời khối."""
        rows = self.teams.recent_feedback(team["team_id"], agent_key, self.clock() - FEEDBACK_DAYS * 86400,
                                          FEEDBACK_LIMIT * 3)
        out = []
        for fb in rows:
            if len(out) >= FEEDBACK_LIMIT:
                break
            msg = self.sessions.team_message(team["session_id"], fb["message_id"])
            if msg is None:
                continue   # tin không còn (phiên bị xoá bớt): phản hồi không còn ngữ cảnh, bỏ
            excerpt = re.sub(r"\s+", " ", str(msg.get("content") or "")).strip()
            if len(excerpt) > FEEDBACK_EXCERPT:
                excerpt = excerpt[:FEEDBACK_EXCERPT] + "..."
            parts = [f'- [#{fb["message_id"]}] "{excerpt}"']
            if fb["value"]:
                parts.append(f"cảm xúc: {REACTION_EMOJI.get(fb['value'], '')} ({fb['value']})")
            if fb["reasons"]:
                parts.append("lý do: " + ", ".join(REASON_LABEL.get(x, x) for x in fb["reasons"]))
            if fb["comment"]:
                # Một dòng mỗi mục: góp ý nhiều dòng không được giả thành đầu mục mới của khối ngữ cảnh.
                comment = re.sub(r"\s+", " ", fb["comment"]).strip()
                parts.append(f'góp ý: "{comment}"')
            out.append(" · ".join(parts))
        return out

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
        # Lượt nhóm không nối tiếp mạch hội thoại của engine (mỗi lượt một lời gọi mới), nên lịch sử phải nằm trong
        # prompt: cửa sổ tin GẦN NHẤT của chính phiên nhóm này, gồm cả tin cũ của chủ và câu trả lời trước của các
        # thành viên (kể cả của bạn), có trần số tin và số ký tự (review T1, R2). Tin sau lượt trước của bạn có nhãn "mới".
        after = self.sessions.last_message_id_by(sid, agent_key)
        recent = self.sessions.team_messages_after(sid, 0, NEW_MSG_LIMIT)
        rendered, size = [], 0
        for m in reversed(recent):
            who = ("Chủ nhóm" if m["author_kind"] == "owner" else
                   self._name(team, m["author_ref"]) if m["author_kind"] == "agent" else "Hệ thống")
            if m["author_kind"] == "agent" and m["author_ref"] == agent_key:
                who += " (bạn)"
            mark = " mới" if int(m["id"]) > int(after) else ""
            row = f"[#{m['id']}{mark} {who}] {m['content']}"
            if size + len(row) > NEW_MSG_CHARS:
                break
            rendered.append(row)
            size += len(row)
        if rendered:
            lines.append(f"\n## Lịch sử gần đây của nhóm (tối đa {NEW_MSG_LIMIT} tin, cũ trước; "
                         "\"mới\" là tin sau lượt trước của bạn)")
            lines.extend(reversed(rendered))
        feedback = self._feedback_lines(team, agent_key)
        if feedback:
            lines.append("\n## Phản hồi gần đây của chủ nhóm (về tin của bạn trong nhóm này)")
            lines.extend(feedback)
            lines.append(FEEDBACK_NOTE)
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
        holder = await self._io(self.teams.busy_of, agent_key)
        if holder and holder["team_id"] != team["team_id"]:
            self._state(team["team_id"])
        try:
            await asyncio.wait_for(lock.acquire(), timeout=wait)
        except (asyncio.TimeoutError, TimeoutError):
            return False
        deadline = time.monotonic() + wait
        try:
            # Bị huỷ khi luồng phụ đang lấy dòng khoá: run_io chờ nó xong rồi nhả đúng dòng vừa lấy (undo).
            while not await self._io(self.teams.acquire_busy, agent_key, team["team_id"], turn_id,
                                     lease_s=BUSY_LEASE_S,
                                     undo=lambda got: got and self.teams.release_busy(agent_key, turn_id)):
                if time.monotonic() > deadline:
                    lock.release()
                    return False
                await asyncio.sleep(0.2)
        except BaseException:
            # Bị huỷ (hay kho lỗi) giữa lúc chờ dòng khoá trong kho: nhả khoá trong tiến trình, kẻo agent kẹt mãi.
            if lock.locked():
                lock.release()
            raise
        return True

    async def _release(self, agent_key: str, turn_id: str) -> None:
        """Nhả dòng khoá trong kho (luồng phụ, chờ xong hẳn kể cả khi bị huỷ) rồi mới nhả khoá trong tiến trình."""
        try:
            await self._io(self.teams.release_busy, agent_key, turn_id)
        finally:
            lock = self._locks.get(agent_key)
            if lock is not None and lock.locked():
                lock.release()

    def _reserve(self, team: dict, task_id: Optional[str], step_id: Optional[str], agent_key: str,
                 role: str) -> str:
        """Kiểm trần và giữ chỗ trong MỘT giao dịch của kho (R5): không có khe giữa đếm và ghi."""
        return self.teams.reserve_turn(team["team_id"], task_id, step_id, agent_key, role,
                                       daily_cap=int(team["caps"]["daily_turns"]), day_start=self._day_start(),
                                       task_cap=int(team["caps"]["task_turns"]) if task_id else None)

    def _refund_if_unmarked(self, turn_id: str) -> None:
        """Hoàn lượt chưa tới mốc gọi engine, đúng một lần. Lượt đã qua mốc thì để nguyên (đã tính)."""
        t = self.teams.turn(turn_id) or {}
        if t and t.get("engine_at") is None and t.get("status") == "reserved":
            self.teams.refund_turn(turn_id)

    def _prepare(self, team_id: str, agent_key: str, role: str, task: Optional[dict], step: Optional[dict],
                 body: str, turn_id: str) -> dict:
        """Phần đồng bộ trước lời gọi engine (luồng phụ): kiểm còn hợp lệ, đọc agent, dựng engine, dựng prompt."""
        pre = self._still_valid(team_id, agent_key, role, task, step)
        team = self._team(team_id)
        info = self.agent_info(team["brain_id"], agent_key)
        if pre == "done" and info is None:
            pre = "member_left"
        # Tạm dừng hay lưu trữ nhóm: lượt trả lời chưa tới engine thì không chạy (spec 11.4). Lượt đã chạy thì chạy hết;
        # bước của việc dừng ở điểm điều phối trong run_job.
        if pre == "done" and role in REPLY_ROLES and team.get("status") != "active":
            pre = "team_paused"
        if pre != "done":
            return {"pre": pre}
        engine, model, fn = self.engine_for(team, agent_key, role)
        req = {"team_id": team_id, "brain": team["brain_id"], "agent_key": agent_key, "role": role,
               "system": str(info.get("system") or ""),
               "prompt": self._context(team, agent_key, role, task, step) + "\n\n" + body,
               "thread": f"teammate:{team_id}:{agent_key}", "task_id": task["id"] if task else None,
               "step_id": step["step_id"] if step else None, "turn_id": turn_id, "tools": []}
        return {"pre": "done", "engine": str(engine or ""), "model": str(model or ""), "fn": fn, "req": req}

    async def _turn(self, team: dict, agent_key: str, role: str, body: str, *, task: Optional[dict] = None,
                    step: Optional[dict] = None, reply_to=None, vet=None) -> dict:
        """Một lượt của thành viên (spec 9.1): giữ chỗ (kèm kiểm trần), khoá bận, kiểm, dựng engine, mốc gọi engine,
        gọi, kiểm kết cục, chấp nhận đầu ra (kiểm muộn + ghi bài học), đăng tin. Mọi I/O chặn chạy ở luồng phụ (R5).

        Mốc gọi engine (R4): engine thật (`fn.marks_engine`) tự gọi `req["engine_started"]` SAU khi đã dựng xong engine,
        ngay trước lời gọi model; lỗi trước mốc đó hoàn lượt đúng một lần. Engine không khai báo (engine giả cũ) thì mốc
        ghi ngay trước lời gọi như trước."""
        team_id = team["team_id"]
        task_id = task["id"] if task else None
        step_id = step["step_id"] if step else None
        try:
            turn_id = await self._io(self._reserve, team, task_id, step_id, agent_key, role,
                                     undo=self.teams.refund_turn)
        except TurnCapReached as cap:
            return {"status": "cap", "cap": cap.cap}
        try:
            got = await self._acquire(team, agent_key, turn_id)
        except BaseException:
            await self._io(self._refund_if_unmarked, turn_id)
            raise
        if not got:
            await self._io(self._refund_if_unmarked, turn_id)
            return {"status": "busy_long", "turn_id": turn_id}
        marked = False
        try:
            try:
                prep = await self._io(self._prepare, team_id, agent_key, role, task, step, body, turn_id)
            except BaseException:
                # Lỗi bất ngờ (kho bận, dựng engine hỏng) hay bị huỷ TRƯỚC mốc gọi engine: hoàn lượt, không tính.
                try:
                    await self._io(self._refund_if_unmarked, turn_id)
                except Exception:  # noqa: BLE001
                    pass
                raise
            if prep["pre"] != "done":
                await self._io(self._refund_if_unmarked, turn_id)
                return {"status": prep["pre"], "before_engine": True, "turn_id": turn_id}
            fn, req = prep["fn"], prep["req"]

            async def engine_started(engine: Optional[str] = None, model: Optional[str] = None) -> None:
                nonlocal marked
                if not marked:
                    await self._io(self.teams.mark_engine, turn_id, str(engine or prep["engine"]),
                                   str(model or prep["model"]))
                    marked = True

            req["engine_started"] = engine_started
            if not getattr(fn, "marks_engine", False):
                await engine_started()
            try:
                res = await fn(req)
            except asyncio.CancelledError:
                if marked:
                    await self._io(self.teams.settle_turn, turn_id, "interrupted")
                else:
                    await self._io(self._refund_if_unmarked, turn_id)
                raise
            except Exception as ex:  # noqa: BLE001
                if not marked:
                    # Chưa tới mốc gọi model (engine chưa dựng được): hoàn đúng một lần, bước thành lỗi để Chạy lại.
                    await self._io(self._refund_if_unmarked, turn_id)
                    return {"status": "error", "error": f"Không dựng được engine: {str(ex)[:300]}",
                            "before_engine": True, "turn_id": turn_id}
                await self._io(self.teams.settle_turn, turn_id, "error")
                msg = (OUTCOME_TEXT.get(ex.kind, ex.kind) + (f" ({ex.detail})" if ex.detail else "")
                       if isinstance(ex, EngineOutcomeError) else str(ex))
                return {"status": "error", "error": msg[:500], "turn_id": turn_id}
            if not marked:
                await engine_started()
            res = res or {}
            await self._io(self.teams.settle_turn, turn_id, "ok", res.get("tokens_in"), res.get("tokens_out"),
                           res.get("cost_usd"))
        finally:
            await self._release(agent_key, turn_id)
        return await self._io(self._accept, team_id, agent_key, role, task, step, turn_id, res, reply_to, vet)

    def _accept(self, team_id: str, agent_key: str, role: str, task: Optional[dict], step: Optional[dict],
                turn_id: str, res: dict, reply_to, vet) -> dict:
        """Pha chấp nhận đầu ra (luồng phụ). Kiểm còn hợp lệ và ghi bài học bền nằm trong cùng `accept_lock` (R3): đầu
        ra đến muộn (thành viên rời, huỷ, sửa yêu cầu, đổi trưởng nhóm, agent đã xoá hay tạo lại cùng slug) chỉ là bằng
        chứng trên tin nhóm, không ghi gì vào bộ nhớ agent. Bài học ghi đúng một lần mỗi lượt (`claim_commit`)."""
        raw = str(res.get("text") or "")
        clean, ops, notes = parse_directives(raw)
        commit = res.get("commit")
        with self.accept_lock:
            status = self._still_valid(team_id, agent_key, role, task, step)
            applied = status == "done"
            # Bước của việc nhóm: bài học ghi ở pha ÁP DỤNG (`_apply_step`), nơi kiểm lại hiệu lực lần cuối trong cùng
            # khoá (review T1 R7). Lượt trò chuyện không có pha áp dụng: ghi ở đây.
            if applied and step is None:
                self._commit_once(turn_id, commit, notes)
        allowed = OPS_BY_ROLE.get(role, set())
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
        held = list(res.get("lessons") or [])
        if held and not applied:
            # Bằng chứng: bài học của đầu ra không được chấp nhận nằm trên tin, KHÔNG vào bộ nhớ agent.
            meta["held_lessons"] = held[:5]
        if task:
            meta["revision"] = step["job_revision"] if step else task["team_rev"]
        meta.update(extra)
        mid = self._post(self._team(team_id), clean or "(không có nội dung)", author_kind="agent", author_ref=agent_key,
                         reply_to=reply_to, task_id=task["id"] if task else None,
                         step_id=step["step_id"] if step else None, meta=meta)
        return {"status": status, "applied": applied, "ops": kept, "notes": notes, "message_id": mid,
                "text": clean, "sha": meta["sha"], "turn_id": turn_id, "extra": extra,
                "commit": commit if applied and step is not None else None, "lessons": held}

    def _commit_once(self, turn_id: str, commit: Any, notes: list) -> None:
        """Ghi bài học của lượt đúng một lần (gọi trong `accept_lock`, sau khi đã kiểm đầu ra còn hiệu lực)."""
        if callable(commit) and self.teams.claim_commit(turn_id):
            try:
                commit()
            except Exception as ex:  # noqa: BLE001
                notes.append(f"Không ghi được bài học của lượt: {type(ex).__name__}")

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
        assignees = self._assignees(task)
        if assignees:
            # Việc @ trực tiếp: chỉ chặn khi chính NGƯỜI ĐƯỢC GIAO rời nhóm (người hỗ trợ rời thì làm lại chuỗi). Mọi người
            # được giao còn thiếu kết quả ở bản hiện tại đều làm lại từ đầu, không chỉ người có lượt vừa bị bỏ.
            gone = [a for a in assignees if not self.teams.is_active_member(team["team_id"], a)]
            if step["agent_key"] in gone or len(gone) == len(assignees):
                return self._block(task["id"], "assignee_removed", "Người được giao đã rời nhóm")
            have = {s["agent_key"] for s in self.teams.steps(task["id"])
                    if s["kind"] == "work" and s["status"] == "done" and s["applied"] and not s["parent_step"]
                    and int(s["job_revision"]) == int(task["team_rev"])}
            specs = [{"kind": "work", "agent": a, "brief": task["intent"], "inputs": self._source_id(task)}
                     for a in assignees if a not in gone and a not in have]
            if not specs:
                return None
            return None if self._add_steps(team, task, specs) else "team_blocked"
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

    def _finish(self, team: dict, task_id: str, msg_id: int, text: str, rev: int) -> Optional[str]:
        """Chốt việc bằng kết quả của bản yêu cầu `rev` (CAS ở kho, review T1 R7). Yêu cầu đã sửa sang bản khác thì kết
        quả này chỉ là bằng chứng: không chốt, việc làm lại theo bản mới."""
        if self.tasks.team_finish(task_id, text, expected_rev=rev) is not None:
            self.sessions.update_team_message_meta(team["session_id"], msg_id, {"job_result": True})
            self._publish({"type": "team_message", "team_id": team["team_id"],
                           "message": self.sessions.team_message(team["session_id"], msg_id)})
            self._state(team["team_id"])
            return "done"
        cur = self.tasks.get_task(task_id)
        if cur and cur["status"] == "team_running" and int(cur["team_rev"]) != int(rev):
            self._supersede(team, msg_id, "old_revision")
            return self._recoordinate(team, cur, {"agent_key": ""}, "yêu cầu đã sửa")
        return None

    def _supersede(self, team: dict, msg_id: Optional[int], status: str) -> None:
        """Tin kết quả đã đăng nhưng hết hiệu lực trước khi áp dụng: đổi nhãn thành bằng chứng (applied=false)."""
        if not msg_id:
            return
        self.sessions.update_team_message_meta(team["session_id"], msg_id,
                                               {"status": status, "applied": False, "superseded": True})
        self._publish({"type": "team_message", "team_id": team["team_id"],
                       "message": self.sessions.team_message(team["session_id"], msg_id)})

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
            # Trưởng nhóm CÓ giao mà mọi lệnh giao đều hỏng: không được coi kế hoạch là kết quả việc.
            return kept, ({"assign_dropped": len(ops)} if ops and not kept else {})
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
        """Chạy các bước của một việc `team_running` tới khi xong, bị chặn, bị huỷ hay nhóm tạm dừng.

        Lỗi bất ngờ (kho bận, lỗi mã) không được để việc nằm `team_running` không ai chạy và đóng băng hàng của nhóm:
        bước đang chạy thành lỗi, việc bị chặn `failed` kèm lý do, có tin hộp thư; chủ bấm Chạy lại bước."""
        try:
            return await self._run_job_steps(task_id)
        except asyncio.CancelledError:
            raise
        except Exception as ex:  # noqa: BLE001
            try:
                return await self._io(self._fail_job, task_id, ex)
            except Exception:  # noqa: BLE001
                return "error"

    def _fail_job(self, task_id: str, ex: BaseException) -> str:
        for s in self.teams.steps(task_id):
            if s["status"] == "running":
                self.teams.finish_step(s["step_id"], "failed", note=f"lỗi nội bộ: {type(ex).__name__}")
        return self._block(task_id, "failed", f"Lỗi nội bộ khi chạy việc: {type(ex).__name__}: {str(ex)[:200]}")

    async def _run_job_steps(self, task_id: str) -> str:
        while True:
            act = await self._io(self._job_tick, task_id)
            if act[0] == "return":
                return act[1]
            if act[0] == "run":
                res = await self._run_step(*act[1:])
                if res:
                    return res

    def _job_tick(self, task_id: str) -> tuple:
        """Một điểm điều phối của việc (luồng phụ): ("return", kết quả), ("continue",) hay ("run", team, task, step).
        Chạy trong `accept_lock` (review T1 R7): đọc trạng thái, chốt việc hay thêm bước không xen được với sửa yêu cầu,
        huỷ, bỏ thành viên, đổi trưởng nhóm."""
        with self.accept_lock:
            return self._job_tick_locked(task_id)

    def _job_tick_locked(self, task_id: str) -> tuple:
        task = self.tasks.get_task(task_id)
        if not task or task["status"] != "team_running":
            if task and task["status"] == "cancelled":
                self.teams.cancel_open_steps(task_id, "việc đã huỷ")
            return ("return", task["status"] if task else "missing")
        team = self._team(task["team_id"])
        if team["status"] == "archived":
            # Lưu trữ = tạm dừng + huỷ việc (spec 11.4): việc đang chạy dừng ở điểm điều phối này (chính task này, nên
            # không huỷ task asyncio).
            self._cancel_records(task_id, "nhóm đã lưu trữ")
            return ("return", "cancelled")
        if team["status"] != "active":
            return ("return", "paused")
        self.tasks.team_heartbeat(task_id, self.worker_id)
        step = self.teams.next_queued_step(task_id)
        if step is None:
            res = self._after_steps(team, task)
            return ("return", res) if res else ("continue",)
        if step["kind"] in ("plan", "synthesize") and step["agent_key"] != team["leader_key"]:
            self.teams.set_step_status(step["step_id"], "cancelled", "trưởng nhóm đã đổi")
            if not team["leader_key"]:
                return ("return", self._block(task_id, "no_leader", "Nhóm chưa có trưởng nhóm"))
            self._coordinator_changed(team, task, team["leader_key"])
            if not self._add_steps(team, task, [{"kind": step["kind"], "agent": team["leader_key"],
                                                 "brief": step["brief"], "inputs": step["input_refs"]}]):
                return ("return", "team_blocked")
            return ("continue",)
        if not self.teams.claim_step(step["step_id"]):
            return ("continue",)
        return ("run", team, task, step)

    def _after_steps(self, team: dict, task: dict) -> Optional[str]:
        """Hết bước chờ: một kết quả thì xong; nhiều kết quả thì trưởng nhóm tổng hợp; không có gì thì chặn."""
        steps = self.teams.steps(task["id"])
        results = [s for s in steps if s["kind"] == "work" and s["status"] == "done" and s["applied"]
                   and int(s["job_revision"]) == int(task["team_rev"])]
        if len(results) == 1:
            m = self.sessions.team_message(team["session_id"], results[0]["result_msg_id"])
            return self._finish(team, task["id"], results[0]["result_msg_id"], (m or {}).get("content", ""),
                                int(results[0]["job_revision"]))
        if len(results) > 1:
            if not team["leader_key"]:
                return self._block(task["id"], "no_leader", "Nhóm chưa có trưởng nhóm để tổng hợp")
            ok = self._add_steps(team, task, [{"kind": "synthesize", "agent": team["leader_key"], "brief": "",
                                               "inputs": [s["result_msg_id"] for s in results]}])
            return None if ok else "team_blocked"
        return self._block(task["id"], "failed", "Không còn bước nào để chạy")

    async def _run_step(self, team: dict, task: dict, step: dict) -> Optional[str]:
        out = await self._turn(team, step["agent_key"], step["kind"], self._body(step, task), task=task, step=step,
                               reply_to=(self._source_id(task) or [None])[0], vet=self._vet_step)
        return await self._io(self._apply_step, team, task, step, out)

    def _apply_step(self, team: dict, task: dict, step: dict, out: dict) -> Optional[str]:
        """Áp kết cục một lượt vào bước và việc (luồng phụ), trong `accept_lock` (review T1 R7).

        Giữa pha chấp nhận và pha này có một khe (hai lần vào luồng phụ): chủ có thể sửa yêu cầu, huỷ, bỏ thành viên hay
        đổi trưởng nhóm. Vì vậy hiệu lực được kiểm LẠI ở đây, trong cùng khoá với các thao tác đó, ngay trước khi áp tác
        động (hoàn tất bước, thêm bước, chốt việc). Hết hiệu lực thì tin kết quả thành bằng chứng và đi đúng nhánh đến
        muộn. Chốt việc còn có CAS revision ở kho (`team_finish(expected_rev=...)`)."""
        with self.accept_lock:
            if out.get("status") == "done" and out.get("applied"):
                now = self._still_valid(team["team_id"], step["agent_key"], step["kind"], task, step)
                if now != "done":
                    self._supersede(team, out.get("message_id"), now)
                    out = dict(out, status=now, applied=False, ops=[], commit=None)
                else:
                    self._commit_once(out.get("turn_id") or "", out.get("commit"), out.setdefault("notes", []))
            return self._apply_step_locked(team, task, step, out)

    def _apply_step_locked(self, team: dict, task: dict, step: dict, out: dict) -> Optional[str]:
        sid = step["step_id"]
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
                # Không áp dụng và để ở trạng thái lỗi: "Chạy lại bước" chạy lại đúng bước này; không có kết quả lặp nào
                # được coi là kết quả việc.
                self.teams.finish_step(sid, "failed", mid, False, "không tiến triển")
                return self._block(task["id"], "no_progress", "Hai lượt liền nhau không có kết quả mới")
        kind = step["kind"]
        if kind == "plan":
            assigns = out["ops"]
            if not assigns and (out.get("extra") or {}).get("assign_dropped"):
                self.teams.finish_step(sid, "failed", mid, False, "không giao được cho ai")
                return self._block(task["id"], "failed", "Kế hoạch giao việc cho người không có trong nhóm")
            self.teams.finish_step(sid, "done", mid, True)
            if not assigns:
                return self._finish(team, task["id"], mid, out["text"], int(step["job_revision"]))
            ok = self._add_steps(team, task, [{"kind": "work", "agent": a["agent"], "brief": a["brief"],
                                               "inputs": [mid]} for a in assigns])
            return None if ok else "team_blocked"
        if kind == "synthesize":
            self.teams.finish_step(sid, "done", mid, True)
            return self._finish(team, task["id"], mid, out["text"], int(step["job_revision"]))
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
        """Nhận việc đầu hàng của các nhóm còn chỗ chạy (spec 8.3). Pool riêng `max_parallel_teams` nhóm.

        Tính chỗ trống, nhận việc và giữ chỗ trong pool là MỘT đoạn găng (`_claim_batch`, khoá `_pool_lock`, luồng phụ),
        nên hai lần đánh thức đồng thời không cùng nhận một chỗ trống (review T1 R8). Model chạy ngoài khoá. Bị huỷ hay
        lỗi giữa lúc nhận và lúc đăng ký task thì việc vừa nhận về lại hàng chờ và trả chỗ."""
        self._jobs = {k: v for k, v in self._jobs.items() if not v.done()}
        claimed = await self._io(self._claim_batch, undo=self._unclaim)
        for task_id, team_id in claimed:
            self._start_job(task_id)
            self._state(team_id)
        if wait:
            await self.wait_jobs()
        return [tid for tid, _ in claimed]

    def _claim_batch(self) -> list:
        with self._pool_lock:
            slots = self.max_parallel_teams - len(self._pool)
            busy_teams = set(self._pool.values())
            out: list = []
            current: Optional[str] = None   # việc đã nhận nhưng chưa xong bước đầu (lỗi ở đây cũng phải trả về hàng)
            try:
                for team_id in self.tasks.teams_with_waiting():
                    if len(out) >= slots:
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
                    current = task["id"]
                    first = self.start_job_steps(task["id"])
                    current = None
                    if first == "no_leader":
                        self._block(task["id"], "no_leader", "Nhóm chưa có trưởng nhóm")
                        continue
                    if first == "assignee_removed":
                        self._block(task["id"], "assignee_removed", "Người được giao đã rời nhóm")
                        continue
                    self._pool[task["id"]] = team_id
                    busy_teams.add(team_id)
                    out.append((task["id"], team_id))
            except BaseException:
                # Lỗi giữa chừng: việc đã nhận trong lượt này (kể cả việc đang tạo bước đầu) về hàng chờ, trả chỗ.
                for tid in [x for x, _ in out] + ([current] if current else []):
                    self._pool.pop(tid, None)
                    try:
                        self.tasks.team_requeue(tid)
                    except Exception:  # noqa: BLE001
                        pass
                raise
            return out

    def _unclaim(self, claimed: list) -> None:
        """Hoàn tác `_claim_batch` khi dispatch bị huỷ trước lúc đăng ký task: việc về hàng chờ, trả chỗ."""
        with self._pool_lock:
            for tid, _ in claimed:
                self._pool.pop(tid, None)
                self.tasks.team_requeue(tid)

    def _start_job(self, task_id: str, team_id: Optional[str] = None) -> None:
        """Tạo task asyncio cho một việc đã giữ chỗ trong pool; xong (kể cả lỗi, huỷ) thì trả chỗ."""
        if team_id is not None:
            with self._pool_lock:
                self._pool.setdefault(task_id, team_id)
        job = asyncio.ensure_future(self.run_job(task_id))
        self._jobs[task_id] = job
        job.add_done_callback(lambda _j, tid=task_id: self._pool_release(tid, _j))

    def _pool_release(self, task_id: str, job: Any) -> None:
        with self._pool_lock:
            if self._jobs.get(task_id) in (None, job):
                self._pool.pop(task_id, None)

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
            self._start_job(tid, "")
        await self.wait_jobs()

    # ───────────── lệnh của chủ, phục hồi ─────────────

    def cancel_job(self, task_id: str, reason: str = "chủ nhóm huỷ") -> Optional[str]:
        """Huỷ việc (spec 7.6). Lượt đang gọi engine bị ngắt (tính một lần, `interrupted`); bước chưa chạy huỷ theo.
        Trả trạng thái trước khi huỷ, None nếu việc đã kết thúc hay không thuộc làn team. Gọi được từ luồng phụ: phần
        ghi kho chạy ngay, phần huỷ task asyncio xếp về event loop."""
        prev = self._cancel_records(task_id, reason)
        if prev is not None:
            self._on_loop(self._cancel_task, task_id)
        return prev

    def _cancel_records(self, task_id: str, reason: str) -> Optional[str]:
        # Cùng khoá với pha chấp nhận đầu ra (R3): lượt đang về không thể vừa được chấp nhận vừa bị huỷ.
        with self.accept_lock:
            prev = self.tasks.team_cancel(task_id, reason)
            if prev is None:
                return None
            self.teams.cancel_open_steps(task_id, "việc đã huỷ")
            for s in self.teams.steps(task_id):
                if s["status"] == "running":
                    self.teams.set_step_status(s["step_id"], "cancelled", "việc đã huỷ")
        task = self.tasks.get_task(task_id)
        if task:
            self._state(task["team_id"])
        return prev

    def _cancel_task(self, task_id: str) -> None:
        job = self._jobs.get(task_id)
        try:
            me = asyncio.current_task()
        except RuntimeError:
            me = None
        if job is not None and not job.done() and job is not me:
            job.cancel()

    def cancel_idle_running(self, team_id: str, reason: str) -> int:
        """Huỷ việc `team_running` của nhóm mà tiến trình này không còn chạy (đã dừng ở điểm điều phối khi tạm dừng).
        Việc còn đang chạy thì tự dừng ở điểm điều phối kế tiếp (run_job thấy nhóm đã lưu trữ)."""
        n = 0
        for t in self.tasks.team_queue(team_id)["running"]:
            job = self._jobs.get(t["id"])
            if (job is None or job.done()) and self.cancel_job(t["id"], reason) is not None:
                n += 1
        return n

    async def resume_team(self, team_id: str) -> None:
        """Nhóm tiếp tục sau tạm dừng: việc đang `team_running` của nhóm chạy tiếp từ điểm điều phối."""
        # Việc đã dừng ở điểm điều phối vẫn còn trong `_jobs` (đã xong) tới lần điều phối sau: chỉ bỏ qua việc CÒN chạy.
        running = await self._io(lambda: [t["id"] for t in self.tasks.team_queue(team_id)["running"]])
        ids = [tid for tid in running if tid not in self._jobs or self._jobs[tid].done()]
        for tid in ids:
            self._start_job(tid, team_id)

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
            self._notify(t["team_id"], f"Việc nhóm \"{t['title']}\" vẫn đang chờ bạn xử lý: {t['block_reason']}")
            sent += 1
        return sent

    def archive_orphans(self) -> list:
        """Nhóm trỏ vào phiên không còn trong kho phiên (kho đã khôi phục về trước khi có nhóm mà kho nhóm còn, review
        T1 R6): không để nhóm sống. Lưu trữ nhóm, ghi sự kiện `session_missing`, huỷ việc còn mở. Dữ liệu nhóm giữ
        nguyên để đối chiếu. Trả các team_id đã lưu trữ."""
        out = []
        for team in self.teams.open_teams():
            if self.sessions.get_session(team["session_id"]) is not None:
                continue
            with self.accept_lock:
                self.teams.update(team["team_id"], by="host", status="archived")
            self.teams.log_event(team["team_id"], "session_missing", "host", None,
                                 {"session_id": team["session_id"]})
            q = self.tasks.team_queue(team["team_id"])
            for t in q["running"] + q["waiting"] + q["blocked"]:
                self._cancel_records(t["id"], "phiên của nhóm không còn")
            out.append(team["team_id"])
        return out

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
