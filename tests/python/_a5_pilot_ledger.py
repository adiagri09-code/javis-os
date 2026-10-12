"""Sổ lượt theo vai của pilot A5 (dùng chung cho `_a5_pilot_server.py` và `test_resonance_a5_pilot_gate.py`).

Sổ là một file JSON {"run_id", "caps": {"maker", "reviewer", "total"}, "calls": [...], "events": [...]}, ghi bằng fsync
rồi os.replace. Mỗi lượt engine của việc nền (một lần dựng engine cho một lượt làm hay review) được GIỮ CHỖ trong sổ
TRƯỚC khi dựng engine. Bất kỳ kết cục nào khác `ok` (lỗi, huỷ, ngoại lệ, không dựng được, thiếu khung kết thúc), hay một
lượt giữ chỗ chưa có kết cục, đều ĐÓNG sổ: không cấp thêm lượt nào. Sổ đọc lỗi hay sai cấu trúc thì không cấp lượt và
KHÔNG ghi đè (giữ nguyên làm bằng chứng). Lần thử bị chặn ghi một sự kiện `refused`, không phải một lượt.
"""
import asyncio
import json
import os
import time
from pathlib import Path

STATUSES = ("reserved", "ok", "engine_error", "cancelled", "exception", "not_built", "no_final")
ROLES = ("maker", "reviewer")


class RoleLedger:
    def __init__(self, path, phase_caps: dict):
        self.path = Path(path)
        self.phase_caps = dict(phase_caps or {})

    # ───── đọc ghi ─────
    def write(self, st: dict) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(st, ensure_ascii=False, indent=1))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    def load(self) -> tuple:
        try:
            st = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            return None, f"ledger_unreadable: {type(e).__name__}"
        calls = st.get("calls") if isinstance(st, dict) else None
        caps = st.get("caps") if isinstance(st, dict) else None
        if not isinstance(calls, list) or not isinstance(caps, dict) or not isinstance(st.get("events"), list) \
                or not all(type(caps.get(k)) is int and caps[k] >= 0 for k in ("maker", "reviewer", "total")):
            return None, "ledger_bad_shape"
        for i, c in enumerate(calls, 1):
            if not isinstance(c, dict) or c.get("n") != i or c.get("status") not in STATUSES \
                    or c.get("role") not in ROLES:
                return None, f"ledger_bad_call_{i}"
        return st, ""

    def event(self, st: dict, kind: str, **kw) -> None:
        st["events"].append({"kind": kind, "at": time.time(), "pid": os.getpid(), **kw})

    # ───── giữ chỗ và chốt ─────
    def reserve(self, role: str) -> tuple:
        """(số thứ tự, "") khi được gọi; (0, lý do) khi bị chặn. Ghi xuống đĩa TRƯỚC khi trả."""
        st, err = self.load()
        if err:
            return 0, err
        why = ""
        if role not in ROLES:
            why = "role_other"
        elif any(c["status"] == "reserved" for c in st["calls"]):
            why = "reserved_without_outcome"
        elif any(c["status"] != "ok" for c in st["calls"]):
            why = "halted_after_" + next(c["status"] for c in st["calls"] if c["status"] != "ok")
        else:
            used = sum(1 for c in st["calls"] if c["role"] == role)
            if used >= int(self.phase_caps.get(role, 0)) or used >= int(st["caps"].get(role, 0)):
                why = f"cap_{role}"
            elif len(st["calls"]) >= int(st["caps"]["total"]):
                why = "cap_total"
        if why:
            self.event(st, "refused", role=role, why=why, phase_caps=self.phase_caps)
            self.write(st)
            return 0, why
        n = len(st["calls"]) + 1
        st["calls"].append({"n": n, "role": role, "status": "reserved", "at": time.time(), "pid": os.getpid()})
        self.write(st)
        return n, ""

    def settle(self, n: int, status: str, **kw) -> None:
        """Chốt kết cục của lượt `n` nếu nó còn `reserved` (chốt lần hai không đổi gì)."""
        st, err = self.load()
        if err or status not in STATUSES:
            return
        changed = False
        for c in st["calls"]:
            if c["n"] == n and c["status"] == "reserved":
                c.update(status=status, settled_at=time.time(), **kw)
                changed = True
        if changed:
            self.write(st)

    def note(self, n: int, **kw) -> None:
        st, err = self.load()
        if err:
            return
        for c in st["calls"]:
            if c["n"] == n:
                c.update(**kw)
        self.write(st)

    def tripwire(self, role: str) -> None:
        st, err = self.load()
        if not err:
            self.event(st, "tripwire", role=role)
            self.write(st)


