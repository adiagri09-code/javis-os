/* Trang Nhóm: nhóm chat team (T1, Quyền giới hạn).

   Thiết kế: docs/superpowers/specs/2026-10-13-team-chat-design.md mục 16; wireframe docs/dev/team-chat-wireframes.md.
   Ba phần: danh sách nhóm (trái), khung chat (giữa), cài đặt nhóm (phải; ngăn kéo dưới 1060px). Màn hẹp: danh sách là
   trang đầu, chạm một nhóm mở khung chat toàn màn, cài đặt là trang trượt lên.

   Gửi tin bằng POST /teams/{id}/messages kèm `client_msg_id`: rớt mạng thì gửi lại ĐÚNG mã cũ, server trả tin cũ, không
   thêm lượt hay việc. Câu trả lời và trạng thái về qua WebSocket chung (app.js đổi gói `team_message` / `team_state`
   thành sự kiện `javis:team-event`).

   @ là danh sách có cấu trúc: chỉ người chọn từ gợi ý mới được gọi; gõ tay "@abc" chỉ là chữ.

   Các hàm *Html, mentionMatches, composerHint thuần (không DOM, không mạng) để test chạy dưới node. */
(function () {
  "use strict";

  function tw(khoa, bien) {
    if (typeof window !== "undefined" && window.t) return window.t(khoa, bien);
    try {
      var s = require("./i18n/vi.json")[khoa] || khoa;
      return String(s).replace(/\{(\w+)\}/g, function (m, ten) {
        return (bien && bien[ten] != null) ? String(bien[ten]) : m;
      });
    } catch (e) { return khoa; }
  }

  function esc(t) {
    return String(t == null ? "" : t)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  // Icon lấy từ bộ Lucide của dashboard; chạy trong Node (test) thì không có, trả chuỗi rỗng.
  var ic = function (n, o) { return (typeof window !== "undefined" && window.ic) ? window.ic(n, o) : ""; };

  var ROLE_KEY = { leader_reply: "teams.role.reply", member_reply: "teams.role.reply", plan: "teams.role.plan",
    work: "teams.role.work", help: "teams.role.help", synthesize: "teams.role.synthesize" };
  // Khoá viết TRỌN (không ghép chuỗi) để bộ kiểm i18n đọc được từng khoá đang dùng.
  var STATUS_KEY = { done: "teams.status.done", late_cancelled: "teams.status.late_cancelled", late: "teams.status.late",
    old_revision: "teams.status.old_revision", member_left: "teams.status.member_left", leader_changed: "teams.status.leader_changed" };
  var TEAM_STATUS_KEY = { active: "teams.status_active", paused: "teams.status_paused", archived: "teams.status_archived" };
  var BLOCK_KEY = { failed: "teams.block.failed", interrupted: "teams.block.interrupted", no_leader: "teams.block.no_leader",
    assignee_removed: "teams.block.assignee_removed", no_progress: "teams.block.no_progress", cap_reached: "teams.block.cap_reached",
    agent_busy_long: "teams.block.agent_busy_long", waiting_user: "teams.block.waiting_user", cancelled: "teams.block.cancelled" };
  var CAP_KEY = { task_turns: "teams.cap.task_turns", task_steps: "teams.cap.task_steps", daily_turns: "teams.cap.daily_turns",
    mentions: "teams.cap.mentions" };
  var TAB_KEY = { members: "teams.tab_members", jobs: "teams.tab_jobs", turns: "teams.tab_turns", settings: "teams.tab_settings" };
  var LATE = ["late_cancelled", "late", "old_revision", "member_left", "leader_changed"];
  // Không tiến triển: chạy lại đúng bước đó (bước lặp đã đánh dấu lỗi, không phải kết quả việc).
  var RETRY_KINDS = ["failed", "interrupted", "no_progress"];
  var RESUME_KINDS = ["cap_reached", "agent_busy_long", "waiting_user"];
  var CAP_FIELDS = ["task_turns", "task_steps", "daily_turns", "mentions"];
  // Toàn quyền (T3, spec 13): trần trưởng nhóm đổi được trong trần trần của chủ.
  var AUTH_CAPS = ["task_turns", "task_steps", "help_depth", "daily_turns"];
  var AUTH_CAP_KEY = { task_turns: "teams.cap.task_turns", task_steps: "teams.cap.task_steps",
    help_depth: "teams.cap.help_depth", daily_turns: "teams.cap.daily_turns" };
  var PROVIDERS = [{ id: "aux", key: "teams.auth.provider_aux" }, { id: "anthropic-cli", key: "teams.auth.provider_claude" }];
  var FIXED_KEYS = ["teams.auth.fixed_server", "teams.auth.fixed_provider", "teams.auth.fixed_account",
    "teams.auth.fixed_technical"];
  // Sáu reaction (spec mục 14.1). Emoji ở đây là DỮ LIỆU sản phẩm (giá trị chủ chọn, lưu nguyên loại), không phải icon
  // trang trí: test_icons.py cho phép đúng sáu ký tự này trong file này và kiểm cả sáu luôn có mặt.
  var REACTIONS = [
    { value: "like", emoji: "👍", key: "teams.react.like" },
    { value: "love", emoji: "❤️", key: "teams.react.love" },
    { value: "haha", emoji: "😂", key: "teams.react.haha" },
    { value: "wow", emoji: "😮", key: "teams.react.wow" },
    { value: "sad", emoji: "😢", key: "teams.react.sad" },
    { value: "angry", emoji: "😡", key: "teams.react.angry" }
  ];
  var REASON_KEY = { on_point: "teams.reason.on_point", wrong_facts: "teams.reason.wrong_facts",
    missing: "teams.reason.missing", too_long: "teams.reason.too_long", unclear: "teams.reason.unclear",
    off_topic: "teams.reason.off_topic" };
  var REASONS = ["on_point", "wrong_facts", "missing", "too_long", "unclear", "off_topic"];
  var COMMENT_MAX = 500;

  function reactionOf(value) {
    for (var i = 0; i < REACTIONS.length; i++) if (REACTIONS[i].value === value) return REACTIONS[i];
    return null;
  }

  // Chọn lại emoji đang chọn là bỏ; chọn cái khác là đổi (spec 14.1).
  function nextReaction(current, picked) {
    return current === picked ? "none" : picked;
  }

  function reactionChipHtml(m, reaction) {
    if (!reaction) return "";
    var r = reactionOf(reaction.value);
    var bits = [];
    if (r) bits.push('<span class="tm-react-emoji">' + r.emoji + "</span>" + esc(tw(r.key)));
    if ((reaction.reasons || []).length) bits.push(esc(tw("teams.react_reasons_n", { n: reaction.reasons.length })));
    if (reaction.comment) bits.push(esc(tw("teams.react_has_comment")));
    if (!bits.length) return "";
    return '<button type="button" class="tm-react-chip" data-react-open="' + esc(m.id) + '" title="' +
      esc(tw("teams.react_change")) + '">' + bits.join(" · ") + "</button>";
  }

  // `draft`: lý do và góp ý đang soạn dở (giữ qua lần vẽ lại khi có tin mới tới).
  function reactionPickerHtml(m, reaction, draft) {
    reaction = reaction || {};
    if (draft) reaction = { value: reaction.value, reasons: draft.reasons, comment: draft.comment };
    var row = REACTIONS.map(function (r) {
      var on = reaction.value === r.value;
      return '<button type="button" class="tm-react-pick" data-react="' + r.value + '" data-mid="' + esc(m.id) + '"' +
        ' aria-pressed="' + (on ? "true" : "false") + '" aria-label="' + esc(tw(r.key)) + '" title="' + esc(tw(r.key)) + '">' +
        r.emoji + "</button>";
    }).join("");
    var have = {};
    (reaction.reasons || []).forEach(function (x) { have[x] = true; });
    var reasons = REASONS.map(function (x) {
      return '<label class="tm-react-reason"><input type="checkbox" name="tm-reason" value="' + x + '"' +
        (have[x] ? " checked" : "") + "> " + esc(tw(REASON_KEY[x])) + "</label>";
    }).join("");
    return '<div class="tm-react-panel" data-panel="' + esc(m.id) + '" role="dialog" aria-label="' + esc(tw("teams.react")) + '">' +
      '<div class="tm-react-row">' + row + "</div>" +
      '<div class="tm-react-sub">' + esc(tw("teams.react_reasons")) + "</div>" +
      '<div class="tm-react-reasons">' + reasons + "</div>" +
      '<label class="tm-react-sub" for="tm-react-comment-' + esc(m.id) + '">' + esc(tw("teams.react_comment")) + "</label>" +
      '<textarea class="tm-react-comment" id="tm-react-comment-' + esc(m.id) + '" maxlength="' + COMMENT_MAX + '" rows="2"' +
      ' placeholder="' + esc(tw("teams.react_comment_ph")) + '">' + esc(reaction.comment || "") + "</textarea>" +
      '<div class="tm-react-note">' + esc(tw("teams.react_note")) + "</div>" +
      '<div class="tm-actions"><button type="button" class="ws-btn" data-react-save="' + esc(m.id) + '">' +
      esc(tw("teams.react_save")) + '</button><button type="button" class="ws-btn" data-react-clear="' + esc(m.id) + '">' +
      esc(tw("teams.react_clear")) + '</button><button type="button" class="ws-btn" data-react-close="' + esc(m.id) + '">' +
      esc(tw("teams.react_close")) + "</button></div></div>";
  }

  function initial(name) {
    var s = String(name || "?").trim();
    return s ? s.charAt(0).toUpperCase() : "?";
  }

  function memberOf(members, key) {
    for (var i = 0; i < (members || []).length; i++) if (members[i].agent_key === key) return members[i];
    return null;
  }

  function nameOf(members, key) {
    var m = memberOf(members, key);
    return m ? (m.name || m.slug || key) : key;
  }

  // ───────────── danh sách nhóm ─────────────

  function teamListHtml(teams, activeId) {
    if (!teams || !teams.length) return '<div class="tm-empty">' + esc(tw("teams.empty")) + "</div>";
    return teams.map(function (t) {
      var c = t.counts || {};
      var sub = [];
      if (c.blocked) sub.push('<span class="tm-badge tm-badge-owner">' + esc(tw("teams.waiting_owner", { n: c.blocked })) + "</span>");
      if (c.running) sub.push("<span>" + esc(tw("teams.running_n", { n: c.running })) + "</span>");
      if (c.waiting) sub.push("<span>" + esc(tw("teams.waiting_n", { n: c.waiting })) + "</span>");
      if (TEAM_STATUS_KEY[t.status] && t.status !== "active") sub.push("<span>" + esc(tw(TEAM_STATUS_KEY[t.status])) + "</span>");
      var on = t.team_id === activeId;
      return '<button type="button" class="tm-team" data-team="' + esc(t.team_id) + '"' + (on ? ' aria-current="true"' : "") + ">" +
        '<span class="tm-team-name">' + esc(t.name) + "</span>" +
        '<span class="tm-team-sub">' + sub.join(" · ") + "</span></button>";
    }).join("");
  }

  // ───────────── tin ─────────────

  function messageHtml(m, ctx) {
    ctx = ctx || {};
    var meta = m.meta || {};
    var mine = m.author_kind === "owner";
    var who = mine ? tw("teams.owner") : m.author_kind === "agent" ? nameOf(ctx.members, m.author_ref) : tw("teams.system");
    var head = ['<span class="tm-ava" aria-hidden="true">' + esc(initial(who)) + "</span>",
      '<span class="tm-who">' + esc(who) + "</span>"];
    if (meta.role && ROLE_KEY[meta.role]) head.push('<span class="tm-role">' + esc(tw(ROLE_KEY[meta.role])) + "</span>");
    if (m.task_id) {
      var title = (ctx.taskTitles || {})[m.task_id] || m.task_id;
      head.push('<button type="button" class="tm-tag" data-task="' + esc(m.task_id) + '">' +
        esc(tw("teams.job_tag", { title: title })) + "</button>");
    }
    if (meta.job_result) head.push('<span class="tm-result">' + esc(tw("teams.job_result")) + "</span>");
    if (m.author_kind === "agent" && STATUS_KEY[meta.status]) {
      var late = LATE.indexOf(meta.status) >= 0;
      head.push('<span class="tm-state' + (late ? " tm-state-late" : "") + '">' +
        ic(late ? "triangle-alert" : "check") + esc(tw(STATUS_KEY[meta.status])) + "</span>");
    }
    if (meta.decision) head.push('<span class="tm-decision">' + esc(tw("teams.decision_pinned")) + "</span>");
    var body = '<div class="tm-text">' + esc(m.content).replace(/\n/g, "<br>") + "</div>";
    var notes = (meta.notes || []).map(function (n) { return '<div class="tm-note-line">' + esc(n) + "</div>"; }).join("");
    var prop = "";
    if (meta.proposal && meta.proposal.title) {
      prop = '<div class="tm-proposal"><div>' + esc(tw("teams.proposal", { name: who, title: meta.proposal.title })) + "</div>" +
        '<div class="tm-actions"><button type="button" class="ws-btn" data-accept="' + esc(m.id) + '">' +
        esc(tw("teams.proposal_create")) + '</button><button type="button" class="ws-btn" data-skip="' + esc(m.id) + '">' +
        esc(tw("teams.proposal_skip")) + "</button></div></div>";
    }
    var pin = '<button type="button" class="tm-pin" data-decision="' + esc(m.id) + '" data-on="' + (meta.decision ? "0" : "1") + '">' +
      esc(tw(meta.decision ? "teams.decision_unpin" : "teams.decision_pin")) + "</button>";
    var cls = "tm-msg" + (mine ? " tm-msg-owner" : "") + (LATE.indexOf(meta.status) >= 0 ? " tm-msg-late" : "") +
      (meta.job_result ? " tm-msg-result" : "");
    var react = "";
    if (m.author_kind === "agent") {
      cls += " tm-msg-agent";
      react = reactionChipHtml(m, m.reaction) +
        '<button type="button" class="tm-react-btn" data-react-open="' + esc(m.id) + '" aria-label="' +
        esc(tw("teams.react")) + '" title="' + esc(tw("teams.react")) + '">' + ic("smile") + "</button>";
    }
    var panel = m.author_kind === "agent" && ctx.picker === m.id ?
      reactionPickerHtml(m, m.reaction, ctx.draft && ctx.draft.mid === m.id ? ctx.draft : null) : "";
    return '<div class="' + cls + '" data-mid="' + esc(m.id) + '"><div class="tm-head">' + head.join("") + "</div>" +
      body + notes + prop + '<div class="tm-foot">' + react + pin + "</div>" + panel + "</div>";
  }

  // ───────────── hàng đợi ─────────────

  function queueHtml(q) {
    q = q || {};
    var running = q.running || [], waiting = q.waiting || [], blocked = q.blocked || [];
    if (!running.length && !waiting.length && !blocked.length) return '<div class="tm-empty">' + esc(tw("teams.queue_empty")) + "</div>";
    var h = "";
    if (running.length) {
      h += '<div class="tm-qhead">' + esc(tw("teams.queue_running")) + "</div>";
      h += running.map(function (t) {
        return '<div class="tm-qrow"><span class="tm-qtitle">' + esc(t.title) + '</span><span class="tm-actions">' +
          '<button type="button" class="ws-btn" data-amend="' + esc(t.id) + '">' + esc(tw("teams.amend")) + "</button>" +
          '<button type="button" class="ws-btn" data-cancel="' + esc(t.id) + '">' + esc(tw("teams.cancel")) + "</button></span></div>";
      }).join("");
    }
    if (waiting.length) {
      h += '<div class="tm-qhead">' + esc(tw("teams.queue_waiting")) + "</div>";
      h += waiting.map(function (t, i) {
        var star = t.team_prio != null;
        return '<div class="tm-qrow"><span class="tm-qpos">' + (i + 1) + "</span>" +
          (star ? '<span class="tm-star" title="' + esc(tw("teams.prioritized")) + '">' + ic("star") + esc(tw("teams.prioritized")) + "</span>" : "") +
          '<span class="tm-qtitle">' + esc(t.title) + '</span><span class="tm-actions">' +
          '<button type="button" class="ws-btn" data-prio="' + esc(t.id) + '" data-on="' + (star ? "0" : "1") + '">' +
          esc(tw(star ? "teams.unprioritize" : "teams.prioritize")) + "</button>" +
          '<button type="button" class="ws-btn" data-cancel="' + esc(t.id) + '">' + esc(tw("teams.cancel")) + "</button></span></div>";
      }).join("");
    }
    if (blocked.length) {
      h += '<div class="tm-qhead">' + esc(tw("teams.queue_blocked")) + "</div>";
      h += blocked.map(function (t) {
        var kind = t.block_kind || "failed";
        var btn = RETRY_KINDS.indexOf(kind) >= 0 ? ["retry", "teams.retry"] : RESUME_KINDS.indexOf(kind) >= 0 ? ["resume", "teams.resume"] : null;
        return '<div class="tm-qrow tm-qblocked"><span class="tm-qtitle">' + esc(t.title) + "</span>" +
          '<span class="tm-qwhy">' + esc(tw(BLOCK_KEY[kind] || BLOCK_KEY.failed)) + (t.block_reason ? ": " + esc(t.block_reason) : "") + "</span>" +
          (kind === "cap_reached" ? '<span class="tm-qwhy">' + esc(tw("teams.cap_hint")) + "</span>" : "") +
          '<span class="tm-actions">' +
          (btn ? '<button type="button" class="ws-btn" data-unblock="' + esc(t.id) + '" data-action="' + btn[0] + '">' + esc(tw(btn[1])) + "</button>" : "") +
          '<button type="button" class="ws-btn" data-cancel="' + esc(t.id) + '">' + esc(tw("teams.cancel")) + "</button></span></div>";
      }).join("");
    }
    return h;
  }

  // ───────────── khung soạn ─────────────

  function mentionMatches(members, query, chosen) {
    var q = String(query || "").toLowerCase();
    return (members || []).filter(function (m) {
      if (m.status && m.status !== "active") return false;
      if ((chosen || []).indexOf(m.agent_key) >= 0) return false;
      if (!q) return true;
      return String(m.name || "").toLowerCase().indexOf(q) === 0 || String(m.slug || "").toLowerCase().indexOf(q) === 0;
    }).slice(0, 8);
  }

  function composerHint(st) {
    var cap = Number(st.cap || 3);
    var ments = st.mentions || [];
    if (ments.length > cap) return { ok: false, text: tw("teams.hint_cap", { cap: cap }) };
    if (!st.asJob) return { ok: true, text: "" };
    var pos = Number(st.waiting || 0) + 1;
    if (ments.length) {
      var names = ments.map(function (k) { return nameOf(st.members, k); }).join(", ");
      return { ok: true, text: tw("teams.hint_job_direct", { names: names, pos: pos }) };
    }
    if (!st.leaderKey) return { ok: true, text: tw("teams.hint_job_noleader") };
    return { ok: true, text: tw("teams.hint_job_general", { name: nameOf(st.members, st.leaderKey), pos: pos }) };
  }

  function newClientId() {
    try {
      if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
    } catch (e) { /* trình duyệt cũ: rơi xuống dưới */ }
    return "c" + Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
  }

  // ───────────── cài đặt nhóm ─────────────

  function rsText(on) { return tw(on ? "resonance.t0_state_on" : "resonance.t0_state_off"); }

  function membersHtml(team, agents) {
    var mem = team.members || [];
    var have = {};
    mem.forEach(function (m) { have[m.slug] = true; });
    var rows = mem.map(function (m) {
      var lead = m.agent_key === team.leader_key;
      return '<div class="tm-mrow"><span class="tm-ava" aria-hidden="true">' + esc(initial(m.name)) + "</span>" +
        '<span class="tm-mname">' + esc(m.name || m.slug) + "</span>" +
        '<span class="tm-mrole">' + esc(tw(lead ? "teams.leader" : "teams.member")) + "</span>" +
        '<label class="tm-rs"><input type="checkbox" class="tm-rs-toggle" data-slug="' + esc(m.slug) + '"' +
        (m.resonance_enabled ? " checked" : "") + ' aria-label="' + esc(rsText(m.resonance_enabled)) + '"><span>' +
        esc(rsText(m.resonance_enabled)) + "</span></label>" +
        '<label class="tm-rs"><input type="checkbox" class="tm-managed-toggle" data-key="' + esc(m.agent_key) + '"' +
        (m.managed ? " checked" : "") + "><span>" + esc(tw("teams.managed")) + "</span></label>" +
        '<span class="tm-actions">' + (lead
          ? '<button type="button" class="ws-btn" data-leader="">' + esc(tw("teams.remove_leader")) + "</button>"
          : '<button type="button" class="ws-btn" data-leader="' + esc(m.agent_key) + '">' + esc(tw("teams.make_leader")) + "</button>") +
        '<button type="button" class="ws-btn" data-remove="' + esc(m.agent_key) + '">' + esc(tw("teams.remove")) + "</button></span></div>";
    }).join("");
    var free = (agents || []).filter(function (a) { return !have[a.slug] && a.status !== "retired"; });
    var add = '<div class="tm-add"><select class="tm-add-pick" aria-label="' + esc(tw("teams.pick_agent")) + '"><option value="">' +
      esc(tw("teams.pick_agent")) + "</option>" + free.map(function (a) {
        return '<option value="' + esc(a.slug) + '">' + esc(a.name || a.slug) + "</option>";
      }).join("") + '</select><button type="button" class="ws-btn tm-add-go">' + esc(tw("teams.add_member")) + "</button></div>";
    return rows + add;
  }

  function settingsFormHtml(team) {
    var caps = team.caps || {};
    var st = ["active", "paused", "archived"].map(function (s) {
      return '<label class="tm-radio"><input type="radio" name="tm-status" value="' + s + '"' + (team.status === s ? " checked" : "") +
        "><span>" + esc(tw(TEAM_STATUS_KEY[s])) + "</span></label>";
    }).join("");
    var lead = '<select name="tm-leader-set"><option value="">' + esc(tw("teams.none")) + "</option>" +
      (team.members || []).map(function (m) {
        return '<option value="' + esc(m.agent_key) + '"' + (m.agent_key === team.leader_key ? " selected" : "") + ">" + esc(m.name || m.slug) + "</option>";
      }).join("") + "</select>";
    var capRows = CAP_FIELDS.map(function (k) {
      return '<label class="tm-field tm-cap"><span>' + esc(tw(CAP_KEY[k])) + '</span><input type="number" min="0" name="tm-cap-' + k +
        '" value="' + esc(caps[k] == null ? "" : caps[k]) + '"></label>';
    }).join("");
    return '<form class="tm-form" onsubmit="return false">' +
      '<label class="tm-field"><span>' + esc(tw("teams.name")) + '</span><input name="tm-set-name" value="' + esc(team.name) + '"></label>' +
      '<label class="tm-field"><span>' + esc(tw("teams.description")) + '</span><textarea name="tm-set-desc" rows="2">' + esc(team.description) + "</textarea></label>" +
      '<div class="tm-field"><span>' + esc(tw("teams.status")) + "</span>" + st + "</div>" +
      '<label class="tm-field"><span>' + esc(tw("teams.leader")) + "</span>" + lead + "</label>" +
      '<div class="tm-qhead">' + esc(tw("teams.caps")) + "</div>" +
      // Toàn quyền đang bật: trần trong hộp Toàn quyền đè trần ở đây; nói rõ thay vì để "Đã lưu" mà không đổi gì.
      (team.authority && team.authority.authority ? '<div class="tm-note-line">' + esc(tw("teams.caps_full_note")) + "</div>" : "") +
      capRows +
      '<button type="button" class="ws-btn tm-save">' + esc(tw("teams.save")) + "</button></form>";
  }

  function capText(v) {
    return v === null || v === undefined ? tw("teams.auth.unlimited") : String(v);
  }

  function capInputs(name, v) {
    var unl = !!(v && typeof v === "object" && v.unlimited);
    var num = !unl && v !== null && v !== undefined && typeof v !== "object" ? String(v) : "";
    return '<input type="number" min="0" name="' + name + '" value="' + esc(num) + '"' + (unl ? " disabled" : "") + ">" +
      '<label class="tm-unl"><input type="checkbox" name="' + name + '-unl"' + (unl ? " checked" : "") + "> " +
      esc(tw("teams.auth.unlimited")) + "</label>";
  }

  // Hộp cấp quyền (spec 13.1): phạm vi, agent do nhóm quản lý, provider được Không giới hạn, nguồn thanh toán, trần và
  // trần trần, quyền Được ngắt việc, các trần không bỏ được (luôn hiện).
  function authorityHtml(team) {
    var view = team.authority || {};
    var auth = view.authority;
    var grant = (auth && auth.grant) || {};
    var eff = view.effective_caps || team.caps || {};
    var leader = team.leader_key ? nameOf(team.members, team.leader_key) : "";
    var managed = (team.members || []).filter(function (m) { return m.managed; }).map(function (m) { return m.name || m.slug; });
    var status = auth ? tw("teams.auth.on", { name: leader, when: new Date(auth.granted_at * 1000).toLocaleString() })
      : tw("teams.auth.off");
    var now = AUTH_CAPS.map(function (k) { return tw(AUTH_CAP_KEY[k]) + ": " + capText(eff[k]); }).join(" · ");
    var rows = AUTH_CAPS.map(function (k) {
      return '<div class="tm-field tm-auth-cap"><span>' + esc(tw(AUTH_CAP_KEY[k])) + "</span>" +
        '<span class="tm-auth-pair"><span class="tm-auth-lbl">' + esc(tw("teams.auth.cap_value")) + "</span>" +
        capInputs("tm-auth-cap-" + k, (grant.caps || {})[k]) + "</span>" +
        '<span class="tm-auth-pair"><span class="tm-auth-lbl">' + esc(tw("teams.auth.cap_ceiling")) + "</span>" +
        capInputs("tm-auth-ceil-" + k, (grant.ceilings || {})[k]) + "</span></div>";
    }).join("");
    var allowed = {};
    (grant.providers_unlimited || []).forEach(function (x) { allowed[x] = true; });
    var prov = PROVIDERS.map(function (x) {
      return '<label class="tm-unl"><input type="checkbox" name="tm-auth-prov" value="' + esc(x.id) + '"' +
        (allowed[x.id] ? " checked" : "") + "> " + esc(tw(x.key)) + "</label>";
    }).join("");
    var bill = ["subscription", "api"].map(function (b) {
      return '<label class="tm-radio"><input type="radio" name="tm-auth-bill" value="' + b + '"' +
        ((grant.billing || "subscription") === b ? " checked" : "") + "><span>" +
        esc(tw(b === "api" ? "teams.auth.billing_api" : "teams.auth.billing_sub")) + "</span></label>";
    }).join("");
    var fixed = FIXED_KEYS.map(function (k) { return "<li>" + esc(tw(k)) + "</li>"; }).join("");
    if (!team.leader_key) {
      return '<section class="tm-auth"><div class="tm-qhead">' + esc(tw("teams.auth.title")) + "</div>" +
        '<div class="tm-note-line">' + esc(tw("teams.auth.need_leader")) + "</div></section>";
    }
    return '<section class="tm-auth" aria-label="' + esc(tw("teams.auth.title")) + '"><div class="tm-qhead">' +
      esc(tw("teams.auth.title")) + "</div>" +
      '<div class="tm-auth-status' + (auth ? " tm-auth-on" : "") + '">' + esc(status) + "</div>" +
      '<div class="tm-react-sub">' + esc(tw("teams.auth.now", { caps: now })) + "</div>" +
      '<div class="tm-react-sub">' + esc(tw("teams.auth.scope")) + "</div>" +
      '<div class="tm-react-sub">' + esc(managed.length ? tw("teams.auth.managed", { names: managed.join(", ") })
        : tw("teams.auth.managed_none")) + "</div>" +
      '<div class="tm-qhead">' + esc(tw("teams.auth.caps_head")) + "</div>" + rows +
      '<div class="tm-field"><span>' + esc(tw("teams.auth.providers")) + "</span>" + prov + "</div>" +
      '<div class="tm-field"><span>' + esc(tw("teams.auth.billing")) + "</span>" + bill + "</div>" +
      '<label class="tm-unl"><input type="checkbox" name="tm-auth-interrupt"' + (grant.can_interrupt ? " checked" : "") +
      "> " + esc(tw("teams.auth.interrupt")) + "</label>" +
      '<div class="tm-react-sub">' + esc(tw("teams.auth.fixed")) + '</div><ul class="tm-auth-fixed">' + fixed + "</ul>" +
      '<div class="tm-actions"><button type="button" class="ws-btn tm-auth-save">' +
      esc(tw(auth ? "teams.auth.update" : "teams.auth.grant")) + "</button>" +
      (auth ? '<button type="button" class="ws-btn tm-auth-revoke">' + esc(tw("teams.auth.revoke")) + "</button>" : "") +
      "</div></section>";
  }

  // Đọc hộp cấp quyền thành `grant` cho POST /teams/{id}/authority. Ô trống, không tích: bỏ (theo mặc định; trần trần
  // vắng nghĩa là trưởng nhóm không đổi được trần đó).
  function readGrant(root) {
    function one(name) {
      var box = root.querySelector('[name="' + name + '-unl"]');
      if (box && box.checked) return { unlimited: true };
      var inp = root.querySelector('[name="' + name + '"]');
      var v = inp ? String(inp.value).trim() : "";
      return v === "" ? undefined : Number(v);
    }
    var caps = {}, ceilings = {};
    AUTH_CAPS.forEach(function (k) {
      var c = one("tm-auth-cap-" + k), l = one("tm-auth-ceil-" + k);
      if (c !== undefined) caps[k] = c;
      if (l !== undefined) ceilings[k] = l;
    });
    var bill = root.querySelector('input[name="tm-auth-bill"]:checked');
    var intr = root.querySelector('input[name="tm-auth-interrupt"]');
    return { caps: caps, ceilings: ceilings,
      providers_unlimited: Array.prototype.map.call(root.querySelectorAll('input[name="tm-auth-prov"]:checked'),
        function (x) { return x.value; }),
      billing: bill ? bill.value : "subscription", can_interrupt: !!(intr && intr.checked) };
  }

  function dayStart() {
    var d = new Date();
    d.setHours(0, 0, 0, 0);
    return d.getTime() / 1000;
  }

  function turnsHtml(turns, team) {
    var counted = (turns || []).filter(function (t) { return t.status !== "refunded"; });
    var today = counted.filter(function (t) { return Number(t.created_at) >= dayStart(); }).length;
    var byAgent = {}, byRole = {};
    counted.forEach(function (t) {
      byAgent[t.agent_key] = (byAgent[t.agent_key] || 0) + 1;
      var rk = ROLE_KEY[t.role] || t.role;
      byRole[rk] = (byRole[rk] || 0) + 1;
    });
    var list = function (obj, label) {
      return Object.keys(obj).map(function (k) { return esc(label(k)) + " " + obj[k]; }).join(" · ");
    };
    return '<div class="tm-turns"><div class="tm-qhead">' + esc(tw("teams.turns_today", { n: today, cap: (team.caps || {}).daily_turns })) + "</div>" +
      "<div>" + esc(tw("teams.turns_by_agent")) + ": " + list(byAgent, function (k) { return nameOf(team.members, k); }) + "</div>" +
      "<div>" + esc(tw("teams.turns_by_role")) + ": " + list(byRole, function (k) { return tw(k); }) + "</div>" +
      '<div class="tm-sub">' + esc(tw("teams.turns_note")) + "</div></div>";
  }

  function createFormHtml(agents) {
    var live = (agents || []).filter(function (a) { return a.status !== "retired" && a.status !== "missing"; });
    return '<form class="tm-form tm-create" onsubmit="return false"><div class="tm-qhead">' + esc(tw("teams.create_title")) + "</div>" +
      '<label class="tm-field"><span>' + esc(tw("teams.name")) + '</span><input name="tm-name" maxlength="120"></label>' +
      '<label class="tm-field"><span>' + esc(tw("teams.description")) + '</span><textarea name="tm-desc" rows="2"></textarea></label>' +
      '<div class="tm-field"><span>' + esc(tw("teams.members_pick")) + "</span>" + live.map(function (a) {
        return '<label class="tm-check"><input type="checkbox" name="tm-member" value="' + esc(a.slug) + '"><span>' + esc(a.name || a.slug) + "</span></label>";
      }).join("") + "</div>" +
      '<label class="tm-field"><span>' + esc(tw("teams.leader_pick")) + '</span><select name="tm-leader"><option value="">' + esc(tw("teams.none")) +
      "</option>" + live.map(function (a) { return '<option value="' + esc(a.slug) + '">' + esc(a.name || a.slug) + "</option>"; }).join("") +
      "</select></label>" +
      '<button type="button" class="ws-btn tm-create-save">' + esc(tw("teams.create_save")) + "</button></form>";
  }

  function bannersHtml(team, teamNames) {
    var out = [];
    if (team.status === "archived") out.push(tw("teams.archived_banner"));
    else if (team.status === "paused") out.push(tw("teams.paused_banner"));
    if (!team.leader_key) out.push(tw("teams.no_leader"));
    Object.keys(team.busy || {}).forEach(function (k) {
      var other = team.busy[k];
      out.push(tw("teams.busy_elsewhere", { name: nameOf(team.members, k), team: (teamNames || {})[other] || other }));
    });
    return out.map(function (s) { return '<div class="tm-banner">' + esc(s) + "</div>"; }).join("");
  }

  // ───────────── phần chạy trong trình duyệt ─────────────

  function brain() {
    try {
      if (window.JavisSessions && window.JavisSessions.brain) return window.JavisSessions.brain();
      return (window.currentBrainPath && window.currentBrainPath()) || "brain";
    } catch (e) { return "brain"; }
  }

  function q(s) { return encodeURIComponent(s); }

  function call(method, url, body) {
    var opt = { method: method, credentials: "same-origin" };
    if (body !== undefined) {
      opt.headers = { "Content-Type": "application/json" };
      opt.body = JSON.stringify(body);
    }
    var sep = url.indexOf("?") >= 0 ? "&" : "?";
    return fetch(url + sep + "brain=" + q(brain()), opt).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) { return { code: r.status, j: j || {} }; });
    });
  }

  var S = null;

  function fresh(el) {
    return { el: el, teams: [], next: null, activeId: "", team: null, queue: null, msgs: [], hasMore: false,
      agents: [], mentions: [], asJob: false, pending: null, tab: "jobs", side: false, view: "list",
      filterTask: "", taskTitles: {}, teamNames: {}, note: "", creating: false, skipped: {}, picker: null, draft: null,
      focusPicker: false, focusBack: null };
  }

  function teamUrl(path) { return "/teams/" + q(S.activeId) + (path || ""); }

  function setNote(text) {
    S.note = text || "";
    var n = S.el.querySelector(".tm-note");
    if (n) { n.textContent = S.note; n.hidden = !S.note; }
  }

  function fail(r) {
    setNote(tw("teams.err", { e: (r && r.j && r.j.error) || (r && r.code) || "?" }));
  }

  function shell() {
    S.el.innerHTML =
      '<div class="tm-page" data-view="' + S.view + '">' +
      '<aside class="tm-list"><div class="tm-bar"><strong>' + esc(tw("page.teams.label")) + "</strong>" +
      '<button type="button" class="ws-btn tm-new">+ ' + esc(tw("teams.create")) + "</button></div>" +
      '<div class="tm-teams"></div><button type="button" class="ws-btn tm-more-teams" hidden>' + esc(tw("teams.next_page")) + "</button></aside>" +
      '<section class="tm-chat"><div class="tm-bar tm-chat-head"></div><div class="tm-note" hidden></div><div class="tm-banners"></div>' +
      '<div class="tm-msgs" aria-live="polite"></div><div class="tm-runbar" hidden></div><div class="tm-composer"></div></section>' +
      '<aside class="tm-side" hidden></aside></div>';
  }

  function drawList() {
    var box = S.el.querySelector(".tm-teams");
    if (box) box.innerHTML = teamListHtml(S.teams, S.activeId);
    var more = S.el.querySelector(".tm-more-teams");
    if (more) more.hidden = !S.next;
  }

  function drawPage() {
    var page = S.el.querySelector(".tm-page");
    if (page) page.setAttribute("data-view", S.view);
  }

  function drawHead() {
    var head = S.el.querySelector(".tm-chat-head");
    if (!head) return;
    if (S.creating || !S.team) { head.innerHTML = '<button type="button" class="ws-btn tm-back">‹ ' + esc(tw("teams.back")) + "</button>"; return; }
    var t = S.team;
    var lead = t.leader_key ? tw("teams.leader_line", { name: nameOf(t.members, t.leader_key), n: (t.members || []).length })
      : tw("teams.no_leader_short");
    var opts = '<option value="">' + esc(tw("teams.filter_all")) + "</option>" + Object.keys(S.taskTitles).map(function (id) {
      return '<option value="' + esc(id) + '"' + (S.filterTask === id ? " selected" : "") + ">" + esc(S.taskTitles[id]) + "</option>";
    }).join("");
    head.innerHTML = '<button type="button" class="ws-btn tm-back" aria-label="' + esc(tw("teams.back")) + '">‹</button>' +
      '<div class="tm-title"><strong>' + esc(t.name) + '</strong><span class="tm-sub">' + esc(lead) + "</span></div>" +
      '<select class="tm-filter" aria-label="' + esc(tw("teams.filter_all")) + '">' + opts + "</select>" +
      '<button type="button" class="ws-btn tm-gear">' + esc(tw("teams.settings_btn")) + "</button>";
    var b = S.el.querySelector(".tm-banners");
    if (b) b.innerHTML = bannersHtml(t, S.teamNames);
  }

  function ctx() {
    return { members: S.team ? S.team.members : [], leaderKey: S.team && S.team.leader_key, taskTitles: S.taskTitles,
      picker: S.picker, draft: S.draft };
  }

  function drawMsgs(stick) {
    var box = S.el.querySelector(".tm-msgs");
    if (!box) return;
    if (S.creating) {
      box.innerHTML = createFormHtml(S.agents);
      return;
    }
    var atEnd = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
    // Đang soạn góp ý trong bộ chọn mà có tin mới tới: giữ con trỏ và chỗ cuộn, không kéo xuống cuối (review T2).
    var act = document.activeElement;
    var typing = S.picker !== null && act && act.classList && act.classList.contains("tm-react-comment") ?
      { start: act.selectionStart, end: act.selectionEnd, top: box.scrollTop } : null;
    var list = S.msgs.filter(function (m) { return !S.skipped[m.id]; });
    box.innerHTML = (S.hasMore ? '<button type="button" class="ws-btn tm-older">' + esc(tw("teams.older")) + "</button>" : "") +
      list.map(function (m) {
        var mm = m;
        if (S.skipped["p" + m.id] && m.meta && m.meta.proposal) mm = Object.assign({}, m, { meta: Object.assign({}, m.meta, { proposal: null }) });
        return messageHtml(mm, ctx());
      }).join("");
    if (typing) {
      box.scrollTop = typing.top;
      var ta = box.querySelector(".tm-react-comment");
      if (ta) { ta.focus(); try { ta.setSelectionRange(typing.start, typing.end); } catch (e) {} }
      return;
    }
    if ((stick || atEnd) && S.picker === null) box.scrollTop = box.scrollHeight;
    if (S.focusPicker) {
      // Mở bộ chọn: focus vào emoji đầu (bàn phím và trình đọc màn hình vào được bảng, Escape đóng được).
      S.focusPicker = false;
      var first = box.querySelector(".tm-react-panel .tm-react-pick");
      if (first) first.focus();
    }
    if (S.focusBack !== null && S.focusBack !== undefined) {
      var back = box.querySelector('.tm-react-btn[data-react-open="' + S.focusBack + '"]');
      S.focusBack = null;
      if (back) back.focus();
    }
  }

  function drawRunbar() {
    var bar = S.el.querySelector(".tm-runbar");
    if (!bar) return;
    var run = (S.queue && S.queue.running) || [];
    bar.hidden = !run.length || S.creating;
    if (!run.length) return;
    bar.innerHTML = '<span class="tm-qtitle">' + esc(tw("teams.doing", { title: run[0].title })) + '</span><span class="tm-actions">' +
      '<button type="button" class="ws-btn" data-amend="' + esc(run[0].id) + '">' + esc(tw("teams.amend")) + "</button>" +
      '<button type="button" class="ws-btn" data-cancel="' + esc(run[0].id) + '">' + esc(tw("teams.cancel")) + "</button></span>";
  }

  function drawComposer() {
    var box = S.el.querySelector(".tm-composer");
    if (!box) return;
    if (!S.team || S.creating) { box.innerHTML = ""; return; }
    var chips = S.mentions.map(function (k) {
      return '<span class="tm-chip">@' + esc(nameOf(S.team.members, k)) + '<button type="button" data-unmention="' + esc(k) +
        '" aria-label="' + esc(tw("teams.remove")) + '">×</button></span>';
    }).join("");
    var draft = S.pending ? S.pending.text : (box.querySelector("textarea") || {}).value || "";
    box.innerHTML = '<div class="tm-chips">' + chips + '</div><div class="tm-sug" hidden></div>' +
      '<div class="tm-row"><label class="tm-job"><input type="checkbox" class="tm-asjob"' + (S.asJob ? " checked" : "") + "><span>" +
      esc(tw("teams.as_job")) + '</span></label><textarea class="tm-input" rows="2" placeholder="' + esc(tw("teams.placeholder")) + '"' +
      (S.team.status === "archived" ? " disabled" : "") + ">" + esc(draft) + '</textarea><button type="button" class="ws-btn tm-send">' +
      esc(tw(S.asJob ? "teams.as_job" : "teams.send")) + '</button></div><div class="tm-hint"></div>';
    drawHint();
  }

  function drawHint() {
    var hintEl = S.el.querySelector(".tm-hint");
    if (!hintEl || !S.team) return;
    var h = composerHint({ mentions: S.mentions, asJob: S.asJob, cap: (S.team.caps || {}).mentions, members: S.team.members,
      leaderKey: S.team.leader_key, waiting: ((S.queue && S.queue.waiting) || []).length });
    hintEl.textContent = h.text;
    var send = S.el.querySelector(".tm-send");
    if (send) send.disabled = !h.ok || S.team.status === "archived";
  }

  function drawSide() {
    var side = S.el.querySelector(".tm-side");
    if (!side) return;
    side.hidden = !S.team || S.creating;
    side.classList.toggle("tm-open", !!S.side);
    var page = S.el.querySelector(".tm-page");
    if (page) page.setAttribute("data-side", side.hidden ? "0" : "1");
    if (side.hidden) return;
    var tabs = ["members", "jobs", "turns", "settings"].map(function (k) {
      return '<button type="button" class="tm-tab" data-tab="' + k + '"' + (S.tab === k ? ' aria-selected="true"' : "") + ">" +
        esc(tw(TAB_KEY[k])) + "</button>";
    }).join("");
    var body = "";
    if (S.tab === "members") body = membersHtml(S.team, S.agents);
    else if (S.tab === "jobs") body = queueHtml(S.queue);
    else if (S.tab === "turns") body = turnsHtml(S.turns || [], S.team);
    else body = settingsFormHtml(S.team) + authorityHtml(S.team);
    side.innerHTML = '<div class="tm-bar"><strong>' + esc(tw("teams.settings_btn")) + '</strong><button type="button" class="ws-btn tm-close" aria-label="' +
      esc(tw("teams.close")) + '">×</button></div><div class="tm-tabs" role="tablist">' + tabs + '</div><div class="tm-side-body">' + body + "</div>";
  }

  function drawAll(stick) {
    drawPage(); drawList(); drawHead(); drawMsgs(stick); drawRunbar(); drawComposer(); drawSide();
  }

  function learnTitles(qq) {
    if (!qq) return;
    ["running", "waiting", "blocked"].forEach(function (k) {
      (qq[k] || []).forEach(function (t) { S.taskTitles[t.id] = t.title; });
    });
  }

  function loadTeams(append) {
    var url = "/teams" + (append && S.next ? "?before=" + q(S.next) : "");
    return call("GET", url).then(function (r) {
      if (r.code !== 200) return fail(r);
      S.teams = append ? S.teams.concat(r.j.teams || []) : (r.j.teams || []);
      S.next = r.j.next || null;
      S.teams.forEach(function (t) { S.teamNames[t.team_id] = t.name; });
      drawList();
    });
  }

  function loadAgents() {
    return call("GET", "/resonance/agents").then(function (r) {
      if (r.code === 200) S.agents = r.j.agents || [];
    });
  }

  function loadQueue() {
    if (!S.activeId) return Promise.resolve();
    return call("GET", teamUrl("/queue")).then(function (r) {
      if (r.code !== 200) return;
      S.queue = r.j;
      learnTitles(S.queue);
      drawRunbar(); drawHint(); if (S.tab === "jobs") drawSide();
    });
  }

  function loadTeam() {
    if (!S.activeId) return Promise.resolve();
    return call("GET", teamUrl()).then(function (r) {
      if (r.code !== 200) return fail(r);
      S.team = r.j.team;
      drawHead(); drawHint(); drawSide();
    });
  }

  function loadMsgs(older) {
    if (!S.activeId) return Promise.resolve();
    var url = S.filterTask ? teamUrl("/tasks/" + q(S.filterTask)) : teamUrl("/messages");
    if (older && S.msgs.length && !S.filterTask) url += "?before_ts=" + q(S.msgs[0].ts) + "&before_id=" + q(S.msgs[0].id);
    return call("GET", url).then(function (r) {
      if (r.code !== 200) return fail(r);
      var got = r.j.messages || [];
      S.msgs = older ? got.concat(S.msgs) : got;
      S.hasMore = !S.filterTask && !!r.j.has_more;
      drawMsgs(!older);
    });
  }

  function loadTurns() {
    if (!S.activeId) return Promise.resolve();
    return call("GET", teamUrl("/turns?since=" + (Date.now() / 1000 - 7 * 86400))).then(function (r) {
      if (r.code === 200) { S.turns = r.j.turns || []; if (S.tab === "turns") drawSide(); }
    });
  }

  function openTeam(id) {
    S.activeId = id; S.creating = false; S.view = "chat"; S.mentions = []; S.asJob = false; S.pending = null; S.filterTask = "";
    S.team = null; S.queue = null; S.msgs = []; S.taskTitles = {};
    drawAll(true);
    Promise.all([loadTeam(), loadQueue(), loadMsgs(false)]).then(function () { drawAll(true); });
  }

  function send() {
    var input = S.el.querySelector(".tm-input");
    if (!input || !S.team) return;
    var text = input.value.trim();
    if (!text) return;
    // Gửi lại sau rớt mạng: cùng chữ thì giữ ĐÚNG mã cũ để server trả tin cũ, không thêm lượt.
    if (!S.pending || S.pending.text !== text) S.pending = { text: text, id: newClientId() };
    var body = { text: text, mentions: S.mentions.slice(), as_job: S.asJob, client_msg_id: S.pending.id };
    var btn = S.el.querySelector(".tm-send");
    if (btn) btn.disabled = true;
    call("POST", teamUrl("/messages"), body).then(function (r) {
      if (r.code !== 200) { fail(r); drawHint(); return; }
      S.pending = null; S.mentions = []; input.value = "";
      setNote(r.j.notes && r.j.notes.length ? r.j.notes.filter(function (n) { return n.indexOf("_") < 0; }).join(" · ") : "");
      if ((r.j.notes || []).indexOf("daily_cap") >= 0) setNote(tw("teams.daily_cap"));
      drawComposer();
      loadMsgs(false); loadQueue();
    }).catch(function () {
      setNote(tw("teams.err", { e: "network" }));
      drawHint();
    });
  }

  function suggest() {
    var input = S.el.querySelector(".tm-input");
    var box = S.el.querySelector(".tm-sug");
    if (!input || !box || !S.team) return;
    var before = input.value.slice(0, input.selectionStart || 0);
    var m = before.match(/@([^\s@]*)$/);
    if (!m) { box.hidden = true; return; }
    var list = mentionMatches(S.team.members, m[1], S.mentions);
    box.hidden = !list.length;
    box.innerHTML = list.map(function (a) {
      return '<button type="button" class="tm-sug-item" data-mention="' + esc(a.agent_key) + '"><span class="tm-ava" aria-hidden="true">' +
        esc(initial(a.name)) + "</span>" + esc(a.name || a.slug) + "</button>";
    }).join("");
  }

  function pickMention(key) {
    var input = S.el.querySelector(".tm-input");
    if (input) {
      var pos = input.selectionStart || input.value.length;
      var before = input.value.slice(0, pos).replace(/@([^\s@]*)$/, "@" + nameOf(S.team.members, key) + " ");
      input.value = before + input.value.slice(pos);
    }
    if (S.mentions.indexOf(key) < 0) S.mentions.push(key);
    S.pending = null;
    drawComposer();
    var again = S.el.querySelector(".tm-input");
    if (again) again.focus();
  }

  function act(r, after) {
    if (r.code === 409 && r.j && r.j.queue) {
      S.queue = r.j.queue; learnTitles(S.queue); setNote(tw("teams.queue_changed")); drawRunbar(); drawSide(); return;
    }
    if (r.code !== 200) return fail(r);
    if (r.j && r.j.team) S.team = r.j.team;
    if (r.j && r.j.queue) S.queue = r.j.queue;
    if (after) after();
    loadQueue(); loadTeam(); loadTeams(false);
  }

  function onClick(e) {
    var t = e.target.closest ? e.target.closest("button, [data-team]") : null;
    if (!t || !S.el.contains(t)) return;
    var d = t.dataset || {};
    if (d.team) return openTeam(d.team);
    if (t.classList.contains("tm-new")) {
      S.creating = true; S.view = "chat"; S.team = null; S.activeId = "";
      loadAgents().then(function () { drawAll(true); });
      return;
    }
    if (t.classList.contains("tm-more-teams")) return loadTeams(true);
    if (t.classList.contains("tm-back")) { S.view = "list"; S.creating = false; drawAll(false); return; }
    if (t.classList.contains("tm-gear")) {
      S.side = !S.side; drawSide();
      if (S.side) { loadAgents().then(drawSide); if (S.tab === "turns") loadTurns(); }
      return;
    }
    if (t.classList.contains("tm-close")) { S.side = false; drawSide(); return; }
    if (d.tab) {
      S.tab = d.tab; drawSide();
      if (d.tab === "turns") loadTurns();
      if (d.tab === "members") loadAgents().then(drawSide);
      return;
    }
    if (t.classList.contains("tm-create-save")) return createTeam();
    if (t.classList.contains("tm-send")) return send();
    if (t.classList.contains("tm-older")) return loadMsgs(true);
    if (d.mention) return pickMention(d.mention);
    if (d.unmention) {
      S.mentions = S.mentions.filter(function (k) { return k !== d.unmention; });
      S.pending = null;
      drawComposer();
      return;
    }
    if (d.reactOpen) {
      var was = S.picker;
      S.picker = S.picker === Number(d.reactOpen) ? null : Number(d.reactOpen);
      S.draft = null;
      if (S.picker !== null) S.focusPicker = true; else S.focusBack = was;
      drawMsgs(false);
      return;
    }
    if (d.reactClose) { S.focusBack = S.picker; S.picker = null; S.draft = null; drawMsgs(false); return; }
    if (d.react) {
      var cur = msgById(Number(d.mid));
      var form = panelValues(Number(d.mid), cur);
      return sendReaction(Number(d.mid), nextReaction(cur && cur.reaction && cur.reaction.value, d.react), form.reasons,
        form.comment);
    }
    if (d.reactSave) {
      var cm = msgById(Number(d.reactSave));
      var fv = panelValues(Number(d.reactSave), cm);
      return sendReaction(Number(d.reactSave), (cm && cm.reaction && cm.reaction.value) || "none", fv.reasons, fv.comment);
    }
    if (d.reactClear) return sendReaction(Number(d.reactClear), "none", [], "");
    if (d.task && t.classList.contains("tm-tag")) { S.filterTask = d.task; drawHead(); loadMsgs(false); return; }
    if (d.accept) return call("POST", teamUrl("/messages/" + q(d.accept) + "/accept")).then(function (r) { act(r); });
    if (d.skip) { S.skipped["p" + d.skip] = true; drawMsgs(false); return; }
    if (d.decision) {
      return call("POST", teamUrl("/messages/" + q(d.decision) + "/decision"), { on: d.on === "1" }).then(function (r) {
        if (r.code !== 200) return fail(r);
        loadMsgs(false);
      });
    }
    if (d.prio) {
      return call("POST", teamUrl("/queue/" + q(d.prio) + "/priority"),
        { on: d.on === "1", expected_queue_version: (S.queue && S.queue.version) || 0 }).then(function (r) { act(r); });
    }
    if (d.cancel) {
      var ct = S.taskTitles[d.cancel] || d.cancel;
      if (typeof confirm === "function" && !confirm(tw("teams.cancel_confirm", { title: ct }))) return;
      return call("POST", teamUrl("/tasks/" + q(d.cancel) + "/cancel")).then(function (r) { act(r); });
    }
    if (d.amend) {
      var at = S.taskTitles[d.amend] || d.amend;
      var text = typeof prompt === "function" ? prompt(tw("teams.amend_prompt", { title: at })) : "";
      if (!text || !text.trim()) return;
      return call("POST", teamUrl("/tasks/" + q(d.amend) + "/amend"), { text: text.trim() }).then(function (r) { act(r); });
    }
    if (d.unblock) {
      return call("POST", teamUrl("/tasks/" + q(d.unblock) + "/unblock"), { action: d.action }).then(function (r) { act(r); });
    }
    if (d.leader !== undefined && t.hasAttribute("data-leader")) {
      return call("POST", teamUrl("/leader"), { agent_key: d.leader || null }).then(function (r) { act(r, drawAll); });
    }
    if (d.remove) {
      var nm = nameOf(S.team && S.team.members, d.remove);
      if (typeof confirm === "function" && !confirm(tw("teams.remove_confirm", { name: nm }))) return;
      return call("DELETE", teamUrl("/members/" + q(d.remove))).then(function (r) { act(r, drawAll); });
    }
    if (t.classList.contains("tm-add-go")) {
      var pick = S.el.querySelector(".tm-add-pick");
      if (!pick || !pick.value) return;
      return call("POST", teamUrl("/members"), { slug: pick.value }).then(function (r) { act(r, drawAll); });
    }
    if (t.classList.contains("tm-save")) return saveSettings();
    if (t.classList.contains("tm-auth-save")) {
      var sec = S.el.querySelector(".tm-auth");
      return call("POST", teamUrl("/authority"), { mode: "full", grant: readGrant(sec) }).then(function (r) {
        if (r.code === 200) setNote(tw("teams.saved"));
        act(r, drawSide);
      });
    }
    if (t.classList.contains("tm-auth-revoke")) {
      if (typeof confirm === "function" && !confirm(tw("teams.auth.revoke_confirm"))) return;
      return call("POST", teamUrl("/authority"), { mode: "limited" }).then(function (r) { act(r, drawSide); });
    }
  }

  function msgById(id) {
    for (var i = 0; i < S.msgs.length; i++) if (Number(S.msgs[i].id) === id) return S.msgs[i];
    return null;
  }

  // Lý do và góp ý đang soạn trong bảng chọn (chưa lưu thì lấy theo phản hồi đã có).
  function panelValues(mid, m) {
    var panel = S.el.querySelector('[data-panel="' + mid + '"]');
    var have = (m && m.reaction) || {};
    if (!panel) return { reasons: have.reasons || [], comment: have.comment || "" };
    var reasons = Array.prototype.map.call(panel.querySelectorAll('input[name="tm-reason"]:checked'), function (x) { return x.value; });
    var box = panel.querySelector(".tm-react-comment");
    return { reasons: reasons, comment: box ? box.value.trim().slice(0, COMMENT_MAX) : "" };
  }

  // Thả cảm xúc: chỉ ghi phản hồi (không mở lượt, không gọi model). Mỗi lần gửi một nonce mới.
  function sendReaction(mid, value, reasons, comment) {
    return call("POST", teamUrl("/messages/" + q(mid) + "/reaction"),
      { value: value, reasons: reasons, comment: comment, nonce: newClientId() }).then(function (r) {
      if (r.code !== 200) return fail(r);
      var m = msgById(mid);
      if (m) m.reaction = r.j.reaction || null;
      S.focusBack = S.picker;
      S.picker = null;
      S.draft = null;
      setNote(tw("teams.react_saved"));
      drawMsgs(false);
    });
  }

  function val(name) {
    var x = S.el.querySelector('[name="' + name + '"]');
    return x ? x.value : "";
  }

  function saveSettings() {
    var status = (S.el.querySelector('input[name="tm-status"]:checked') || {}).value || S.team.status;
    var caps = {};
    CAP_FIELDS.forEach(function (k) {
      var v = val("tm-cap-" + k);
      if (v !== "" && Number(v) !== Number((S.team.caps || {})[k])) caps[k] = Number(v);
    });
    var lead = val("tm-leader-set");
    var steps = [call("PATCH", teamUrl(), { name: val("tm-set-name"), description: val("tm-set-desc"), status: status })];
    if (Object.keys(caps).length) steps.push(call("POST", teamUrl("/caps"), { caps: caps }));
    if ((lead || null) !== (S.team.leader_key || null)) steps.push(call("POST", teamUrl("/leader"), { agent_key: lead || null }));
    Promise.all(steps).then(function (rs) {
      var bad = rs.filter(function (r) { return r.code !== 200; })[0];
      if (bad) return fail(bad);
      setNote(tw("teams.saved"));
      act(rs[rs.length - 1], drawAll);
    });
  }

  function createTeam() {
    var name = val("tm-name").trim();
    if (!name) { setNote(tw("teams.err", { e: tw("teams.name") })); return; }
    var members = Array.prototype.map.call(S.el.querySelectorAll('input[name="tm-member"]:checked'), function (x) { return x.value; });
    call("POST", "/teams", { name: name, description: val("tm-desc"), members: members, leader_slug: val("tm-leader") }).then(function (r) {
      if (r.code !== 200) return fail(r);
      S.creating = false;
      loadTeams(false).then(function () { openTeam(r.j.team.team_id); });
    });
  }

  function onInput(e) {
    if (e.target.name === "tm-reason" && S.picker !== null) {
      var pv = panelValues(S.picker, msgById(S.picker));
      S.draft = { mid: S.picker, reasons: pv.reasons, comment: pv.comment };
      return;
    }
    if (e.target.classList.contains("tm-input")) { suggest(); return; }
    if (e.target.classList.contains("tm-asjob")) {
      S.asJob = !!e.target.checked;
      // Đổi loại tin là một tin KHÁC: mã client cũ thuộc tin trước, gửi lại bằng nó sẽ được trả tin cũ khác loại.
      S.pending = null;
      var btn = S.el.querySelector(".tm-send");
      if (btn) btn.textContent = tw(S.asJob ? "teams.as_job" : "teams.send");
      drawHint();
      return;
    }
    if (e.target.classList.contains("tm-filter")) { S.filterTask = e.target.value; loadMsgs(false); return; }
    if (e.target.name && /^tm-auth-(cap|ceil)-[a-z_]+-unl$/.test(e.target.name)) {
      // Tích Không giới hạn thì ô số tắt (giá trị là null + cờ, không phải một số lớn).
      var num = S.el.querySelector('[name="' + e.target.name.slice(0, -4) + '"]');
      if (num) num.disabled = e.target.checked;
      return;
    }
    if (e.target.classList.contains("tm-managed-toggle")) {
      var mb = e.target;
      var want = mb.checked;
      mb.checked = !want;
      mb.disabled = true;
      call("POST", teamUrl("/members/" + q(mb.getAttribute("data-key")) + "/managed"), { on: want }).then(function (r) {
        act(r, drawSide);
      });
      return;
    }
    if (e.target.classList.contains("tm-rs-toggle")) {
      var box = e.target;
      var on = box.checked;
      box.checked = !on;
      box.disabled = true;
      var RA = window.JavisResonanceAgent;
      var p = RA && RA.toggleAgent ? RA.toggleAgent(box.getAttribute("data-slug"), on)
        : call("POST", "/resonance/agents/toggle", { slug: box.getAttribute("data-slug"), enabled: on }).then(function (r) {
          return { ok: r.code === 200, error: r.j && r.j.error };
        });
      p.then(function (res) {
        if (!res || !res.ok) setNote(tw("teams.err", { e: (res && res.error) || "?" }));
        loadTeam();
      });
    }
  }

  function onKey(e) {
    if (e.key === "Escape" && S.picker !== null) { S.focusBack = S.picker; S.picker = null; S.draft = null; drawMsgs(false); return; }
    if (e.target.classList && e.target.classList.contains("tm-input") && e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      send();
    }
  }

  var refreshTimer = null;
  function onTeamEvent(ev) {
    if (!S || !S.el || !S.el.isConnected) return;
    var d = (ev && ev.detail) || {};
    if (d.type === "team_message" && d.team_id === S.activeId && d.message && !S.filterTask) {
      var i = S.msgs.findIndex(function (m) { return m.id === d.message.id; });
      // Gói không mang phản hồi (tin đổi nhãn, kết quả việc): giữ phản hồi đang có của tin.
      var nm = d.message;
      if (i >= 0 && !("reaction" in nm)) nm = Object.assign({}, nm, { reaction: S.msgs[i].reaction });
      if (i >= 0) S.msgs[i] = nm; else S.msgs.push(nm);
      drawMsgs(false);
    }
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(function () {
      loadTeams(false);
      if (d.team_id === S.activeId) { loadQueue(); loadTeam(); }
    }, 300);
  }

  function render(el) {
    S = fresh(el);
    shell();
    el.addEventListener("click", onClick);
    el.addEventListener("change", onInput);
    el.addEventListener("input", function (e) {
      if (e.target.classList.contains("tm-react-comment") && S.picker !== null) {
        S.draft = { mid: S.picker, reasons: panelValues(S.picker, msgById(S.picker)).reasons, comment: e.target.value };
        return;
      }
      if (e.target.classList.contains("tm-input")) { S.pending = S.pending && S.pending.text === e.target.value.trim() ? S.pending : null; suggest(); }
    });
    el.addEventListener("keydown", onKey);
    // Điện thoại: nhấn giữ tin của trợ lý mở bộ chọn cảm xúc (spec 14.3).
    var hold = null, hx = 0, hy = 0, held = false;
    var stopHold = function () { clearTimeout(hold); hold = null; };
    el.addEventListener("pointerdown", function (e) {
      if (e.pointerType === "mouse") return;   // chuột đã có nút mặt cười khi rê; giữ chuột để bôi chữ như thường
      var msg = e.target.closest && e.target.closest(".tm-msg-agent");
      if (!msg || e.target.closest("button, a, input, textarea, select")) return;
      stopHold();
      hx = e.clientX; hy = e.clientY;
      hold = setTimeout(function () {
        hold = null; held = true;
        S.picker = Number(msg.getAttribute("data-mid")); S.draft = null; S.focusPicker = true; drawMsgs(false);
      }, 500);
    });
    // Nhấn giữ đã mở bộ chọn: chặn menu ngữ cảnh mặc định của máy chạm (chọn chữ, sao chép) cho lần giữ đó.
    el.addEventListener("contextmenu", function (e) {
      if (held) { e.preventDefault(); held = false; }
    });
    el.addEventListener("pointermove", function (e) {
      if (hold && (Math.abs(e.clientX - hx) > 10 || Math.abs(e.clientY - hy) > 10)) stopHold();
    });
    ["pointerup", "pointercancel", "pointerleave"].forEach(function (n) { el.addEventListener(n, stopHold); });
    drawAll(false);
    loadTeams(false);
  }

  if (typeof window !== "undefined" && window.addEventListener) {
    window.addEventListener("javis:team-event", onTeamEvent);
  }

  var api = { render: render, teamListHtml: teamListHtml, messageHtml: messageHtml, queueHtml: queueHtml,
    mentionMatches: mentionMatches, composerHint: composerHint, newClientId: newClientId, membersHtml: membersHtml,
    settingsFormHtml: settingsFormHtml, turnsHtml: turnsHtml, createFormHtml: createFormHtml, bannersHtml: bannersHtml,
    reactionPickerHtml: reactionPickerHtml, reactionChipHtml: reactionChipHtml, nextReaction: nextReaction,
    REACTIONS: REACTIONS, authorityHtml: authorityHtml, readGrant: readGrant };
  if (typeof window !== "undefined") window.JavisTeams = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})();
