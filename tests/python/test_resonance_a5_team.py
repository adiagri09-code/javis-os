"""Resonance A5: một agent làm, một agent review cho mỗi mục tiêu (thiết kế chốt tại 56f7ab50).

    python tests/run.py resonance_a5_team -v

Kho SQLite thật, engine GIẢ hai vai (lượt review nhận `R.REVIEW_SYSTEM`), đồng hồ giả. Mục tiêu tạo qua `form_goal` thật
(đường của tool javis_goal và /goal-requests; T31, T32 đi qua chính plugin và chính route), chạy qua `R.advance` thật
(cổng, scheduler, kho). Không gọi model thật. Tên ca theo ma trận nghiệm thu mục 15 của
docs/superpowers/specs/2026-10-11-resonance-a5-maker-reviewer-design.md. Mỗi ca kiểm: trạng thái và lý do, lượt (maker,
reviewer, tổng), số lần engine giả được gọi, và kết quả nào được phép dùng.

Ngân sách và bộ đếm thử lại (T5 đến T9, T47 đến T54, T61 đến T67) ở test_resonance_a5_budget.py.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import importlib.util
import json
import os
import sqlite3
import tempfile
from pathlib import Path

_STATE = Path(tempfile.mkdtemp(prefix="javis-res-a5-"))
os.environ["JAVIS_STATE_DIR"] = str(_STATE)
os.environ.pop("JAVIS_RESONANCE_CALL_CEILING", None)

import resonance as R  # noqa: E402
import resonance_heartbeat as HB  # noqa: E402
import resonance_store as RS  # noqa: E402
import _resonance_agent as RA  # noqa: E402
import _resonance_team as T  # noqa: E402

_fails = []


def check(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond or not detail else f"  [{str(detail)[:400]}]"))
    if not cond:
        _fails.append(name)


GOOD2 = T.GOOD.replace("Xong.", "Xong, bản sửa theo góp ý.")
GOOD3 = T.GOOD.replace("Xong.", "Xong, bản sửa lần hai.")
GOOD4 = T.GOOD.replace("Xong.", "Xong, bản sửa lần ba.")

# ═══════════ parse_review: hàm thuần, đóng khi lỗi (mục 5.2; T5, T26) ═══════════
check("parse: pass hợp lệ", R.parse_review(T.PASS, 1)["verdict"] == "pass")
check("parse: needs_changes hợp lệ", R.parse_review(T.CHANGES, 1)["verdict"] == "needs_changes")
check("parse: bỏ được một lớp rào ```json", R.parse_review("```json\n" + T.PASS + "\n```", 1)["verdict"] == "pass")
for label, txt in (("không phải JSON", "Đạt, bản tốt."), ("JSON lẫn chữ", "Kết luận: " + T.PASS),
                   ("thiếu criteria", json.dumps({"verdict": "pass", "fixes": ""})),
                   ("verdict lạ", json.dumps({"verdict": "ok", "criteria": [{"index": 0, "ok": True}]})),
                   ("ok không phải bool", json.dumps({"verdict": "pass", "criteria": [{"index": 0, "ok": "true"}]})),
                   ("index trùng", json.dumps({"verdict": "pass", "criteria": [{"index": 0, "ok": True},
                                                                              {"index": 0, "ok": True}]})),
                   ("thiếu một chỉ số", T.verdict("pass", (True,))), ("index ngoài tầm", json.dumps(
                       {"verdict": "pass", "criteria": [{"index": 5, "ok": True}]})),
                   ("mảng thay vì đối tượng", "[" + T.PASS + "]")):
    n = 2 if label == "thiếu một chỉ số" else 1
    r = R.parse_review(txt, n)
    check(f"T5 parse đóng khi lỗi: {label} -> unknown/parse_error", r["verdict"] == "unknown"
          and r["reason_code"] == "parse_error", r)
r = R.parse_review(T.verdict("pass", (False,)), 1)
check("T5 parse: pass mà có tiêu chí ok=false -> unknown/inconsistent", r == {**r, "verdict": "unknown",
                                                                             "reason_code": "inconsistent"}, r)
r = R.parse_review(T.verdict("needs_changes", (True,), ""), 1)
check("T5 parse: needs_changes mà mọi tiêu chí đạt và không có fixes -> inconsistent",
      r["verdict"] == "unknown" and r["reason_code"] == "inconsistent", r)
r = R.parse_review(json.dumps({"verdict": "pass", "criteria": [{"index": 0, "ok": True}], "fixes": "",
                               "budget_calls": 99, "criteria_override": ["x"], "role": "maker"}), 1)
check("T26 parse: trường lạ bị bỏ qua, chỉ báo tên; kết luận chỉ từ ba trường",
      r["verdict"] == "pass" and r["extra_keys"] == ["budget_calls", "criteria_override", "role"]
      and set(r) == {"verdict", "reason_code", "criteria", "fixes", "extra_keys"}, r)

# ═══════════ T1: làm, đạt khách quan, review pass ═══════════
t = T.Team(_STATE, "t1")
g = t.create()
t.run(g)
rv = t.reviews(g)
check("T1 succeeded; lượt (1, 1, 2); engine giả: 1 lượt làm, 1 lượt review", t.g(g).status == "succeeded"
      and t.calls(g) == (1, 1, 2) and t.work.queries == 1 and t.rev.queries == 1, (t.g(g).status, t.calls(g)))
check("T1 kết luận dùng để chốt là review pass của H1; sự kiện kết thúc mang review_id",
      len(rv) == 1 and rv[0]["verdict"] == "pass" and rv[0]["status"] == "done" and rv[0]["charged"] == 1
      and any(e["payload"].get("review_id") == rv[0]["id"] for e in t.events(g, "succeeded")), rv)
check("T1 review không ghi gì vào brain: file đích là đúng bản của vai làm",
      t.target().read_text(encoding="utf-8") == T.GOOD)
check("T1 lượt review đọc ảnh chụp bản đã tiếp nhận (hash bytes gửi bằng hash đã ghim)",
      T.GOOD in t.rev.prompts[0] and rv[0]["artifact_sha"] == R._sha(T.GOOD.encode("utf-8")))
check("T1 lời dặn review đúng hợp đồng: mô tả vai của reviewer là dữ liệu",
      "Mô tả vai của bạn (dữ liệu)" in t.rev.prompts[0] and "Trợ lý thử nguoi-duyet" in t.rev.prompts[0])
check("T1 đội gắn lúc tạo: budget 8, maker 4, reviewer 4, tối đa 2 vòng",
      t.g(g).budget_calls == 8 and t.team(g)["calls"] == {"maker": {"cap": 4, "used": 1}, "reviewer": {"cap": 4, "used": 1}}
      and t.team(g)["max_rounds"] == 2)

# ═══════════ T2: có human_confirmation ═══════════
t = T.Team(_STATE, "t2")
g = t.create(human=True)
t.run(g)
check("T2 review pass rồi mới chờ người xác nhận: waiting/human_confirmation, (1, 1, 2)",
      t.st(g) == {"run_state": "waiting", "block_reason": "human_confirmation"} and t.calls(g) == (1, 1, 2)
      and t.rev.queries == 1, (t.st(g), t.calls(g)))
gg = t.g(g)
crit = next(c for c in gg.criteria if c.get("evaluator") == "human_confirmation")
R.apply_feedback(t.store, t.owner, g.id, "outcome_accepted",
                 {"expected_revision": gg.revision, "criterion_id": crit["id"],
                  "artifact_ref": R.current_artifact_ref(gg, t.deps())}, t.brain)
t.run(g)
check("T2 chủ xác nhận đúng sha: succeeded, không thêm lượt", t.g(g).status == "succeeded" and t.calls(g) == (1, 1, 2),
      (t.g(g).status, t.st(g), t.calls(g)))

# ═══════════ T3: needs_changes, làm sửa, review bản mới pass ═══════════
t = T.Team(_STATE, "t3")
t.work.script = [T.GOOD, GOOD2]
t.rev.script = [T.CHANGES, T.PASS]
g = t.create()
t.run(g)
rv = t.reviews(g)
check("T3 succeeded; (2, 2, 4); hai hàng review gắn hai bộ ghim khác nhau", t.g(g).status == "succeeded"
      and t.calls(g) == (2, 2, 4) and len(rv) == 2 and rv[0]["bundle_ref"] != rv[1]["bundle_ref"]
      and [x["verdict"] for x in rv] == ["needs_changes", "pass"], [(x["verdict"], x["bundle_ref"][:30]) for x in rv])
check("T3 góp ý vào lời nhắc lượt sửa (dữ liệu), vòng 1/2", "Người review góp ý" in t.work.prompts[1]
      and "Thêm mục Kết luận rõ hơn" in t.work.prompts[1]
      and t.store.review_rounds(t.owner, g.id, 1) == 1, t.work.prompts[1][-400:])
check("T3 file đích là bản sửa đã được review pass", t.target().read_text(encoding="utf-8") == GOOD2)

# ═══════════ T4: needs_changes ba lần: k=1,2 cho sửa, k=3 chặn ═══════════
t = T.Team(_STATE, "t4")
t.work.script = [T.GOOD, GOOD2, GOOD3, GOOD4]
t.rev.script = [T.CHANGES]
g = t.create()
t.run(g, n=20)
ob = [r for r in sqlite3.connect(str(t.store.path)).execute("SELECT kind FROM outbox WHERE goal_id=?", (g.id,))]
check("T4 blocked/review_rounds sau kết luận needs_changes thứ 3; (3, 3, 6); không có lượt sửa thứ ba",
      t.st(g) == {"run_state": "blocked", "block_reason": "review_rounds"} and t.calls(g) == (3, 3, 6)
      and t.work.queries == 3 and t.rev.queries == 3 and t.store.review_rounds(t.owner, g.id, 1) == 3,
      (t.st(g), t.calls(g), t.work.queries))
check("T4 tin goal.review_exhausted (loại phải gửi)", ("goal.review_exhausted",) in ob, ob)
check("T4 không tự nới: chạy thêm không gọi model", (t.run(g), t.work.queries, t.rev.queries)[1:] == (3, 3))

# ═══════════ T31 tới T36: gắn đội trong giao dịch tạo (R1) ═══════════
# T31: tạo qua CHÍNH tool javis_goal (plugin), trong lượt chat của agent làm, kho mặc định của host.
_spec = importlib.util.spec_from_file_location("javis_goal_plugin", str(Path(ROOT) / "system" / "plugins" / "javis-goal"
                                                                          / "plugin.py"))
PLUG = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(PLUG)


class _Ctx:
    def __init__(self, vault):
        self.vault_root = vault


t = T.Team(_STATE, "resonance")          # kho mặc định của host: STATE_DIR/resonance.sqlite3 (plugin mở kho này)
check("T31 kho của test là kho mặc định mà plugin mở", Path(t.store.path) == Path(RS.GoalStore().path))
orig_assign = RS.GoalStore.assign_goal


def _no_assign(*a, **k):
    raise AssertionError("create không được gọi assign_goal")


RS.GoalStore.assign_goal = _no_assign
mid, ref = t.next()
with RA.turn(t.ag(), t.sid, mid, T.USER, t.brain, slug=T.MAKER, store=t.store):
    out = asyncio.run(PLUG.javis_goal({"op": "create", **t.proposal()}, _Ctx(t.brain)))
RS.GoalStore.assign_goal = orig_assign
g = t.store.find_by_key(t.owner, ref)
tm = t.team(g)
created = [e for e in t.store.events(t.owner, g.id) if e["kind"] in ("created", "team_attached")]
check("T31 tool javis_goal: đội active, 4/4, budget 8, gắn trong giao dịch tạo (không qua assign_goal)",
      "Đã lập mục tiêu" in out and tm and tm["status"] == "active" and tm["reviewer_agent_key"] == t.reviewer["agent_key"]
      and t.g(g).budget_calls == 8 and [e["kind"] for e in created] == ["created", "team_attached"]
      and len({e["created_at"] for e in created}) == 1, (out[:200], tm, created))
try:
    t.store.assign_goal(t.owner, g.id, t.maker["agent_key"], g.revision)
    _conf = False
except RS.ConflictError:
    _conf = True
check("T31 gọi assign_goal sau đó bị từ chối (đã gán), không có giao dịch thứ hai", _conf)

# T32: tạo qua CHÍNH route POST /goal-requests (bộ lập mục tiêu chạy bằng engine giả, không phải model thật).
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import resonance_api as RAPI  # noqa: E402

t32 = T.Team(_STATE, "t32")
_framer = T.Engine(json.dumps(t32.proposal(), ensure_ascii=False))
_msgs = {}


class _Sessions:
    def get_session(self, sid):
        return {"brain": t32.brain, "channel": f"agent:{T.MAKER}", "created_at": 1.0} if sid in _msgs else None

    def get_messages(self, sid):
        return [{"id": i, "role": "user", "content": txt} for i, txt in _msgs.get(sid, {}).items()]


_app = FastAPI()
RAPI.register(_app, RAPI.ResonanceApiDeps(
    store=lambda: t32.store, brain_key=lambda b: t32.brain,
    engine_factory=lambda s, tag: (_framer, {"provider": "fake", "model": "fake-1", "text_only": True}),
    session_store=lambda: _Sessions()))
_msgs["s32"] = {7: T.USER}
r = TestClient(_app).post("/goal-requests", params={"brain": "x"}, json={"message_ref": R.message_ref("s32", 7)})
g32 = t32.store.find_by_key(t32.owner, R.message_ref("s32", 7))
check("T32 /goal-requests: đội active trong giao dịch tạo, budget 8; bộ lập là engine giả (1 lượt, sổ riêng)",
      r.status_code == 200 and g32 is not None and (t32.team(g32) or {}).get("status") == "active"
      and t32.g(g32).budget_calls == 8 and _framer.queries == 1 and t32.calls(g32) == (0, 0, 0),
      (r.status_code, r.text[:300]))

# T33: tạo lặp cùng tin, giữa hai lần đổi cặp sang reviewer khác: không đổi gì.
t = T.Team(_STATE, "t33")
mid, ref = t.next()
g = t.create(mid, ref)
third = RA.enable(t.store, t.brain, "nguoi-thu-ba")
t.store.team_pair_set(t.owner, t.maker["agent_key"], third["agent_key"])
g2 = t.create(mid, ref)
check("T33 tạo lặp cùng khoá: trả mục tiêu cũ; reviewer, budget, team_calls không đổi; không thêm sự kiện gắn đội",
      g2.id == g.id and t.team(g)["reviewer_agent_key"] == t.reviewer["agent_key"] and t.g(g).budget_calls == 8
      and len(t.events(g, "team_attached")) == 1, t.team(g))
g3 = t.create()
check("T33 đổi cặp chỉ áp cho mục tiêu MỚI", t.team(g3)["reviewer_agent_key"] == third["agent_key"]
      and t.team(g)["reviewer_agent_key"] == t.reviewer["agent_key"])

# T34 / T25: cặp tắt, hay không có cặp: không có đội, chạy như A4.
t = T.Team(_STATE, "t34")
t.store.team_pair_set(t.owner, t.maker["agent_key"], None)
g = t.create()
t.run(g)
check("T34 cặp tắt lúc tạo: không có goal_team; như A4 (succeeded, 1 lượt, budget 4 như người gọi đưa, 0 review)",
      t.team(g) is None and t.g(g).status == "succeeded" and t.g(g).calls_used == 1 and t.g(g).budget_calls == 4
      and t.rev.queries == 0, (t.team(g), t.g(g).status))
t = T.Team(_STATE, "t25", pair=False)
g = t.create()
t.run(g)
check("T25 không có cặp: như A4", t.team(g) is None and t.g(g).status == "succeeded" and t.rev.queries == 0)

# T35: reviewer bị tắt đúng lúc tạo (cặp vẫn bật): vẫn có đội, cổng chặn, không bỏ review.
t = T.Team(_STATE, "t35")
RA.disable(t.store, t.brain, T.REVIEWER)
g = t.create()
t.run(g)
check("T35 reviewer tắt lúc tạo: đội active, blocked/reviewer_off, không gọi model nào, không chốt",
      (t.team(g) or {}).get("status") == "active" and t.st(g) == {"run_state": "blocked", "block_reason": "reviewer_off"}
      and t.work.queries == 0 and t.rev.queries == 0 and t.g(g).status == "active", (t.st(g), t.work.queries))

# T36: mục tiêu cũ đã tiêu lượt, gán qua assign_goal cho agent có cặp: không có đội.
t = T.Team(_STATE, "t36")
d0 = R.GoalDeps(engine_factory=lambda s, x: (None, {}), budget=R.CallBudget(0), store=t.store)
it = t.store.add_intent(t.owner, t.sid, 99, T.USER)
gl, _ = t.store.create(t.owner, it["id"], R.validate_proposal(t.proposal(), T.USER, source_ref="legacy"), "legacy:1",
                       budget_calls=6)
with sqlite3.connect(str(t.store.path)) as c:
    c.execute("UPDATE goals SET calls_used=3 WHERE id=?", (gl.id,))
RA.assign(t.store, t.brain, gl.id, t.maker["agent_key"])
ev = t.events(gl, "agent_assigned")
check("T36 assign_goal: không gắn đội, calls_used giữ 3, sự kiện ghi not_attached_legacy, thẻ nói không có người review",
      t.team(gl) is None and t.g(gl).calls_used == 3 and ev and ev[-1]["payload"].get("team") == "not_attached_legacy"
      and (R.goal_view(t.store, t.owner, gl.id, t.brain) or {}).get("team") == {"legacy": True},
      (t.team(gl), ev))

if _fails:
    print(f"\n{len(_fails)} FAIL:", _fails)
    raise SystemExit(1)
print("\nOK")
