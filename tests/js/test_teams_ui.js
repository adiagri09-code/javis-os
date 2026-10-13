// Nhóm chat team T1, nhiệm vụ 7: trang Nhóm (spec 2026-10-13-team-chat-design mục 16, wireframe docs/dev/team-chat-wireframes.md).
//
//     python tests/run.py --js teams_ui -v
//
// Hàm thuần của teams.js chạy dưới node: danh sách nhóm, tin có người gửi và trạng thái bằng chữ, hàng đợi đánh số đúng
// thứ tự chạy, khung soạn (@ có cấu trúc, Giao việc), cài đặt một cột. Cộng các chỗ nối: thanh bên, script, CSS, i18n.
"use strict";
const fs = require("fs");
const path = require("path");
const ROOT = path.join(__dirname, "..", "..");
const TM = require(path.join(ROOT, "dashboard", "teams.js"));
const vi = JSON.parse(fs.readFileSync(path.join(ROOT, "dashboard", "i18n", "vi.json"), "utf8"));
const en = JSON.parse(fs.readFileSync(path.join(ROOT, "dashboard", "i18n", "en.json"), "utf8"));
const consoleJs = fs.readFileSync(path.join(ROOT, "dashboard", "console.js"), "utf8");
const indexHtml = fs.readFileSync(path.join(ROOT, "dashboard", "index.html"), "utf8");
const css = fs.readFileSync(path.join(ROOT, "dashboard", "console.css"), "utf8");
const appJs = fs.readFileSync(path.join(ROOT, "dashboard", "app.js"), "latin1");
const teamsJs = fs.readFileSync(path.join(ROOT, "dashboard", "teams.js"), "utf8");

let fails = 0;
function check(name, cond, extra) {
  console.log((cond ? "ok   " : "FAIL ") + name + (cond || !extra ? "" : "  " + extra));
  if (!cond) fails++;
}

const members = [
  { agent_key: "ag_lan", slug: "lan", name: "Lan", role: "leader", status: "active", resonance_enabled: true, agent_status: "active" },
  { agent_key: "ag_minh", slug: "minh", name: "Minh <b>", role: "member", status: "active", resonance_enabled: false, agent_status: "active" },
];
const team = { team_id: "tm_1", name: "Ra mắt <i>", description: "", leader_key: "ag_lan", status: "active",
  caps: { mentions: 3, daily_turns: 100, task_turns: 12, task_steps: 8 }, members: members,
  counts: { running: 1, waiting: 2, blocked: 1 }, running: [{ id: "t_1", title: "Soạn kế hoạch" }], busy: {} };

// ───────────── danh sách nhóm ─────────────
let h = TM.teamListHtml([team, Object.assign({}, team, { team_id: "tm_2", name: "Nội dung", counts: { running: 0, waiting: 0, blocked: 0 } })], "tm_1");
check("danh sách: tên nhóm được escape", h.includes("Ra mắt &lt;i&gt;") && !h.includes("<i>"), h);
check("danh sách: nhóm đang mở được đánh dấu", /data-team="tm_1"[^>]*aria-current="true"/.test(h), h);
check("danh sách: số việc chờ anh bằng chữ", h.includes(vi["teams.waiting_owner"].replace("{n}", "1")), h);
check("danh sách rỗng: lời mời tạo nhóm", TM.teamListHtml([], "").includes(vi["teams.empty"]));

// ───────────── tin ─────────────
const ctx = { members: members, leaderKey: "ag_lan", taskTitles: { t_1: "Soạn kế hoạch" } };
h = TM.messageHtml({ id: 1, author_kind: "owner", content: "Giao <b>việc</b>", meta: { as_job: true, mentions: ["ag_minh"] } }, ctx);
check("tin chủ nhóm: nhãn Chủ nhóm, nội dung escape", h.includes(vi["teams.owner"]) && h.includes("&lt;b&gt;việc"), h);
h = TM.messageHtml({ id: 2, author_kind: "agent", author_ref: "ag_minh", content: "Xong", task_id: "t_1", step_id: "st_1",
  meta: { role: "work", status: "done", applied: true } }, ctx);
check("tin agent: tên, vai, nhãn việc bấm được, trạng thái bằng chữ", h.includes("Minh &lt;b&gt;") && h.includes(vi["teams.role.work"])
      && /data-task="t_1"/.test(h) && h.includes(vi["teams.status.done"]), h);
h = TM.messageHtml({ id: 3, author_kind: "agent", author_ref: "ag_lan", content: "Tổng hợp", task_id: "t_1",
  meta: { role: "synthesize", status: "done", applied: true, job_result: true } }, ctx);
