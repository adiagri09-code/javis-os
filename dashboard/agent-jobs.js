/* Tab Công việc của một trợ lý ở trang Cộng sự (0.142.0), thay tab Thư mục.
 *
 * Đọc GET /agents/{slug}/jobs: việc của trợ lý gom theo agent_key từ nhóm, chat riêng và Auto (cùng bản ghi gốc, không
 * sao chép). Bốn trạng thái: Đang làm, Đang chờ, Cần bạn, Đã xong. Nút Giao việc tạo một việc cho trợ lý, kết quả báo về
 * cuộc chat riêng. Mỗi việc: nguồn, vai của trợ lý, tiến độ hay kết quả, bấm Mở để tới đúng nhóm hay cuộc chat, Huỷ để
 * huỷ đúng việc đó (dùng route gốc của từng nguồn, huỷ một việc không đụng việc khác).
 *
 * Hàm vẽ là hàm THUẦN (test dưới node); `mount` gắn sự kiện và gọi API.
 */
(function () {
  "use strict";

  var STR = {};
  function tw(khoa, bien) {
    var s = (typeof window !== "undefined" && window.t) ? window.t(khoa, bien) : (STR[khoa] || khoa);
    if (bien) {
      s = String(s).replace(/\{(\w+)\}/g, function (m, ten) {
        return Object.prototype.hasOwnProperty.call(bien, ten) ? String(bien[ten]) : m;
      });
    }
    return s;
  }
  function esc(t) {
    return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  var ic = function (n) { return (typeof window !== "undefined" && window.ic) ? window.ic(n) : ""; };

  var BUCKETS = ["needs_you", "running", "waiting", "done"];
  var BUCKET_KEY = { needs_you: "ajobs.b.needs_you", running: "ajobs.b.running", waiting: "ajobs.b.waiting",
    done: "ajobs.b.done" };
  var ROLE_KEY = { assignee: "ajobs.role.assignee", coordinator: "ajobs.role.coordinator", worker: "ajobs.role.worker",
    helper: "ajobs.role.helper", owner: "ajobs.role.owner", reviewer: "ajobs.role.reviewer" };
  var SOURCE_KEY = { team: "ajobs.src.team", chat: "ajobs.src.chat", auto: "ajobs.src.auto" };
  var REASON_KEY = { review_removed: "ajobs.reason.review_removed", paused: "ajobs.reason.paused" };
  var SOURCE_ICON = { team: "users", chat: "message-circle", auto: "zap" };

  function sourceText(j) {
    if (j.source === "team") return tw("ajobs.src.team", { name: j.source_label || "" });
    return tw(SOURCE_KEY[j.source] || "ajobs.src.chat");
  }

  function jobHtml(j, ui) {
    ui = ui || {};
    var roles = (j.roles || []).map(function (r) {
      return '<span class="aj-role">' + esc(tw(ROLE_KEY[r] || "ajobs.role.assignee")) + "</span>";
    }).join("");
    var lines = [];
    if (j.progress && j.progress.total) lines.push(tw("ajobs.progress", { done: j.progress.done, total: j.progress.total }));
    if (j.queue_pos) lines.push(tw("ajobs.queue_pos", { n: j.queue_pos }));
    if (j.board_off) lines.push(tw("ajobs.board_off"));
    if (j.cancelled) lines.push(tw("ajobs.cancelled"));
    if (j.failed) lines.push(tw("ajobs.failed"));
    // Mã lý do của mục tiêu Auto (đang dừng, đã gỡ người review cố định) đọc bằng lời thường; lý do khác hiện nguyên văn.
    var why = REASON_KEY[j.reason_code] ? tw(REASON_KEY[j.reason_code]) : j.reason;
    var reason = why ? '<div class="aj-reason">' + esc(why) + "</div>" : "";
    var result = j.result ? '<div class="aj-result">' + esc(j.result) + "</div>" : "";
    var openable = j.open && (j.open.team_id || j.open.session_id || j.open.task_id);
    var busy = ui.cancelling && ui.cancelling[j.id];
    var acts = (openable ? '<button type="button" class="ws-btn aj-open" data-aj-open="' + esc(j.id) + '">' + ic("external-link") +
      esc(tw("ajobs.open")) + "</button>" : "") +
      (j.cancel ? '<button type="button" class="ws-btn aj-cancel" data-aj-cancel="' + esc(j.id) + '"' + (busy ? " disabled" : "") + ">" +
        esc(tw(busy ? "ajobs.cancelling" : "ajobs.cancel")) + "</button>" : "");
    return '<li class="aj-job aj-' + esc(j.bucket) + '" data-aj-id="' + esc(j.id) + '">' +
      '<div class="aj-top"><span class="aj-title">' + esc(j.title) + "</span></div>" +
      '<div class="aj-meta"><span class="aj-src">' + ic(SOURCE_ICON[j.source] || "circle") + esc(sourceText(j)) + "</span>" + roles + "</div>" +
      (lines.length ? '<div class="aj-line">' + esc(lines.join(" · ")) + "</div>" : "") + reason + result +
      (acts ? '<div class="aj-acts">' + acts + "</div>" : "") + "</li>";
  }

  function filterHtml(data, ui) {
    var counts = (data && data.counts) || {};
    var cur = ui.filter || "";
    var chip = function (key, label, n) {
      var on = cur === key;
      return '<button type="button" class="aj-chip' + (on ? " is-on" : "") + (key ? " aj-chip-" + key : "") + '" data-aj-filter="' +
        esc(key) + '" aria-pressed="' + (on ? "true" : "false") + '">' + esc(label) +
        (n != null ? ' <span class="aj-n">' + n + "</span>" : "") + "</button>";
    };
    var total = BUCKETS.reduce(function (a, b) { return a + (counts[b] || 0); }, 0);
    return '<div class="aj-filters" role="group" aria-label="' + esc(tw("ajobs.filter")) + '">' + chip("", tw("ajobs.all"), total) +
      ["running", "waiting", "needs_you", "done"].map(function (b) { return chip(b, tw(BUCKET_KEY[b]), counts[b] || 0); }).join("") +
      "</div>";
  }

  function assignHtml(ui) {
    if (!ui.assignOpen) {
      return '<button type="button" class="ws-btn primary aj-assign-open">' + ic("plus") + esc(tw("ajobs.assign")) + "</button>";
    }
    return '<div class="aj-assign"><label class="aj-assign-label" for="ajText">' + esc(tw("ajobs.assign_label", { name: ui.name || "" })) +
      '</label><textarea id="ajText" class="aj-text" rows="3" maxlength="4000" placeholder="' + esc(tw("ajobs.assign_ph")) + '">' +
      esc(ui.draft || "") + "</textarea>" +
      '<div class="aj-help">' + esc(tw("ajobs.assign_help")) + "</div>" +
      (ui.assignError ? '<div class="aj-err" role="alert">' + esc(ui.assignError) + "</div>" : "") +
      '<div class="aj-acts"><button type="button" class="ws-btn aj-assign-cancel">' + esc(tw("ajobs.cancel_form")) + "</button>" +
      '<button type="button" class="ws-btn primary aj-assign-send"' + (ui.sending ? " disabled" : "") + ">" +
      esc(tw(ui.sending ? "ajobs.sending" : "ajobs.send")) + "</button></div></div>";
  }

  function html(data, ui) {
    ui = ui || {};
    var head = '<div class="aj-head">' + assignHtml(ui) + "</div>";
    if (ui.note) head += '<div class="aj-note" role="status">' + esc(ui.note) + "</div>";
    if (!data) return '<div class="aj">' + head + '<div class="aj-empty">' + esc(tw(ui.error ? "ajobs.load_err" : "ajobs.loading")) +
      (ui.error ? ' <button type="button" class="ws-btn aj-reload">' + esc(tw("ajobs.reload")) + "</button>" : "") + "</div></div>";
    var jobs = (data.jobs || []).filter(function (j) { return !ui.filter || j.bucket === ui.filter; });
    var errs = (data.errors || []).map(function (e) {
      return '<div class="aj-err">' + esc(tw("ajobs.source_err", { src: tw(SOURCE_KEY[e.source] || "ajobs.src.chat", { name: "" }) })) + "</div>";
    }).join("");
    var body;
    if (!jobs.length) {
      body = '<div class="aj-empty">' + esc(tw((data.jobs || []).length ? "ajobs.empty_filter" : "ajobs.empty")) + "</div>";
    } else if (ui.filter) {
      body = '<ul class="aj-list">' + jobs.map(function (j) { return jobHtml(j, ui); }).join("") + "</ul>";
    } else {
      body = BUCKETS.map(function (b) {
        var part = jobs.filter(function (j) { return j.bucket === b; });
        if (!part.length) return "";
        return '<section class="aj-sec"><h4 class="aj-sec-h">' + esc(tw(BUCKET_KEY[b])) + ' <span class="aj-n">' + part.length +
          '</span></h4><ul class="aj-list">' + part.map(function (j) { return jobHtml(j, ui); }).join("") + "</ul></section>";
      }).join("");
    }
    var foot = '<div class="aj-foot">' + esc(tw(data.board === "off" ? "ajobs.foot_off" : "ajobs.foot", { n: data.max_workers || 2 })) +
      "</div>";
    return '<div class="aj">' + head + filterHtml(data, ui) + errs + body + foot + "</div>";
  }

  function newNonce() {
    try { if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID(); } catch (e) { /* cũ */ }
    return "n" + Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
  }

  // ───────────── gắn vào trang ─────────────
  // opts: { slug, name, brain: () => string, openChat(sessionId), openTeam(teamId, taskId), openWork(taskId) }
  function mount(host, opts) {
    if (!host) return null;
    var st = { data: null, ui: { filter: "", assignOpen: false, draft: "", name: opts.name, cancelling: {} }, nonce: "" };
    var alive = true;
    function q(s) { return encodeURIComponent(s); }
    function draw() {
      if (!alive || !host.isConnected) return;
      var ta = host.querySelector(".aj-text");
      var keep = ta && document.activeElement === ta ? { s: ta.selectionStart, e: ta.selectionEnd } : null;
      host.innerHTML = html(st.data, st.ui);
      if (keep) {
        var nt = host.querySelector(".aj-text");
        if (nt) { nt.focus(); try { nt.setSelectionRange(keep.s, keep.e); } catch (e) {} }
      }
    }
    function load() {
      var forSlug = opts.slug;
      return fetch("/agents/" + q(forSlug) + "/jobs?brain=" + q(opts.brain())).then(function (r) { return r.json(); }).then(function (j) {
        if (!alive || forSlug !== opts.slug) return;
        if (!j || !j.ok) { st.ui.error = true; draw(); return; }
        st.data = j; st.ui.error = false; draw();
      }, function () { if (alive) { st.ui.error = true; draw(); } });
    }
    function byId(id) { return ((st.data && st.data.jobs) || []).filter(function (x) { return x.id === id; })[0]; }
    function cancelJob(j) {
      var c = j.cancel || {};
      if (typeof confirm === "function" && !confirm(tw("ajobs.cancel_confirm", { title: j.title }))) return;
      st.ui.cancelling[j.id] = true; draw();
      var b = q(opts.brain()), req;
      if (c.kind === "team") req = fetch("/teams/" + q(c.team_id) + "/tasks/" + q(c.task_id) + "/cancel?brain=" + b, { method: "POST" });
      else if (c.kind === "kanban") {
        var fd = new FormData(); fd.append("id", c.task_id); fd.append("brain", opts.brain());
        req = fetch("/kanban/task/cancel", { method: "POST", body: fd });
      } else if (c.kind === "goal") {
        req = fetch("/goals/" + q(c.goal_id) + "/commands?brain=" + b, { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ command: "cancel" }) });
      } else return;
      req.then(function (r) { return r.json().catch(function () { return {}; }).then(function (j2) { return { ok: r.ok && j2.ok !== false, j: j2 }; }); })
        .then(function (res) {
          delete st.ui.cancelling[j.id];
          st.ui.note = res.ok ? tw("ajobs.cancelled_note", { title: j.title }) : tw("ajobs.cancel_err", { e: (res.j && res.j.error) || "" });
          load();
        }, function () { delete st.ui.cancelling[j.id]; st.ui.note = tw("ajobs.net_err"); draw(); });
    }
    function send() {
      var text = String(st.ui.draft || "").trim();
      if (!text) { st.ui.assignError = tw("ajobs.need_text"); draw(); return; }
      if (!st.nonce) st.nonce = newNonce();   // gửi lại sau rớt mạng: cùng mã, server trả đúng việc cũ
      st.ui.sending = true; st.ui.assignError = ""; draw();
      fetch("/agents/" + q(opts.slug) + "/jobs?brain=" + q(opts.brain()), { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text, nonce: st.nonce }) })
        .then(function (r) { return r.json().catch(function () { return {}; }); })
        .then(function (j) {
          st.ui.sending = false;
          if (!j || !j.ok) { st.ui.assignError = (j && j.error) || tw("ajobs.net_err"); draw(); return; }
          st.nonce = ""; st.ui.draft = ""; st.ui.assignOpen = false;
          st.ui.note = tw(j.board === "off" ? "ajobs.assigned_off" : "ajobs.assigned");
          load();
        }, function () { st.ui.sending = false; st.ui.assignError = tw("ajobs.net_err"); draw(); });
    }
    host.addEventListener("input", function (e) {
      if (e.target.classList.contains("aj-text")) { st.ui.draft = e.target.value; st.nonce = ""; }
    });
    host.addEventListener("click", function (e) {
      var t = e.target.closest ? e.target.closest("button") : null;
      if (!t || !host.contains(t)) return;
      var d = t.dataset || {};
      if (d.ajFilter !== undefined) { st.ui.filter = d.ajFilter; draw(); return; }
      if (t.classList.contains("aj-assign-open")) {
        st.ui.assignOpen = true; st.ui.note = ""; draw();
        var ta = host.querySelector(".aj-text"); if (ta) ta.focus();
        return;
      }
      if (t.classList.contains("aj-assign-cancel")) { st.ui.assignOpen = false; st.ui.assignError = ""; draw(); return; }
      if (t.classList.contains("aj-assign-send")) { send(); return; }
      if (t.classList.contains("aj-reload")) { st.ui.error = false; draw(); load(); return; }
      if (d.ajCancel) { var jc = byId(d.ajCancel); if (jc) cancelJob(jc); return; }
      if (d.ajOpen) {
        var j = byId(d.ajOpen);
        if (!j || !j.open) return;
        if (j.open.kind === "team" && opts.openTeam) opts.openTeam(j.open.team_id, j.open.task_id);
        else if (j.open.kind === "chat" && j.open.session_id && opts.openChat) opts.openChat(j.open.session_id);
        else if (opts.openWork) opts.openWork(j.open.task_id);
      }
    });
    draw();
    load();
    return { reload: load, destroy: function () { alive = false; }, state: function () { return st; } };
  }

  var api = { html: html, jobHtml: jobHtml, filterHtml: filterHtml, assignHtml: assignHtml, mount: mount,
    setStrings: function (o) { STR = o || {}; } };
  if (typeof window !== "undefined") window.JavisAgentJobs = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})();