class Counted:
    """Bọc engine của MỘT lượt. Kết cục `ok` chỉ khi có khung `final` mà chưa có khung lỗi. Chốt NGAY khi thấy khung kết
    thúc (trước khi trả khung cho host): host có thể ngừng đọc sau khung đó, và generator bị bỏ dở không chắc được đóng
    ngay. Huỷ, ngoại lệ, thiếu khung kết thúc: chốt ở nhánh tương ứng; mọi kết cục đều tính."""

    def __init__(self, inner, ledger: RoleLedger, n: int):
        object.__setattr__(self, "inner", inner)
        object.__setattr__(self, "ledger", ledger)
        object.__setattr__(self, "n", n)

    def __getattr__(self, k):
        return getattr(self.inner, k)

    def __setattr__(self, k, v):
        # Host đặt `max_wall_s` lên engine: chuyển xuống engine thật để trần thời gian của nó vẫn áp dụng.
        setattr(self.inner, k, v)

    async def query(self, prompt):
        done = False
        try:
            async for ev in self.inner.query(prompt):
                t = ev.get("type") if isinstance(ev, dict) else None
                if t == "error" and not done:
                    self.ledger.settle(self.n, "engine_error", error=str(ev.get("content") or "")[:300])
                    done = True
                elif t == "final" and not done:
                    self.ledger.settle(self.n, "ok", **{k: ev.get(k) for k in ("tokens_in", "tokens_out")
                                                        if ev.get(k) is not None})
                    done = True
                yield ev
        except asyncio.CancelledError:
            if not done:
                self.ledger.settle(self.n, "cancelled")
                done = True
            raise
        except Exception as e:  # noqa: BLE001
            if not done:
                self.ledger.settle(self.n, "exception", error=f"{type(e).__name__}: {str(e)[:200]}")
                done = True
            raise
        finally:
            if not done:
                self.ledger.settle(self.n, "no_final")


def wrap_factory(real_factory, ledger: RoleLedger, role_of):
    """Hàm dựng engine bọc sổ: giữ chỗ TRƯỚC khi dựng; bị chặn thì trả (None, lý do) và KHÔNG gọi `real_factory`."""
    def factory(system_prompt, tag="resonance"):
        role = role_of(system_prompt)
        n, why = ledger.reserve(role)
        if not n:
            return None, {"blocked": f"pilot_ledger:{why}"}
        try:
            eng, info = real_factory(system_prompt, tag)
        except Exception as e:  # noqa: BLE001
            ledger.settle(n, "not_built", error=f"{type(e).__name__}: {str(e)[:200]}")
            raise
        if eng is None:
            ledger.settle(n, "not_built", info={k: str(v)[:200] for k, v in (info or {}).items()})
            return None, info
        ledger.note(n, engine={k: (info or {}).get(k) for k in ("provider", "model") if (info or {}).get(k)})
        return Counted(eng, ledger, n), info
    return factory


# ───── hàm thuần của bộ chạy (test ở test_resonance_a5_pilot_gate.py) ─────

def ledger_counts(st: dict) -> dict:
    """Số lượt đã giữ chỗ theo vai (mọi kết cục đều tính), số lần thử bị chặn, sự kiện bẫy."""
    calls = st["calls"]
    return {"maker": sum(1 for c in calls if c["role"] == "maker"),
            "reviewer": sum(1 for c in calls if c["role"] == "reviewer"),
            "total": len(calls), "not_ok": [c["status"] for c in calls if c["status"] != "ok"],
            "refused": [e.get("why") for e in st["events"] if e.get("kind") == "refused"],
            "tripwire": sum(1 for e in st["events"] if e.get("kind") == "tripwire")}


def classify(status: str, verdicts: list, work: list, refused: list, block_reason: str = "") -> str:
    """Nhánh đã xảy ra, đọc từ kho (không ép). `verdicts`: kết luận hợp lệ theo thứ tự; `work`: trạng thái lượt làm;
    `refused`: lý do các lần sổ pilot chặn; `block_reason`: lý do chặn hiện tại của mục tiêu.

    Lượt sửa thứ hai có thể bị chặn ở một trong hai lớp: trần kho của pilot (`JAVIS_RESONANCE_CALL_CEILING`, chặn ngay lúc
    giữ chỗ nên mục tiêu thành `blocked/budget`, sổ pilot không thấy gì) hay sổ pilot (`refused cap_*`, host hoàn lượt,
    mục tiêu thành `blocked/engine_blocked`). Cả hai là cùng nhánh: trần pilot chặn sau hai lần cần sửa."""
    if any(w != "succeeded" for w in work[:1]):
        return "maker_error"
    if status == "succeeded" and verdicts == ["pass"]:
        return "pass_first"
    if status == "succeeded" and verdicts == ["needs_changes", "pass"]:
        return "one_fix_then_pass"
    if verdicts[:2] == ["needs_changes", "needs_changes"] and (
            any(str(r).startswith("cap_") for r in refused) or block_reason in ("budget", "engine_blocked")):
        return "pilot_cap_after_two_reviews"
    if verdicts and verdicts[-1] == "unknown":
        return "review_unknown"
    if not verdicts:
        return "no_review"
    return "other"
