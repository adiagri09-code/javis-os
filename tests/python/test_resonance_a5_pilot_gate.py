"""Resonance A5: cổng chi phí của bộ chạy pilot (sổ lượt theo vai `_a5_pilot_ledger.py`), không cần server hay model.

    python tests/run.py resonance_a5_pilot_gate -v

Kiểm đúng mã sổ mà launcher `_a5_pilot_server.py` dùng: giữ chỗ và ghi xuống đĩa trước khi dựng engine; trần vai, trần
tổng, trần giai đoạn; vai khác bị chặn; lượt giữ chỗ chưa có kết cục và mọi kết cục khác `ok` đóng sổ (kể cả sau khi
"tiến trình" mới mở lại sổ); sổ hỏng, thiếu hay sai cấu trúc không cấp lượt và không bị ghi đè; bị chặn thì không chạm
hàm dựng thật; kết cục của lượt (final, lỗi, ngoại lệ, huỷ, không có final) chốt đúng và chốt NGAY khi thấy khung kết
thúc; `max_wall_s` chuyển xuống engine thật; phân nhánh và đếm lượt của bộ chạy. Engine ở đây là engine giả.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import json
import tempfile
from pathlib import Path

import _a5_pilot_ledger as PL

_fails = []
CAPS = {"maker": 2, "reviewer": 2, "total": 4}
TMP = Path(tempfile.mkdtemp(prefix="a5pg-"))


def check(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond or not detail else f"  [{str(detail)[:300]}]"))
    if not cond:
        _fails.append(name)


def fresh(name, caps=CAPS, phase=None):
    p = TMP / f"{name}.json"
    p.write_text(json.dumps({"run_id": name, "caps": caps, "calls": [], "events": []}), encoding="utf-8")
    return PL.RoleLedger(p, phase if phase is not None else {"maker": caps["maker"], "reviewer": caps["reviewer"]})


def calls(led):
    return [(c["role"], c["status"]) for c in led.load()[0]["calls"]]


def refused(led):
    return [e["why"] for e in led.load()[0]["events"] if e["kind"] == "refused"]


# ───── giữ chỗ, trần ─────
led = fresh("basic")
n1, w1 = led.reserve("maker")
on_disk = json.loads(led.path.read_text(encoding="utf-8"))["calls"]
check("giữ chỗ ghi xuống đĩa TRƯỚC khi trả (dòng reserved đã có trên đĩa)", n1 == 1 and not w1
      and on_disk == [{**on_disk[0], "role": "maker", "status": "reserved"}])
led.settle(1, "ok")
led.settle(1, "engine_error")
check("chốt lần hai không đổi kết cục đã chốt", calls(led) == [("maker", "ok")])
n2, _ = led.reserve("reviewer")
led.settle(n2, "ok")
n3, _ = led.reserve("maker")
led.settle(n3, "ok")
n4, w4 = led.reserve("maker")
check("hết trần vai làm (2): bị chặn cap_maker, không thêm dòng, ghi sự kiện refused",
      n4 == 0 and w4 == "cap_maker" and len(calls(led)) == 3 and refused(led) == ["cap_maker"])
n5, _ = led.reserve("reviewer")
led.settle(n5, "ok")
n6, w6 = led.reserve("reviewer")
check("trần tổng (4) và trần vai review (2) chặn lượt thứ năm", n6 == 0 and w6 in ("cap_reviewer", "cap_total")
      and len(calls(led)) == 4)

led = fresh("total", caps={"maker": 3, "reviewer": 3, "total": 2}, phase={"maker": 3, "reviewer": 3})
for r in ("maker", "reviewer"):
    n, _ = led.reserve(r)
    led.settle(n, "ok")
check("trần tổng chặn dù vai còn phần", led.reserve("maker") == (0, "cap_total"))

led = fresh("phase", phase={"maker": 0, "reviewer": 0})
check("trần giai đoạn 0 (dựng, dựng lại): mọi vai bị chặn, có sự kiện refused",
      led.reserve("maker") == (0, "cap_maker") and led.reserve("reviewer") == (0, "cap_reviewer")
      and calls(led) == [] and refused(led) == ["cap_maker", "cap_reviewer"])
check("vai khác (bộ lập mục tiêu, lời dặn lạ) luôn bị chặn", fresh("other").reserve("other") == (0, "role_other"))

# ───── sổ đóng ─────
led = fresh("crash")
led.reserve("maker")
again = PL.RoleLedger(led.path, {"maker": 2, "reviewer": 2})          # "tiến trình mới" mở lại sổ
check("lượt giữ chỗ chưa có kết cục (chết giữa lượt) đóng sổ, kể cả ở tiến trình mới",
      again.reserve("reviewer") == (0, "reserved_without_outcome"))
for st in ("engine_error", "cancelled", "exception", "not_built", "no_final"):
    led = fresh("halt-" + st)
    n, _ = led.reserve("maker")
    led.settle(n, st)
    check(f"kết cục {st}: lượt vẫn tính, sổ đóng", calls(led) == [("maker", st)]
          and led.reserve("reviewer") == (0, f"halted_after_{st}"))

for name, body in (("corrupt", "{hỏng"), ("shape", json.dumps({"calls": [], "events": []})),
                   ("badcall", json.dumps({"caps": CAPS, "events": [], "calls": [{"n": 2, "role": "maker",
                                                                                  "status": "ok"}]})),
                   ("badcap", json.dumps({"caps": {"maker": "2", "reviewer": 2, "total": 4}, "calls": [],
                                          "events": []}))):
    p = TMP / f"{name}.json"
    p.write_text(body, encoding="utf-8")
    n, why = PL.RoleLedger(p, {"maker": 2, "reviewer": 2}).reserve("maker")
    check(f"sổ {name}: không cấp lượt, không ghi đè (giữ nguyên làm bằng chứng)", n == 0 and why.startswith("ledger_")
          and p.read_text(encoding="utf-8") == body, why)
n, why = PL.RoleLedger(TMP / "khong-co.json", {"maker": 2}).reserve("maker")
check("thiếu sổ: không cấp lượt", n == 0 and why.startswith("ledger_unreadable"))


# ───── hàm dựng bọc sổ và kết cục của lượt ─────
class Eng:
    def __init__(self, events, raise_at=None):
        self.events, self.raise_at, self.max_wall_s = events, raise_at, None

    def is_available(self):
        return True

    async def query(self, prompt):
        for i, ev in enumerate(self.events):
            if self.raise_at == i:
                raise RuntimeError("engine giả lỗi giữa chừng")
            if ev == "sleep":
                await asyncio.sleep(10)
                continue
            yield ev


def role_of(sp):
    return {"R": "reviewer", "W": "maker"}.get(sp, "other")


built = []


def real(eng):
    def f(sp, tag="resonance"):
        built.append(sp)
        return eng, {"provider": "fake", "model": "fake-1"}
    return f


led = fresh("wrap-block", phase={"maker": 0, "reviewer": 0})
built.clear()
e, info = PL.wrap_factory(real(Eng([])), led, role_of)("W")
check("bị chặn: trả (None, lý do) và KHÔNG gọi hàm dựng thật", e is None and built == []
      and "pilot_ledger:cap_maker" in info["blocked"])


async def consume(eng, stop_after_final=True):
    out = []
    async for ev in eng.query("p"):
        out.append(ev)
        if stop_after_final and ev.get("type") in ("final", "error"):
            break
    return out


led = fresh("wrap-ok")
f = PL.wrap_factory(real(Eng([{"type": "stream", "content": "x"}, {"type": "final", "content": "y",
                                                                     "tokens_in": 3}])), led, role_of)
e, info = f("W")
e.max_wall_s = 120
check("max_wall_s đặt lên engine bọc được chuyển xuống engine thật", e.inner.max_wall_s == 120)
asyncio.run(consume(e))
check("khung final: chốt ok NGAY (host ngừng đọc sau final), ghi engine và token",
      calls(led) == [("maker", "ok")] and led.load()[0]["calls"][0].get("engine") == {"provider": "fake",
                                                                                     "model": "fake-1"}
      and led.load()[0]["calls"][0].get("tokens_in") == 3)

led = fresh("wrap-err")
asyncio.run(consume(PL.wrap_factory(real(Eng([{"type": "error", "content": "x"}])), led, role_of)("R")[0]))
check("khung lỗi: engine_error, sổ đóng", calls(led) == [("reviewer", "engine_error")])

led = fresh("wrap-exc")
try:
    asyncio.run(consume(PL.wrap_factory(real(Eng([{"type": "stream"}, {"type": "final", "content": "y"}], raise_at=1)),
                                        led, role_of)("W")[0]))
except RuntimeError:
    pass
check("ngoại lệ giữa lượt: exception, vẫn tính", calls(led) == [("maker", "exception")])


async def cancel_mid():
    led = fresh("wrap-cancel")
    e, _ = PL.wrap_factory(real(Eng(["sleep"])), led, role_of)("R")
    t = asyncio.ensure_future(consume(e))
    await asyncio.sleep(0.05)
    t.cancel()
    try:
        await t
    except asyncio.CancelledError:
        pass
    return led


led = asyncio.run(cancel_mid())
check("huỷ trong lúc engine chạy: cancelled, vẫn tính", calls(led) == [("reviewer", "cancelled")])


async def no_final():
    led = fresh("wrap-nofinal")
    e, _ = PL.wrap_factory(real(Eng([{"type": "stream"}])), led, role_of)("W")
    gen = e.query("p")
    async for _ev in gen:
        pass
    return led


led = asyncio.run(no_final())
check("hết khung mà không có final: no_final, vẫn tính", calls(led) == [("maker", "no_final")])


def boom(sp, tag="resonance"):
    raise RuntimeError("không dựng được")


led = fresh("wrap-build")
try:
    PL.wrap_factory(boom, led, role_of)("W")
except RuntimeError:
    pass
check("hàm dựng thật ném lỗi: lượt đã giữ chỗ chốt not_built (bảo thủ, vẫn tính), sổ đóng",
      calls(led) == [("maker", "not_built")] and led.reserve("reviewer")[0] == 0)
led = fresh("wrap-none")
e, info = PL.wrap_factory(lambda sp, tag="r": (None, {"blocked": "sai provider"}), led, role_of)("W")
check("hàm dựng thật trả None: not_built, trả nguyên lý do cho host", e is None and calls(led) == [("maker", "not_built")]
      and info == {"blocked": "sai provider"})

# ───── phân nhánh và đếm của bộ chạy ─────
check("nhánh: đạt ngay", PL.classify("succeeded", ["pass"], ["succeeded"], []) == "pass_first")
check("nhánh: một vòng sửa rồi đạt", PL.classify("succeeded", ["needs_changes", "pass"], ["succeeded", "succeeded"],
                                                 []) == "one_fix_then_pass")
check("nhánh: hai lần cần sửa rồi chạm trần pilot", PL.classify(
    "active", ["needs_changes", "needs_changes"], ["succeeded", "succeeded", "failed"], ["cap_maker"])
    == "pilot_cap_after_two_reviews")
check("nhánh: hai lần cần sửa, lượt sửa bị trần kho của pilot chặn lúc giữ chỗ (blocked/budget, sổ không thấy gì)",
      PL.classify("active", ["needs_changes", "needs_changes"], ["succeeded", "succeeded"], [], "budget")
      == "pilot_cap_after_two_reviews")
check("nhánh: review không đọc được", PL.classify("active", ["unknown"], ["succeeded"], []) == "review_unknown")
check("nhánh: lượt làm đầu lỗi", PL.classify("active", [], ["failed"], []) == "maker_error")
check("nhánh: hai lần cần sửa mà KHÔNG do trần pilot thì không gán nhầm nhánh trần",
      PL.classify("active", ["needs_changes", "needs_changes"], ["succeeded", "succeeded"], []) == "other")
st = {"calls": [{"n": 1, "role": "maker", "status": "ok"}, {"n": 2, "role": "reviewer", "status": "engine_error"}],
      "events": [{"kind": "refused", "why": "cap_maker"}, {"kind": "tripwire"}], "caps": CAPS}
check("đếm: mọi kết cục đều tính theo vai; liệt kê kết cục khác ok, lần bị chặn, bẫy",
      PL.ledger_counts(st) == {"maker": 1, "reviewer": 1, "total": 2, "not_ok": ["engine_error"],
                               "refused": ["cap_maker"], "tripwire": 1})

print(f"\n{len(_fails)} FAIL: {_fails}" if _fails else "\nOK")
raise SystemExit(1 if _fails else 0)
