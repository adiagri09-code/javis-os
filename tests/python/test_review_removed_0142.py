"""0.142.0: bỏ người review cố định (A5) và migration của mục tiêu cũ.

    python tests/run.py review_removed_0142

Dựng kho đúng như thời A5 (đội gắn khi tạo), có mục tiêu đang CHỜ REVIEW và mục tiêu đang làm. Bỏ bảng đánh dấu
migration để giả lập kho trước 0.142.0, mở lại bằng mã mới, rồi kiểm:
- không mục tiêu nào bị tự đánh dấu đạt (kể cả khi thức lại), lịch sử review và lượt giữ nguyên;
- đội được gỡ có ghi lý do, mục tiêu đang mở tạm dừng chờ chủ quyết, lý do thức của vai review được chốt;
- có bản sao kho trước khi nâng; mở lại lần hai không đổi gì;
- mục tiêu mới không còn đội; tab Công việc xếp mục tiêu đã gỡ vào Cần bạn với lý do bằng lời.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import json
import os
import sqlite3
import tempfile
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-review-removed-")

import resonance as R  # noqa: E402
import resonance_store as RS  # noqa: E402
import agent_jobs  # noqa: E402
import _resonance_team as T  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {str(extra)[:500]}" if extra and not cond else ""))
    if not cond:
        fails.append(name)


STATE = Path(tempfile.mkdtemp(prefix="state-review-removed-"))
t = T.Team(STATE, "rr")                 # kho thời A5: cặp làm/review, đội gắn khi tạo
g_wait = t.create()
t.wake(g_wait)                          # người làm nộp bản, mục tiêu chờ review
g_work = t.create()                     # có đội, chưa chạy
st = t.st(g_wait)
check("dựng đúng: một mục tiêu đang chờ review có đội active",
      st.get("block_reason") == "review_pending" and t.team(g_wait)["status"] == "active"
      and t.team(g_work)["status"] == "active", st)
reviews_before = len(t.reviews(g_wait))
calls_before = t.calls(g_wait)
db = Path(t.store.path)

# Giả lập kho trước 0.142.0: chưa có bảng đánh dấu migration.
with sqlite3.connect(str(db)) as c:
    c.execute("DROP TABLE review_migrations")
store = RS.GoalStore(db)
owner = t.owner
bak = db.with_name(db.name + RS.REVIEW_REMOVED_BACKUP_SUFFIX)
with sqlite3.connect(str(bak)) as c:
    bak_team = c.execute("SELECT status FROM goal_team WHERE goal_id=?", (g_wait.id,)).fetchone()
check("có bản sao kho trước khi nâng, đội trong bản sao vẫn active", bak.is_file() and bak_team == ("active",))

for g, label in ((g_wait, "đang chờ review"), (g_work, "đang làm")):
    cur = store.get(owner, g.id)
    team = store.goal_team(owner, g.id)
    rs = store.run_state(owner, g.id)
    check(f"mục tiêu {label}: vẫn active (không tự đạt), tạm dừng, đội đã gỡ bởi host",
          cur.status == "active" and cur.paused and team["status"] == "detached"
          and team["detached_by"] == "host:review_removed", (cur.status, cur.paused, team))
    check(f"mục tiêu {label}: không còn chặn thuộc đội", rs.get("block_reason") not in RS.TEAM_BLOCKS, rs)

ev = [e for e in store.events(owner, g_wait.id) if e["kind"] == "team_detached"]
check("sự kiện team_detached ghi lý do và trạng thái trước đó",
      len(ev) == 1 and ev[0]["payload"].get("reason") == "review_removed"
      and ev[0]["payload"].get("prev_block") == "review_pending", ev)
check("lịch sử review và lượt giữ nguyên", len(store.reviews(owner, g_wait.id, limit=50)) == reviews_before
      and (store.goal_team(owner, g_wait.id)["calls"].get("maker", {}).get("used"),
           store.goal_team(owner, g_wait.id)["calls"].get("reviewer", {}).get("used")) == calls_before[:2])
pending = [r for r in store.reasons(owner, g_wait.id, state="pending") if r["code"].startswith("review_")]
check("lý do thức của vai review đã chốt", pending == [], pending)
with sqlite3.connect(str(db)) as c:
    pair = c.execute("SELECT enabled, by FROM team_pairs WHERE maker_agent_key=?", (t.maker["agent_key"],)).fetchone()
check("cặp làm/review cũ tắt, dòng vẫn giữ", pair == (0, "host:review_removed"), pair)

# Thức lại: mục tiêu đang dừng không tự kết thúc, không gọi model.
t.store = store
q0 = t.work.queries + t.rev.queries
t.wake(g_wait)
check("thức lại sau migration: không tự đạt, không gọi model", store.get(owner, g_wait.id).status == "active"
      and t.work.queries + t.rev.queries == q0)

# Mở lại lần hai: không đổi gì.
n_events = len(store.events(owner, g_wait.id))
store2 = RS.GoalStore(db)
check("mở lại lần hai: migration không chạy lại", len(store2.events(owner, g_wait.id)) == n_events
      and sorted(store2.review_removed_goals()) == sorted([g_wait.id, g_work.id]))
mig = [e["kind"] for e in store2.events(owner, g_wait.id) if e["by"] == "host:review_removed"]
check("migration ghi đúng hai sự kiện: gỡ đội và tạm dừng", sorted(mig) == ["paused", "team_detached"], mig)

# Tab Công việc: mục tiêu đã gỡ nằm ở Cần bạn, lý do bằng lời.
rows = store2.agent_goal_rows(owner, t.maker["agent_key"])
jobs = agent_jobs._auto_jobs(t.maker["agent_key"], store2, owner)
mine = {j["id"]: j for j in jobs}
check("tab Công việc: mục tiêu đã gỡ người review ở ngăn Cần bạn, mã lý do review_removed",
      mine[f"goal:{g_wait.id}"]["bucket"] == "needs_you" and mine[f"goal:{g_wait.id}"]["reason_code"] == "review_removed",
      rows)
check("người review cũ không còn thấy mục tiêu ở vai review (đội đã gỡ)",
      all(r["role"] != "reviewer" for r in store2.agent_goal_rows(owner, t.reviewer["agent_key"])))

# Mục tiêu mới sau 0.142.0: không có đội (cờ test tắt như máy thật).
t.store = store2
store2.attach_reviewer_teams = False
g_new = t.create()
check("mục tiêu mới không có người review cố định", store2.goal_team(owner, g_new.id) is None)

# Chủ bấm Tiếp tục: mục tiêu chạy lại theo luật thường (quyết định của chủ, không phải của migration).
store2.set_paused(owner, g_wait.id, False)
check("chủ Tiếp tục được", not store2.get(owner, g_wait.id).paused)

print(("FAIL" if fails else "PASS") + f" - test_review_removed_0142: {len(fails)} lỗi")
raise SystemExit(1 if fails else 0)
