"""0.142.0: tab Công việc của trợ lý ở trang Cộng sự.

    python tests/run.py agent_jobs_0142

Gom việc theo agent_key, đọc thẳng bản ghi gốc (không sao chép): việc nhóm (giao thẳng, điều phối, bước con, hỗ trợ),
việc Kanban từ chat riêng và từ nút Giao việc, mục tiêu Auto. Đi qua route thật của main với kho SQLite thật, không gọi
model.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import tempfile
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-agent-jobs-")
BR = Path(tempfile.mkdtemp(prefix="javis-agent-jobs-brain-")).resolve()
(BR / "agents").mkdir()
for slug, name in (("lan", "Lan"), ("minh", "Minh"), ("hoa", "Hoa")):
    (BR / "agents" / f"{slug}.md").write_text(f"---\nname: {name}\nrole: Thành viên\n---\nBạn là {name}.\n",
                                              encoding="utf-8", newline="\n")

import main  # noqa: E402
import agent_jobs  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {str(extra)[:500]}" if extra and not cond else ""))
    if not cond:
        fails.append(name)


api = main._TEAM_API
api.deps.spawn = lambda coro: coro.close()
client = TestClient(main.app, base_url="http://127.0.0.1:8080")
B = str(BR)


def jobs(slug):
    r = client.get(f"/agents/{slug}/jobs", params={"brain": B})
    return r.status_code, r.json()


# Chưa có gì: không lỗi, không tạo gì.
code, j = jobs("lan")
check("trợ lý chưa có việc: danh sách rỗng, đủ bốn ngăn", code == 200 and j["jobs"] == []
      and set(j["counts"]) == {"running", "waiting", "needs_you", "done"}, j)
check("chỉ đọc không cấp mã, không tạo kho nhóm", j["agent_key"] is None and not api.exists(), j)
check("trợ lý không có: 404", client.get("/agents/khong-co/jobs", params={"brain": B}).status_code == 404)

# Nhóm: Lan trưởng nhóm (điều phối), Minh được giao thẳng, Hoa chỉ hỗ trợ một bước.
r = client.post("/teams", params={"brain": B}, json={"name": "Ra mắt", "members": ["lan", "minh", "hoa"],
                                                      "leader_slug": "lan"})
team = r.json()["team"]
tid = team["team_id"]
keys = {m["slug"]: m["agent_key"] for m in team["members"]}
r = client.post(f"/teams/{tid}/messages", params={"brain": B},
                json={"text": "Viết thông cáo", "mentions": [keys["minh"]], "as_job": True, "client_msg_id": "j1"})
task_id = r.json()["task_id"]
r2 = client.post(f"/teams/{tid}/messages", params={"brain": B},
                 json={"text": "Việc chung", "as_job": True, "client_msg_id": "j2"})
task2 = r2.json()["task_id"]
teams = api.teams()
t = main.tasks_feature.store.get_task(task_id)
# Thêm bước qua bộ chạy (đúng đường của việc thật): Minh làm, Hoa hỗ trợ.
api.runner()._put_steps(teams.get(tid), t, [{"kind": "work", "agent": keys["minh"], "brief": "viết"},
                                            {"kind": "help", "agent": keys["hoa"], "brief": "soát số liệu"}])

code, j = jobs("minh")
mine = [x for x in j["jobs"] if x["source"] == "team"]
check("Minh thấy việc giao thẳng, nguồn là nhóm, mở đúng nhóm và việc",
      len(mine) == 1 and mine[0]["roles"][0] == "assignee" and mine[0]["source_label"] == "Ra mắt"
      and mine[0]["open"] == {"kind": "team", "team_id": tid, "task_id": task_id}, j)
check("việc đang chờ: ngăn Đang chờ, vị trí thật trong hàng của nhóm, có Huỷ",
      mine[0]["bucket"] == "waiting" and mine[0]["queue_pos"] == 1 and mine[0]["cancel"]["task_id"] == task_id, mine)
check("tiến độ là số bước thật", mine[0]["progress"] == {"done": 0, "total": 2}, mine)
code, j = jobs("hoa")
hoa = [x for x in j["jobs"] if x["source"] == "team"]
check("người chỉ hỗ trợ một bước cũng thấy việc liên quan, vai Hỗ trợ",
      [x["id"] for x in hoa] == [f"team:{task_id}"] and hoa[0]["roles"] == ["helper"], j)
code, j = jobs("lan")
lan = {x["id"]: x for x in j["jobs"] if x["source"] == "team"}
check("trưởng nhóm thấy cả hai việc với vai Điều phối", set(lan) == {f"team:{task_id}", f"team:{task2}"}
      and all("coordinator" in x["roles"] for x in lan.values()), j)
check("cùng bản ghi gốc: không sinh việc Kanban mới khi đọc",
      [x for x in main.tasks_feature.store.list_tasks(str(BR)) if x.get("lane") != "team"] == [])

# Huỷ một việc không ảnh hưởng việc khác.
client.post(f"/teams/{tid}/tasks/{task2}/cancel", params={"brain": B})
code, j = jobs("lan")
lan = {x["id"]: x for x in j["jobs"]}
check("huỷ một việc: việc đó sang Đã xong (huỷ), việc kia giữ nguyên",
      lan[f"team:{task2}"]["bucket"] == "done" and lan[f"team:{task2}"]["cancelled"]
      and lan[f"team:{task_id}"]["bucket"] == "waiting", lan)

# Giao việc: một việc Kanban gắn mã trợ lý, báo về chat riêng, chống gửi trùng.
main.tasks_feature.store.set_orchestration(str(BR), "off")
r = client.post("/agents/minh/jobs", params={"brain": B}, json={"text": "Soạn email cảm ơn khách", "nonce": "n1"})
a1 = r.json()
r = client.post("/agents/minh/jobs", params={"brain": B}, json={"text": "Soạn email cảm ơn khách", "nonce": "n1"})
check("Giao việc: bấm hai lần cùng nonce chỉ một việc", a1["ok"] and r.json()["task_id"] == a1["task_id"], (a1, r.json()))
r = client.post("/agents/lan/jobs", params={"brain": B}, json={"text": "Soạn email cảm ơn khách", "nonce": "n2"})
check("cùng nội dung giao cho trợ lý khác là việc khác (không gộp theo tiêu đề)", r.json()["task_id"] != a1["task_id"])
kt = main.tasks_feature.store.get_task(a1["task_id"])
sess = main.get_store().get_session(a1["session_id"])
check("việc Kanban báo về đúng cuộc chat riêng với trợ lý", kt["chat_id"] == f"web:{a1['session_id']}"
      and sess["channel"] == "agent:minh" and "Minh" in kt["title"], (kt, sess))
code, j = jobs("minh")
kj = [x for x in j["jobs"] if x["source"] == "chat"]
check("việc giao hiện ở tab, nguồn chat riêng, mở đúng cuộc chat",
      len(kj) == 1 and kj[0]["open"] == {"kind": "chat", "session_id": a1["session_id"]}, j)
check("hàng chờ trung thực: AI tự vận hành tắt thì ghi rõ", kj[0]["bucket"] == "waiting" and kj[0]["board_off"]
      and j["board"] == "off", kj)
code, j2 = jobs("lan")
check("việc của trợ lý khác không lẫn sang", all(x["id"] != f"kanban:{a1['task_id']}" for x in j2["jobs"]))
check("thiếu nội dung: 400", client.post("/agents/minh/jobs", params={"brain": B},
                                          json={"text": " ", "nonce": "n3"}).status_code == 400)

# Việc xếp từ chat riêng (javis_task với chat_id web:<phiên>) cũng thuộc trợ lý đó.
t2 = main.tasks_feature.enqueue(B, "Tra giá đối thủ", "Tra giá", chat_id=f"web:{a1['session_id']}")
code, j = jobs("minh")
check("việc xếp từ chat riêng thuộc trợ lý của phiên", any(x["id"] == f"kanban:{t2}" for x in j["jobs"]), j)
# Huỷ một việc Kanban không đụng việc khác.
main.tasks_feature.store.move(t2, "cancelled", "test")
code, j = jobs("minh")
by = {x["id"]: x for x in j["jobs"]}
check("huỷ việc Kanban: chỉ việc đó Đã xong", by[f"kanban:{t2}"]["bucket"] == "done"
      and by[f"kanban:{a1['task_id']}"]["bucket"] == "waiting", by)

# Persona: việc giao cho trợ lý chạy với vai của trợ lý đó, engine và quyền của Kanban giữ nguyên.
p = main.tasks_feature._persona(kt, str(BR))
check("việc giao mang vai của trợ lý", "Minh" in p and "Bạn là Minh" in p, p[:300])
check("việc Kanban thường không mang vai", main.tasks_feature._persona(main.tasks_feature.store.get_task(t2), str(BR)) == "")
check("khoá giao việc đọc ngược được", agent_jobs.parse_assign_key(kt["idempotency_key"]) == (j["agent_key"], "minh"))

# Ngăn và thứ tự: Cần bạn trước, rồi Đang làm, Đang chờ, Đã xong.
order = [x["bucket"] for x in j["jobs"]]
rank = {"needs_you": 0, "running": 1, "waiting": 2, "done": 3}
check("thứ tự ngăn đúng", order == sorted(order, key=lambda b: rank[b]), order)
check("không nguồn nào lỗi ngầm", j["errors"] == [], j["errors"])
check("đếm theo ngăn khớp danh sách", all(j["counts"][b] == order.count(b) for b in rank), j["counts"])

# review #8: nonce chỉ toàn ký tự lạ thì từ chối, không dùng chung một khoá.
r = client.post("/agents/minh/jobs", params={"brain": B}, json={"text": "Việc lạ", "nonce": "!!! ###"})
check("review #8: nonce rỗng sau khi lọc: 400", r.status_code == 400, r.text)
# review #7: phiên chat cũ đã ghim mã của trợ lý trước (cùng slug) không nhận việc của trợ lý hiện tại.
old_sid = main.get_store().create_session(brain=B, channel="agent:hoa", title="Hoa cũ")
with main._resonance_store()._conn() as c:
    c.execute("INSERT INTO session_agents(session_id,brain_id,agent_key,by,created_at) VALUES(?,?,?,?,?)",
              (old_sid, str(BR), "ag_tro_ly_cu", "test", 0))
r = client.post("/agents/hoa/jobs", params={"brain": B}, json={"text": "Gửi báo giá", "nonce": "h1"})
check("review #7: Giao việc không báo vào phiên của trợ lý cũ cùng slug, mở phiên mới",
      r.json()["ok"] and r.json()["session_id"] != old_sid, r.json())

print(("FAIL" if fails else "PASS") + f" - test_agent_jobs_0142: {len(fails)} lỗi")
raise SystemExit(1 if fails else 0)