check("bản tổng hợp cuối: nhãn Kết quả việc", h.includes(vi["teams.job_result"]), h);
for (const st of ["late_cancelled", "old_revision", "member_left", "leader_changed"]) {
  h = TM.messageHtml({ id: 4, author_kind: "agent", author_ref: "ag_minh", content: "x", task_id: "t_1",
    meta: { role: "work", status: st, applied: false } }, ctx);
  check("tin không áp dụng có nhãn bằng chữ: " + st, h.includes(vi["teams.status." + st]) && h.includes("tm-msg-late"), h);
}
h = TM.messageHtml({ id: 5, author_kind: "agent", author_ref: "ag_lan", content: "Nên làm",
  meta: { role: "leader_reply", status: "done", applied: true, proposal: { title: "Bảng <giá>", brief: "x" } } }, ctx);
check("thẻ đề xuất: tiêu đề escape, hai nút Tạo việc và Bỏ qua", h.includes("Bảng &lt;giá&gt;") && /data-accept="5"/.test(h)
      && h.includes(vi["teams.proposal_create"]) && h.includes(vi["teams.proposal_skip"]), h);
h = TM.messageHtml({ id: 6, author_kind: "agent", author_ref: "ag_lan", content: "x", meta: { role: "plan", notes: ["Lệnh 'fly' <x>"] } }, ctx);
check("ghi chú của host hiện dưới tin, escape", h.includes("Lệnh &#39;fly&#39; &lt;x&gt;"), h);
h = TM.messageHtml({ id: 7, author_kind: "owner", content: "Chốt giá 99k", meta: { decision: true } }, ctx);
check("tin đã ghim quyết định: có nhãn và nút bỏ ghim", h.includes(vi["teams.decision_pinned"]) && /data-decision="7"[^>]*data-on="0"/.test(h), h);
h = TM.messageHtml({ id: 8, author_kind: "agent", author_ref: "ag_cu", content: "x", meta: {} }, ctx);
check("tác giả đã rời nhóm vẫn hiện được (mã)", h.includes("ag_cu"), h);

// ───────────── hàng đợi ─────────────
const queue = { version: 7,
  running: [{ id: "t_1", title: "Soạn kế hoạch", team_rev: 1 }],
  waiting: [{ id: "t_3", title: "Bảng giá", team_prio: 1 }, { id: "t_2", title: "Ảnh <bìa>", team_prio: null }],
  blocked: [{ id: "t_4", title: "Video", block_kind: "failed", block_reason: "Lượt lỗi: hết giờ" },
            { id: "t_5", title: "Số liệu", block_kind: "cap_reached", block_reason: "Đã chạm trần lượt mỗi việc" }] };
h = TM.queueHtml(queue);
check("đang làm: nút Sửa yêu cầu và Huỷ", /data-amend="t_1"/.test(h) && /data-cancel="t_1"/.test(h), h);
check("hàng chờ đánh số đúng thứ tự chạy", h.indexOf("Bảng giá") < h.indexOf("Ảnh &lt;bìa&gt;") && h.includes(">1<") && h.includes(">2<"), h);
check("việc ưu tiên: dấu sao kèm chữ, nút Bỏ ưu tiên", /data-prio="t_3"[^>]*data-on="0"/.test(h) && h.includes(vi["teams.unprioritize"])
      && h.includes(vi["teams.prioritized"]), h);
check("việc thường: nút Ưu tiên có chữ", /data-prio="t_2"[^>]*data-on="1"/.test(h) && h.includes(vi["teams.prioritize"]), h);
check("bị chặn: lý do bằng chữ; lỗi thì Chạy lại bước; chạm trần thì Cho chạy tiếp", h.includes("Lượt lỗi: hết giờ")
      && /data-unblock="t_4"[^>]*data-action="retry"/.test(h) && /data-unblock="t_5"[^>]*data-action="resume"/.test(h), h);
h = TM.queueHtml({ version: 1, running: [], waiting: [], blocked: [{ id: "t_6", title: "Lặp", block_kind: "no_progress", block_reason: "x" }] });
check("không tiến triển: nút Chạy lại bước (không phải Cho chạy tiếp ra kết quả lặp)",
      /data-unblock="t_6"[^>]*data-action="retry"/.test(h), h);
check("đổi công tắc Giao việc thì gửi lại là tin MỚI (không trả nhầm tin cũ khác loại)",
      /tm-asjob[\s\S]{0,200}S\.pending = null/.test(teamsJs));
