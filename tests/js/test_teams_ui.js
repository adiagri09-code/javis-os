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

// ───────────── T2: sáu reaction, lý do, góp ý (spec mục 14) ─────────────
check("đúng sáu reaction theo thứ tự, giữ nguyên giá trị", TM.REACTIONS.map(function (r) { return r.value; }).join(",") ===
      "like,love,haha,wow,sad,angry");
check("sáu emoji gốc 👍 ❤️ 😂 😮 😢 😡", TM.REACTIONS.map(function (r) { return r.emoji; }).join("") ===
      "\u{1F44D}❤️\u{1F602}\u{1F62E}\u{1F622}\u{1F621}");
const rkeys = TM.REACTIONS.map(function (r) { return r.key; }).concat(["on_point", "wrong_facts", "missing", "too_long",
  "unclear", "off_topic"].map(function (k) { return "teams.reason." + k; }));
check("nhãn sáu reaction và sáu lý do có ở cả vi và en", rkeys.every(function (k) { return vi[k] && en[k]; }),
      rkeys.filter(function (k) { return !vi[k] || !en[k]; }).join(","));
check("chọn lại cái đang chọn là bỏ; chọn cái khác là đổi", TM.nextReaction("sad", "sad") === "none"
      && TM.nextReaction("sad", "wow") === "wow" && TM.nextReaction(undefined, "like") === "like");
const am = { id: 7, author_kind: "agent", author_ref: "ag_lan", content: "Chuyện buồn", meta: { status: "done" } };
let mh = TM.messageHtml(am, { members: members });
check("tin của trợ lý có nút thả cảm xúc, chưa mở bộ chọn", mh.includes('class="tm-react-btn"') && mh.includes('data-react-open="7"')
      && !mh.includes("tm-react-panel"), mh);
check("tin của chủ không có nút thả cảm xúc", !TM.messageHtml({ id: 8, author_kind: "owner", content: "x", meta: {} },
  { members: members }).includes("tm-react-btn"));
mh = TM.messageHtml(am, { members: members, picker: 7 });
check("mở bộ chọn ngay tại tin: sáu nút, lý do, ô góp ý tối đa 500", (mh.match(/class="tm-react-pick"/g) || []).length === 6
      && (mh.match(/name="tm-reason"/g) || []).length === 6 && mh.includes('maxlength="500"') && mh.includes(vi["teams.react_note"]), mh);
const withR = Object.assign({}, am, { reaction: { value: "sad", reasons: ["too_long"], comment: "Gọn <b>hơn</b>" } });
mh = TM.messageHtml(withR, { members: members, picker: 7 });
check("emoji đã chọn hiện dưới tin, bấm để đổi", /class="tm-react-chip" data-react-open="7"/.test(mh) && mh.includes("\u{1F622}")
      && mh.includes(vi["teams.react.sad"]), mh);
check("bộ chọn đánh dấu emoji đang chọn và lý do đã chọn", /data-react="sad"[^>]*aria-pressed="true"/.test(mh)
      && /value="too_long" checked/.test(mh), mh);
check("góp ý được escape", mh.includes("Gọn &lt;b&gt;hơn&lt;/b&gt;") && !mh.includes("<b>hơn"), mh);
const draft = TM.reactionPickerHtml(am, { value: "like", reasons: [], comment: "" }, { reasons: ["missing"], comment: "đang gõ" });
check("bản nháp đang soạn giữ qua lần vẽ lại", /value="missing" checked/.test(draft) && draft.includes("đang gõ")
      && /data-react="like"[^>]*aria-pressed="true"/.test(draft), draft);
check("chỉ có lý do/góp ý (bỏ emoji): chip vẫn hiện", TM.reactionChipHtml(am, { value: null, reasons: ["missing"], comment: "" })
      .includes(vi["teams.react_reasons_n"].replace("{n}", "1")));
