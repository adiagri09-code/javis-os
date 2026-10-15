"""CHƯA CHẠY. Kịch bản đo nhóm chat thích nghi TRÊN VPS (T4, 0.157.0), chỉ ĐỌC, chuẩn bị sẵn để chạy khi chủ dự án cho phép.

TRẠNG THÁI: chưa chạy lần nào. Không ai được chạy script này khi chưa có lệnh duyệt trực tiếp của chủ dự án (GOAL mục 10, 13).
Script KHÔNG tự kết nối tới VPS nào: người vận hành đăng nhập VPS theo cách thường lệ, chép script vào trong container Javis
rồi chạy ở ĐÓ, trỏ tới chính Javis trong container (mặc định http://127.0.0.1:8080).

    python team_adaptive_vps_measure.py --owner-approved "<mã duyệt hay link tin duyệt>" \\
        --base-url http://127.0.0.1:8080 --state-dir /app/state --brain "<tên brain>" --out vps-t4.json

Chỉ đọc:
- HTTP: chỉ GET (danh sách nhóm, trang nhóm, trang tin, khung nhịp của trợ lý, /health). Không POST, không thả reaction,
  không gửi tin, không bật tắt gì, không gọi model. Phiên đăng nhập lấy từ biến môi trường JAVIS_MEASURE_COOKIE (chuỗi
  Cookie của trình duyệt đã đăng nhập), không ghi ra file kết quả.
- SQLite: mở `mode=ro` (URI chỉ đọc), chỉ đếm dòng và kích thước file; không ghi, không VACUUM, không tạo chỉ mục.
- Header `Server-Timing` (app;dur=) tách thời gian Javis xử lý khỏi thời gian đi qua proxy.

Kết quả là JSON: máy, phiên bản, số dòng các kho, p50/p95 từng route (thời gian vòng và Server-Timing), độ trễ `/health` khi
có tải đọc đồng thời (đại diện cho event loop bị giữ). So với docs/dev/team-chat-t4-bench.md (máy local, engine giả).
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sqlite3
import statistics
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

STORES = {
    "team.sqlite3": ("teams", "team_members", "team_reactions", "team_turns", "team_replies"),
    "conversations.db": ("sessions", "messages", "dm_reactions"),
    "resonance.sqlite3": ("resonance_agents", "agent_calls", "agent_pulse", "pulse_signals", "pulse_contrib"),
    "agent_judge.sqlite3": ("decisions",),
    "kanban.sqlite3": ("tasks",),
}


def get(base, path, params, cookie, timeout=30):
    url = base.rstrip("/") + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, method="GET", headers={"Cookie": cookie} if cookie else {})
    t = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
        st = r.headers.get("server-timing", "")
    ms = (time.perf_counter() - t) * 1000.0
    app = None
    if st.startswith("app;dur="):
        try:
            app = float(st.split("=", 1)[1].split(",")[0])
        except ValueError:
            app = None
    return ms, app, body


def pct(xs, q):
    s = sorted(xs)
    return s[min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))] if s else 0.0


def store_counts(state: Path) -> dict:
    out = {}
    for name, tables in STORES.items():
        p = state / name
        if not p.is_file():
            out[name] = {"present": False}
            continue
        row = {"present": True, "bytes": p.stat().st_size}
        con = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True, timeout=5)
        try:
            for t in tables:
                try:
                    row[t] = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                except sqlite3.Error:
                    row[t] = None
        finally:
            con.close()
        out[name] = row
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="CHƯA CHẠY: đo chỉ đọc trên VPS, cần chủ dự án duyệt")
    ap.add_argument("--owner-approved", default="", help="mã hay link tin duyệt của chủ dự án (bắt buộc)")
    ap.add_argument("--base-url", default="http://127.0.0.1:8080")
    ap.add_argument("--state-dir", default=os.environ.get("JAVIS_STATE_DIR", ""))
    ap.add_argument("--brain", default="brain")
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--readers", type=int, default=4, help="số luồng GET đồng thời khi đo /health có tải")
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    if not a.owner_approved.strip():
        print("DỪNG: chưa có duyệt của chủ dự án (--owner-approved). Script này chưa chạy lần nào và chỉ chạy khi được "
              "cho phép.", file=sys.stderr)
        return 2
    host = urllib.parse.urlparse(a.base_url).hostname or ""
    if host not in ("127.0.0.1", "localhost", "::1"):
        print("DỪNG: chỉ đo Javis ngay trong container (127.0.0.1); không đo qua mạng.", file=sys.stderr)
        return 2
    cookie = os.environ.get("JAVIS_MEASURE_COOKIE", "")
    q = {"brain": a.brain}
    report = {"kind": "t4_vps_readonly", "approved_by": a.owner_approved.strip()[:200],
              "date": time.strftime("%Y-%m-%d %H:%M:%S"),
              "machine": {"platform": platform.platform(), "python": platform.python_version(),
                          "cpu_count": os.cpu_count()}}
    if a.state_dir:
        report["stores"] = store_counts(Path(a.state_dir))
    _, _, body = get(a.base_url, "/teams", q, cookie)
    teams = json.loads(body).get("teams") or []
    report["teams_seen"] = len(teams)
    biggest = max(teams, key=lambda t: int((t.get("counts") or {}).get("messages") or 0), default=None)
    routes = {"GET /health": ("/health", {}), "GET /teams": ("/teams", q)}
    if biggest:
        tid = biggest["team_id"]
        routes["GET /teams/{id}"] = (f"/teams/{tid}", q)
        routes["GET /teams/{id}/messages"] = (f"/teams/{tid}/messages", q)
        slug = next((m.get("slug") for m in biggest.get("members") or [] if m.get("slug")), None)
        if slug:
            routes["GET /agents/{slug}/pulse"] = (f"/agents/{slug}/pulse", q)
    res = {}
    for name, (path, params) in routes.items():
        rt, app = [], []
        for _ in range(a.runs):
            ms, srv, _ = get(a.base_url, path, params, cookie)
            rt.append(ms)
            if srv is not None:
                app.append(srv)
        res[name] = {"round_trip_p50_ms": round(statistics.median(rt), 1), "round_trip_p95_ms": round(pct(rt, 0.95), 1),
                     "server_timing_p50_ms": round(statistics.median(app), 1) if app else None,
                     "server_timing_p95_ms": round(pct(app, 0.95), 1) if app else None}
    report["routes"] = res
    # /health khi có tải đọc đồng thời: độ trễ tăng mạnh nghĩa là event loop bị giữ.
    stop, health = threading.Event(), []

    def reader(path, params):
        while not stop.is_set():
            try:
                get(a.base_url, path, params, cookie)
            except Exception:  # noqa: BLE001
                time.sleep(0.2)

    load = [r for n, r in routes.items() if n != "GET /health"]
    threads = [threading.Thread(target=reader, args=load[i % len(load)], daemon=True) for i in range(a.readers)] if load else []
    for t in threads:
        t.start()
    for _ in range(a.runs * 2):
        ms, _, _ = get(a.base_url, "/health", {}, cookie)
        health.append(ms)
        time.sleep(0.05)
    stop.set()
    report["health_under_read_load"] = {"readers": len(threads), "p50_ms": round(statistics.median(health), 1),
                                        "p95_ms": round(pct(health, 0.95), 1), "max_ms": round(max(health), 1)}
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