check("mọi lớp đặt display có luật [hidden] riêng", [".tm-job", ".tm-sug-item", ".tm-radio", ".tm-check", ".tm-ava"]
  .every(function (c) { return css.includes(c + "[hidden]"); }));
check("hàng rỗng: có chữ", TM.queueHtml({ version: 0, running: [], waiting: [], blocked: [] }).includes(vi["teams.queue_empty"]));

// ───────────── khung soạn ─────────────
const sug = TM.mentionMatches(members, "mi", []);
check("@ gợi ý theo tên hay slug, chỉ thành viên đang hoạt động", sug.length === 1 && sug[0].agent_key === "ag_minh");
check("@ đã chọn thì không gợi ý lại", TM.mentionMatches(members, "", ["ag_minh"]).every(function (m) { return m.agent_key !== "ag_minh"; }));
let hint = TM.composerHint({ mentions: ["ag_minh"], asJob: true, cap: 3, waiting: 2, members: members });
check("Giao việc: nói rõ tạo một việc, giao cho ai, vị trí trong hàng", hint.text.includes("Minh") && hint.text.includes("3") && hint.ok, hint.text);
hint = TM.composerHint({ mentions: ["a", "b", "c", "d"], asJob: false, cap: 3, waiting: 0, members: members });
check("quá trần @: tắt nút Gửi, nói rõ trần", !hint.ok && hint.text.includes("3"), hint.text);
hint = TM.composerHint({ mentions: [], asJob: true, cap: 3, waiting: 0, members: members, leaderKey: "ag_lan" });
check("Giao việc không @: giao chung cho trưởng nhóm", hint.text.includes("Lan") && hint.ok, hint.text);
check("mã tin client mới mỗi lần, dạng chuỗi", TM.newClientId() !== TM.newClientId() && typeof TM.newClientId() === "string");

// ───────────── cài đặt nhóm ─────────────
h = TM.membersHtml(team, [{ slug: "hoa", name: "Hoa", agent_key: null, status: "unregistered" }, { slug: "lan", name: "Lan" }]);
check("thành viên: vai bằng chữ, trạng thái Cộng hưởng bằng chữ", h.includes(vi["teams.leader"]) && h.includes(vi["teams.member"])
      && h.includes(vi["resonance.t0_state_on"]) && h.includes(vi["resonance.t0_state_off"]), h);
check("thành viên: nút Đặt làm trưởng nhóm, Bỏ khỏi nhóm", /data-leader="ag_minh"/.test(h) && /data-remove="ag_minh"/.test(h), h);
check("thêm thành viên: chỉ agent chưa trong nhóm", h.includes('value="hoa"') && !h.includes('value="lan"'), h);
h = TM.settingsFormHtml(team);
check("cài đặt một cột, nút Lưu ở cuối", h.lastIndexOf("tm-save") > h.lastIndexOf("tm-cap") && !h.includes("<table"), h);
check("ba trạng thái nhóm bằng chữ", h.includes(vi["teams.status_active"]) && h.includes(vi["teams.status_paused"])
      && h.includes(vi["teams.status_archived"]), h);
h = TM.turnsHtml([{ agent_key: "ag_lan", role: "plan", status: "ok", created_at: Date.now() / 1000, tokens_in: 10, tokens_out: 2 },
                  { agent_key: "ag_minh", role: "work", status: "refunded", created_at: Date.now() / 1000 }], team);
check("lượt: lượt hoàn không tính, theo agent và vai", h.includes(vi["teams.turns_today"].replace("{n}", "1").replace("{cap}", "100"))
      && h.includes("Lan") && h.includes(vi["teams.role.plan"]), h);
h = TM.createFormHtml([{ slug: "lan", name: "Lan" }, { slug: "minh", name: "M<x>" }]);
check("tạo nhóm: tên, mô tả, chọn thành viên, trưởng nhóm, nút Tạo ở cuối", h.includes('name="tm-name"') && h.includes("M&lt;x&gt;")
      && h.includes('name="tm-leader"') && h.lastIndexOf("tm-create-save") > h.lastIndexOf('name="tm-leader"'), h);
check("băng rôn nhóm chưa có trưởng nhóm", TM.bannersHtml(Object.assign({}, team, { leader_key: null })).includes(vi["teams.no_leader"]));
check("băng rôn tạm dừng", TM.bannersHtml(Object.assign({}, team, { status: "paused" })).includes(vi["teams.paused_banner"]));
check("băng rôn thành viên bận ở nhóm khác", TM.bannersHtml(Object.assign({}, team, { busy: { ag_minh: "tm_9" } }), { tm_9: "Nhóm Y" })
      .includes("Nhóm Y"));

