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
viet(B, "kt", "type: agent\nname: KT\nslug: kt\nrole: x\ntags:\n- Kỹ thuật\n", "Thân KT.")
r = client.post("/agents/tags/rename", data={"brain": str(B), "from_tag": "Kỹ thuật", "to_tag": "nội DUNG"})
j = r.json()
check("7 đổi tên sang tag đã có: gộp, báo merged, không nhân đôi",
      j["merged"] and doc(B, "nd")[0]["tags"] == ["Nội dung"], r.text)
check("7 gộp dùng CÁCH VIẾT của tag đã có, kể cả agent chỉ mang tag cũ",
      j["tag"] == "Nội dung" and doc(B, "kt")[0]["tags"] == ["Nội dung"], (j, doc(B, "kt")[0]))
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

# ============================================================ Review PR #617 vòng 1: R1 đến R4
# R1. Dữ liệu ĐANG CÓ vượt giới hạn tag mới (nhóm cũ dài hơn 40 ký tự, file có hơn 20 tag) không bị cắt hay
# xoá khi người dùng chỉ ghim, lưu form, nhập gói hay tải lại. Kiểm metadata nguồn trong file, không chỉ HTTP 200.
B4 = brain_moi("javis-tags-r1-")
DAI = "Marketing noi dung cho thi truong quoc te 2026"          # 46 ký tự, hợp lệ ở 0.96.1
viet(B4, "dai", f"type: agent\nname: Dài\nslug: dai\nrole: x\ngroup: {DAI}\nmodel: sonnet\n", "Thân dài.")
viet(B4, "thuong", "type: agent\nname: Thường\nslug: thuong\nrole: x\ngroup: Marketing\n", "Thân thường.")
check("R1 nhóm cũ dài đọc thành đúng một tag (không bị lọc mất)", mot(B4, "dai")["tags"] == [DAI])
r = meta(B4, "dai", pinned="1")
m, body = doc(B4, "dai")
check("R1 ghim agent nhóm cũ dài: giữ nguyên tag và gương group trong file",
      r.status_code == 200 and m.get("tags") == [DAI] and m.get("group") == DAI and body == "Thân dài.", (r.text, m))
r = client.post("/agents", data={"brain": str(B4), "slug": "dai", "name": "Dài 2", "role": "y", "model": "sonnet"})
m, _ = doc(B4, "dai")
check("R1 lưu form không gửi tags: giữ nguyên tag dài", r.status_code == 200 and m.get("tags") == [DAI]
      and m.get("group") == DAI and m.get("name") == "Dài 2", (r.text, m))
check("R1 tải lại (F5) vẫn đúng tag dài", mot(B4, "dai")["tags"] == [DAI])
meta(B4, "thuong", pinned="1")
check("R1 đối chứng: tên thường qua cùng đường vẫn đúng", doc(B4, "thuong")[0].get("tags") == ["Marketing"])
r = meta(B4, "dai", remove_tags=J(DAI))
check("R1 bỏ được tag cũ dài (so theo khoá, không áp giới hạn độ dài)", r.status_code == 200 and r.json()["tags"] == [], r.text)
r = meta(B4, "dai", add_tags=J(DAI))
check("R1 THÊM MỚI tag dài vẫn bị từ chối (giới hạn chỉ cho đầu vào mới)",
      r.status_code == 400 and r.json().get("code") == "tag_too_long", r.text)
