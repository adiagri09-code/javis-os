/* Sáu reaction trên câu trả lời ở chat riêng (trang Trò chuyện chính và trang Cộng sự), T2 0.154.0.

   Hợp đồng: docs/dev/team-chat-t2-contract.md mục 4 và 6. Bảng emoji, chip, bộ chọn, trạng thái lấy từ reactions.js; file
   này chỉ nối chúng vào bong bóng trả lời của #chatArea (app.js gọi):

   - attach(el, info): bong bóng đã có mã tin (lịch sử: `m.id`) thì mang `data-mid`, `data-sid` và hàng reaction. Chưa có mã
     thì không có nút (không thả được lên tin chưa lưu).
   - expect(sid, el, entry): bong bóng vừa chốt của một lượt chờ gói `turn_saved` để nhận mã tin.
   - onFrame(data, hint): gói WS `turn_saved` (gắn mã cho bong bóng vừa chốt) và `chat_reaction` (vẽ lại mọi bong bóng của tin
     đó trong khung, kể cả khi đổi ở tab khác).
   - refresh(sid): sau F5 hỏi lại reaction của các tin đang hiện (bản lưu cục bộ có thể đã cũ).

   Gửi: POST /sessions/{sid}/messages/{mid}/reaction?brain=..., nonce giữ theo thao tác (reactions.js nonceKeeper): rớt mạng
   thì nút Thử lại gửi đúng nonce cũ. Không gọi model, không mở lượt. Chỉ bong bóng trả lời (role assistant) mới gắn.

   rowHtml và reactionUrl thuần (không DOM, không mạng) để test chạy dưới node. */
