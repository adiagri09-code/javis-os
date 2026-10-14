"""Nhóm chat team T5 (trang Nhóm gọn như app chat): phần server.

    python tests/run.py team_ux -v

Việc bị chặn vì hết lượt có MỘT nút giải quyết ("Cho thêm lượt": nâng đúng trần đã chạm rồi cho chạy tiếp), lý do chặn viết
bằng lời thường, số lần đã dùng hôm nay. Kho thật trên SQLite tạm, engine giả, không gọi model.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import tempfile
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-team-ux-")
TEMP = Path(tempfile.mkdtemp(prefix="javis-team-ux-w-"))

import sessions  # noqa: E402
import task_store  # noqa: E402
import team_runner as TR  # noqa: E402
import team_store  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {str(extra)[:400]}" if extra and not cond else ""))
    if not cond:
        fails.append(name)


class Fake:
    def __init__(self):
        self.calls = []

    def engine_for(self, team, key, role):
        async def run_(req):
            self.calls.append(req)
            return {"text": f"{key} xong {len(self.calls)}"}
        return "fake", "fake", run_


_n = [0]


def world(label):
    _n[0] += 1
    d = TEMP / f"{_n[0]:02d}-{label}"
    d.mkdir()
    ss = sessions.SessionStore(db_path=d / "chat.db")
    ts = task_store.TaskStore(d / "kanban.sqlite3")
    tm = team_store.TeamStore(d / "team.sqlite3")
    fake = Fake()
    r = TR.TeamRunner(teams=tm, tasks=ts, sessions=ss, engine_for=fake.engine_for,
                      agent_info=lambda root, key: {"slug": key, "name": key.title(), "system": ""})
    tid = team_store.new_team_id()
    sid = ss.create_session(brain=str(d), channel=f"team:{tid}")
    tm.create_team(str(d), label, "", sid, team_id=tid)
    for k in ("lan", "minh"):
        tm.add_member(tid, k, k)
    tm.set_leader(tid, "lan")
    return r, tm, ts, ss, fake, tm.get(tid)


def run(coro):
    return asyncio.run(coro)


# ═════ Hết lượt trong ngày: Cho thêm lượt nâng trần ngày rồi chạy tiếp ═════
r, tm, ts, ss, fake, T = world("daily")
tm.set_caps(T["team_id"], {"daily_turns": 1})
run(r.run_replies(r.submit(T["team_id"], "Chào", client_msg_id="c1")))
job = r.submit(T["team_id"], "Viết bài", mentions=["minh"], as_job=True, client_msg_id="j1")["task_id"]
run(r.dispatch_once())
t = ts.get_task(job)
check("việc chặn vì hết lượt trong ngày, lý do bằng lời thường (không có chữ 'trần')",
      t["status"] == "team_blocked" and t["block_kind"] == "cap_reached" and "trần" not in t["block_reason"]
      and "hôm nay" in t["block_reason"], t["block_reason"])
out = r.extend_job(job)
check("Cho thêm lượt: nâng đúng trần ngày (+20), việc về hàng chờ", out and out["cap"] == "daily_turns"
      and out["value"] == 21 and tm.get(T["team_id"])["caps"]["daily_turns"] == 21
      and ts.get_task(job)["status"] == "team_queued", out)
check("Cho thêm lượt: có sự kiện và tin hệ thống nói rõ", any(e["kind"] == "caps_extended" for e in tm.events(T["team_id"]))
      and any(m["author_kind"] == "system" and "20" in m["content"]
              for m in ss.get_team_messages_page(T["session_id"], limit=50)["messages"]))
run(r.dispatch_once())
check("sau khi cho thêm lượt: việc chạy xong", ts.get_task(job)["status"] == "done")

# ═════ Hết lượt của việc: nâng trần lượt mỗi việc ═════
r, tm, ts, ss, fake, T = world("task")
tm.set_caps(T["team_id"], {"task_turns": 1})
job = r.submit(T["team_id"], "Việc nhiều bước", as_job=True, client_msg_id="j2")["task_id"]


async def planner(req):
    if req["role"] == "plan":
        return {"text": 'Chia.\n<!-- JAVIS_TEAM: {"op": "assign", "agent": "minh", "brief": "a"} -->'}
    return {"text": "Bài"}
r.engine_for = lambda team, key, role: ("fake", "fake", planner)
run(r.dispatch_once())
t = ts.get_task(job)
check("việc chặn vì hết lượt của việc", t["block_kind"] == "cap_reached"
      and t["block_reason"].startswith("Việc đã dùng hết số lần trả lời"), t["block_reason"])
out = r.extend_job(job)
check("Cho thêm lượt: nâng trần lượt mỗi việc (+6)", out and out["cap"] == "task_turns" and out["value"] == 7, out)
run(r.dispatch_once())
check("chạy tiếp tới xong", ts.get_task(job)["status"] == "done", ts.get_task(job)["status"])

# ═════ Toàn quyền đặt số cho trần: nâng trần trong hộp cấp quyền (cả trần tối đa), không đụng trần nhóm ═════
r, tm, ts, ss, fake, T = world("auth")
r.grant_authority(T["team_id"], {"caps": {"daily_turns": 1}, "ceilings": {"daily_turns": 1}})
run(r.run_replies(r.submit(T["team_id"], "Chào", client_msg_id="a1")))
job = r.submit(T["team_id"], "Viết", mentions=["minh"], as_job=True, client_msg_id="a2")["task_id"]
run(r.dispatch_once())
check("Toàn quyền trần ngày 1: việc chặn hết lượt", ts.get_task(job)["block_kind"] == "cap_reached")
out = r.extend_job(job)
g = tm.active_authority(T["team_id"])["grant"]
check("Cho thêm lượt khi Toàn quyền: nâng trần trong hộp cấp quyền và trần tối đa, trần nhóm giữ nguyên",
      out["value"] == 21 and g["caps"]["daily_turns"] == 21 and g["ceilings"]["daily_turns"] == 21
      and tm.get(T["team_id"])["caps"]["daily_turns"] == 100, (out, g))
check("usage theo trần đang áp (Toàn quyền)", r.usage(T["team_id"])["cap"] == 21, r.usage(T["team_id"]))

# ═════ Không phải việc bị chặn vì hết lượt: không làm gì ═════
r, tm, ts, ss, fake, T = world("other")
job = r.submit(T["team_id"], "Việc", as_job=True, client_msg_id="j3")["task_id"]
check("việc không bị chặn hết lượt: Cho thêm lượt không làm gì", r.extend_job(job) is None
      and tm.get(T["team_id"])["caps"]["daily_turns"] == 100)

# ═════ Số lần đã dùng hôm nay ═════
r, tm, ts, ss, fake, T = world("usage")
run(r.run_replies(r.submit(T["team_id"], "Một", client_msg_id="u1")))
run(r.run_replies(r.submit(T["team_id"], "Hai", client_msg_id="u2")))
u = r.usage(T["team_id"])
check("số lần đã dùng hôm nay kèm giới hạn đang áp", u == {"today": 2, "cap": 100}, u)

# ═════ Lý do chặn bằng lời thường ═════
src = (ROOT / "server" / "team_runner.py").read_text(encoding="utf-8")
check("lý do chặn không còn chữ 'trần', 'Lượt lỗi', 'Server khởi động lại'",
      "Đã chạm trần" not in src and 'f"Lượt lỗi:' not in src and "Server khởi động lại khi bước" not in src)

print(f"\n{'FAIL' if fails else 'PASS'} - test_team_ux: {len(fails)} lỗi")
raise SystemExit(1 if fails else 0)
