// 0.142.0: chat nhóm không im lặng (trạng thái từng lượt, Thử lại) và @ đúng người theo agent_key kể cả trùng tên.
//
//     python tests/run.py --js team_chat_0142 -v
"use strict";
const fs = require("fs");
const path = require("path");
const ROOT = path.join(__dirname, "..", "..");
const TM = require(path.join(ROOT, "dashboard", "teams.js"));
const vi = JSON.parse(fs.readFileSync(path.join(ROOT, "dashboard", "i18n", "vi.json"), "utf8"));
const en = JSON.parse(fs.readFileSync(path.join(ROOT, "dashboard", "i18n", "en.json"), "utf8"));
const appJs = fs.readFileSync(path.join(ROOT, "dashboard", "app.js"), "latin1");
const css = fs.readFileSync(path.join(ROOT, "dashboard", "console.css"), "utf8");

let fails = 0;
function check(name, cond, extra) {
  console.log((cond ? "ok   " : "FAIL ") + name + (cond || !extra ? "" : "  " + extra));
  if (!cond) fails++;
}

// ───────────── @ theo agent_key, kể cả trùng tên ─────────────
const mem = [
  { agent_key: "ag_one", slug: "one", name: "One", status: "active" },
  { agent_key: "ag_one2", slug: "one-2", name: "One", status: "active" },
  { agent_key: "ag_lan", slug: "lan", name: "Lan", status: "active" },
];
let sc = TM.mentionScan("@One giúp với", mem, []);
check("trùng tên, gõ tay không chọn: không gọi ai, báo mơ hồ", sc.keys.length === 0 && sc.ambiguous.join() === "One",
  JSON.stringify(sc));
sc = TM.mentionScan("@One giúp với", mem, ["ag_one2"]);
check("trùng tên, đã chọn trong gợi ý: gọi đúng agent_key đã chọn", sc.keys.join() === "ag_one2" && !sc.ambiguous.length,
  JSON.stringify(sc));
sc = TM.mentionScan("@One và @One cùng xem", mem, ["ag_one2", "ag_one"]);
check("hai @ trùng tên, chọn cả hai: đủ hai người theo thứ tự chọn", sc.keys.join() === "ag_one2,ag_one", JSON.stringify(sc));
sc = TM.mentionScan("@one-2 xem", mem, []);
check("gõ slug riêng: không mơ hồ", sc.keys.join() === "ag_one2" && !sc.ambiguous.length, JSON.stringify(sc));
sc = TM.mentionScan("@Lan ơi", mem, []);
check("tên không trùng: như cũ", sc.keys.join() === "ag_lan");
const hint = TM.composerHint({ mentions: [], ambiguous: ["One"], cap: 3 });
check("khung soạn chặn gửi khi @ mơ hồ, nói rõ tên", hint.ok === false && hint.text.includes("One"), JSON.stringify(hint));

// ───────────── trạng thái lượt trả lời ─────────────
const team = [{ agent_key: "ag_lan", slug: "lan", name: "Lan", status: "active" },
  { agent_key: "ag_minh", slug: "minh", name: "Minh <b>", status: "active" }];
const ctx = { members: team, authors: {}, retrying: {} };
const msg = { id: 7, author_kind: "owner", content: "Chào", meta: {}, replies: [
  { agent_key: "ag_lan", status: "queued", reason: "" },
  { agent_key: "ag_minh", status: "error", reason: "engine_unavailable", detail: "model việc nền <x>" }] };
let h = TM.messageHtml(msg, ctx);
check("tin của chủ hiện trạng thái từng người: đang chờ", h.includes("tm-reply-queued") && h.includes(vi["teams.reply.queued"]), h);
check("lỗi hiện lý do bằng lời thường và chi tiết đã escape", h.includes(vi["teams.reply.why.engine_unavailable"])
  && h.includes("model việc nền &lt;x&gt;") && h.includes("Minh &lt;b&gt;") && !h.includes("<x>"), h);
check("lỗi có nút Thử lại gắn đúng tin và agent_key", /data-retry="7" data-retry-key="ag_minh"/.test(h), h);
h = TM.replyStatusHtml({ id: 7, replies: [{ agent_key: "ag_lan", status: "running", reason: "answering" }] }, ctx);
check("đang trả lời", h.includes("tm-reply-answering") && h.includes(vi["teams.reply.answering"]), h);
h = TM.replyStatusHtml({ id: 7, replies: [{ agent_key: "ag_lan", status: "done", result_msg_id: 9 }] }, ctx);
check("đã xong thì không thêm dòng (câu trả lời nằm ngay dưới)", h === "", h);
h = TM.replyStatusHtml({ id: 7, replies: [{ agent_key: "ag_lan", status: "error", reason: "member_left" }] }, ctx);
check("trợ lý đã rời: không có Thử lại", h.includes(vi["teams.reply.why.member_left"]) && !h.includes("data-retry"), h);
h = TM.replyStatusHtml({ id: 7, replies: [{ agent_key: "ag_lan", status: "error", reason: "restart" }] },
  Object.assign({}, ctx, { retrying: { "7|ag_lan": true } }));
check("đang gửi Thử lại: nút khoá, chữ đổi", /data-retry-key="ag_lan" disabled/.test(h) && h.includes(vi["teams.reply.retrying"]), h);
h = TM.replyStatusHtml({ id: 7, replies: [{ agent_key: "ag_lan", status: "error", reason: "lạ" }] }, ctx);
check("lý do lạ: Không rõ lý do", h.includes(vi["teams.reply.why.unknown"]), h);
check("tin của trợ lý không vẽ trạng thái lượt", !TM.messageHtml({ id: 8, author_kind: "agent", author_ref: "ag_lan",
  content: "x", meta: {}, replies: msg.replies }, ctx).includes("tm-replies"));

// ───────────── nối dây ─────────────
check("app.js chuyển gói team_replies cho trang Nhóm", /data\.type === "team_replies"/.test(appJs));
check("chữ của dòng trạng thái tối thiểu 16px, nút Thử lại cao 44px", /\.tm-reply \{[^}]*font-size: 16px/.test(css)
  && /\.tm-reply-retry \{[^}]*min-height: 44px/.test(css));
const keys = Object.keys(vi).filter(function (k) { return k.indexOf("teams.reply.") === 0; });
check("khoá teams.reply.* có đủ hai thứ tiếng", keys.length >= 14 && keys.every(function (k) { return en[k]; }));

console.log(fails ? "\nĐỎ " + fails + " mục" : "\nTất cả xanh.");
process.exit(fails ? 1 : 0);