viet(B4, "dai2", f"type: agent\nname: Dài 2\nslug: dai2\nrole: x\ngroup: {DAI}\n", "Thân.")
r = client.post("/agents/tags/rename", data={"brain": str(B4), "from_tag": DAI, "to_tag": "Marketing QT"})
check("R1 đổi tên được tag cũ dài sang tên hợp lệ", r.status_code == 200 and doc(B4, "dai2")[0]["tags"] == ["Marketing QT"], r.text)
viet(B4, "dai3", f"type: agent\nname: Dài 3\nslug: dai3\nrole: x\ngroup: {DAI}\n", "Thân.")
r = client.post("/agents/tags/delete", data={"brain": str(B4), "tag": DAI})
check("R1 xoá được tag cũ dài", r.status_code == 200 and doc(B4, "dai3")[0]["tags"] == [], r.text)
B5 = brain_moi("javis-tags-r1-nhap-")
cu = f"---\ntype: agent\nname: Gói dài\nslug: goi-dai\nrole: x\ngroup: {DAI}\n---\nthân\n".encode("utf-8")
share_bundle.import_bundle(cu, "goi-dai.md", agents_dir=B5 / "agents", workflows_dir=B5 / "workflows",
                           skills_root=B5 / "skills")
meta(B5, "goi-dai", pinned="1")
check("R1 nhập gói cũ có nhóm dài rồi ghim: giữ đúng tag", doc(B5, "goi-dai")[0].get("tags") == [DAI]
      and mot(B5, "goi-dai")["tags"] == [DAI])
NHIEU = [f"t{i:02d}" for i in range(25)]
viet(B4, "nhieu", "type: agent\nname: Nhiều\nslug: nhieu\nrole: x\ntags:\n" + "".join(f"- {x}\n" for x in NHIEU), "Thân.")
check("R1 file có 25 tag: đọc đủ 25, không cắt", mot(B4, "nhieu")["tags"] == NHIEU)
meta(B4, "nhieu", pinned="1")
client.post("/agents", data={"brain": str(B4), "slug": "nhieu", "name": "Nhiều", "role": "z"})
check("R1 ghim rồi lưu form: file vẫn đủ 25 tag", doc(B4, "nhieu")[0].get("tags") == NHIEU, doc(B4, "nhieu")[0].get("tags"))
r = meta(B4, "nhieu", add_tags=J("moi"))
check("R1 thêm tag thứ 26: từ chối, không đổi file", r.status_code == 400 and r.json().get("code") == "too_many_tags"
      and doc(B4, "nhieu")[0].get("tags") == NHIEU, r.text)
r = meta(B4, "nhieu", add_tags=J("T05"))
check("R1 thêm tag đã có (khác hoa thường) khi đang quá 20: không lỗi, không đổi", r.status_code == 200
      and r.json()["tags"] == NHIEU, r.text)
r = meta(B4, "nhieu", remove_tags=J("t00"))
check("R1 bỏ tag khi đang quá 20 luôn được", r.status_code == 200 and r.json()["tags"] == NHIEU[1:], r.text)

# R2 + R3. Dữ liệu API THẬT đưa vào mã thật của trang Cộng sự và Studio (tests/js/agent_tags_ui_probe.js).
import subprocess  # noqa: E402
B6 = brain_moi("javis-tags-r3-")
NFD = "Viết"
for slug, tgs in (("a", ["Straße"]), ("b", ["STRASSE"]), ("c", ["Viết"]), ("d", ["VIẾT"]), ("e", ["Viet"]),
                  ("f", [NFD]), ("g", ["__proto__", "constructor", "Marketing"]), ("h", ["constructor"])):
    client.post("/agents", data={"brain": str(B6), "slug": slug, "name": slug.upper(), "role": "x",
                                 "tags": json.dumps(tgs, ensure_ascii=False)})
api = client.get("/agents", params={"brain": str(B6), "prompt": "0"}).json()
# .get: chạy được cả trên mã chưa có `tag_keys` (đối chứng head cũ) để các ca sau vẫn chạy; thiếu thì ca này hỏng.
khoa = {a["slug"]: a.get("tag_keys") for a in api["agents"]}
check("R3 API trả khoá host: Straße và STRASSE cùng khoá casefold", khoa["a"] == khoa["b"] == ["strasse"], khoa)
check("R3 API: Viết, VIẾT, Viết dạng NFD cùng khoá; Viet khác",
      khoa["c"] == khoa["d"] == khoa["f"] and khoa["e"] != khoa["c"], khoa)
