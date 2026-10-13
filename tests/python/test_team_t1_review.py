"""Nhóm chat team T1: hồi quy cho review mã vòng 1 (exports/reviews/PR-628-T1-code-r1-review.md, R1 tới R5).

    python tests/run.py team_t1_review -v

Đi qua factory THẬT `main._team_engine_for` (chỉ thay `_resonance_engine` bằng engine giả có `query`) và kho SQLite thật
trong thư mục tạm; không gọi model. R6 (hạ, nâng cả bộ kho) nằm ở test_team_rollback.py vì cần mã 0.109.0 thật.
Mỗi nhóm có đối chứng hợp lệ: đường đúng vẫn ra "done", bài học hợp lệ vẫn được ghi, v.v.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import sqlite3
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-team-review-")
TEMP = Path(tempfile.mkdtemp(prefix="javis-team-review-w-"))

import main  # noqa: E402
import sessions  # noqa: E402
import task_store  # noqa: E402
import team_runner as TR  # noqa: E402
import team_store  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {str(extra)[:400]}" if extra and not cond else ""))
    if not cond:
        fails.append(name)


def run(coro):
    return asyncio.run(coro)


INFO = {"agent-one": {"slug": "one", "name": "One", "system": "You are One.", "model": "", "model_provider": ""},
        "agent-two": {"slug": "two", "name": "Two", "system": "You are Two.", "model": "", "model_provider": ""}}
IDENT = dict(INFO)   # mã bền -> thông tin agent; test sửa để giả lập xoá, tạo lại cùng slug


def ident(root, key):
    return IDENT.get(key)


class Engine:
    """Engine giả có `query` như engine thật; `effect` chạy khi bắt đầu query (lúc lượt đang ở engine)."""

    def __init__(self, events, effect=None, available=True):
        self.events, self.effect, self.available, self.prompts = events, effect, available, []

    def is_available(self):
        return self.available

    async def query(self, prompt):
        self.prompts.append(prompt)
        if self.effect:
            self.effect()
        for ev in self.events:
            yield ev


_n = [0]


def world(label, engine_for=None, agents=("agent-one", "agent-two")):
    _n[0] += 1
    d = TEMP / f"{_n[0]:02d}-{label}"
    (d / "agents").mkdir(parents=True)
    for k in agents:
        (d / "agents" / f"{INFO[k]['slug']}.md").write_text(f"---\nname: {INFO[k]['name']}\nrole: Helper\n---\n",
                                                            encoding="utf-8", newline="\n")
    ss = sessions.SessionStore(db_path=d / "chat.db")
    ts = task_store.TaskStore(d / "kanban.sqlite3")
    tm = team_store.TeamStore(d / "team.sqlite3")
    tid = team_store.new_team_id()
    sid = ss.create_session(brain=str(d), channel=f"team:{tid}")
    tm.create_team(str(d), label, "", sid, team_id=tid)
    for k in agents:
        tm.add_member(tid, k, INFO[k]["slug"])
    tm.set_leader(tid, agents[0])
    r = TR.TeamRunner(teams=tm, tasks=ts, sessions=ss, engine_for=engine_for or main._team_engine_for,
                      agent_info=ident)
    return r, tm, ts, ss, tm.get(tid), d


def memory_text(d):
    return "\n".join(p.read_text(encoding="utf-8") for p in d.glob("memory/agents/**/*") if p.is_file())


def agent_msgs(ss, team):
    return [m for m in ss.get_team_messages_page(team["session_id"], limit=200)["messages"] if m["author_kind"] == "agent"]


def job_via_factory(label, events, *, effect=None, available=True, build=None, mention="agent-one", text="Viết tóm tắt"):
    """Một việc @ trực tiếp chạy qua factory thật. `build` thay hẳn `_resonance_engine` (vd. trả None hay ném lỗi)."""
    r, tm, ts, ss, t, d = world(label)
    job = r.submit(t["team_id"], text, mentions=[mention], as_job=True, client_msg_id=label)["task_id"]
    holder = {}

    def make_effect():
        return (lambda: effect(r, tm, ts, ss, t, job)) if effect else None

    def fake_resonance(system, tag):
        if build is not None:
            return build()
        eng = Engine(events, make_effect(), available)
        holder["eng"] = eng
        return eng, {"reason": "fake"}

    with patch.object(main, "_team_agent_info", side_effect=ident), \
            patch.object(main, "_resonance_engine", side_effect=fake_resonance):
        run(r.dispatch_once())
    return {"r": r, "tm": tm, "ts": ts, "ss": ss, "t": t, "d": d, "job": job, "task": ts.get_task(job),
            "turns": tm.turns(t["team_id"]), "msgs": agent_msgs(ss, t), "eng": holder.get("eng")}


class Recorder:
    def __init__(self, answers=None):
        self.reqs, self.answers = [], list(answers or [])

    def engine_for(self, team, key, role):
        async def run_(req):
            self.reqs.append(req)
            return {"text": self.answers.pop(0) if self.answers else "OK"}
        return "fake", "fake", run_



# ═════════════ R1: kết cục engine lỗi hay rỗng không bao giờ thành sản phẩm ═════════════
def section_r1():
    BAD = {
        "final_error": [{"type": "final", "content": "Engine failed", "is_error": True, "subtype": "error_during_execution"}],
        "auth_race": [{"type": "final", "content": "Please run /login", "auth_refresh_race": True}],
        "error_after_final": [{"type": "final", "content": "Câu trả lời"}, {"type": "error", "content": "socket closed"}],
        "error_event": [{"type": "error", "content": "rate limited"}, {"type": "final", "content": "Câu trả lời"}],
        "tool_call": [{"type": "tool_call", "name": "Write", "input": {}}, {"type": "final", "content": "OK"}],
        "tool_result": [{"type": "tool_result", "content": "x"}, {"type": "final", "content": "OK"}],
        "empty_final": [{"type": "final", "content": ""}],
        "blank_final": [{"type": "final", "content": "  \n "}],
        "no_final": [{"type": "text", "content": "đang nghĩ"}],
    }
    for name, events in BAD.items():
        w = job_via_factory(f"r1-{name}", events)
        turns = w["turns"]
        check(f"R1 {name}: việc không xong, bị chặn 'failed' để Chạy lại",
              w["task"]["status"] == "team_blocked" and w["task"]["block_kind"] == "failed", w["task"])
        check(f"R1 {name}: lượt đã gọi model nên TÍNH (error, có mốc engine), không hoàn, không 'ok'",
              [x["status"] for x in turns] == ["error"] and turns[0]["engine_at"] is not None, turns)
        check(f"R1 {name}: không có tin kết quả nào của agent", w["msgs"] == [], w["msgs"])

    w = job_via_factory("r1-control", [{"type": "usage", "input_tokens": 5, "output_tokens": 3},
                                       {"type": "final", "content": "Bản tóm tắt hợp lệ"}])
    check("R1 đối chứng: final hợp lệ thì việc xong, lượt ok, có token",
          w["task"]["status"] == "done" and [(x["status"], x["tokens_in"]) for x in w["turns"]] == [("ok", 5)]
          and w["task"]["result"] == "Bản tóm tắt hợp lệ")
    w = job_via_factory("r1-resume", [{"type": "error", "content": "mất mạch", "resume_failed": True},
                                      {"type": "final", "content": "Đã mồi lại, trả lời"}])
    check("R1 đối chứng: lỗi mất mạch đã được engine mồi lại trong lượt không biến lượt tốt thành lỗi",
          w["task"]["status"] == "done")

    # Chạy lại sau khi engine trả lời được: việc xong.
    w = job_via_factory("r1-retry", BAD["final_error"])
    with patch.object(main, "_team_agent_info", side_effect=ident), \
            patch.object(main, "_resonance_engine", return_value=(Engine([{"type": "final", "content": "Lần này ổn"}]),
                                                                   {})):
        w["r"].unblock(w["job"], "retry")
        run(w["r"].dispatch_once())
    check("R1 Chạy lại sau lỗi engine: việc xong, hai lượt đều tính (error rồi ok)",
          w["ts"].get_task(w["job"])["status"] == "done"
          and sorted(x["status"] for x in w["tm"].turns(w["t"]["team_id"])) == ["error", "ok"])

    # Lượt trò chuyện: final lỗi không thành câu trả lời.
    r, tm, ts, ss, t, d = world("r1-reply")
    with patch.object(main, "_team_agent_info", side_effect=ident), \
            patch.object(main, "_resonance_engine", return_value=(Engine(BAD["final_error"]), {})):
        outs = run(r.run_replies(r.submit(t["team_id"], "Chào", client_msg_id="r1-reply")))
    check("R1 lượt trò chuyện final lỗi: kết cục error, không đăng câu trả lời, lượt tính",
          [o["status"] for o in outs] == ["error"] and agent_msgs(ss, t) == []
          and [x["status"] for x in tm.turns(t["team_id"])] == ["error"])

    o = TR.TextOnlyOutcome()
    for ev in ({"type": "text", "content": "a"}, {"type": "usage", "input_tokens": 2, "output_tokens": 1},
               {"type": "final", "content": "Xong"}):
        o.note(ev)
    check("R1 hợp đồng chỉ chữ: final hợp lệ trả chữ và token", o.result() == {"text": "Xong", "tokens_in": 2,
                                                                              "tokens_out": 1})
    o = TR.TextOnlyOutcome()
    o.note({"type": "final", "content": "x", "is_error": True, "subtype": "error_max_turns"})
    try:
        o.result()
        kind = None
    except TR.EngineOutcomeError as ex:
        kind = ex.kind
    check("R1 hợp đồng chỉ chữ: final is_error ném EngineOutcomeError(final_error)", kind == "final_error")


# ═════════════ R2: lượt sau còn lịch sử trước (cửa sổ có giới hạn, chỉ của nhóm này) ═════════════
def section_r2():
    rec = Recorder(["ANSWER_ONE: đã ghi nhận ngân sách."])
    r, tm, ts, ss, t, d = world("r2", rec.engine_for)
    run(r.run_replies(r.submit(t["team_id"], "SOURCE_739: budget 73 million", client_msg_id="a")))
    run(r.run_replies(r.submit(t["team_id"], "Divide that budget into three parts.", client_msg_id="b")))
    p2 = rec.reqs[1]["prompt"]
    check("R2 lượt thứ hai có tin gốc của chủ và câu trả lời trước", "SOURCE_739" in p2 and "ANSWER_ONE" in p2, p2)
    check("R2 câu trả lời trước của chính agent có nhãn (bạn), tin sau lượt trước có nhãn mới",
          "One (bạn)] ANSWER_ONE" in p2 and " mới Chủ nhóm] Divide" in p2, p2)

    # Đối chứng phạm vi: nhóm khác cùng kho không lọt vào.
    tid_b = team_store.new_team_id()
    sid_b = ss.create_session(brain=str(d), channel=f"team:{tid_b}")
    tm.create_team(str(d), "B", "", sid_b, team_id=tid_b)
    tm.add_member(tid_b, "agent-one", "one")
    tm.set_leader(tid_b, "agent-one")
    run(r.run_replies(r.submit(tid_b, "SECRET_B chỉ của nhóm B", client_msg_id="sb")))
    run(r.run_replies(r.submit(t["team_id"], "Tiếp tục nhé", client_msg_id="c")))
    check("R2 không đưa dữ liệu nhóm khác vào prompt", "SECRET_B" not in rec.reqs[-1]["prompt"]
          and "SECRET_B" in rec.reqs[-2]["prompt"])

    # Trần: tối đa 20 tin gần nhất, tối đa 8.000 ký tự.
    rec = Recorder()
    r, tm, ts, ss, t, d = world("r2-cap", rec.engine_for)
    tm.set_caps(t["team_id"], {"daily_turns": 1000})
    for i in range(25):
        ss.append_team_message(t["session_id"], "user", f"MSG_{i:02d}", author_kind="owner", client_msg_id=f"m{i}")
    run(r.run_replies(r.submit(t["team_id"], "Câu hỏi cuối", client_msg_id="last")))
    p = rec.reqs[-1]["prompt"]
    check("R2 trần 20 tin: tin cũ nhất ngoài cửa sổ bị bỏ, tin gần nhất còn",
          "MSG_05" not in p and "MSG_06" in p and "MSG_24" in p, p[-1500:])
    ss.append_team_message(t["session_id"], "user", "BIG_" + "x" * 9000, author_kind="owner", client_msg_id="big")
    run(r.run_replies(r.submit(t["team_id"], "SHORT_AFTER", client_msg_id="short")))
    p = rec.reqs[-1]["prompt"]
    check("R2 trần 8.000 ký tự: tin quá dài không vào cửa sổ, tin mới hơn vẫn có", "BIG_" not in p.split("\n\n")[0]
          and "SHORT_AFTER" in p)


# ═════════════ R3: đầu ra không hợp lệ không ghi bộ nhớ bền ═════════════
def section_r3():
    LESSON = "\nJAVIS_LESSON: {}"


    def lesson_events(mark):
        return [{"type": "final", "content": "Kết quả" + LESSON.format(mark)}]


    w = job_via_factory("r3-control", lesson_events("GOOD_LESSON_101"))
    check("R3 đối chứng: đầu ra hợp lệ ghi bài học vào bộ nhớ agent, tin sạch marker",
          "GOOD_LESSON_101" in memory_text(w["d"]) and w["task"]["status"] == "done"
          and "JAVIS_LESSON" not in w["msgs"][0]["content"])
    w = job_via_factory("r3-rule", [{"type": "final", "content": "Kết quả\nJAVIS_RULE: RULE_202 luôn viết ngắn"}])
    check("R3 JAVIS_RULE trong lượt nhóm hạ thành bài học (không có chủ nói trực tiếp), ghi khi hợp lệ",
          "RULE_202" in memory_text(w["d"]) and "JAVIS_RULE" not in w["msgs"][0]["content"])

    LATE = {
        "member_left": lambda r, tm, ts, ss, t, job: tm.remove_member(t["team_id"], "agent-one"),
        "cancelled": lambda r, tm, ts, ss, t, job: ts.team_cancel(job),
        "revision": lambda r, tm, ts, ss, t, job: ts.team_amend(job, "thêm phần mới"),
    }
    for name, eff in LATE.items():
        mark = f"LATE_{name.upper()}_739"
        w = job_via_factory(f"r3-{name}", lesson_events(mark), effect=eff)
        m = w["msgs"][0] if w["msgs"] else {"meta": {}}
        check(f"R3 {name}: đầu ra muộn KHÔNG ghi bài học vào bộ nhớ agent", mark not in memory_text(w["d"]),
              memory_text(w["d"]))
        check(f"R3 {name}: đầu ra muộn giữ làm bằng chứng trên tin (applied=false, bài học treo)",
              m["meta"].get("applied") is False and mark in " ".join(m["meta"].get("held_lessons") or []), m["meta"])

    # Đổi trưởng nhóm giữa bước lập kế hoạch (việc chung, không @).
    r, tm, ts, ss, t, d = world("r3-leader")
    job = r.submit(t["team_id"], "Việc chung", as_job=True, client_msg_id="lead")["task_id"]
    eng = Engine(lesson_events("LATE_LEADER_739"), lambda: tm.set_leader(t["team_id"], "agent-two"))
    eng2 = Engine([{"type": "final", "content": "Two tự làm xong"}])
    with patch.object(main, "_team_agent_info", side_effect=ident), \
            patch.object(main, "_resonance_engine", side_effect=[(eng, {}), (eng2, {})]):
        run(r.dispatch_once())
    check("R3 đổi trưởng nhóm giữa lượt điều phối: kế hoạch cũ không ghi bài học, trưởng nhóm mới làm tiếp",
          "LATE_LEADER_739" not in memory_text(d) and ts.get_task(job)["status"] == "done")


    # Xoá agent rồi tạo lại CÙNG slug khi lượt đang ở engine: mã bền cũ không còn trỏ tới slug đó.
    def recreate(r, tm, ts, ss, t, job):
        IDENT.pop("agent-one", None)
        IDENT["agent-one-new"] = dict(INFO["agent-one"])


    w = job_via_factory("r3-recreate", lesson_events("LATE_RECREATE_739"), effect=recreate)
    IDENT.clear()
    IDENT.update(INFO)
    check("R3 xoá rồi tạo lại cùng slug: bài học của mã cũ không vào bộ nhớ của agent mới",
          "LATE_RECREATE_739" not in memory_text(w["d"]), memory_text(w["d"]))

    # Không có khe giữa kiểm và ghi: thao tác bỏ thành viên đang giữ khoá chấp nhận thì pha chấp nhận đợi, rồi thấy đã rời.
    holding = threading.Event()


    def remove_under_lock(r, tm, ts, ss, t, job):
        def hold():
            with r.accept_lock:
                holding.set()
                time.sleep(0.3)
                tm.remove_member(t["team_id"], "agent-one")
        threading.Thread(target=hold, daemon=True).start()
        holding.wait(2)


    w = job_via_factory("r3-race", lesson_events("LATE_RACE_739"), effect=remove_under_lock)
    check("R3 bỏ thành viên trong khoá chấp nhận: pha chấp nhận đợi khoá, thấy đã rời, không ghi bài học",
          "LATE_RACE_739" not in memory_text(w["d"]) and w["msgs"][0]["meta"]["status"] == "member_left", w["msgs"])

    # Một lượt bị xử lý lặp: bài học ghi đúng một lần.
    r, tm, ts, ss, t, d = world("r3-twice", Recorder().engine_for)
    tu = tm.reserve_turn(t["team_id"], None, None, "agent-one", "leader_reply")
    tm.mark_engine(tu, "fake", "fake")
    tm.settle_turn(tu, "ok")
    hits = []
    res = {"text": "Trả lời", "commit": lambda: hits.append(1), "lessons": ["L"]}
    r._accept(t["team_id"], "agent-one", "leader_reply", None, None, tu, res, None, None)
    r._accept(t["team_id"], "agent-one", "leader_reply", None, None, tu, res, None, None)
    check("R3 xử lý lặp cùng lượt: commit đúng một lần", hits == [1], hits)
    tu2 = tm.reserve_turn(t["team_id"], None, None, "agent-one", "leader_reply")
    tm.mark_engine(tu2, "fake", "fake")
    tm.settle_turn(tu2, "error")
    check("R3 lượt không 'ok' không giành được quyền ghi", tm.claim_commit(tu2) is False)


# ═════════════ R4: chưa dựng được engine thì không tính lượt ═════════════
def section_r4():
    def none_engine():
        return None, {"reason": "provider chưa sẵn sàng"}


    def broken_build():
        raise RuntimeError("cấu hình hỏng")


    for name, kw in (("none", {"build": none_engine}), ("unavailable", {"available": False}),
                     ("build_raises", {"build": broken_build})):
        w = job_via_factory(f"r4-{name}", [{"type": "final", "content": "không bao giờ tới"}], **kw)
        turns = w["turns"]
        check(f"R4 {name}: lượt hoàn đúng một lần, không có mốc engine",
              [x["status"] for x in turns] == ["refunded"] and turns[0]["engine_at"] is None, turns)
        check(f"R4 {name}: không lời gọi model nào", (w["eng"] is None) or w["eng"].prompts == [])
        check(f"R4 {name}: việc bị chặn có lý do để Chạy lại, trần ngày không bị trừ",
              w["task"]["status"] == "team_blocked" and "engine" in (w["task"]["block_reason"] or "")
              and w["tm"].count_team_turns(w["t"]["team_id"], 0) == 0, w["task"])

    # Bị huỷ khi engine đang dựng (chưa tới mốc): hoàn, không interrupted.
    gate = threading.Event()


    def slow_build():
        gate.wait(5)
        return Engine([{"type": "final", "content": "x"}]), {}


    r, tm, ts, ss, t, d = world("r4-cancel")
    job = r.submit(t["team_id"], "Việc", mentions=["agent-one"], as_job=True, client_msg_id="c")["task_id"]


    async def cancel_while_building():
        await r.dispatch_once(wait=False)
        for _ in range(300):
            if [x for x in tm.turns(t["team_id"]) if x["status"] == "reserved"] and tm.busy_of("agent-one"):
                break
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.1)
        r.cancel_job(job)
        await r.wait_jobs()
        gate.set()


    with patch.object(main, "_team_agent_info", side_effect=ident), \
            patch.object(main, "_resonance_engine", side_effect=lambda s, tag: slow_build()):
        run(cancel_while_building())
    check("R4 huỷ khi engine đang dựng: lượt hoàn (không interrupted), khoá bận nhả",
          [x["status"] for x in tm.turns(t["team_id"])] == ["refunded"] and tm.busy_of("agent-one") is None,
          tm.turns(t["team_id"]))

    # Restart khi lượt còn giữ chỗ chưa tới mốc: phục hồi hoàn đúng một lần, chạy lại phục hồi không đổi gì.
    r, tm, ts, ss, t, d = world("r4-restart")
    tu = tm.reserve_turn(t["team_id"], None, None, "agent-one", "leader_reply")
    r.recover()
    r.recover()
    check("R4 phục hồi sau restart: lượt chưa tới mốc hoàn đúng một lần",
          [(x["status"], x["engine_at"]) for x in tm.turns(t["team_id"])] == [("refunded", None)])


# ═════════════ R5: I/O chặn không chạy trên event loop ═════════════
def section_r5():
    def slow(fn, s=0.25, log=None, name=""):
        def wrap(*a, **k):
            time.sleep(s)
            out = fn(*a, **k)
            if log is not None:
                log.append((name, time.monotonic()))
            return out
        return wrap


    async def max_gap(coro_factory, beats_n=80):
        beats = []
        stop = asyncio.Event()

        async def pulse():
            while not stop.is_set():
                t0 = time.perf_counter()
                await asyncio.sleep(0.005)
                beats.append(time.perf_counter() - t0)
        p = asyncio.create_task(pulse())
        await asyncio.sleep(0.02)
        out = await coro_factory()
        stop.set()
        await p
        return round(max(beats) * 1000, 1), out


    rec = Recorder()
    r, tm, ts, ss, t, d = world("r5-reply", rec.engine_for)
    with patch.object(tm, "reserve_turn", side_effect=slow(tm.reserve_turn)), \
            patch.object(tm, "settle_turn", side_effect=slow(tm.settle_turn)), \
            patch.object(ss, "append_team_message", side_effect=slow(ss.append_team_message)):
        sub = r.submit(t["team_id"], "Hello", client_msg_id="lag")
        gap, _ = run(max_gap(lambda: r.run_replies(sub)))
    check("R5 lượt trả lời với kho chậm 250 ms mỗi ghi: event loop không bị chặn quá 100 ms", gap < 100, gap)

    rec = Recorder()
    r, tm, ts, ss, t, d = world("r5-job", rec.engine_for)
    job = r.submit(t["team_id"], "Việc", mentions=["agent-one"], as_job=True, client_msg_id="j")["task_id"]
    with patch.object(ts, "get_task", side_effect=slow(ts.get_task, 0.1)), \
            patch.object(tm, "claim_step", side_effect=slow(tm.claim_step)), \
            patch.object(tm, "finish_step", side_effect=slow(tm.finish_step)):
        gap, _ = run(max_gap(lambda: r.dispatch_once()))
    check("R5 việc nhóm với kho chậm: event loop không bị chặn, việc vẫn xong", gap < 100
          and ts.get_task(job)["status"] == "done", (gap, ts.get_task(job)["status"]))

    # Đồng thời: trần ngày 1, hai lượt cùng lúc chỉ một lượt được giữ chỗ (đếm và ghi cùng giao dịch).
    rec = Recorder()
    r, tm, ts, ss, t, d = world("r5-cap", rec.engine_for)
    s1 = r.submit(t["team_id"], "A", mentions=["agent-one"], client_msg_id="x1")
    s2 = r.submit(t["team_id"], "B", mentions=["agent-two"], client_msg_id="x2")
    tm.set_caps(t["team_id"], {"daily_turns": 1})


    async def both():
        return await asyncio.gather(r.run_replies(s1), r.run_replies(s2))


    with patch.object(tm, "reserve_turn", side_effect=slow(tm.reserve_turn, 0.1)):
        outs = run(both())
    statuses = sorted(o[0]["status"] for o in outs)
    check("R5 hai lượt đồng thời, trần ngày 1: đúng một lượt chạy, lượt kia chạm trần, không lượt nào tới engine thừa",
          statuses == ["cap", "done"] and len(rec.reqs) == 1
          and len([x for x in tm.turns(t["team_id"]) if x["status"] != "refunded"]) == 1, (statuses, len(rec.reqs)))
    tm2 = team_store.TeamStore(TEMP / "r5-threads.sqlite3")
    got, errs = [], []


    def grab():
        try:
            got.append(tm2.reserve_turn("tmX", None, None, "a", "leader_reply", daily_cap=3, day_start=0))
        except team_store.TurnCapReached:
            errs.append(1)


    ths = [threading.Thread(target=grab) for _ in range(8)]
    for th in ths:
        th.start()
    for th in ths:
        th.join()
    check("R5 tám luồng giữ chỗ cùng lúc, trần 3: đúng 3 lượt, 5 lượt bị từ chối", len(got) == 3 and len(errs) == 5,
          (len(got), len(errs)))

    # Huỷ (lặp) khi luồng phụ đang ghi lượt giữ chỗ: chờ ghi xong rồi hoàn, không lượt mồ côi, không kẹt khoá.
    rec = Recorder()
    r, tm, ts, ss, t, d = world("r5-cancel", rec.engine_for)
    sub = r.submit(t["team_id"], "Hello", client_msg_id="cc")


    async def cancel_twice():
        task = asyncio.ensure_future(r.run_replies(sub))
        await asyncio.sleep(0.05)
        task.cancel()
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
            return "finished"
        except asyncio.CancelledError:
            return "cancelled"


    with patch.object(tm, "reserve_turn", side_effect=slow(tm.reserve_turn, 0.3)):
        how = run(cancel_twice())
    lock = r._locks.get("agent-one")
    check("R5 huỷ lặp khi đang giữ chỗ: lượt vừa ghi được hoàn, không còn 'reserved', không gọi engine, không kẹt khoá",
          how == "cancelled" and [x["status"] for x in tm.turns(t["team_id"])] == ["refunded"] and rec.reqs == []
          and tm.busy_of("agent-one") is None and not (lock and lock.locked()), (how, tm.turns(t["team_id"])))

    # Huỷ khi luồng phụ đang chốt lượt: chốt xong (không bỏ dở 'running'), dòng khoá chỉ nhả SAU khi chốt xong.
    rec = Recorder()
    r, tm, ts, ss, t, d = world("r5-settle", rec.engine_for)
    sub = r.submit(t["team_id"], "Hello", client_msg_id="cs")
    order = []


    async def cancel_during_settle():
        task = asyncio.ensure_future(r.run_replies(sub))
        for _ in range(300):
            if rec.reqs:
                break
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.05)
        task.cancel()
        await asyncio.sleep(0.02)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


    with patch.object(tm, "settle_turn", side_effect=slow(tm.settle_turn, 0.3, order, "settle")), \
            patch.object(tm, "release_busy", side_effect=slow(tm.release_busy, 0, order, "release")):
        run(cancel_during_settle())
    lock = r._locks.get("agent-one")
    names = [n for n, _ in order]
    check("R5 huỷ khi đang chốt lượt: lượt chốt 'ok' (không treo running), nhả khoá sau khi chốt xong",
          [x["status"] for x in tm.turns(t["team_id"])] == ["ok"] and names[:2] == ["settle", "release"]
          and tm.busy_of("agent-one") is None and not (lock and lock.locked()), (tm.turns(t["team_id"]), names))

    # Huỷ khi luồng phụ đang lấy dòng khoá bận: dòng vừa lấy được nhả (undo), khoá trong tiến trình nhả.
    rec = Recorder()
    r, tm, ts, ss, t, d = world("r5-busy", rec.engine_for)
    sub = r.submit(t["team_id"], "Hello", client_msg_id="cb")


    async def cancel_during_busy():
        task = asyncio.ensure_future(r.run_replies(sub))
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


    with patch.object(tm, "acquire_busy", side_effect=slow(tm.acquire_busy, 0.3)):
        run(cancel_during_busy())
    lock = r._locks.get("agent-one")
    check("R5 huỷ khi đang lấy khoá bận: dòng khoá nhả, khoá trong tiến trình nhả, lượt hoàn",
          tm.busy_of("agent-one") is None and not (lock and lock.locked())
          and [x["status"] for x in tm.turns(t["team_id"])] == ["refunded"], tm.turns(t["team_id"]))

    # Kho lỗi khi giữ chỗ: không có dòng nào, việc bị chặn có lý do, không kẹt khoá.
    rec = Recorder()
    r, tm, ts, ss, t, d = world("r5-error", rec.engine_for)
    job = r.submit(t["team_id"], "Việc", mentions=["agent-one"], as_job=True, client_msg_id="e")["task_id"]
    with patch.object(tm, "reserve_turn", side_effect=sqlite3.OperationalError("database is locked")):
        run(r.dispatch_once())
    lock = r._locks.get("agent-one")
    check("R5 kho lỗi khi giữ chỗ: việc chặn 'failed' có lý do, không có lượt, không kẹt khoá",
          ts.get_task(job)["status"] == "team_blocked" and "database is locked" in ts.get_task(job)["block_reason"]
          and tm.turns(t["team_id"]) == [] and not (lock and lock.locked()), ts.get_task(job))

    # Route ghi thật (POST /teams/{id}/messages) với kho phiên chậm: event loop không bị chặn.
    import httpx  # noqa: E402

    BR = TEMP / "route-brain"
    (BR / "agents").mkdir(parents=True)
    for k in ("agent-one", "agent-two"):
        (BR / "agents" / f"{INFO[k]['slug']}.md").write_text(f"---\nname: {INFO[k]['name']}\nrole: Helper\n---\n",
                                                             encoding="utf-8", newline="\n")
    main._TEAM_API.deps.spawn = lambda coro: coro.close() if asyncio.iscoroutine(coro) else None


    async def route_probe():
        tr = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=tr, base_url="http://127.0.0.1:8080") as c:
            resp = await c.post(f"/teams?brain={BR}", json={"name": "Route", "members": ["one"], "leader_slug": "one"})
            tid = resp.json()["team"]["team_id"]
            store = main.get_store()
            with patch.object(store, "append_team_message", side_effect=slow(store.append_team_message)):
                async def send():
                    return await c.post(f"/teams/{tid}/messages?brain={BR}",
                                        json={"text": "Xin chào", "client_msg_id": "route-1"})
                gap, resp2 = await max_gap(send)
            return gap, resp2.status_code


    gap, code = run(route_probe())
    check("R5 route gửi tin với kho phiên chậm 250 ms: 200 và event loop không bị chặn quá 100 ms",
          code == 200 and gap < 100, (gap, code))


# Mỗi nhóm chạy riêng: một nhóm văng lỗi (vd. mã cũ thiếu API) thành FAIL của nhóm đó, không che nhóm khác.
for _name, _fn in (("R1", section_r1), ("R2", section_r2), ("R3", section_r3), ("R4", section_r4), ("R5", section_r5)):
    try:
        _fn()
    except Exception as _ex:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        check(f"{_name} chạy hết nhóm kiểm", False, f"{type(_ex).__name__}: {_ex}")

print(f"\n{'FAIL' if fails else 'PASS'} - test_team_t1_review: {len(fails)} lỗi")
raise SystemExit(1 if fails else 0)
