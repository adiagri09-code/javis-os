"""T3 (0.156.0): các chỗ nối giữa nhịp thích nghi (P), bộ phán xử (J) và học trong đội (L) qua main.py thật.

    python tests/run.py t3_integration -v

Không model nào được gọi: chốt chặn làm test DỪNG NGAY nếu có đường nào dựng engine thật (engine nhóm, chat, Cộng hưởng,
phán xử). Kiểm: vòng nhịp dựng bộ phán xử, lý do related_review/wait_unblocked có người phục vụ, hàm gửi của bộ phán xử
đăng tin chủ động đúng ngữ cảnh, mục "judge" của trang nhịp không lỗi.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import tempfile
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-t3-int-")
os.environ.pop("JAVIS_RESONANCE_CALL_CEILING", None)
BR = Path(tempfile.mkdtemp(prefix="javis-t3-int-brain-"))
(BR / "agents").mkdir()
(BR / "agents" / "lan.md").write_text("---\nname: Lan\nrole: Trợ lý\n---\nBạn là Lan.\n", encoding="utf-8", newline="\n")

import main  # noqa: E402
import agent_judge  # noqa: E402
import agent_pulse_host  # noqa: E402
import resonance_store as RS  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {str(extra)[:400]}" if extra and not cond else ""))
    if not cond:
        fails.append(name)


class RealEngineUsed(AssertionError):
    pass


def _no_real_engine(*a, **k):
    raise RealEngineUsed("test tried to build a REAL engine")


main.team_engine.build = _no_real_engine
main.claude_engine = _no_real_engine
main.CodexCLI = _no_real_engine
check("chốt phán xử không dựng engine thật đang bật cho test", os.environ.get("JAVIS_NO_REAL_JUDGE_ENGINE") == "1")

rs = main._resonance_store()
BK = main._brain_key(str(BR))
owner = RS.Principal("owner", "owner", BK)
lan = rs.agent_set_enabled(owner, "lan", True)

host = main._pulse_host()
check("vòng nhịp dựng bộ phán xử cùng lúc (sau khởi động lại lý do chờ có người phục vụ)", main._AGENT_JUDGE[0] is not None)
handlers = dict(agent_pulse_host._REASON_HANDLERS)
check("lý do related_review và wait_unblocked có hàm phục vụ của bộ phán xử",
      "related_review" in handlers and "wait_unblocked" in handlers)
check("bộ phán xử có hàm gửi tin (không còn 'no_sender')", main._judge_send in main._AGENT_JUDGE[0]._senders)

view = agent_pulse_host.view(rs, lan["agent_key"])
check("trang nhịp có mục 'judge' của bộ phán xử, không lỗi chữ ký", "judge" in view["parts"]
      and "error" not in (view["parts"]["judge"] or {}), view["parts"].get("judge"))

S = main.get_store().create_session(brain=str(BR), channel="agent:lan")
main._pulse_dm_session = lambda key: (S, "lan")
before = len(main.get_store().get_messages(S))
got = main._judge_send({"agent_key": lan["agent_key"], "context_ref": f"dm:{lan['agent_key']}", "decision_id": 7,
                        "source_event": "goal:g1"}, {"draft": "Anh xem giúp mục tiêu g1"}, "send")
msgs = main.get_store().get_messages(S)
check("hàm gửi của bộ phán xử đăng đúng một tin chủ động vào chat riêng của trợ lý", got and len(msgs) == before + 1
      and msgs[-1]["role"] == "assistant" and "mục tiêu g1" in msgs[-1]["content"], (got, msgs[-1:]))
check("hàm gửi bỏ qua bản nháp rỗng", main._judge_send({"agent_key": lan["agent_key"],
                                                        "context_ref": f"dm:{lan['agent_key']}"}, {"draft": " "},
                                                       "send") is None)

print(f"\n{'FAIL' if fails else 'PASS'} - test_t3_integration: {len(fails)} lỗi")
raise SystemExit(1 if fails else 0)