check("R2 API nhận và trả nguyên tag __proto__, constructor", mot(B6, "g")["tags"] == ["__proto__", "constructor", "Marketing"])
p = subprocess.run(["node", str(Path(ROOT) / "tests" / "js" / "agent_tags_ui_probe.js")], input=json.dumps(api),
                   capture_output=True, text=True, encoding="utf-8", timeout=60)
try:
    ui = json.loads(p.stdout)
except ValueError:
    ui = None
check("R2/R3 probe giao diện chạy được trên dữ liệu API", ui is not None, (p.returncode, p.stderr[-400:]))
if ui:
    # Kỳ vọng: nhóm agent theo khoá SERVER đã trả.
    theo_server = {}
    for a in api["agents"]:
        for k in (agent_tags.tag_key(x) for x in a["tags"]):     # khoá server tính lại từ tên, không cần API trả
            theo_server.setdefault(k, set()).add(a["slug"])
    ws = {b.get("key"): b["n"] for b in ui["workspace"]["buckets"]}
    st = {b.get("key"): b["n"] for b in ui["studio"]["buckets"]}
    check("R3 Cộng sự đếm đúng theo khoá server (Straße/STRASSE = 2, Viết = 3, Viet = 1)",
          ws == {k: len(v) for k, v in theo_server.items()}, ws)
    check("R3 Studio đếm giống hệt Cộng sự và server", st == ws, st)
    check("R3 lọc theo khoá ra đúng tập agent của server (Cộng sự và Studio)",
          all(sorted(theo_server[k]) == ui["workspace"]["filter"].get(k) == ui["studio"]["filter"].get(k)
              for k in theo_server), ui["workspace"]["filter"])
    check("R3 lọc theo TÊN 'STRASSE' cũng ra cả hai agent", ui["workspace"]["filterByName"].get("STRASSE") == ["a", "b"],
          ui["workspace"]["filterByName"])
    check("R2/R3 dấu tick bộ chọn đúng khoá của chính agent (kể cả __proto__, constructor)",
          ui["workspace"]["ticks"] is not None
          and all(sorted(agent_tags.tag_key(x) for x in a["tags"]) == ui["workspace"]["ticks"].get(a["slug"])
                  for a in api["agents"]), ui["workspace"]["ticks"])
    check("R2 tag __proto__ và constructor được đếm, không làm hỏng prototype",
          ws.get("__proto__") == 1 and ws.get("constructor") == 2 and ui["prototypeClean"], ws)
r = meta(B6, "a", remove_tags=J("STRASSE"))
check("R3 server bỏ 'STRASSE' trên agent mang 'Straße' (cùng khoá với giao diện)", r.json().get("tags") == [], r.text)
r = client.post("/agents/tags/rename", data={"brain": str(B6), "from_tag": "viết", "to_tag": "Viết bài"})
check("R3 đổi tên theo khoá: Viết, VIẾT, NFD cùng đổi; Viet giữ nguyên",
      sorted(r.json()["changed"]) == ["c", "d", "f"] and doc(B6, "e")[0]["tags"] == ["Viet"]
      and r.json().get("tag_key") == agent_tags.tag_key("Viết bài"), r.text)

# R4. I/O của các đường tag chạy ở worker: event loop vẫn phản hồi khi đĩa chậm. Ghi chậm là GIẢ LẬP
# (sleep trong _write_md), không phải số đo máy thật.
B7 = brain_moi("javis-tags-r4-")
for i in range(3):
    viet(B7, f"cham{i}", f"type: agent\nname: C{i}\nslug: cham{i}\nrole: x\ntags:\n- Chậm\n", f"Thân {i}.")
import time  # noqa: E402
_goc2 = main._write_md


def _ghi_cham(path, m, body):
    time.sleep(0.08)
    return _goc2(path, m, body)