check("không có phản hồi: không chip", TM.reactionChipHtml(am, null) === "");
check("thả cảm xúc gửi nonce mới mỗi lần, không mở lượt", /\/reaction"\)[\s\S]{0,120}nonce: newClientId\(\)/.test(teamsJs));
check("điện thoại: nhấn giữ tin mở bộ chọn, có ngưỡng rung tay", teamsJs.includes('"pointerdown"') && /> 10/.test(teamsJs));
check("gói WS không mang phản hồi thì giữ phản hồi đang có", teamsJs.includes('!("reaction" in nm)'));
check("CSS: nút mặt cười hiện khi rê chuột, luôn hiện trên máy chạm, tắt menu nhấn giữ của máy",
      /\.tm-msg-agent:hover \.tm-react-btn/.test(css)
      && /@media \(hover: none\) \{ \.tm-react-btn \{ opacity: 1; \} \.tm-msg-agent \{ -webkit-touch-callout: none; \} \}/.test(css));
// Review T2 #4 tới #6
check("đang soạn góp ý thì vẽ lại giữ con trỏ, chỗ cuộn, không kéo xuống cuối",
      /typing = S\.picker !== null && act && act\.classList/.test(teamsJs) && /ta\.setSelectionRange\(typing\.start, typing\.end\)/.test(teamsJs)
      && /\(stick \|\| atEnd\) && S\.picker === null/.test(teamsJs));
check("mở bộ chọn đưa focus vào emoji đầu; đóng trả focus về nút mặt cười",
      /S\.focusPicker = true/.test(teamsJs) && /\.tm-react-panel \.tm-react-pick"\);\s*if \(first\) first\.focus\(\)/.test(teamsJs)
      && /\.tm-react-btn\[data-react-open="' \+ S\.focusBack/.test(teamsJs));
check("nhấn giữ chỉ cho chạm và bút, không cho chuột; chặn menu ngữ cảnh của lần giữ đó",
      teamsJs.includes('if (e.pointerType === "mouse") return;') && /"contextmenu"[\s\S]{0,80}if \(held\) \{ e\.preventDefault\(\)/.test(teamsJs));
check("CSS: điện thoại hàng ngang lớn, vùng chạm >= 44px", /\.tm-react-pick \{ flex: 1 1 0; min-width: 44px; min-height: 48px/.test(css));
check("CSS 375px: sáu nút 44px lọt bề ngang (khe 4px, đệm 6px; smoke T2 thấy 😡 tràn mép)",
      /\.tm-react-panel \{ padding: 8px 6px; \}/.test(css) && /\.tm-react-row \{ flex-wrap: nowrap; justify-content: space-between; gap: 4px; \}/.test(css));
check("CSS: bảng chọn display:flex có luật [hidden] riêng", /\.tm-react-panel\[hidden\] \{ display: none; \}/.test(css));

// ───────────── T3: hộp cấp Toàn quyền, công tắc Nhóm quản lý (spec mục 13) ─────────────
const limitedTeam = Object.assign({}, team, { authority: { authority: null,
  effective_caps: { task_turns: 12, task_steps: 8, help_depth: 2, daily_turns: 100 }, fixed_limits: {} } });
let ah = TM.authorityHtml(limitedTeam);
check("Quyền giới hạn: nói rõ trưởng nhóm chỉ đề xuất, có nút Bật, không có nút Thu hồi",
      ah.includes(vi["teams.auth.off"]) && ah.includes(vi["teams.auth.grant"]) && !ah.includes("tm-auth-revoke"), ah);
check("hộp cấp quyền đủ dòng của 13.1: phạm vi, agent do nhóm quản lý, provider, thanh toán, trần, ngắt việc, trần không bỏ được",
      ah.includes(vi["teams.auth.scope"]) && ah.includes(vi["teams.auth.managed_none"]) && ah.includes(vi["teams.auth.providers"])
      && ah.includes(vi["teams.auth.billing"]) && (ah.match(/name="tm-auth-ceil-[a-z_]+" value/g) || []).length === 4
      && ah.includes(vi["teams.auth.interrupt"]) && ["teams.auth.fixed_server", "teams.auth.fixed_provider",
        "teams.auth.fixed_account", "teams.auth.fixed_technical"].every(function (k) { return ah.includes(vi[k]); }), ah);
const fullTeam = Object.assign({}, team, { members: [Object.assign({}, members[0]), Object.assign({}, members[1], { managed: true })],
  authority: { authority: { leader_key: "ag_lan", granted_at: 1791900000,
    grant: { caps: { task_turns: { unlimited: true } }, ceilings: { task_turns: { unlimited: true }, daily_turns: 150 },
      providers_unlimited: ["aux"], can_interrupt: true, billing: "api" } },
    effective_caps: { task_turns: null, task_steps: 8, help_depth: 2, daily_turns: 100 } } });
ah = TM.authorityHtml(fullTeam);
check("Toàn quyền bật: trạng thái nêu trưởng nhóm, có Lưu và Thu hồi", ah.includes("tm-auth-on") && ah.includes("Lan")
      && ah.includes(vi["teams.auth.update"]) && ah.includes("tm-auth-revoke"), ah);
check("Không giới hạn hiện bằng chữ, ô số tắt, ô tích bật (null + cờ, không phải số lớn)",
      ah.includes(vi["teams.cap.task_turns"] + ": " + vi["teams.auth.unlimited"])
      && /name="tm-auth-cap-task_turns" value="" disabled/.test(ah) && /name="tm-auth-cap-task_turns-unl" checked/.test(ah), ah);
check("trần trần số hiện đúng, provider và quyền ngắt việc đã chọn được đánh dấu",
      /name="tm-auth-ceil-daily_turns" value="150"/.test(ah) && /value="aux" checked/.test(ah)
      && /name="tm-auth-interrupt" checked/.test(ah) && /value="api" checked/.test(ah), ah);
check("agent do nhóm quản lý được liệt kê", ah.includes(vi["teams.auth.managed"].replace("{names}", "Minh &lt;b&gt;")), ah);
check("chưa có trưởng nhóm: chỉ nhắc chọn trưởng nhóm", TM.authorityHtml(Object.assign({}, limitedTeam, { leader_key: null }))
      .includes(vi["teams.auth.need_leader"]));
const mh3 = TM.membersHtml(fullTeam, []);
check("tab Thành viên có công tắc Nhóm quản lý theo trạng thái", (mh3.match(/class="tm-managed-toggle"/g) || []).length === 2
      && /data-key="ag_minh" checked/.test(mh3) && mh3.includes(vi["teams.managed"]), mh3);
check("review T3 #6: Toàn quyền bật thì form trần báo trần lấy theo mục Toàn quyền; giới hạn thì không",
      TM.settingsFormHtml(fullTeam).includes(vi["teams.caps_full_note"]) && !TM.settingsFormHtml(limitedTeam).includes(vi["teams.caps_full_note"]));
// ───────────── T4: tìm trong nhóm, nhảy tới tin cũ ─────────────
const hits = [{ id: 41, ts: 100.5, author_kind: "agent", author_ref: "ag_lan", snippet: "Kế hoạch <script>" },
  { id: 12, ts: 50, author_kind: "owner", author_ref: "", snippet: "Ra mắt" }];
const sh = TM.searchResultsHtml(hits, members, "ke hoach");
check("kết quả tìm: đếm, người gửi, đoạn trích escape, nút nhảy kèm id và ts",
      sh.includes(vi["teams.search_results"].replace("{n}", "2")) && sh.includes("Lan") && sh.includes("Kế hoạch &lt;script&gt;")
      && !sh.includes("<script>") && /data-jump="41" data-ts="100.5"/.test(sh), sh);
check("không có kết quả: nói rõ câu đã tìm, escape", TM.searchResultsHtml([], members, "<b>x").includes("&lt;b&gt;x")
      && TM.searchResultsHtml(null, members, "") === "");
check("tin được nhảy tới được tô sáng", TM.messageHtml(am, { members: members, jumped: 7 }).includes("tm-msg-hit")
      && !TM.messageHtml(am, { members: members, jumped: 8 }).includes("tm-msg-hit"));
check("nhảy tới tin: tải trang kết thúc ở đúng tin đó, có nút về tin mới nhất",
      /before_ts=" \+ q\(ts\) \+ "&before_id=" \+ q\(Number\(mid\) \+ 1\)/.test(teamsJs) && teamsJs.includes("tm-jump-back"));
check("đang xem tin cũ: tin mới tới không chèn vào giữa khúc cũ",
      teamsJs.includes("else if (S.jumped === null || S.jumped === undefined) S.msgs.push(nm);"));
check("CSS: lớp flex mới của tìm có [hidden], vùng chạm 44px trên điện thoại",
      /\.tm-search\[hidden\]/.test(css) && /\.tm-search-row\[hidden\]/.test(css) && /\.tm-jumped\[hidden\]/.test(css)
      && /\.tm-search-btn, \.tm-search-go, \.tm-search-input, \.tm-search-hit, \.tm-jump-back \{ min-height: 44px; \}/.test(css));
// Review T4
check("review #1: tải lại trang tin mới nhất (gửi tin, lọc việc) thì thoát chế độ xem tin cũ",
      /function loadMsgs\(older\) \{[\s\S]{0,200}if \(!older\) S\.jumped = null;/.test(teamsJs));
check("review #5: mở form tạo nhóm thì đóng ô tìm", /tm-new"\)\) \{[\s\S]{0,160}S\.searchOpen = false/.test(teamsJs));
check("review #6: băng xem tin cũ dính ở đầu khung", /\.tm-jumped \{[^}]*position: sticky; top: 0;/.test(css));
check("review #7: nút tìm đủ 44px bề ngang trên điện thoại", /\.tm-back, \.tm-close, \.tm-search-btn \{ min-width: 44px;/.test(css));
check("review #8: kết quả tìm, nhảy tới về muộn sau khi đổi nhóm thì bỏ",
      /var forTeam = S\.activeId;[\s\S]{0,200}if \(S\.activeId !== forTeam\) return;/.test(teamsJs)
      && (teamsJs.match(/if \(S\.activeId !== forTeam\) return;/g) || []).length >= 2);
const authKeys = ["teams.cap.help_depth", "teams.auth.provider_aux", "teams.auth.provider_claude", "teams.auth.billing_sub",
  "teams.auth.billing_api", "teams.auth.fixed_server", "teams.auth.fixed_provider", "teams.auth.fixed_account",
  "teams.auth.fixed_technical"];
check("khoá Toàn quyền tra qua bảng có ở cả vi và en", authKeys.every(function (k) { return vi[k] && en[k]; }));
check("CSS: lớp flex mới của Toàn quyền có luật [hidden] riêng", /\.tm-auth\[hidden\]/.test(css) && /\.tm-auth-pair\[hidden\]/.test(css)
      && /\.tm-unl\[hidden\]/.test(css));

process.exit(fails ? 1 : 0);