(function () {
  "use strict";

  var JR = (typeof window !== "undefined" && window.JavisReactions) || require("./reactions.js");
  var P = { prefix: "jr" };

  function tw(khoa, bien) {
    if (typeof window !== "undefined" && window.t) return window.t(khoa, bien);
    try {
      var s = require("./i18n/vi.json")[khoa] || khoa;
      return String(s).replace(/\{(\w+)\}/g, function (m, ten) {
        return (bien && bien[ten] != null) ? String(bien[ten]) : m;
      });
    } catch (e) { return khoa; }
  }
  var esc = JR.esc;
  var ic = function (n, o) { return (typeof window !== "undefined" && window.ic) ? window.ic(n, o) : ""; };

  function reactionUrl(sid, mid, brain) {
    return "/sessions/" + encodeURIComponent(sid) + "/messages/" + encodeURIComponent(mid) + "/reaction?brain=" +
      encodeURIComponent(brain || "brain");
  }

  // Hàng reaction dưới một bong bóng: nút mở bộ chọn, chip của chủ, trạng thái host ghi; bộ chọn khi mở; dòng lỗi kèm Thử lại.
  // st: {mid, reaction, open, draft, busy, error: {text, retry}}
  function rowHtml(st) {
    var mid = esc(st.mid);
    var R = st.reaction || null;
    var btn = '<button type="button" class="jr-react-btn" data-react-open="' + mid + '" aria-expanded="' +
      (st.open ? "true" : "false") + '" aria-label="' + esc(tw("teams.react")) + '" title="' + esc(tw("teams.react")) + '">' +
      ic("smile") + "</button>";
    var busy = st.busy ? '<span class="jr-react-busy" role="status">' + esc(tw("react.sending")) + "</span>" : "";
    var err = st.error ? '<div class="jr-react-err" role="alert"><span>' + esc(st.error.text) + "</span>" +
      (st.error.retry ? '<button type="button" class="ws-btn" data-react-retry="' + mid + '">' + esc(tw("react.retry")) +
        "</button>" : "") + "</div>" : "";
    return '<div class="jr-chat" data-jr-mid="' + mid + '"><div class="jr-row">' + btn + JR.chipHtml(R, { mid: st.mid, prefix: "jr" }) +
      JR.statusHtml(R, P) + busy + "</div>" + (st.open ? JR.pickerHtml(st.mid, R, { prefix: "jr", draft: st.draft || null }) : "") +
      err + "</div>";
  }

  var root = null;
  var cfg = {};
  var keeper = JR.nonceKeeper();
  var pending = {};   // session_id -> {el, entry}: bong bóng vừa chốt, chờ turn_saved

  function brainOf(st) {
    if (st.brain) return st.brain;
    try { return (cfg.brain && cfg.brain()) || "brain"; } catch (e) { return "brain"; }
  }

  function changed() { try { if (cfg.onChange) cfg.onChange(); } catch (e) {} }

  function render(el) {
    var st = el && el._jr;
    if (!st) return;
    var old = el.querySelector(".jr-chat");
    // Đang gõ góp ý mà có gói mới (trạng thái host đổi): giữ con trỏ trong ô góp ý.
    var act = typeof document !== "undefined" ? document.activeElement : null;
    var typing = old && act && old.contains(act) && act.classList.contains("jr-react-comment")
      ? { start: act.selectionStart, end: act.selectionEnd } : null;
    var wrap = document.createElement("div");
    wrap.innerHTML = rowHtml(st);
    var node = wrap.firstChild;
    if (old) old.parentNode.replaceChild(node, old);
    else {
      var acts = el.querySelector(".msg-acts");
      if (acts && acts.parentNode === el) el.insertBefore(node, acts.nextSibling); else el.appendChild(node);
    }
    if (typing) {
      var ta = node.querySelector(".jr-react-comment");
      if (ta) { ta.focus(); try { ta.setSelectionRange(typing.start, typing.end); } catch (e) {} }
    }
  }

  function attach(el, info) {
    if (!el || !info || info.mid == null || info.mid === "" || !info.sid) return false;
    el.dataset.mid = String(info.mid);
    el.dataset.sid = String(info.sid);
    if (info.sha) el.dataset.sha = String(info.sha);
    el._jr = { sid: String(info.sid), mid: String(info.mid), sha: info.sha || "", brain: info.brain || "",
      reaction: info.reaction || null, entry: info.entry || null, open: false, draft: null, busy: false, error: null };
    render(el);
    return true;
  }

  function expect(sid, el, entry) {
    if (!sid || !el) return;
    pending[sid] = { el: el, entry: entry || null };
  }

  function bubbles(sid, mid) {
    if (!root) return [];
    return Array.prototype.filter.call(root.querySelectorAll('.msg-javis[data-mid="' + String(mid).replace(/"/g, "") + '"]'),
      function (el) { return el._jr && el._jr.sid === String(sid); });
  }

  // Ghi reaction mới cho mọi bong bóng của tin (một tab có thể đang hiện cùng tin ở bản lưu cục bộ và bản vừa tải).
  function apply(sid, mid, R, quiet) {
    var list = bubbles(sid, mid);
    list.forEach(function (el) {
      el._jr.reaction = R || null;
      if (el._jr.entry) el._jr.entry.reaction = R || null;
      render(el);
    });
    if (list.length && !quiet) changed();
    return list.length;
  }

  function onFrame(data, hint) {
    if (!data) return false;
    if (data.type === "turn_saved") {
      var sid = data.session_id;
      var p = pending[sid];
      delete pending[sid];
      var el = (p && p.el) || (hint && hint.bubble) || null;
      if (!el || el.dataset.mid || data.message_id == null) return false;
      var entry = p && p.entry;
      if (entry) { entry.mid = data.message_id; entry.sha = data.content_sha || ""; entry.reaction = null; }
      attach(el, { sid: sid, mid: data.message_id, sha: data.content_sha || "", brain: el.dataset.rbrain || "",
        reaction: null, entry: entry });
      changed();
      return true;
    }
    if (data.type === "chat_reaction") return apply(data.session_id, data.message_id, data.reaction || null) > 0;
    return false;
  }

  function stateOf(t) {
    var box = t && t.closest && t.closest(".jr-chat");
    var el = box && box.closest(".msg-javis");
    return el && el._jr ? el : null;
  }

  function setOpen(el, open) {
    var st = el._jr;
    st.open = open;
    st.draft = null;
    render(el);
    var f = open ? el.querySelector(".jr-react-panel .jr-react-pick") : el.querySelector(".jr-react-btn");
    if (f) { try { f.focus(); } catch (e) {} }
  }

  function send(el, value, reasons, axis, comment) {
    var st = el._jr;
    var body = JR.payload(value, reasons, axis, comment, st.sha);
    var key = st.sid + "|" + st.mid;
    body.nonce = keeper.take(key, body);
    st.last = { value: value, reasons: reasons, axis: axis, comment: comment };
    st.busy = true;
    st.error = null;
    render(el);
    var done = function (code, j) {
      keeper.settle(key, code);
      st.busy = false;
      if (code === 200 && j && j.ok !== false) {
        st.open = false;
        st.draft = null;
        if (!apply(st.sid, st.mid, j.reaction || null)) { st.reaction = j.reaction || null; render(el); }
        return;
      }
      st.error = code === 0 ? { text: tw("react.err_network"), retry: true }
        : { text: tw("react.err", { e: (j && j.error) || code }), retry: code >= 500 };
      render(el);
    };
    return fetch(reactionUrl(st.sid, st.mid, brainOf(st)), {
      method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) { done(r.status, j || {}); });
    }, function () { done(0, null); });
  }

  function panelOf(el) { return el.querySelector(".jr-react-panel"); }

  function onClick(e) {
    var t = e.target && e.target.closest && e.target.closest(
      "[data-react-open],[data-react],[data-react-save],[data-react-clear],[data-react-close],[data-react-retry]");
    var el = t && stateOf(t);
    if (!el) return;
    var st = el._jr;
    var d = t.dataset;
    if (d.reactOpen != null) return setOpen(el, !st.open);
    if (d.reactClose != null) return setOpen(el, false);
    if (st.busy) return;
    if (d.reactRetry != null && st.last) return send(el, st.last.value, st.last.reasons, st.last.axis, st.last.comment);
    var cur = st.reaction || {};
    var form = JR.readPanel(panelOf(el), st.reaction, P);
    if (d.react != null) return send(el, JR.nextReaction(cur.value, d.react), form.reasons, form.axis, form.comment);
    if (d.reactSave != null) return send(el, cur.value || "none", form.reasons, form.axis, form.comment);
    if (d.reactClear != null) return send(el, "none", [], "", "");
  }

  // Lý do, trục, góp ý đang soạn: giữ qua lần vẽ lại khi có gói mới tới.
  function onEdit(e) {
    var el = stateOf(e.target);
    if (!el || !el._jr.open) return;
    el._jr.draft = JR.readPanel(panelOf(el), el._jr.reaction, P);
  }

  function onKey(e) {
    if (e.key !== "Escape") return;
    var el = stateOf(e.target);
    if (el && el._jr.open) { e.preventDefault(); setOpen(el, false); }
  }

  // Sau F5: khung dựng từ bản lưu cục bộ, reaction có thể đã đổi ở máy khác. Hỏi lại khúc tin cuối của phiên.
  function refresh(sid) {
    if (!root || !sid || typeof fetch !== "function") return Promise.resolve(0);
    if (!root.querySelector('.msg-javis[data-mid][data-sid="' + String(sid).replace(/"/g, "") + '"]')) return Promise.resolve(0);
    return fetch("/sessions/" + encodeURIComponent(sid) + "/messages?limit=30", { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var n = 0;
        ((d && d.messages) || []).forEach(function (m) {
          if (m.role === "assistant" && m.id != null && "reaction" in m) n += apply(sid, m.id, m.reaction || null, true);
        });
        if (n) changed();
        return n;
      }).catch(function () { return 0; });
  }

  function init(opts) {
    cfg = opts || {};
    if (root || !cfg.root) return;
    root = cfg.root;
    root.addEventListener("click", onClick);
    root.addEventListener("change", onEdit);
    root.addEventListener("input", onEdit);
    root.addEventListener("keydown", onKey);
    // Điện thoại: nhấn giữ bong bóng trả lời 500 ms mở bộ chọn (nút vẫn luôn hiện ở máy chạm).
    JR.bindLongPress(root, ".msg-javis[data-mid]", function (el) { if (el._jr && !el._jr.open) setOpen(el, true); });
  }

  var api = { init: init, attach: attach, expect: expect, onFrame: onFrame, apply: apply, refresh: refresh,
    rowHtml: rowHtml, reactionUrl: reactionUrl };
  if (typeof window !== "undefined") window.JavisChatReactions = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})();
