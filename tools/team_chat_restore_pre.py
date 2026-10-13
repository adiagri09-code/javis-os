"""Hạ nhóm chat team về bản trước 0.111.0 bằng snapshot lúc nâng (spec 2026-10-13-team-chat-design mục 18).

    python tools/team_chat_restore_pre.py --yes
    python tools/team_chat_restore_pre.py --state-dir /duong/dan/state --yes

CHẠY KHI JAVIS ĐÃ TẮT. Với từng kho có snapshot (`kanban.sqlite3`, `conversations.db`), script làm đúng hai bước, đều
bằng SQLite backup API (lấy cả phần còn trong WAL, không chép thô file):
1. Chép kho HIỆN TẠI sang `<tên>.post-0.111.0-<thời điểm>` để giữ hồ sơ sau nâng (việc nhóm, tin nhóm).
2. Ghi đè kho bằng snapshot `<tên>.pre-0.111.0` mà mã 0.111.0 tạo một lần lúc nâng.

Hậu quả, cũng ghi trong ghi chú phát hành: mọi việc Kanban và tin chat sau lúc nâng biến mất khỏi kho chạy (bản sao ở
bước 1 vẫn đọc được). `team.sqlite3` để nguyên: mã cũ không đọc nó. Hạ KHÔNG khôi phục vẫn chạy được: mã cũ không nhặt
việc nhóm, nhưng trang Việc hiện các dòng `team_*` với trạng thái lạ và phiên `team:` hiện như phiên thường.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path

SNAPSHOT_SUFFIX = ".pre-0.111.0"
# (file kho, bảng, cột chỉ có từ 0.111.0): kiểm snapshot đúng là bản trước nâng.
STORES = (("kanban.sqlite3", "tasks", "lane"), ("conversations.db", "messages", "author_kind"))


def _backup(src: Path, dst: Path) -> None:
    with closing(sqlite3.connect(str(src), timeout=10)) as s, closing(sqlite3.connect(str(dst), timeout=10)) as d:
        s.backup(d)


def restore(state_dir: str) -> dict:
    """Khôi phục các snapshot trước 0.111.0 trong `state_dir`. Trả {ok, restored, kept, error}."""
    root = Path(state_dir)
    restored, kept = [], []
    stamp = time.strftime("%Y%m%d-%H%M%S")
    todo = [(root / f, t, c) for f, t, c in STORES if (root / (f + SNAPSHOT_SUFFIX)).is_file()]
    if not todo:
        return {"ok": False, "restored": [], "kept": [],
                "error": "không có snapshot .pre-0.111.0: kho chưa từng được 0.111.0 nâng lên, không có gì để khôi phục"}
    for store, table, marker in todo:
        snap = store.with_name(store.name + SNAPSHOT_SUFFIX)
        with closing(sqlite3.connect(str(snap), timeout=10)) as c:
            if marker in {r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}:
                return {"ok": False, "restored": restored, "kept": kept,
                        "error": f"{snap.name} đã có cột {marker}; không phải bản trước 0.111.0"}
        if store.is_file():
            post = store.with_name(f"{store.name}.post-0.111.0-{stamp}")
            _backup(store, post)
            kept.append(str(post))
        _backup(snap, store)
        with closing(sqlite3.connect(str(store), timeout=10)) as c:
            c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        restored.append(str(store))
    return {"ok": True, "restored": restored, "kept": kept}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Khôi phục kho Kanban và kho phiên về snapshot trước 0.111.0 "
                                             "(chạy khi Javis đã tắt).")
    ap.add_argument("--state-dir", default=os.environ.get("JAVIS_STATE_DIR", ""),
                    help="thư mục state của Javis (mặc định JAVIS_STATE_DIR)")
    ap.add_argument("--yes", action="store_true", help="xác nhận Javis đã tắt và chấp nhận mất thay đổi sau lúc nâng")
    a = ap.parse_args(argv)
    if not a.state_dir:
        print("Thiếu --state-dir (hay biến JAVIS_STATE_DIR).", file=sys.stderr)
        return 2
    if not a.yes:
        print("Tắt Javis trước, rồi chạy lại với --yes. Việc Kanban và tin chat sau lúc nâng lên 0.111.0 sẽ không còn "
              "trong kho chạy; bản sao kho hiện tại được giữ cạnh file kho.", file=sys.stderr)
        return 2
    res = restore(a.state_dir)
    if not res["ok"]:
        print("Không khôi phục được: " + res["error"], file=sys.stderr)
        return 1
    print("Đã khôi phục: " + ", ".join(res["restored"]) +
          (". Kho trước khi khôi phục giữ ở: " + ", ".join(res["kept"]) if res["kept"] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
