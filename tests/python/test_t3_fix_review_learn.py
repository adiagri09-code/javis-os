"""Review T3 phần L (0.156.0 sửa): lượt xem xét reaction và tự rà soát.

    python tests/run.py t3_fix_review_learn -v

- L P2-1: ask_back/revise ở chat riêng không mất vì hạn mức của lượt phán xử: lượt phán xử tiêu ở mức ưu tiên
  reaction_review; cần 2 lượt trống trước khi nhận lý do; phán xử dừng vì hết hạn mức thì trạng thái "Chờ hạn mức" và nguồn
  về lý do chờ (không tiêu thụ).
- L P2-2: tin mới ở chat riêng mang mã phiên nguồn để vào ĐÚNG phiên có tin bị phản hồi (phần main ở test_t3_fix_pulse_main).

Kho thật, bộ chiếu T2 thật, hạn mức thật (`agent_budget`), lớp `agent_judge.Judge` THẬT với hàm hỏi model GIẢ (đánh dấu),
engine lượt xem xét GIẢ. Không model thật nào.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import json
import os
import tempfile
from contextlib import closing
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-fix-learn-")
os.environ.pop("JAVIS_RESONANCE_CALL_CEILING", None)
TEMP = Path(tempfile.mkdtemp(prefix="javis-fix-learn-w-"))

import agent_budget as AB  # noqa: E402
import agent_judge as AJ  # noqa: E402
import agent_judge_store as AJS  # noqa: E402
import agent_ledger as ALG  # noqa: E402
import agent_review as AR  # noqa: E402
import feedback_projector as FP  # noqa: E402
import resonance_store as RS  # noqa: E402
import sessions  # noqa: E402
import team_store  # noqa: E402

MARK = getattr(AJ, "mark_test_fake", lambda f: f)
fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {str(extra)[:500]}" if extra and not cond else ""))
    if not cond:
        fails.append(name)


def run(coro):
    return asyncio.run(coro)


def out(outcome, consumed, message="", reason="lý do"):
    return json.dumps({"outcome": outcome, "message": message, "consumed": consumed, "reason": reason},
                      ensure_ascii=False)


class Engine:
    def __init__(self):
        self.text = None
        self.calls = []

    def engine_for(self, key, ctx, purpose):
        async def run_(req):
            await req["engine_started"]()
            self.calls.append(req)
            return {"text": self.text, "tokens_in": 1, "tokens_out": 1}
        run_.marks_engine = True
        return "fake", "fake-model", run_


_n = [0]


def world(judge=None, ask_reply='{"verdict":"speak","score":0.95,"reason":"đúng lúc"}'):
    """`judge=None`: lớp Judge THẬT (kho phán xử thật, hạn mức thật qua agent_budget.wire) với hàm hỏi GIẢ."""
    _n[0] += 1
    d = TEMP / f"{_n[0]:02d}"
    d.mkdir()
    gs = RS.GoalStore(d / "resonance.sqlite3")
    ss = sessions.SessionStore(db_path=d / "chat.db")
    tm = team_store.TeamStore(d / "team.sqlite3")
    owner = RS.Principal("owner", "owner", str(d))
    key = gs.agent_set_enabled(owner, "viet", True)["agent_key"]
    AB.wire(lambda: gs)
    asks = []

    async def ask(prompt, purpose, started):
        started()
        asks.append(purpose)
        return ask_reply

    real = AJ.Judge(store=AJS.JudgeStore(d / "agent_judge.sqlite3"), ledger=lambda: ALG.CallLedger(gs),
                    wake=lambda: ALG.WakeReasons(gs), ask=MARK(ask), engine_label=lambda: ("fake-aux", "j"))
    AJ.wire(real)
    box = {"sent": [], "events": []}
    pj = FP.FeedbackProjector(resonance=lambda: gs, sessions=lambda: ss, teams=lambda: tm, team_view=lambda t, s, m: None)
    dsid = ss.create_session(brain=str(d), channel="agent:viet")
    other = ss.create_session(brain=str(d), channel="agent:viet")   # phiên báo cáo khác phiên nguồn
    eng = Engine()

    def send(k, ctx, text, meta):
        box["sent"].append((k, ctx, text, dict(meta)))
        return {"session_id": meta.get("session_id") or other, "message_id": 1}

    deps = AR.ReviewDeps(store=lambda: gs, reactions=pj, engine_for=eng.engine_for, persona=lambda k: "",
                         try_busy=lambda k, tok: True, release_busy=lambda k, tok: None, send=send,
                         publish=lambda ev: box["events"].append(ev), contexts=lambda k: [f"dm:{k}"])
    if judge is not None:
        deps.judge = judge
    host = AR.ReviewHost(deps)
    return {"gs": gs, "ss": ss, "pj": pj, "key": key, "dsid": dsid, "other": other, "eng": eng, "host": host,
            "W": ALG.WakeReasons(gs), "box": box, "asks": asks}


def dm_react(w, text, value="sad", reasons=("too_long",)):
    mid = w["ss"].append_message(w["dsid"], "assistant", text)
    got = w["ss"].set_dm_reaction(w["dsid"], mid, value=value, reasons=list(reasons), comment="", nonce=f"n{mid}-{text}",
                                  agent_key=w["key"])
    w["pj"].project("dm", got["log_id"])
    return mid, f"rx:dm:{got['log_id']}"


def use_scans(w, n):
    led = ALG.CallLedger(w["gs"])
    for i in range(n):
        cid = led.reserve(purpose="scan", reason_ref=f"scan:fill:{w['key']}:{i}", agent_key=w["key"],
                          context_ref=f"dm:{w['key']}", obligation=False)
        led.settle(cid, "ok")


def pending(w):
    return w["W"].reasons(agent_key=w["key"], status="pending", code="reaction_review")


# ═════ L P2-1a: cap 6, đã quét 4: lượt xem xét (5) rồi lượt phán xử tin mới (6) vẫn chạy và gửi ═════
w = world()
use_scans(w, 4)
mid, src = dm_react(w, "Báo cáo dài dòng")
rs = pending(w)
w["eng"].text = out("revise", [src], message="Bản ngắn gọn hơn")
res = run(w["host"].serve_reaction_review(rs[0]))
check("cap 6 đã dùng 4: lượt phán xử tin mới không bị hạn mức chặn, tin revise được gửi",
      len(w["box"]["sent"]) == 1 and w["asks"] == ["agent_judge"], (res, w["box"]["sent"], w["asks"]))
st = w["ss"].dm_reaction_of(w["dsid"], mid)
check("trạng thái 'Đã điều chỉnh' (không phải 'Phán xử chọn im')", st["status"] == "adjusted", st)

# ═════ L P2-2: tin mới mang mã phiên nguồn ═════
check("tin mới ở chat riêng mang session_id của phiên có tin bị phản hồi, reply_to đúng tin",
      w["box"]["sent"] and w["box"]["sent"][0][3].get("session_id") == w["dsid"]
      and w["box"]["sent"][0][3].get("reply_to") == mid, w["box"]["sent"])

# ═════ L P2-1b: chỉ còn 1 lượt: không nhận lý do, phản hồi không bị tiêu thụ ═════
w2 = world()
use_scans(w2, 5)
mid2, src2 = dm_react(w2, "Tin thứ hai")
rs2 = pending(w2)
w2["eng"].text = out("revise", [src2], message="Bản sửa")
res2 = run(w2["host"].serve_reaction_review(rs2[0]))
check("chỉ còn 1 lượt ở chat riêng: lượt xem xét KHÔNG chạy (cần 2: xem xét + phán xử)",
      res2.get("outcome") == "quota" and w2["eng"].calls == [], res2)
check("chỉ còn 1 lượt: lý do giữ pending, nguồn chưa tiêu thụ",
      w2["W"].get(rs2[0]["id"])["status"] == "pending"
      and all(s["consumed_at"] is None for s in w2["W"].sources(rs2[0]["id"])), w2["W"].get(rs2[0]["id"]))
check("chỉ còn 1 lượt: trạng thái 'Chờ hạn mức'", w2["ss"].dm_reaction_of(w2["dsid"], mid2)["status"] == "waiting_quota",
      w2["ss"].dm_reaction_of(w2["dsid"], mid2))
import agent_pulse as AP  # noqa: E402
n_ev = len(AP.events(w2["gs"], w2["key"], kinds=("quota",)))
n_ws = len(w2["box"]["events"])
for _ in range(3):
    run(w2["host"].serve_reaction_review(rs2[0]))
check("hết hạn mức phục vụ lại nhiều nhịp: không ghi thêm dòng sự kiện 'quota' hay gói WS (khử lặp, L P3)",
      len(AP.events(w2["gs"], w2["key"], kinds=("quota",))) == n_ev == 1 and len(w2["box"]["events"]) == n_ws,
      (n_ev, len(AP.events(w2["gs"], w2["key"], kinds=("quota",))), n_ws, len(w2["box"]["events"])))


# ═════ L P2-1c: phán xử dừng vì hết hạn mức: nguồn về lý do chờ, trạng thái 'Chờ hạn mức' ═════
class QuotaJudge:
    def __init__(self):
        self.calls = 0

    async def proactive(self, **kw):
        self.calls += 1
        return {"verdict": "silent", "silence_code": "waiting_quota", "decision_id": 7, "reason": "agent_daily_calls"}

    def profile(self, k):
        return {"offsets": {}}

w3 = world(judge=QuotaJudge())
mid3, src3 = dm_react(w3, "Tin thứ ba")
rs3 = pending(w3)
w3["eng"].text = out("ask_back", [src3], message="Anh muốn ngắn cỡ nào?")
res3 = run(w3["host"].serve_reaction_review(rs3[0]))
st3 = w3["ss"].dm_reaction_of(w3["dsid"], mid3)
check("phán xử báo waiting_quota: trạng thái 'Chờ hạn mức', KHÔNG phải 'Phán xử chọn im'",
      st3["status"] == "waiting_quota", (st3, res3))
again = pending(w3)
check("phán xử báo waiting_quota: nguồn về một lý do chờ mới, chưa tiêu thụ (không mất phản hồi)",
      len(again) == 1 and [s["source_ref"] for s in w3["W"].sources(again[0]["id"], live_only=True)] == [src3],
      (again, res3))
check("không gửi tin nào", w3["box"]["sent"] == [])
res3b = run(w3["host"].serve_reaction_review(again[0]))
check("lùi lại: lý do vừa trả về không bị phục vụ lại ngay ở nhịp kế (backoff)", res3b.get("outcome") == "backoff", res3b)

if fails:
    print(f"\n{len(fails)} FAIL")
    raise SystemExit(1)
print("\nOK")
