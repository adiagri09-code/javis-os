"""Bộ chiếu phản hồi (outbox của reaction, T2 0.154.0). Thiết kế 2026-10-15 mục 3.3, 3.5, 4.3.

Ghi reaction (kho của reaction: `conversations.db` cho chat riêng, `team.sqlite3` cho nhóm) kèm `effect_state = 'pending'`
trên dòng nhật ký. Bộ chiếu áp tác động sang `resonance.sqlite3` (không có giao dịch xuyên kho):

- Idempotent theo `source_ref` (`rx:dm:<log_id>`, `rx:team:<log_id>`): UNIQUE ở `agent_wake_sources`, INSERT OR IGNORE ở
  `wake_reasons` của A2. Chạy lại sau lỗi giữa chừng không tạo tác động kép.
- Mỗi cặp (tin, người phản hồi) chiếu theo đúng thứ tự mã nhật ký; dòng `pending` đã có dòng mới hơn của cùng cặp thì chỉ
  áp TRẠNG THÁI RÒNG của dòng mới nhất, các dòng cũ đánh `superseded`. Đổi hay bỏ thì nguồn cũ trong lý do còn chờ bị gỡ.
- Định tuyến (3.3): reaction trên tin gắn goal chỉ tạo lý do `feedback` của goal ở A2; tin không gắn goal tạo lý do
  `reaction_review` ở lớp 3 (ngữ cảnh `team:<id>` hay `dm:<agent_key>`). Chỉ khi agent tác giả bật Cộng hưởng và sự
  kiện sau `resumed_at`; Cộng hưởng tắt thì `stored_only`. Câu trả lời ở trang Trò chuyện chính (không agent): `received`.
  Reaction của agent (trưởng nhóm, thành viên) không bao giờ tạo lý do và không vào ước lượng hữu ích.
- Trạng thái hiển thị trên reaction do bộ chiếu ghi ngược theo trạng thái lý do (`refresh`).
- Chạy ngay sau khi ghi (lỗi thì nuốt và ghi log, dòng giữ `pending`), mỗi nhịp và lúc khởi động cho mọi dòng còn chờ.

Emoji là cảm xúc: bộ chiếu không chốt đạt, không đổi ưu tiên, không cấp quyền, không đổi trạng thái việc hay goal.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Callable, Optional

import reaction_values as RV

log = logging.getLogger("javis.feedback_projector")

REVIEW_CODE = "reaction_review"
A2_CODE = "feedback"
OPEN_STATUSES = ("pending_review", "reviewing")
FEEDBACK_LIMIT = 5
FEEDBACK_DAYS = 30
FEEDBACK_EXCERPT = 160
# Câu dặn đi kèm khối phản hồi ở chat riêng (gửi model, không dịch). Cùng ý với FEEDBACK_NOTE của nhóm.
DM_FEEDBACK_NOTE = ("Emoji là cảm xúc của chủ, có thể về sự việc được kể; đừng coi là chấm điểm hay mệnh lệnh. Chỉ điều "
                    "chỉnh theo lý do chất lượng, trục nói/im và góp ý chữ. Chưa rõ thì giữ cách làm.")


def _chu(vi: str, en: str) -> str:
    try:
        import localefmt
        return localefmt.chu(vi, en)
    except Exception:  # noqa: BLE001
        return vi


def source_ref(kind: str, log_id: int) -> str:
    return f"rx:{kind}:{int(log_id)}"


def group_ref(kind: str, session_id: str, message_id: int, reactor: str) -> str:
    return f"{kind}:{session_id}:{int(message_id)}:{reactor}"


class FeedbackProjector:
    """`resonance`, `sessions`, `teams`: hàm trả kho (hay None khi chưa có kho). `team_view(team_id, session_id, mid)`:
    tin nhóm đã gắn reaction cho gói WS `team_message`. Mọi phương thức trả danh sách gói WS cần đẩy (người gọi đẩy)."""

    def __init__(self, *, resonance: Callable[[], Any], sessions: Optional[Callable[[], Any]] = None,
                 teams: Optional[Callable[[], Any]] = None,
                 team_view: Optional[Callable[[str, str, int], Optional[dict]]] = None,
                 clock: Callable[[], float] = time.time):
        self._resonance = resonance
        self._sessions = sessions or (lambda: None)
        self._teams = teams or (lambda: None)
        self._team_view = team_view
        self.clock = clock

    # ───────────── điểm nối cho T3 ─────────────

    def record_pulse_signal(self, kind: str, log_row: dict, agent_key: str, context_ref: str) -> None:
        """Điểm nối CỐ Ý để trống cho T3: ghi tín hiệu hữu ích (`pulse_signals`, UNIQUE `(source_ref, agent_key)`) của
        một reaction hợp lệ. T2 không ghi gì (chưa có ước lượng hữu ích)."""
        return None

    # ───────────── kho ─────────────

    def _store(self, kind: str):
        return self._sessions() if kind == "dm" else self._teams()

    def _log_row(self, kind: str, log_id: int) -> Optional[dict]:
        st = self._store(kind)
        if st is None:
            return None
        return st.dm_reaction_log_row(log_id) if kind == "dm" else st.reaction_log_row(log_id)

    def _pair(self, kind: str, row: dict) -> list:
        st = self._store(kind)
        return (st.dm_pair_logs(row["session_id"], row["message_id"], row["reactor"]) if kind == "dm"
                else st.pair_logs(row["session_id"], row["message_id"], row["reactor"]))

    def _mark(self, kind: str, ids: list, state: str, refs: Optional[dict] = None) -> None:
        st = self._store(kind)
        if kind == "dm":
            st.mark_dm_reaction_effects(ids, state, refs)
        else:
            st.mark_reaction_effects(ids, state, refs)

    def _reaction(self, kind: str, row: dict) -> Optional[dict]:
        st = self._store(kind)
        return (st.dm_reaction_of(row["session_id"], row["message_id"], row["reactor"]) if kind == "dm"
                else st.reaction_of(row["session_id"], row["message_id"], row["reactor"]))

    def _set_status(self, kind: str, row: dict, log_id: Optional[int], status: str, reason: str) -> Optional[dict]:
        st = self._store(kind)
        if kind == "dm":
            return st.set_dm_reaction_status(row["session_id"], row["message_id"], row["reactor"], log_id, status,
                                             reason)
        return st.set_reaction_status(row["session_id"], row["message_id"], row["reactor"], log_id, status, reason)

    def _event(self, kind: str, row: dict) -> Optional[dict]:
        """Gói WS sau khi host đổi trạng thái: `chat_reaction` (chat riêng) hay `team_message` (nhóm)."""
        if kind == "dm":
            if row.get("reactor") != "owner":
                return None
            st = self._sessions()
            cur = st.dm_reaction_of(row["session_id"], row["message_id"]) if st else None
            return {"type": "chat_reaction", "session_id": row["session_id"], "message_id": int(row["message_id"]),
                    "reaction": RV.public(cur)}
        if self._team_view is None:
            return None
        msg = self._team_view(row.get("team_id") or "", row["session_id"], int(row["message_id"]))
        if not msg:
            return None
        return {"type": "team_message", "team_id": row.get("team_id") or "", "message": msg}

    # ───────────── chiếu ─────────────

    def project(self, kind: str, log_id: int) -> list:
        """Chiếu MỘT dòng nhật ký (và mọi dòng chờ của cùng cặp). Lỗi thì ghi log, dòng giữ `pending` để nhịp sau chiếu
        lại; không bao giờ ném ra ngoài (ghi reaction đã xong, lỗi tác động không được làm hỏng request)."""
        try:
            return self._project(kind, int(log_id))
        except Exception as ex:  # noqa: BLE001
            log.warning("feedback projector: %s log %s failed: %s: %s", kind, log_id, type(ex).__name__, ex)
            return []

    def _project(self, kind: str, log_id: int) -> list:
        row = self._log_row(kind, log_id)
        if row is None:
            return []
        pair = self._pair(kind, row)
        if not pair:
            return []
        newest = pair[-1]
        older_pending = [x["id"] for x in pair[:-1] if x.get("effect_state") == "pending"]
        if older_pending:
            self._mark(kind, older_pending, "superseded", {"superseded_by": source_ref(kind, newest["id"])})
        if newest.get("effect_state") != "pending":
            return []
        older = [x["id"] for x in pair[:-1]]
        refs = self._apply(kind, newest, older)
        # Đổi hay bỏ: nguồn cũ của cùng cặp trong lý do còn chờ bị gỡ SAU khi nguồn mới đã vào (lý do không bị chốt
        # `superseded` giữa chừng chỉ vì đang thay nguồn).
        self._drop_old(kind, newest, older)
        self._mark(kind, [newest["id"]], "done", refs)
        ev = self._event(kind, newest)
        return [ev] if ev else []

    def _next_state(self, kind: str, row: dict) -> Optional[dict]:
        if kind == "dm":
            return row.get("next")
        st = {"value": row.get("value"), "reasons": row.get("reasons") or [], "axis": row.get("axis") or "",
              "comment": row.get("comment") or ""}
        return None if RV.is_empty(st) else st

    def _context_of(self, kind: str, row: dict, agent_key: str) -> str:
        return f"team:{row.get('team_id') or ''}" if kind == "team" else f"dm:{agent_key}"

    def _brain_of(self, kind: str, row: dict) -> str:
        if kind == "team":
            tm = self._teams()
            team = tm.get(row.get("team_id") or "") if tm is not None else None
            return (team or {}).get("brain_id") or ""
        return ""

    def _apply(self, kind: str, row: dict, older_ids: list) -> dict:
        """Áp trạng thái ròng của dòng mới nhất một cặp. Trả `effect_refs` (bằng chứng tác động)."""
        src = source_ref(kind, row["id"])
        grp = group_ref(kind, row["session_id"], row["message_id"], row["reactor"])
        old_refs = [source_ref(kind, i) for i in older_ids]
        agent_key = str(row.get("agent_key") or "")
        goal_id = str(row.get("goal_id") or "") if kind == "dm" else ""
        res = self._resonance() if (agent_key or goal_id) else None
        nxt = self._next_state(kind, row)
        if nxt is None:
            return {"route": "cleared", "source_ref": src, "removed": old_refs}
        source_kind = str(row.get("source_kind") or "owner")
        if source_kind != "owner":
            # Reaction của agent: góp ý cộng tác, không tạo lý do, không vào ước lượng hữu ích (chống tự thưởng).
            self._set_status(kind, row, row["id"], "received", "")
            return {"route": "agent_reaction", "source_ref": src}
        if not agent_key:
            # Trang Trò chuyện chính (tác giả là Javis): lưu và hiện, không vào học hay phán xử của agent nào.
            self._set_status(kind, row, row["id"], "received", "")
            return {"route": "none", "source_ref": src}
        ctx = self._context_of(kind, row, agent_key)
        agent = res.agent_any(agent_key) if res is not None else None
        on = bool(agent and agent.get("status") == "active" and agent.get("enabled"))
        resumed = res.resumed_at(agent_key, ctx) if (res is not None and on) else None
        if not on or (resumed is not None and float(row.get("created_at") or 0) < float(resumed)):
            # Nhãn "Đã nhận, chỉ lưu" do giao diện dịch; lý do nói ĐÚNG vì sao (tắt, hay có trước lúc bật lại), không lặp nhãn.
            why = (_chu("Cộng hưởng của trợ lý đang tắt", "The assistant's Resonance is off") if not on else
                   _chu("Phản hồi có trước lúc bật lại Cộng hưởng", "Sent before Resonance was turned back on"))
            self._set_status(kind, row, row["id"], "stored_only", why)
            return {"route": "stored_only", "source_ref": src, "agent_key": agent_key}
        if goal_id:
            g = res.goal_brain(goal_id)
            if g is None or g.get("status") != "active":
                self._set_status(kind, row, row["id"], "no_change",
                                 _chu("Mục tiêu đã kết thúc", "The goal has already ended"))
                return {"route": "a2_closed", "source_ref": src, "goal_id": goal_id}
            import resonance_store as RS
            res.add_reason_event(RS.Principal("agent", "javis", g["brain_id"]), goal_id, A2_CODE, src)
            self.record_pulse_signal(kind, row, agent_key, ctx)
            refs = {"route": "a2", "source_ref": src, "goal_id": goal_id, "agent_key": agent_key}
            self._sync_one(kind, row, refs)
            return refs
        from agent_ledger import WakeReasons
        rid = WakeReasons(res).add_source(agent_key, ctx, REVIEW_CODE, src, grp)
        self.record_pulse_signal(kind, row, agent_key, ctx)
        refs = {"route": "l3", "source_ref": src, "reason_id": rid, "context_ref": ctx, "agent_key": agent_key}
        self._sync_one(kind, row, refs)
        return refs

    def _drop_old(self, kind: str, row: dict, older_ids: list) -> list:
        """Gỡ nguồn của các lần đổi cũ hơn của cùng cặp khỏi lý do còn chờ (lớp 3) và lý do `feedback` còn chờ (A2)."""
        if not older_ids:
            return []
        agent_key = str(row.get("agent_key") or "")
        goal_id = str(row.get("goal_id") or "") if kind == "dm" else ""
        if not (agent_key or goal_id):
            return []
        res = self._resonance()
        if res is None:
            return []
        from agent_ledger import WakeReasons
        src = source_ref(kind, row["id"])
        removed = WakeReasons(res).remove_group(group_ref(kind, row["session_id"], row["message_id"], row["reactor"]),
                                                keep=[src])
        if goal_id:
            res.supersede_reason_events(goal_id, A2_CODE, [source_ref(kind, i) for i in older_ids])
        return removed

    # ───────────── trạng thái hiển thị ─────────────

    def _status_for(self, refs: dict) -> Optional[tuple]:
        """(status, status_reason) theo trạng thái lý do thật; None khi không đổi gì."""
        res = self._resonance()
        if res is None:
            return None
        route = refs.get("route")
        if route == "a2":
            st = res.reason_event_state(refs.get("goal_id") or "", A2_CODE, refs.get("source_ref") or "")
            if st == "pending":
                return "pending_review", ""
            if st == "served":
                return "no_change", _chu("Mục tiêu đã đọc phản hồi ở lượt việc kế tiếp",
                                         "The goal read this feedback on its next work turn")
            return None
        if route == "l3":
            from agent_ledger import WakeReasons
            s = WakeReasons(res).source(refs.get("source_ref") or "")
            if s is None or s.get("removed_at") is not None:
                return None
            rs = s.get("reason_status")
            if rs == "pending":
                return "pending_review", ""
            if rs == "claimed":
                return "reviewing", ""
            if rs == "failed":
                return "pending_review", _chu("Lượt xem xét lỗi nhiều lần, chờ bạn bấm thử lại",
                                              "The review failed several times and waits for you to retry")
            if rs == "served" and s.get("consumed_at") is not None:
                return "no_change", ""
            return None
        return None

    def _sync_one(self, kind: str, row: dict, refs: dict) -> Optional[dict]:
        got = self._status_for(refs)
        if got is None:
            return None
        cur = self._reaction(kind, row)
        if cur is None or int(cur.get("log_id") or 0) != int(row["id"]):
            return None
        # Trạng thái do lượt xem xét thật ghi (T3: adjusted/no_change kèm lý do) không bị bộ chiếu ghi đè bằng mặc định.
        if got[0] == "no_change" and cur.get("status") in ("adjusted", "no_change") and not got[1]:
            return None
        if (cur.get("status"), cur.get("status_reason") or "") == got:
            return None
        return self._set_status(kind, row, row["id"], got[0], got[1])

    def refresh(self, kind: str, log_ids: list) -> list:
        """Ghi ngược trạng thái của các reaction theo trạng thái lý do hiện tại (gọi khi lý do đổi trạng thái)."""
        events = []
        for lid in log_ids or []:
            try:
                row = self._log_row(kind, int(lid))
                if row is None or row.get("effect_state") != "done":
                    continue
                if self._sync_one(kind, row, row.get("effect_refs") or {}) is not None:
                    ev = self._event(kind, row)
                    if ev:
                        events.append(ev)
            except Exception as ex:  # noqa: BLE001
                log.warning("feedback projector refresh %s %s: %s", kind, lid, ex)
        return events

    def project_pending(self, limit: int = 200) -> list:
        """Nhịp và lúc khởi động: chiếu mọi dòng còn `pending` (theo thứ tự mã nhật ký), rồi ghi ngược trạng thái của
        các reaction đang chờ hay đang xem xét. Kho nào chưa có thì bỏ qua."""
        events: list = []
        for kind in ("dm", "team"):
            try:
                st = self._store(kind)
                if st is None:
                    continue
                rows = st.pending_dm_reaction_logs(limit) if kind == "dm" else st.pending_reaction_logs(limit)
                done = set()
                for row in rows:
                    pair = (row["session_id"], row["message_id"], row["reactor"])
                    if pair in done:
                        continue
                    done.add(pair)
                    events.extend(self.project(kind, row["id"]))
                open_ids = (st.dm_open_reaction_logs(OPEN_STATUSES, limit) if kind == "dm"
                            else st.open_reaction_logs(OPEN_STATUSES, limit))
                events.extend(self.refresh(kind, open_ids))
            except Exception as ex:  # noqa: BLE001
                log.warning("feedback projector pending %s: %s: %s", kind, type(ex).__name__, ex)
        return events


# ───────────── khối phản hồi cho lượt chat riêng ─────────────

def dm_feedback_lines(sessions: Any, agent_key: str, now: Optional[float] = None, limit: int = FEEDBACK_LIMIT) -> list:
    """Mục phản hồi gần đây của CHỦ trên câu trả lời của ĐÚNG agent này ở chat riêng (ngữ cảnh `dm:<agent_key>`): tối đa
    `limit` mục trong 30 ngày, emoji gốc kèm tên loại, lý do, trục nói/im, góp ý, đoạn trích. Mục đã bỏ không còn trong kho
    nên tự rời khối. Không đọc gì của ngữ cảnh khác."""
    if not agent_key or sessions is None:
        return []
    t = time.time() if now is None else float(now)
    rows = sessions.recent_dm_feedback(agent_key, t - FEEDBACK_DAYS * 86400, limit * 3)
    msgs = sessions.messages_by_ids([r["message_id"] for r in rows])
    out = []
    for fb in rows:
        if len(out) >= limit:
            break
        m = msgs.get(int(fb["message_id"]))
        if m is None or m.get("session_id") != fb["session_id"]:
            continue
        excerpt = re.sub(r"\s+", " ", str(m.get("content") or "")).strip()
        if len(excerpt) > FEEDBACK_EXCERPT:
            excerpt = excerpt[:FEEDBACK_EXCERPT] + "..."
        parts = [f'- [#{fb["message_id"]}] "{excerpt}"']
        if fb.get("value"):
            parts.append(f"cảm xúc: {RV.REACTION_EMOJI.get(fb['value'], '')} ({fb['value']})")
        if fb.get("reasons"):
            parts.append("lý do: " + ", ".join(RV.REASON_LABEL.get(x, x) for x in fb["reasons"]))
        if fb.get("axis"):
            parts.append("nói/im: " + RV.AXIS_LABEL.get(fb["axis"], fb["axis"]))
        if fb.get("comment"):
            parts.append('góp ý: "' + re.sub(r"\s+", " ", fb["comment"]).strip() + '"')
        out.append(" · ".join(parts))
    return out


def dm_feedback_block(sessions: Any, agent_key: str, now: Optional[float] = None) -> str:
    lines = dm_feedback_lines(sessions, agent_key, now)
    if not lines:
        return ""
    return ("\n\n## Phản hồi gần đây của chủ (về câu trả lời của bạn trong chat riêng)\n" + "\n".join(lines) + "\n"
            + DM_FEEDBACK_NOTE + "\n")
