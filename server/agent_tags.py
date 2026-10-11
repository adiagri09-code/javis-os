"""Tag của agent (0.98.0): mỗi agent gắn nhiều tag, nhóm cũ thành một tag.

Hàm thuần, không đọc ghi file, để test được và để server, chỉ mục, giao diện hiểu tag giống nhau.
Hợp đồng đầy đủ: docs/dev/agent-tags.md.

- `tags` trong frontmatter là nguồn chuẩn khi khoá có mặt, kể cả danh sách rỗng.
- File cũ chưa có `tags`: `group` thật (chuỗi không rỗng) thành đúng một tag. Không suy từ nhãn
  "Chung" mà API cũ tự điền khi file không khai `group`.
- Chỉ áp cho AGENT. Workflow và skill vẫn dùng `group`.
"""
from __future__ import annotations

import json
import re
import unicodedata

TAG_MAX_CHARS = 40
TAGS_MAX = 20

_WS = re.compile(r"\s+")


class TagError(ValueError):
    """Mã lỗi máy (`tag_too_long`, `too_many_tags`, `bad_tags`), giao diện dịch sang câu người đọc."""


def normalize_tag(value) -> str:
    """Dạng chuẩn của một tag, "" nếu không phải tag. NFC, bỏ ký tự điều khiển, gộp khoảng trắng."""
    if not isinstance(value, str):
        return ""
    s = unicodedata.normalize("NFC", value)
    s = "".join(ch for ch in s if not unicodedata.category(ch).startswith("C") or ch in "\t\n\r")
    s = _WS.sub(" ", s).strip()
    if len(s) > TAG_MAX_CHARS:
        raise TagError("tag_too_long")
    return s


def tag_key(value) -> str:
    """Khoá so trùng: dạng chuẩn rồi casefold. Giữ dấu: "Viết" khác "Viet"."""
    return normalize_tag(value).casefold()


def normalize_tags(values, *, strict: bool = True) -> list:
    """Danh sách tag chuẩn, bỏ trùng theo `tag_key`, giữ cách viết gặp trước.

    `strict=False` (khi ĐỌC file): tag quá dài hay phần tử lạ thì bỏ qua thay vì ném lỗi, để một
    file sửa tay sai không làm hỏng cả danh sách agent.
    """
    out, seen = [], set()
    for v in values or []:
        try:
            t = normalize_tag(v)
        except TagError:
            if strict:
                raise
            continue
        k = t.casefold()
        if not t or k in seen:
            continue
        seen.add(k)
        out.append(t)
    if len(out) > TAGS_MAX:
        if strict:
            raise TagError("too_many_tags")
        out = out[:TAGS_MAX]
    return out


def tags_of(meta) -> list:
    """Tag của một agent đọc từ frontmatter (luật đọc tương thích)."""
    meta = meta if isinstance(meta, dict) else {}
    if "tags" in meta:
        raw = meta.get("tags")
        if isinstance(raw, str):
            raw = [raw]
        elif not isinstance(raw, (list, tuple)):
            raw = []
        return normalize_tags(raw, strict=False)
    g = meta.get("group")
    if isinstance(g, str) and g.strip():
        return normalize_tags([g], strict=False)
    return []


def write_tags(meta: dict, tags: list) -> dict:
    """Ghi dạng chuẩn vào `meta` (sửa tại chỗ và trả lại): `tags` + gương `group` để hạ phiên bản
    vẫn có nhãn. Không còn tag thì xoá `group`, để mã cũ hiện "Chung" chứ không hiện tag đã bỏ."""
    tags = normalize_tags(tags)
    meta["tags"] = list(tags)
    if tags:
        meta["group"] = tags[0]
    else:
        meta.pop("group", None)
    return meta


def parse_list(raw) -> list | None:
    """Tham số danh sách từ form: None = không gửi. Nhận JSON (danh sách chuỗi) hoặc một chuỗi đơn."""
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise TagError("bad_tags")
    s = raw.strip()
    if not s:
        return []
    if s.startswith("["):
        try:
            v = json.loads(s)
        except ValueError as e:
            raise TagError("bad_tags") from e
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            raise TagError("bad_tags")
        return v
    return [s]


def apply_ops(current: list, *, replace=None, add=None, remove=None) -> list:
    """Tập tag mới: thay cả tập (nếu có), rồi thêm, rồi bỏ theo khoá. Không gửi gì thì giữ nguyên."""
    out = normalize_tags(replace) if replace is not None else list(current or [])
    if add:
        out = normalize_tags(out + list(add))
    if remove:
        bo = {tag_key(x) for x in remove if tag_key(x)}
        out = [t for t in out if t.casefold() not in bo]
    return normalize_tags(out)


def from_old_group(current: list, group: str) -> list:
    """Luật tương thích cho client cũ chỉ gửi `group` (một nhóm). Agent đang có từ hai tag trở lên
    thì từ chối (`stale_client`): thay nhiều tag bằng một là mất dữ liệu. Còn lại: nhóm không rỗng
    thành đúng một tag, rỗng là bỏ tag (nghĩa cũ "về Chưa xếp nhóm")."""
    if len(current or []) > 1:
        raise TagError("stale_client")
    g = normalize_tag(group or "")
    return [g] if g else []


def rename(current: list, src: str, dst: str) -> tuple[list, bool]:
    """Đổi tag `src` thành `dst` trên một agent, giữ các tag khác và vị trí. Trả (tập mới, có đổi).
    `dst` trùng khoá một tag khác của agent thì gộp, không nhân đôi."""
    ks = tag_key(src)
    d = normalize_tag(dst)
    if not ks or not d:
        raise TagError("bad_tags")
    if not any(t.casefold() == ks for t in current or []):
        return list(current or []), False
    out = [d if t.casefold() == ks else t for t in current]
    out = normalize_tags(out)
    return out, out != list(current)