async def _do_tre(coro):
    tre, dung = [], [False]

    async def nhip():
        while not dung[0]:
            t0 = time.perf_counter()
            await asyncio.sleep(0.02)
            tre.append(time.perf_counter() - t0 - 0.02)
    tk = asyncio.create_task(nhip())
    # Cho nhịp đo CHẠY TRƯỚC (đang ngủ 20 ms) rồi mới gọi route: route đồng bộ chặn loop thì nhịp đó thức muộn
    # và bị ghi lại. Không đợi ở đây thì route cũ chạy xong trước khi nhịp bắt đầu, không có mẫu nào.
    await asyncio.sleep(0.005)
    try:
        kq = await coro
    finally:
        dung[0] = True
        await tk
    # Không có mẫu đo nào là phép đo hỏng, không phải "không trễ".
    return kq, max(tre) if tre else float("inf")


main._write_md = _ghi_cham
try:
    resp, tre = asyncio.run(_do_tre(main.agent_tag_rename(brain=str(B7), from_tag="Chậm", to_tag="Nhanh")))
    j = json.loads(resp.body)
    check(f"R4 đổi tên 3 agent khi mỗi lần ghi chậm 80 ms: event loop trễ tối đa {tre * 1000:.0f} ms (< 60 ms)",
          tre < 0.06 and sorted(j["changed"]) == ["cham0", "cham1", "cham2"], (tre, j))
    resp, tre = asyncio.run(_do_tre(main.agent_tag_delete(brain=str(B7), tag="Nhanh")))
    check(f"R4 xoá tag 3 agent khi ghi chậm: event loop trễ tối đa {tre * 1000:.0f} ms (< 60 ms)",
          tre < 0.06 and json.loads(resp.body)["ok"], tre)

    def _cap(slug, **kw):
        base = dict(kind="agent", slug=slug, brain=str(B7), pinned=None, group=None, tags=None, add_tags=None,
                    remove_tags=None)
        base.update(kw)
        return main.capability_meta(**base)

    def _form(slug, role):
        return main.save_agent(name=slug.upper(), role=role, skills="", model="", slug=slug, prompt="", brain=str(B7),
                               model_provider="", group=None, avatar_shape=None, avatar_palette=None,
                               avatar_color=None, avatar_eye=None, avatar_eye_color=None, avatar_eye_size=None,
                               tags=None)

    async def _xen(form_truoc):
        a = _form("cham0", "vai mới") if form_truoc else _cap("cham0", add_tags=J("Xen"))
        b = _cap("cham0", add_tags=J("Xen")) if form_truoc else _form("cham0", "vai mới")
        return await asyncio.gather(a, b)

    for form_truoc in (True, False):
        meta(B7, "cham0", tags="[]")
        asyncio.run(_xen(form_truoc))
        m, _ = doc(B7, "cham0")
        check(f"R4 form lưu xen với thêm tag ({'form trước' if form_truoc else 'tag trước'}): giữ cả vai mới lẫn tag",
              m.get("tags") == ["Xen"] and m.get("role") == "vai mới", m)
    _goc3 = main._write_md

    def _ghi_cham_hong(path, m, body):
        if Path(path).stem == "cham1":
            raise OSError("đĩa đầy")
        return _goc3(path, m, body)
    for i in range(3):
        meta(B7, f"cham{i}", tags=J("Lỗi"))
    main._write_md = _ghi_cham_hong
    resp, tre = asyncio.run(_do_tre(main.agent_tag_delete(brain=str(B7), tag="Lỗi")))
    j = json.loads(resp.body)
    check("R4 lỗi một phần trên worker vẫn báo đúng đã đổi và chưa đổi",
          resp.status_code == 500 and j["changed"] == ["cham0", "cham2"] and [f["slug"] for f in j["failed"]] == ["cham1"]
          and doc(B7, "cham1")[0]["tags"] == ["Lỗi"], j)
finally:
    main._write_md = _goc2

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
