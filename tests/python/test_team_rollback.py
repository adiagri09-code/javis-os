"""Nhóm chat team T1, nhiệm vụ 8: nâng từ 0.109.0, hạ về bằng snapshot (spec 2026-10-13-team-chat-design mục 18; ca TC39).

    python tests/run.py team_rollback -v

Nạp `server/task_store.py` và `server/sessions.py` của commit phát hành 0.109.0 (`bfb1c29f` trên main, bản cuối trước nhóm
chat) qua `git show`:
1. mã 0.109.0 THẬT lập kho Kanban có một việc và kho phiên có một tin;
2. mã T1 mở hai kho: mỗi kho có đúng một snapshot `.pre-0.111.0`, chụp TRƯỚC khi thêm cột; việc và tin cũ còn nguyên;
3. hạ KHÔNG khôi phục: mã 0.109.0 mở được hai kho, KHÔNG nhặt việc nhóm (không chạy bằng aux); phiên `team:` hiện như
   phiên thường (giới hạn đã công bố);
4. công cụ khôi phục giữ bản kho hiện tại `post-0.111.0-*` rồi ghi snapshot; mã 0.109.0 mở được, không còn cột hay việc
   nhóm;
5. nâng lại: snapshot đã có thì không chép lại.
Không gọi model. Máy không có lịch sử git của commit đó thì in SKIP; trên CI (biến CI) thì ĐỎ.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import importlib.util
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-team-rb-")

import sessions as NEW_SS  # noqa: E402
import task_store as NEW_TS  # noqa: E402
import team_migration as TM  # noqa: E402

sys.path.insert(0, str(ROOT / "tools"))
import team_chat_restore_pre as RESTORE  # noqa: E402

OLD_SHA = "bfb1c29f9e87e8b43a0bf1a8a43d3535581047d6"
fails = []


def check(name, cond, info=None):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond or info is None else f"  ({str(info)[:300]})"))
    if not cond:
        fails.append(name)


def _show(path):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", f"{OLD_SHA}:{path}"],
                                   stderr=subprocess.DEVNULL).decode("utf-8")


try:
    srcs = {n: _show(f"server/{n}.py") for n in ("task_store", "sessions")}
except (subprocess.CalledProcessError, OSError):
    if os.environ.get("CI"):
        print(f"FAIL không đọc được mã của {OLD_SHA}: CI phải fetch commit này trước")
        sys.exit(1)
    print(f"SKIP máy này không có lịch sử git của {OLD_SHA}")
    sys.exit(0)

_dir = Path(tempfile.mkdtemp(prefix="old-0109-"))


def _load(name, src):
    f = _dir / f"{name}.py"
    f.write_text(src, encoding="utf-8", newline="\n")
    spec = importlib.util.spec_from_file_location(name, f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


OLD_TS = _load("task_store_0109", srcs["task_store"])
OLD_SS = _load("sessions_0109", srcs["sessions"])
check("nạp đúng mã 0.109.0: chưa có làn team, chưa có tin có người gửi",
      not hasattr(OLD_TS.TaskStore, "enqueue_team") and not hasattr(OLD_SS.SessionStore, "append_team_message"))


def cols(db, table):
    with sqlite3.connect(str(db)) as c:
        return {r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}


state = Path(tempfile.mkdtemp(prefix="state-team-rb-"))
kdb, sdb = state / "kanban.sqlite3", state / "conversations.db"
B = "D:/brain"

# 1. Mã 0.109.0 lập hai kho.
ot = OLD_TS.TaskStore(kdb)
k_old = ot.enqueue(B, "Việc cũ", "Việc cũ", status="ready")
ot.close()
os_ = OLD_SS.SessionStore(db_path=sdb)
s_old = os_.create_session(brain="B", channel="web")
os_.append_message(s_old, "user", "tin cũ")
os_._conn.close()

# 2. Mã T1 mở: snapshot một lần, chụp trước khi thêm cột.
nt = NEW_TS.TaskStore(kdb)
ns = NEW_SS.SessionStore(db_path=sdb)
ksnap, ssnap = kdb.with_name(kdb.name + TM.SNAPSHOT_SUFFIX), sdb.with_name(sdb.name + TM.SNAPSHOT_SUFFIX)
check("nâng lên: kanban có snapshot .pre-0.111.0, chụp TRƯỚC khi thêm cột làn team",
      ksnap.is_file() and "lane" not in cols(ksnap, "tasks") and "lane" in cols(kdb, "tasks"))
check("nâng lên: kho phiên có snapshot .pre-0.111.0, chụp TRƯỚC khi thêm cột người gửi",
      ssnap.is_file() and "author_kind" not in cols(ssnap, "messages") and "author_kind" in cols(sdb, "messages"))
check("việc cũ và tin cũ còn nguyên sau nâng", nt.get_task(k_old)["status"] == "ready"
      and [m["content"] for m in ns.get_messages(s_old)] == ["tin cũ"])
tid, _ = nt.enqueue_team(B, "tm_1", "Việc nhóm", "Việc nhóm", source_ref="msg:s:1")
team_sid = ns.create_session(brain="B", channel="team:tm_1", title="Nhóm")
ns.append_team_message(team_sid, "user", "tin nhóm", author_kind="owner", client_msg_id="c1")
k_mtime, s_mtime = ksnap.stat().st_mtime_ns, ssnap.stat().st_mtime_ns
nt.close()
ns._conn.close()

# 3. Hạ KHÔNG khôi phục: mã 0.109.0 trên kho đã nâng.
ot = OLD_TS.TaskStore(kdb)
cand = ot.next_candidate(B)
check("hạ không khôi phục: mã 0.109.0 mở được kho, chỉ nhặt việc Kanban, không bao giờ nhặt việc nhóm",
      cand is not None and cand["id"] == k_old and ot.claim(tid, "w-old") is None)
ot.reclaim_stale(B, set())
check("hạ không khôi phục: thu hồi của mã cũ không đụng việc nhóm", ot.get_task(tid)["status"] == "team_queued")
check("hạ không khôi phục: bảng Việc của mã cũ thấy dòng team_queued (giới hạn đã công bố)",
      any(t["id"] == tid and t["status"] == "team_queued" for t in ot.list_tasks(B)))
ot.close()
os_ = OLD_SS.SessionStore(db_path=sdb)
check("hạ không khôi phục: mã 0.109.0 đọc được tin nhóm như tin thường, phiên team: hiện như phiên thường",
      [m["content"] for m in os_.get_messages(team_sid)] == ["tin nhóm"]
      and team_sid in {s["id"] for s in os_.list_sessions(limit=50)})
os_._conn.close()

# 4. Công cụ khôi phục.
r = RESTORE.restore(str(state))
check("công cụ khôi phục: ok, giữ bản hiện tại post-0.111.0 của cả hai kho", r["ok"] and len(r["kept"]) == 2
      and all(Path(p).is_file() for p in r["kept"]) and all(".post-0.111.0-" in p for p in r["kept"]), r)
kept_k = next(Path(p) for p in r["kept"] if "kanban" in p)
with sqlite3.connect(str(kept_k)) as c:
    kept_team = c.execute("SELECT COUNT(*) FROM tasks WHERE lane='team'").fetchone()[0]
check("bản giữ lại còn việc nhóm để tra cứu", kept_team == 1)
check("khôi phục: không còn cột mới", "lane" not in cols(kdb, "tasks") and "author_kind" not in cols(sdb, "messages"))
ot = OLD_TS.TaskStore(kdb)
os_ = OLD_SS.SessionStore(db_path=sdb)
check("khôi phục rồi chạy 0.109.0: việc cũ còn, không còn việc nhóm hay phiên nhóm", ot.get_task(k_old) is not None
      and ot.get_task(tid) is None and os_.get_session(team_sid) is None
      and [m["content"] for m in os_.get_messages(s_old)] == ["tin cũ"])
ot.close()
os_._conn.close()

# 5. Nâng lại: snapshot đã có thì không chép lại.
nt = NEW_TS.TaskStore(kdb)
ns = NEW_SS.SessionStore(db_path=sdb)
check("nâng lại: không chép đè snapshot", ksnap.stat().st_mtime_ns == k_mtime and ssnap.stat().st_mtime_ns == s_mtime
      and "lane" in cols(kdb, "tasks"))
nt.close()
ns._conn.close()

# Kho mới tinh thì không chụp gì.
fresh = Path(tempfile.mkdtemp(prefix="state-fresh-"))
NEW_TS.TaskStore(fresh / "kanban.sqlite3").close()
NEW_SS.SessionStore(db_path=fresh / "conversations.db")._conn.close()
check("kho mới tinh: không có snapshot", not list(fresh.glob("*" + TM.SNAPSHOT_SUFFIX)))
check("công cụ báo rõ khi không có snapshot", RESTORE.restore(str(fresh))["ok"] is False)
raise SystemExit(1 if fails else 0)
