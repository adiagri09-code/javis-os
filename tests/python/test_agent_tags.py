"""Tag của agent (0.98.0): mỗi agent gắn nhiều tag, nhóm cũ thành một tag. Chạy tay / CI:

    python tests/run.py agent_tags

Hợp đồng: docs/dev/agent-tags.md. Test HÀNH VI qua HTTP thật của app (TestClient) trên brain tạm:
chuyển đổi file cũ, thêm/bỏ/đổi tên/xoá tag, client cũ chỉ gửi `group`, hai thao tác đồng thời, lỗi ghi
giữa chừng, chuẩn hoá Unicode, xuất/nhập gói, và tag không chạm danh tính, phiên hay Cộng hưởng.

KHÔNG chạm mạng, KHÔNG gọi model. KHÔNG dùng ký tự em dash.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import json
import os
import sys
import tempfile
import threading
from pathlib import Path

STATE = tempfile.mkdtemp(prefix="javis-tags-state-")
os.environ.setdefault("JAVIS_STATE_DIR", STATE)

import agent_tags  # noqa: E402
import main  # noqa: E402
import share_bundle  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

_fails = []


def check(ten, dk, them=""):
    print(("ok   " if dk else "FAIL ") + ten + (("  [" + str(them)[:300] + "]") if them and not dk else ""))
    if not dk:
        _fails.append(ten)


main.cfgmod.gate_active = lambda: False
client = TestClient(main.app, base_url="http://127.0.0.1")


def brain_moi(prefix):
    b = Path(tempfile.mkdtemp(prefix=prefix))
    (b / "agents").mkdir(parents=True)
    (b / "workflows").mkdir(parents=True)
    return b


B = brain_moi("javis-tags-a-")
B2 = brain_moi("javis-tags-b-")


def viet(brain, slug, fm, body="Bạn là trợ lý. Giữ giọng gần gũi."):
    (brain / "agents" / f"{slug}.md").write_text(f"---\n{fm}---\n{body}\n", encoding="utf-8")


def doc(brain, slug):
    return main._read_md(brain / "agents" / f"{slug}.md")


def ds(brain):
    return client.get("/agents", params={"brain": str(brain), "prompt": "0"}).json()["agents"]


def mot(brain, slug):
    return next(a for a in ds(brain) if a["slug"] == slug)


def meta(brain, slug, kind="agent", **form):
    return client.post("/capability/meta", data=dict(form, kind=kind, slug=slug, brain=str(brain)))


def J(*x):
    return json.dumps(list(x), ensure_ascii=False)


# Cộng hưởng và engine KHÔNG được chạm khi gắn tag: thay bằng bẫy, chạm là ghi lại.
_cham = []
main._resonance_store = lambda *a, **k: _cham.append("resonance_store") or (_ for _ in ()).throw(RuntimeError("cham"))
main._resonance_engine = lambda *a, **k: _cham.append("engine") or None

# ============================================================ 1-2. Đọc file cũ, chuyển đổi lặp an toàn
viet(B, "mk", "type: agent\nname: MK\nslug: mk\nrole: tiếp thị\ngroup: Marketing\nmodel: sonnet\n")
viet(B, "khong-nhom", "type: agent\nname: Không nhóm\nslug: khong-nhom\nrole: x\n")
viet(B, "chung-that", "type: agent\nname: Chung thật\nslug: chung-that\nrole: x\ngroup: Chung\n")
viet(B, "nhom-rong", "type: agent\nname: Nhóm rỗng\nslug: nhom-rong\nrole: x\ngroup: ''\n")

check("1 file cũ group: Marketing đọc thành tags [Marketing]", mot(B, "mk")["tags"] == ["Marketing"])
check("2 file không có group vẫn hiện, chưa gắn tag", mot(B, "khong-nhom")["tags"] == [])
check("2 group rỗng: chưa gắn tag", mot(B, "nhom-rong")["tags"] == [])
check("2 group: Chung THẬT thành tag Chung (khác nhãn mặc định)", mot(B, "chung-that")["tags"] == ["Chung"])
check("2 đọc danh sách KHÔNG ghi file (không có khoá tags sau khi tải)", "tags" not in doc(B, "mk")[0])
for _ in range(2):
    meta(B, "mk", pinned="1")
m, body = doc(B, "mk")
check("1 lưu (ghim) hai lần: tags [Marketing] không nhân đôi, gương group đúng",
      m.get("tags") == ["Marketing"] and m.get("group") == "Marketing", m)
check("1 chuyển đổi giữ nội dung và khoá khác", "Bạn là trợ lý" in body and m.get("model") == "sonnet"
      and m.get("role") == "tiếp thị" and m.get("pinned") is True, m)

# ============================================================ 3-4. Nhiều tag, thêm, bỏ, bỏ hết
r = meta(B, "mk", add_tags=J("Viết nội dung"))
check("4 gắn tag mới giữ tag cũ", r.json().get("tags") == ["Marketing", "Viết nội dung"], r.text)
lst = ds(B)
check("3 agent nhiều tag xuất hiện MỘT lần trong danh sách", [a["slug"] for a in lst].count("mk") == 1)
check("3 tổng số agent không nhân đôi", len(lst) == 4, len(lst))
r = meta(B, "mk", remove_tags=J("marketing"))
check("4 bỏ một tag (khác hoa thường) giữ tag còn lại", r.json().get("tags") == ["Viết nội dung"], r.text)
r = meta(B, "mk", remove_tags=J("Viết nội dung"))
m, _ = doc(B, "mk")
check("4 bỏ hết: file ghi tags: [] và xoá gương group", m.get("tags") == [] and "group" not in m, m)
check("4 bỏ hết rồi tải lại không hồi sinh nhóm cũ", mot(B, "mk")["tags"] == [])
main._RESONANCE_STORE = None
check("4 sau 'khởi động lại' (đọc lại từ đĩa) vẫn rỗng", agent_tags.tags_of(doc(B, "mk")[0]) == [])
r = meta(B, "mk", tags=J("A", "B", "a"))
check("thay cả tập bằng `tags` (bỏ trùng khoá)", r.json().get("tags") == ["A", "B"], r.text)
r = meta(B, "mk", tags="[]")
check("6 `tags: []` có chủ ý là bỏ hết", r.json().get("tags") == [], r.text)

# ============================================================ 5. Form sửa không gửi tags giữ nguyên tag
meta(B, "mk", tags=J("Marketing", "Viết nội dung"))
meta(B, "mk", pinned="1")
r = client.post("/agents", data={"brain": str(B), "slug": "mk", "name": "MK mới", "role": "tiếp thị 2",
                                 "prompt": "Prompt mới.", "model": "opus", "skills": "",
                                 "avatar_shape": "star", "avatar_palette": "amber"})
m, body = doc(B, "mk")
check("5 form không gửi tags giữ đủ tag", m.get("tags") == ["Marketing", "Viết nội dung"], m)
check("5 form vẫn lưu tên/prompt/model/avatar và giữ ghim",
      m.get("name") == "MK mới" and body.strip() == "Prompt mới." and m.get("model") == "opus"
      and (m.get("avatar") or {}).get("shape") == "star" and m.get("pinned") is True, m)
r = client.post("/agents", data={"brain": str(B), "name": "Agent mới", "role": "x"})
check("agent mới không gửi tag: tags: [] (không ghi 'Chung' giả)",
      doc(B, r.json()["slug"])[0].get("tags") == [] and "group" not in doc(B, r.json()["slug"])[0])

# ============================================================ 6. Client cũ chỉ gửi group
r = meta(B, "mk", group="Sales")
check("6 client cũ group-only trên agent nhiều tag: 409, không đổi gì",
      r.status_code == 409 and r.json().get("code") == "stale_client"
      and doc(B, "mk")[0].get("tags") == ["Marketing", "Viết nội dung"], r.text)
r = client.post("/agents", data={"brain": str(B), "slug": "mk", "name": "MK mới", "role": "x", "group": "Sales"})
check("6 form cũ gửi group trên agent nhiều tag: 409, giữ tag",
      r.status_code == 409 and doc(B, "mk")[0].get("tags") == ["Marketing", "Viết nội dung"], r.text)
r = meta(B, "chung-that", group="Sales")
check("6 client cũ group-only trên agent một tag: thành đúng một tag", r.json().get("tags") == ["Sales"], r.text)
r = meta(B, "chung-that", group="X", add_tags=J("Y"))
check("6 gửi cùng group và tags: 400 rõ ràng", r.status_code == 400 and r.json().get("code") == "group_and_tags", r.text)

# ============================================================ 7. Đổi tên, gộp, xoá tag
viet(B, "nd", "type: agent\nname: ND\nslug: nd\nrole: x\ntags:\n- Viết nội dung\n- Kỹ thuật\n", "Thân ND.")
viet(B2, "mk2", "type: agent\nname: MK2\nslug: mk2\nrole: x\ntags:\n- Marketing\n", "Thân MK2.")
r = client.post("/agents/tags/rename", data={"brain": str(B), "from_tag": "Viết nội dung", "to_tag": "Nội dung"})
j = r.json()
check("7 đổi tên: đúng các agent có tag", r.status_code == 200 and sorted(j["changed"]) == ["mk", "nd"] and not j["merged"], r.text)
check("7 đổi tên giữ tag khác và vị trí", doc(B, "nd")[0]["tags"] == ["Nội dung", "Kỹ thuật"]
      and doc(B, "mk")[0]["tags"] == ["Marketing", "Nội dung"])
check("7 đổi tên giữ nội dung file", doc(B, "nd")[1] == "Thân ND.")
check("7 brain khác không bị chạm", doc(B2, "mk2")[0]["tags"] == ["Marketing"])
r = client.post("/agents/tags/rename", data={"brain": str(B), "from_tag": "Kỹ thuật", "to_tag": "nội DUNG"})
j = r.json()
check("7 đổi tên sang tag đã có: gộp, báo merged, không nhân đôi",
      j["merged"] and doc(B, "nd")[0]["tags"] == ["Nội dung"], r.text)
r = client.post("/agents/tags/delete", data={"brain": str(B), "tag": "nội dung"})
check("7 xoá tag chỉ gỡ nhãn, agent còn nguyên",
      r.json()["ok"] and (B / "agents" / "nd.md").is_file() and doc(B, "nd")[0]["tags"] == []
      and doc(B, "mk")[0]["tags"] == ["Marketing"] and doc(B, "nd")[1] == "Thân ND.", r.text)
check("7 xoá tag ở brain này không chạm brain khác", doc(B2, "mk2")[0]["tags"] == ["Marketing"])

# ============================================================ 8. Đồng thời và lỗi ghi giữa chừng
viet(B, "dua", "type: agent\nname: Đua\nslug: dua\nrole: x\ntags: []\n")
loi = []


def them_nhieu(tien_to):
    for i in range(10):
        try:
            asyncio.run(main.capability_meta(kind="agent", slug="dua", brain=str(B), pinned=None, group=None,
                                             tags=None, add_tags=J(f"{tien_to}{i}"), remove_tags=None))
        except Exception as e:  # noqa: BLE001
            loi.append(repr(e))


th = [threading.Thread(target=them_nhieu, args=(p,)) for p in ("a", "b")]
[x.start() for x in th]
[x.join() for x in th]
tg = doc(B, "dua")[0].get("tags") or []
check("8 hai 'tab' thêm tag cùng lúc: không mất tag nào",
      not loi and set(tg) == {f"a{i}" for i in range(10)} | {f"b{i}" for i in range(10)}, (len(tg), loi))
viet(B, "loi-a", "type: agent\nname: LA\nslug: loi-a\nrole: x\ntags:\n- Hỏng\n")
viet(B, "loi-b", "type: agent\nname: LB\nslug: loi-b\nrole: x\ntags:\n- Hỏng\n")
_goc = main._write_md


def _ghi_hong(path, m, body):
    if Path(path).stem == "loi-b":
        raise OSError("đĩa đầy")
    return _goc(path, m, body)


main._write_md = _ghi_hong
r = client.post("/agents/tags/delete", data={"brain": str(B), "tag": "Hỏng"})
main._write_md = _goc
j = r.json()
check("8 lỗi ghi giữa chừng: không báo thành công, nói rõ đã làm và chưa làm",
      r.status_code == 500 and j["ok"] is False and j["changed"] == ["loi-a"]
      and [f["slug"] for f in j["failed"]] == ["loi-b"] and j.get("error"), r.text)
check("8 file lỗi giữ nguyên tag", doc(B, "loi-b")[0]["tags"] == ["Hỏng"])
viet(B, "yaml-hong", "type: agent\nname: [hỏng\nrole: x\n")
r = meta(B, "yaml-hong", add_tags=J("X"))
check("8 frontmatter hỏng: từ chối, không xoá sạch khoá",
      r.status_code == 422 and "name: [hỏng" in (B / "agents" / "yaml-hong.md").read_text(encoding="utf-8"), r.text)

# ============================================================ 9. Chuẩn hoá, Unicode, ký tự đặc biệt
dac_biet = 'a: b # c [d] \'e\' "f" <script>x</script>'
r = meta(B, "nd", tags=J("  Viết   nội\tdung ", "viết nội dung", "Viet noi dung", dac_biet))
tg = r.json().get("tags")
check("9 gộp khoảng trắng, bỏ trùng hoa thường, giữ dấu (Viết khác Viet)",
      tg[:2] == ["Viết nội dung", "Viet noi dung"], tg)
check("9 ký tự đặc biệt qua YAML khứ hồi nguyên vẹn", doc(B, "nd")[0]["tags"][2] == dac_biet and tg[2] == dac_biet)
nfd = "Viết"   # "Viết" dạng tổ hợp (NFD)
meta(B, "nd", tags=J("Viết"))
r = meta(B, "nd", add_tags=J(nfd))
check("9 NFD và NFC là một tag", r.json().get("tags") == ["Viết"], r.text)
r = meta(B, "nd", add_tags=J("x" * 41))
check("9 tag quá 40 ký tự: 400 tag_too_long", r.status_code == 400 and r.json().get("code") == "tag_too_long", r.text)
r = meta(B, "nd", add_tags="không-phải-json[")
check("9 chuỗi đơn được nhận như một tag", r.status_code == 200 and "không-phải-json[" in r.json()["tags"], r.text)

# ============================================================ 10. Xuất / nhập
meta(B, "mk", tags=J("Marketing", "Viết nội dung"))
zipb, _ten = share_bundle.build_bundle("agent", "mk", agents_dir=B / "agents", workflows_dir=B / "workflows",
                                       skills_root=B / "skills")
B3 = brain_moi("javis-tags-c-")
share_bundle.import_bundle(zipb, "goi.zip", agents_dir=B3 / "agents", workflows_dir=B3 / "workflows",
                           skills_root=B3 / "skills")
check("10 xuất/nhập vòng kín giữ đủ tag", mot(B3, "mk")["tags"] == ["Marketing", "Viết nội dung"])
cu = "---\ntype: agent\nname: Gói cũ\nslug: goi-cu\nrole: x\ngroup: Bán hàng\n---\nthân\n".encode("utf-8")
share_bundle.import_bundle(cu, "goi-cu.md", agents_dir=B3 / "agents", workflows_dir=B3 / "workflows",
                           skills_root=B3 / "skills")
check("10 nhập gói cũ: group thành đúng một tag", mot(B3, "goi-cu")["tags"] == ["Bán hàng"])
meta(B3, "goi-cu", pinned="1")
meta(B3, "goi-cu", pinned="0")
check("10 gói cũ chuyển đúng một lần (lưu hai lần không nhân đôi)", doc(B3, "goi-cu")[0]["tags"] == ["Bán hàng"])
idx = main._render_javis_index(main._gather_capabilities(str(B)))
check("chỉ mục ghi tag trên dòng agent", "tags: Marketing, Viết nội dung" in idx)

# ============================================================ 11-12. Không chạm danh tính, phiên, Cộng hưởng; workflow như cũ
check("11 gắn/bỏ/đổi tên/xoá tag không chạm Cộng hưởng hay engine", _cham == [], _cham)
check("11 không tạo kho Cộng hưởng hay sổ lượt engine",
      not (Path(STATE) / "resonance.sqlite3").exists() and not (Path(STATE) / "usage-events.jsonl").exists())
(B / "workflows" / "wf.md").write_text("---\ntype: workflow\nname: WF\nslug: wf\nstatus: active\ngroup: Content\n"
                                       "steps: []\n---\nmô tả\n", encoding="utf-8")
r = meta(B, "wf", kind="workflow", group="Nội dung")
check("12 workflow vẫn chuyển nhóm như cũ", r.json().get("group") == "Nội dung"
      and main._read_md(B / "workflows" / "wf.md")[0].get("group") == "Nội dung" and "tags" not in r.json(), r.text)
r = meta(B, "wf", kind="workflow", add_tags=J("X"))
check("12 workflow không nhận tag (400)", r.status_code == 400 and r.json().get("code") == "tags_not_for_kind", r.text)

# ============================================================ Hàm thuần
check("thuần: rename không có tag thì không đổi", agent_tags.rename(["A"], "B", "C") == (["A"], False))
check("thuần: tags chuỗi đơn trong file đọc thành một tag", agent_tags.tags_of({"tags": "Marketing"}) == ["Marketing"])
check("thuần: tags lạ (số) bỏ qua khi đọc", agent_tags.tags_of({"tags": [1, "A", None]}) == ["A"])
check("thuần: có tags thì không đọc group", agent_tags.tags_of({"tags": [], "group": "Cũ"}) == [])
try:
    agent_tags.normalize_tags([f"t{i}" for i in range(21)])
    check("thuần: quá 20 tag bị từ chối", False)
except agent_tags.TagError as e:
    check("thuần: quá 20 tag bị từ chối", str(e) == "too_many_tags")

if _fails:
    print(f"\n{len(_fails)} FAIL:", _fails)
    sys.exit(1)
print("\nOK - test_agent_tags: tất cả pass")
