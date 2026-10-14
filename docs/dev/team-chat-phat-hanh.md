# Nhóm chat team: tích hợp T0 tới T5 vào main, phát hành 0.138.0

Ngày 14/10/2026. Nhánh tích hợp `claude/team-chat-release`, PR [#649](https://github.com/blogminhquy/javis-os/pull/649).
Spec: [2026-10-13-team-chat-design.md](../superpowers/specs/2026-10-13-team-chat-design.md). Biên bản từng mốc:
`team-chat-t1.md` tới `team-chat-t5.md` (số phiên bản ghi trong các biên bản đó là số GIỮ CHỖ lúc làm, chưa từng phát hành).

## Chuỗi và cách tích hợp

Sáu PR chồng nhau, thẳng, không merge commit, cùng nền `bfb1c29f` (0.109.0):

| Mốc | PR | Head | Số giữ chỗ cũ | Commit trên nhánh tích hợp |
|---|---|---|---|---|
| T0 công tắc Cộng hưởng + tài liệu thiết kế | #627 | `83a1be54` | 0.110.0 | `57d5aa8e` |
| T1 lõi nhóm chat | #628 | `cee0159d` | 0.111.0 | `bb9c27e7` |
| T2 sáu reaction và góp ý | #639 | `a82c0d05` | 0.120.0 | `04347f98` |
| T3 Toàn quyền của trưởng nhóm | #640 | `c9f4d97c` | 0.121.0 | `dada3360` |
| T4 lịch sử dài, tìm, đo | #643 | `bc7d653b` | 0.124.0 | `69f59f75` |
| T5 trang Nhóm gọn, ảnh thật, ghim | #645 | `95db0f57` | 0.129.0 | `a37ae0f7` |

- **Cách làm:**
  - main đã đi thêm 38 commit (tới 0.137.0, `24cfe57c`). Nhánh tích hợp bắt đầu từ `origin/main`.
  - Áp phần thay đổi của từng PR so với PR trước đúng thứ tự phụ thuộc (`git diff prev..head`, `git apply --3way`), mỗi PR một commit, BỎ các commit giữ chỗ `VERSION` và CHANGELOG cũ.
  - Không đưa lại commit nào đã có trên main: main chưa chứa commit nào của chuỗi.
- **Xung đột văn bản:** không có. Số dòng thêm, bớt của từng file trong 61 file trùng khít giữa "chuỗi so với nền cũ" và "nhánh tích hợp so với main".
- **Bốn file main cũng đã sửa từ nền chung,** kiểm riêng từng file:
  - `dashboard/i18n/vi.json`, `en.json`: gộp đủ, hai bên cùng 3998 khoá, đúng định dạng.
  - `server/main.py`: phần đăng ký `/teams` vẫn nằm sau route cuối của main.
  - `tests/python/route_table.json`: chụp lại. 422 route của main giữ nguyên thứ tự, 25 route `/teams` nối sau.
- **Số phát hành 0.138.0:**
  - main đang ở 0.137.0; PR mở khác giữ số thấp hơn (#644 giữ 0.126.0, chuỗi giữ tới 0.129.0).
  - Giữ chỗ bằng commit đầu nhánh và PR nháp #649 trước khi tích hợp.

## Sửa khi phát hành

- **Nhãn snapshot đổi từ `.pre-0.111.0` thành `.pre-0.138.0`.** Áp cho `team_migration.py`, công cụ `tools/team_chat_restore_pre.py` (`.post-0.138.0-<thời điểm>`), chú thích ở `sessions.py`, `task_store.py`, `ui_targets.py`. Vì sao: 0.111.0 chưa từng phát hành, người dùng sẽ thấy file mang một số lạ.
- **Phép thử quay về chạy mã 0.137.0 thật** (`24cfe57c`, bản phát hành cuối trước nhóm chat) thay cho 0.109.0. Áp cho `test_team_rollback.py` và bước fetch trong `ci.yml`. Mã 0.137.0 mở được kho đã nâng, không nhặt việc nhóm; công cụ khôi phục đưa về đúng snapshot (31 ca).
- **Test mới `test_team_release.py`:** kho nhóm đời T1 (lược đồ chép nguyên văn, chưa có `pinned_at`, `identity_json`, `committed_at`) mở bằng mã phát hành thì tự thêm cột. Dữ liệu cũ giữ nguyên, ghim và chụp nhân dạng chạy được, mở lại lần hai không lỗi.
- **CHANGELOG một khối 0.138.0** ngắn theo điều người dùng thấy; các khối giữ chỗ 0.110.0 tới 0.129.0 không đưa lên main.

## Kiểm

Ghi ở mục cuối sau khi chạy đủ (máy local và CI đúng HEAD).
