// T0 nhóm chat team (spec 2026-10-13-team-chat-design mục 10): công tắc Cộng hưởng trên từng dòng trợ lý.
//
//     python tests/run.py --js team_t0_toggle -v
//
// Hàm thuần của resonance-agent.js chạy dưới node: trạng thái bằng chữ, công tắc trên dòng, câu hỏi lại khi tắt.
"use strict";
const fs = require("fs");
const path = require("path");
const ROOT = path.join(__dirname, "..", "..");
const RA = require(path.join(ROOT, "dashboard", "resonance-agent.js"));
const vi = JSON.parse(fs.readFileSync(path.join(ROOT, "dashboard", "i18n", "vi.json"), "utf8"));
const en = JSON.parse(fs.readFileSync(path.join(ROOT, "dashboard", "i18n", "en.json"), "utf8"));

let fails = 0;
function check(name, cond, extra) {
  console.log((cond ? "ok   " : "FAIL ") + name + (cond || !extra ? "" : "  " + extra));
  if (!cond) fails++;
}

const on = { slug: "viet-bai", name: "Viết <b>bài</b>", agent_key: "ag_1", enabled: true, status: "active", goals_open: 2 };
const off = Object.assign({}, on, { enabled: false, goals_open: 0 });

let h = RA.rowToggleHtml(on, {});
check("bật: chữ Bật và ô đã chọn", h.includes(vi["resonance.t0_state_on"]) && /ws-rs-toggle"[^>]*checked/.test(h), h);
h = RA.rowToggleHtml(off, {});
check("tắt: chữ Tắt, ô chưa chọn", h.includes(vi["resonance.t0_state_off"]) && !/checked/.test(h), h);
h = RA.rowToggleHtml({ slug: "moi", status: "unregistered", enabled: false }, {});
check("chưa đăng ký coi như Tắt", h.includes(vi["resonance.t0_state_off"]), h);
h = RA.rowToggleHtml(Object.assign({}, on, { status: "missing" }), {});
check("missing: chữ Cần xác nhận, không có ô bật, có nút mở bảng", h.includes(vi["resonance.t0_state_missing"])
      && !h.includes("ws-rs-toggle") && h.includes("ws-rs-confirm"), h);
h = RA.rowToggleHtml(Object.assign({}, on, { status: "retired" }), {});
check("retired: chữ Đã nghỉ, không có ô bật", h.includes(vi["resonance.t0_state_retired"]) && !h.includes("ws-rs-toggle"), h);
h = RA.rowToggleHtml(on, { saving: true });
check("đang lưu: ô bị khoá, chữ Đang lưu", /ws-rs-toggle"[^>]*disabled/.test(h) && h.includes(vi["resonance.t0_saving"]), h);
check("không có dữ liệu: không vẽ công tắc", RA.rowToggleHtml(undefined, {}) === "");
check("nhãn aria và title không chèn HTML", !RA.rowToggleHtml(on, {}).includes("<b>"));
check("trạng thái bằng chữ, không chỉ màu", RA.stateKey(on) === "resonance.t0_state_on"
      && RA.stateKey(off) === "resonance.t0_state_off" && RA.stateKey({ status: "missing" }) === "resonance.t0_state_missing");
check("tắt khi có mục tiêu mở: hỏi kèm số mục tiêu", RA.offConfirmText(on).includes("2"), RA.offConfirmText(on));
check("tắt khi không có mục tiêu: không hỏi", RA.offConfirmText(off) === "");
check("bảng bên phải không còn công tắc riêng", !RA.panelHtml(on, "ready", []).includes("rsa-toggle")
      && RA.panelHtml(on, "ready", []).includes(vi["resonance.t0_state_on"])
      && RA.panelHtml(on, "ready", []).includes(vi["resonance.t0_where"]));
const st = RA.settingsHtml({ agents: [on, off, Object.assign({}, on, { slug: "mat", status: "missing" })] }, []);
check("trang Cài đặt: chỉ tóm tắt và nút sang trang Cộng sự, không còn công tắc", !st.includes("rsa-set-toggle")
      && st.includes("rsa-goto-ws") && st.includes(vi["resonance.t0_settings_manage"])
      && st.includes(vi["resonance.t0_settings_summary"].replace("{n}", "1")), st);

const keys = Object.keys(vi).filter(function (k) { return k.indexOf("resonance.t0_") === 0; });
check("đủ khoá tiếng Anh", keys.length >= 11 && keys.every(function (k) { return typeof en[k] === "string" && en[k]; }),
      keys.filter(function (k) { return !en[k]; }).join(","));
check("không em dash trong chuỗi mới", keys.every(function (k) { return !/—/.test(vi[k] + en[k]); }));

process.exit(fails ? 1 : 0);
