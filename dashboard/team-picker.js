/* Hộp chọn thành viên nhóm kiểu Zalo (0.142.0): dùng cho Tạo nhóm và Thêm thành viên ở trang Nhóm.
 *
 * Máy tính: hộp giữa màn hình. Điện thoại (<= 640px): màn đầy đủ, footer cố định ở đáy. Gồm:
 * - ô tìm KHÔNG CẦN DẤU (tên, vai, mã, tag);
 * - hàng chip tag lấy từ trang Cộng sự (cùng tag của trợ lý), lọc một tag mỗi lần, đổi lọc KHÔNG mất người đã chọn;
 * - dòng trợ lý có ảnh, tên, vai; hàng chip người đã chọn (bấm x để bỏ);
 * - người tạo tự hiện "Bạn · Người tạo nhóm/quản lý", tách khỏi ô Điều phối (AI); Điều phối chỉ chọn trong người đã chọn;
 * - footer cố định: số đã chọn, Huỷ, nút chính.
 *
 * File này chỉ có hàm THUẦN (trạng thái vào, HTML ra). teams.js giữ trạng thái, gọi API và gắn sự kiện.
 */
(function () {
  "use strict";

  function tw(khoa, bien) {
    var s = (typeof window !== "undefined" && window.t) ? window.t(khoa, bien) : khoa;
    if (s === khoa && typeof module !== "undefined" && module.exports && FALLBACK[khoa]) s = FALLBACK[khoa];
    if (bien) {
      s = String(s).replace(/\{(\w+)\}/g, function (m, ten) {
        return Object.prototype.hasOwnProperty.call(bien, ten) ? String(bien[ten]) : m;
      });
    }
    return s;
  }
  var FALLBACK = {};   // test dưới node nạp vi.json vào đây qua setStrings

  function esc(t) {
    return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  var ic = function (n, o) { return (typeof window !== "undefined" && window.ic) ? window.ic(n, o) : ""; };

  // Bỏ dấu tiếng Việt và hoa thường để tìm "khong dau" ra "Không dấu". "đ" không phải dấu ghép nên đổi tay.
  function fold(s) {
    s = String(s == null ? "" : s);
    if (s.normalize) s = s.normalize("NFD").replace(/[̀-ͯ]/g, "");
    return s.replace(/\u0111/g, "d").replace(/\u0110/g, "D").toLowerCase().trim();
  }

  function live(roster) {
    return (roster || []).filter(function (a) { return a && a.slug && a.status !== "retired" && a.status !== "missing"; });
  }

  // Tag của trang Cộng sự, theo khoá host cấp (`tag_keys`) để "Bán hàng" và "bán hàng" là một chip. Đếm số trợ lý.
  function tagsOf(roster) {
    var by = {}, order = [];
    live(roster).forEach(function (a) {
      (a.tags || []).forEach(function (t, i) {
        var key = (a.tag_keys || [])[i] || fold(t);
        if (!by[key]) { by[key] = { key: key, label: t, count: 0 }; order.push(key); }
        by[key].count++;
      });
    });
    return order.map(function (k) { return by[k]; }).sort(function (x, y) { return y.count - x.count || (x.label < y.label ? -1 : 1); });
  }

  function hasTag(a, key) {
    return (a.tags || []).some(function (t, i) { return ((a.tag_keys || [])[i] || fold(t)) === key; });
  }

  // Trợ lý hiện trong danh sách: theo tag đang lọc và chữ đang tìm. Người đã chọn VẪN được giữ trong `st.selected` dù bị
  // lọc khỏi danh sách (đổi bộ lọc không làm mất lựa chọn).
  function visible(roster, st) {
    var q = fold(st.query);
    var skip = {};
    (st.exclude || []).forEach(function (s) { skip[s] = true; });
    return live(roster).filter(function (a) {
      if (skip[a.slug]) return false;
      if (st.tag && !hasTag(a, st.tag)) return false;
      if (!q) return true;
      return [a.name, a.role, a.slug].concat(a.tags || []).some(function (x) { return fold(x).indexOf(q) >= 0; });
    });
  }

  function bySlug(roster, slug) {
    var all = roster || [];
    for (var i = 0; i < all.length; i++) if (all[i].slug === slug) return all[i];
    return null;
  }

  // Bật/tắt một người. Bỏ đúng người đang Điều phối thì Điều phối chuyển cho người đầu còn lại (nếu chủ chưa tự chọn
  // thì luôn là người đầu tiên). Trả trạng thái MỚI, không sửa trạng thái cũ.
  function toggle(st, slug) {
    var sel = (st.selected || []).slice();
    var i = sel.indexOf(slug);
    if (i >= 0) sel.splice(i, 1); else sel.push(slug);
    return normalize(Object.assign({}, st, { selected: sel }));
  }

  function normalize(st) {
    var sel = st.selected || [];
    var leader = st.leader || "";
    // Người Điều phối bị bỏ chọn: chuyển cho người đầu còn lại. Chưa ai tự chọn Điều phối: mặc định người đầu tiên. Chủ đã
    // chủ động chọn "Chưa chọn" thì giữ trống.
    if (leader && sel.indexOf(leader) < 0) leader = sel[0] || "";
    else if (!leader && !st.leaderTouched) leader = sel[0] || "";
    return Object.assign({}, st, { leader: leader });
  }

  // Tên nhóm để trống: như Zalo, ghép tên ba người đầu.
  function autoName(st, roster) {
    return (st.selected || []).slice(0, 3).map(function (s) { var a = bySlug(roster, s); return a ? (a.name || a.slug) : s; })
      .join(", ");
  }

  function canSubmit(st) {
    return !st.saving && (st.selected || []).length > 0;
  }

  function face(a, size) {
    var A = typeof window !== "undefined" && window.JavisAvatar;
    if (A && A.html && a && a.slug) {
      return '<span class="tmp-face" aria-hidden="true">' + A.html({ slug: a.slug, avatar: a.avatar || undefined }, size) + "</span>";
    }
    var n = String((a && (a.name || a.slug)) || "?").trim();
    return '<span class="tmp-face tmp-initial" aria-hidden="true">' + esc(n.charAt(0).toUpperCase()) + "</span>";
  }

  function tagsHtml(roster, st) {
    var tags = tagsOf(roster);
    if (!tags.length) return "";
    var chip = function (key, label, n) {
      var on = (st.tag || "") === key;
      return '<button type="button" class="tmp-chip' + (on ? " is-on" : "") + '" data-pick-tag="' + esc(key) + '" aria-pressed="' +
        (on ? "true" : "false") + '">' + esc(label) + (n != null ? ' <span class="tmp-chip-n">' + n + "</span>" : "") + "</button>";
    };
    return '<div class="tmp-tags" role="group" aria-label="' + esc(tw("teams.pick.tags")) + '">' +
      chip("", tw("teams.pick.all"), null) + tags.map(function (t) { return chip(t.key, t.label, t.count); }).join("") + "</div>";
  }

  function selectedHtml(roster, st) {
    var sel = st.selected || [];
    if (!sel.length) return '<div class="tmp-selected tmp-selected-empty">' + esc(tw("teams.pick.none_selected")) + "</div>";
    return '<div class="tmp-selected" aria-label="' + esc(tw("teams.pick.selected_label")) + '">' + sel.map(function (s) {
      var a = bySlug(roster, s) || { slug: s, name: s };
      return '<span class="tmp-sel">' + face(a, 24) + '<span class="tmp-sel-name">' + esc(a.name || a.slug) + "</span>" +
        '<button type="button" class="tmp-sel-x" data-pick-toggle="' + esc(s) + '" aria-label="' +
        esc(tw("teams.pick.unselect", { name: a.name || a.slug })) + '">' + ic("x") + "</button></span>";
    }).join("") + "</div>";
  }

  function listHtml(roster, st) {
    var rows = visible(roster, st);
    var sel = st.selected || [];
    var owner = st.mode === "create" ? '<div class="tmp-row tmp-owner"><span class="tmp-face tmp-initial tmp-you" aria-hidden="true">' +
      esc(tw("teams.pick.you").charAt(0)) + '</span><span class="tmp-text"><span class="tmp-name">' + esc(tw("teams.pick.you")) +
      '</span><span class="tmp-role">' + esc(tw("teams.pick.you_role")) + '</span></span><span class="tmp-badge">' +
      esc(tw("teams.pick.owner_badge")) + "</span></div>" : "";
    if (!rows.length) {
      return owner + '<div class="tmp-empty">' + esc(tw(live(roster).length ? "teams.pick.no_match" : "teams.pick.no_agents")) + "</div>";
    }
    return owner + rows.map(function (a) {
      var on = sel.indexOf(a.slug) >= 0;
      var sub = a.role || (a.tags || []).join(" · ");
      return '<label class="tmp-row' + (on ? " is-on" : "") + '"><input type="checkbox" class="tmp-check" data-pick-slug="' +
        esc(a.slug) + '"' + (on ? " checked" : "") + ">" + face(a, 40) + '<span class="tmp-text"><span class="tmp-name">' +
        esc(a.name || a.slug) + "</span>" + (sub ? '<span class="tmp-role">' + esc(sub) + "</span>" : "") +
        '</span><span class="tmp-tick" aria-hidden="true">' + (on ? ic("check") : "") + "</span></label>";
    }).join("");
  }

  function leaderHtml(roster, st) {
    if (st.mode !== "create") return "";
    var sel = st.selected || [];
    var opts = '<option value="">' + esc(tw("teams.pick.leader_none")) + "</option>" + sel.map(function (s) {
      var a = bySlug(roster, s) || { slug: s, name: s };
      return '<option value="' + esc(s) + '"' + (st.leader === s ? " selected" : "") + ">" + esc(a.name || a.slug) + "</option>";
    }).join("");
    return '<label class="tmp-leader"><span class="tmp-leader-label">' + esc(tw("teams.pick.leader")) + "</span>" +
      '<select class="tmp-leader-pick"' + (sel.length ? "" : " disabled") + ">" + opts + "</select>" +
      '<span class="tmp-help">' + esc(tw("teams.pick.leader_help")) + "</span></label>";
  }

  function footerHtml(st) {
    var n = (st.selected || []).length;
    var main = st.mode === "create" ? tw(st.saving ? "teams.pick.creating" : "teams.pick.create")
      : tw(st.saving ? "teams.pick.adding" : "teams.pick.add", { n: n });
    return '<div class="tmp-foot"><span class="tmp-count">' + esc(tw("teams.pick.count", { n: n })) + "</span>" +
      '<button type="button" class="ws-btn tmp-cancel">' + esc(tw("teams.pick.cancel")) + "</button>" +
      '<button type="button" class="ws-btn tm-primary tmp-submit"' + (canSubmit(st) ? "" : " disabled") + ">" + esc(main) +
      "</button></div>";
  }

  function html(st, roster) {
    var create = st.mode === "create";
    var title = tw(create ? "teams.pick.title_create" : "teams.pick.title_add");
    var head = '<div class="tmp-head"><h2 class="tmp-title" id="tmp-title">' + esc(title) + "</h2>" +
      '<button type="button" class="tmp-close tmp-cancel" aria-label="' + esc(tw("teams.pick.close")) + '">' + ic("x") +
      "</button></div>";
    var name = create ? '<div class="tmp-namebox"><label class="tmp-field"><span>' + esc(tw("teams.name")) + "</span>" +
      '<input class="tmp-name-input" maxlength="120" value="' + esc(st.name || "") + '" placeholder="' +
      esc(tw("teams.pick.name_ph")) + '"></label><label class="tmp-field"><span>' + esc(tw("teams.description")) + "</span>" +
      '<input class="tmp-desc-input" maxlength="2000" value="' + esc(st.desc || "") + '" placeholder="' +
      esc(tw("teams.pick.desc_ph")) + '"></label></div>' : "";
    var err = st.error ? '<div class="tmp-error" role="alert">' + esc(st.error) + "</div>" : "";
    return '<div class="tmp-layer"><div class="tmp-scrim tmp-cancel"></div><div class="tmp-dialog" role="dialog" aria-modal="true" ' +
      'aria-labelledby="tmp-title">' + head + '<div class="tmp-body">' + name +
      '<div class="tmp-search"><span class="tmp-search-ico" aria-hidden="true">' + ic("search") + "</span>" +
      '<input class="tmp-search-input" type="search" value="' + esc(st.query || "") + '" placeholder="' +
      esc(tw("teams.pick.search_ph")) + '" aria-label="' + esc(tw("teams.pick.search_ph")) + '"></div>' +
      '<div class="tmp-tags-box">' + tagsHtml(roster, st) + "</div>" +
      '<div class="tmp-selected-box">' + selectedHtml(roster, st) + "</div>" +
      '<div class="tmp-list" role="list">' + listHtml(roster, st) + "</div>" +
      '<div class="tmp-leader-box">' + leaderHtml(roster, st) + "</div>" + err + "</div>" +
      '<div class="tmp-foot-box">' + footerHtml(st) + "</div></div></div>";
  }

  var api = { fold: fold, tagsOf: tagsOf, visible: visible, toggle: toggle, normalize: normalize, autoName: autoName,
    canSubmit: canSubmit, html: html, listHtml: listHtml, selectedHtml: selectedHtml, tagsHtml: tagsHtml,
    leaderHtml: leaderHtml, footerHtml: footerHtml,
    setStrings: function (o) { FALLBACK = o || {}; } };
  if (typeof window !== "undefined") window.JavisTeamPicker = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})();