// ───────────── chỗ nối ─────────────
const rail = (consoleJs.match(/const RAIL_ITEMS = \[\s*([\s\S]*?)\]\.map/) || [])[1] || "";
check("thanh bên có mục teams ngay sau workspace", /"workspace", "teams"/.test(rail), rail);
check("nhóm Năng lực chứa teams", /ids: \["workspace", "teams"/.test(consoleJs));
check("icon và tiêu đề trang teams", /teams: "users"/.test(consoleJs) && consoleJs.includes('"teams"') && /id === "teams"/.test(consoleJs));
check("index.html nạp teams.js", /<script src="\/static\/teams\.js\?v=\d+"><\/script>/.test(indexHtml));
check("app.js chuyển gói team_message, team_state thành sự kiện trang", appJs.includes('"team_message"') && appJs.includes("javis:team-event"));
check("lớp flex của trang có luật [hidden]", /\.tm-page\[hidden\]\{display:none\}|\.tm-[a-z-]+\[hidden\]\s*\{\s*display:\s*none/.test(css)
      && css.includes(".tm-"), "");
check("nút .ws-btn bị hidden thật sự ẩn (smoke: nút Trang sau vẫn hiện)", /\.tm-page \.ws-btn\[hidden\]\s*\{\s*display:\s*none/.test(css));
check("chưa mở nhóm: không chừa cột cài đặt trống", /\.tm-page\[data-side="0"\]\s*\{\s*grid-template-columns/.test(css)
      && teamsJs.includes('setAttribute("data-side"'));
check("màn hẹp: đầu khung chat xuống hai hàng, tên nhóm không bị ép (smoke 375px)",
      /\.tm-chat-head\s*\{\s*flex-wrap:\s*wrap/.test(css) && /\.tm-chat-head \.tm-title\s*\{\s*flex:\s*1 1 calc\(100% - 60px\)/.test(css));
check("ngăn kéo cài đặt có nền đặc (smoke 375px: nhìn xuyên thấy tin)",
      /\.tm-side \{ position: fixed;[^}]*background: var\(--bg\)/.test(css));
check("màn hẹp: nút tối thiểu 44px", /@media[^{]*max-width[^{]*\{[\s\S]*\.tm-[\s\S]*min-height:\s*44px/.test(css));
const keys = Object.keys(vi).filter(function (k) { return k.indexOf("teams.") === 0 || k === "page.teams.label"; });
check("đủ khoá tiếng Anh cho mọi chữ của trang", keys.length >= 40 && keys.every(function (k) { return typeof en[k] === "string" && en[k]; }),
      keys.filter(function (k) { return !en[k]; }).join(","));
check("en.json không có chữ Việt ở khoá teams", keys.every(function (k) { return !/[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]/i.test(en[k]); }));
check("không em dash trong teams.js và chuỗi mới", teamsJs.indexOf(String.fromCharCode(0x2014)) < 0
      && keys.every(function (k) { return (vi[k] + en[k]).indexOf(String.fromCharCode(0x2014)) < 0; }));
// Chỉ khoá viết trọn (`tw("teams.x")` hay `tw("teams.x", {...})`); khoá ghép động kiểm riêng ở dưới.
const used = Array.from(new Set((teamsJs.match(/tw\("(teams\.[a-z0-9_.]+)"[,)]/g) || []).map(function (m) { return m.slice(4, -2); })));
const dynamic = ["teams.status_active", "teams.status_paused", "teams.status_archived", "teams.tab_members", "teams.tab_jobs",
  "teams.tab_turns", "teams.tab_settings", "teams.cap.task_turns", "teams.cap.task_steps", "teams.cap.daily_turns", "teams.cap.mentions"]
  .concat(["failed", "interrupted", "no_leader", "assignee_removed", "no_progress", "cap_reached", "agent_busy_long", "waiting_user"]
    .map(function (k) { return "teams.block." + k; }))
  .concat(["done", "late_cancelled", "late", "old_revision", "member_left", "leader_changed"].map(function (k) { return "teams.status." + k; }));
check("khoá ghép động đều có trong vi.json", dynamic.every(function (k) { return vi[k]; }), dynamic.filter(function (k) { return !vi[k]; }).join(","));
check("mọi khoá teams.js dùng đều có trong vi.json", used.length > 20 && used.every(function (k) { return vi[k]; }),
      used.filter(function (k) { return !vi[k]; }).join(","));

process.exit(fails ? 1 : 0);
