# Resonance A5: biên bản kiểm mã (12/10/2026)

Đội một agent làm, một agent review. Thiết kế đã chốt: [2026-10-11-resonance-a5-maker-reviewer-design.md](../superpowers/specs/2026-10-11-resonance-a5-maker-reviewer-design.md) (`56f7ab50`; phương án A cho file sửa tay). Hướng dẫn: [resonance-a5-team.md](resonance-a5-team.md).

**Trạng thái: mã chờ review.** Chưa pilot model thật, chưa merge, chưa phát hành, không đụng VPS. Mọi kiểm dưới đây dùng engine GIẢ; số lượt engine thật bằng 0.

## Test mới

| File | Nội dung | Ca |
|---|---|---|
| `tests/python/test_resonance_a5_team.py` | Luồng chính, gắn đội qua đường host thật (plugin `javis_goal`, route `/goal-requests`), bộ ghim và lịch, đồng thời, khởi động lại, tắt/bật/mất/nghỉ reviewer, file sửa tay và ảnh chụp, quyền và dừng, tag | T1 tới T4, T10 tới T14, T17 tới T29, T31 tới T46, T55 tới T60; parse đóng khi lỗi (T5, T26) |
| `tests/python/test_resonance_a5_budget.py` | Sổ vai, bảng vết V1, V2, V3, V5, V8, hoàn lượt, bộ đếm thử lại, lịch đối soát, vòng sửa | T5 tới T9, T15, T16, T47 tới T54, T61 tới T67 |
| `tests/python/test_resonance_a5_rollback.py` | Mã 0.100.0 THẬT (`a02663cb`, qua `git show`): nâng, hạ không khôi phục (ghi nhận giới hạn), script khôi phục, nâng lại | T30 |
| `tests/python/test_resonance_a5_api.py` | Route thật: chọn và bỏ chọn người review, từ chối trợ lý chưa bật hay chính nó, khối `team` của goal view, lệnh `team_detach` | 4.2, 11, 12 |
| `tests/python/test_resonance_a5_perf.py` | 200 mục tiêu có đội so với 200 không đội; timer 10 ms khi review lưu bằng chứng chậm | 14 |
| `tests/js/test_resonance_a5_ui.js` | Ô Người review (chỉ trợ lý đã bật, không theo tag), dòng đội, góp ý, hai nút và request của chúng, i18n | 11 |

Ca đi qua đường host thật dùng kho SQLite thật, `form_goal` thật (tool và API), cổng `_gate`, `R.advance` và `R.tick` thật; chỉ engine là giả (phân vai theo lời dặn hệ thống của lượt). Không chèn sẵn `goal_team` hay `reviews` vào fixture. Ngoại lệ có chủ đích, ghi rõ trong test: T12 sửa trực tiếp hàng review đang chạy để tạo kết luận lệch (chỉ có thể xảy ra khi dữ liệu bị can thiệp); T14, T15, T61, T62, T64, T66 gọi đúng các pha `_advance_prepare` và `_review_pre` của host rồi dừng giữa chừng để mô phỏng tiến trình chết hay huỷ ở đúng điểm đó.

## Bảng yêu cầu và test

| Yêu cầu (GOAL, thiết kế) | Test |
|---|---|
| Gắn đội trong giao dịch tạo, cả tool lẫn goal-requests; idempotent; không qua `assign_goal` | T31, T32, T33; T36 (mục tiêu cũ không có đội) |
| Danh tính bền hai vai, không chọn đội bằng tag | T46, T60; API (chọn theo slug, lưu mã); UI (ô không theo tag) |
| Cổng quyền, snapshot, bundle, parser đóng khi lỗi; kiểm lại bundle khi lưu kết quả và khi chốt | parse (T5, T26); T11, T12, T19, T43, T58, T59; `finish` từ chối không có review hợp lệ (chốt chặn ở kho) |
| Tổng 8, maker 4, reviewer 4, tối đa 2 vòng; không tự nâng | T1, T4, T7, T8, T47 tới T50 |
| `seq` chỉ lưu vết; trần 3 và backoff đếm `charged` của đúng bundle | T5, T14, T39, T61, T62, T63 |
| Chỉ hoàn khi chắc chưa gọi model; huỷ và engine không dựng được dùng chung đường hoàn, idempotent, không để `running` | T15, T53, T61, T64, T65 |
| Model có thể đã chạy thì tính lượt | T6, T14, T16, T23, T63 |
| Sau khởi động lại, đối soát bằng code, không thành lượt maker; thử lại đúng backoff và còn đủ lượt | T14, T39, T44, T66; T50 (không thử lượt cuối) |
| needs_changes thứ 1 và 2 cho sửa, thứ 3 dừng; lỗi thời/sai bản không tăng vòng | T3, T4, T47, T67, T12 |
| File sửa tay chờ, không gọi model, không chốt; chỉ dùng lại review khi bytes và bundle khớp; Bỏ yêu cầu review là thao tác chủ dự án | T10, T55, T56, T57; T24, T46 |
| Reviewer không có quyền ghi; trường lạ không đổi quyền hay hạn mức | T1 (file đích là bản của vai làm), T26 |
| Làn M của A3 bị kho chặn trên mục tiêu có đội | T51, T8 (không đề xuất phép thử) |
| I/O không chặn event loop; huỷ chờ pha ghi xong | perf (timer 10 ms); T16 (huỷ trong lúc gọi engine) |
| Hạ về 0.100.0 bằng snapshot | T30 |

## Kết quả chạy (máy local, `.venv` của checkout gốc, mã tại `0ae4cc2b`)

| Lệnh | Kết quả |
|---|---|
| `python tests/python/test_resonance_a5_team.py` | 86 ok, exit 0 |
| `python tests/python/test_resonance_a5_budget.py` | 31 ok, exit 0 |
| `python tests/python/test_resonance_a5_rollback.py` | 11 ok, exit 0 (mã 0.100.0 thật) |
| `python tests/python/test_resonance_a5_api.py` | 10 ok, exit 0 |
| `python tests/python/test_resonance_a5_perf.py` | 5 ok, exit 0 (200 thẻ có đội chậm hơn khoảng 7 ms mỗi thẻ so với không đội; timer 10 ms đúng giờ khi review lưu bằng chứng chậm 0,2 giây) |
| `node tests/js/test_resonance_a5_ui.js` | 32 ok, exit 0 |
| `tests/run.py resonance route_table i18n version_khop_changelog nhat_ky_song_ngu tai_lieu_song_ngu ignore_files phien_ban_moi_nhat prompt_budget prefix_slim agent_tags workspace` | 63/63 file xanh, exit 0 |
| Toàn repo `tests/run.py` (mã tại `5048fc4d`, trước các commit cuối chỉ đổi câu báo, test và tài liệu) | 639/654. 14 file đỏ trùng khít khi chạy cùng 14 file trên bản xuất `main` sạch `a02663cb` (các test phụ thuộc máy: agy_prompt_dai, antigravity_cli, ba_loi_mac_va_telegram, cai_windows, grok_cli, install_admin, khoi_dong_nhe, link_file_uri, machine_translations, memory_hoa_thuong, model_theo_phien, ollama_local, terminal, windows_no_console). File đỏ thứ 15 là `test_resonance_a2_ui.js`: đếm số nhãn lý do thức là 24, A5 thêm đúng 6 nhãn; đã cập nhật thành 30 và chạy xanh trong nhóm trên |

## Lỗi tìm ra khi viết mã, đã sửa, và đối chứng

Chạy test cuối trên đúng cây mã trước mỗi lần sửa (bản xuất `git archive`, chép test hiện tại vào):

| Lỗi | Sửa ở | Đỏ trên mã trước sửa |
|---|---|---|
| Kết luận `stale` hay `review_mismatch` không hẹn lần thức nào, mục tiêu đứng yên | `2b264122` (`record_review`, `review_interrupted` hẹn `review_done` chỉ-kiểm) | T12, T19, T43 trên `3c290b5c` |
| So bản sửa tay bằng `current_artifact_ref`, mà hàm này trả rỗng ở revision mới chưa có lượt làm, nên revision mới bị coi là sửa tay | `2b264122` (`_disk_sha`) | T11, T37 trên `3c290b5c` |
| Hẹn `action_recovery` chỉ-kiểm còn sau khi lượt review xong, kéo lịch vật lý sớm hơn backoff | `2b264122` (`_drop_idle_action_recovery`) | T39 trên `3c290b5c` |
| Tin mới của người dùng trên mục tiêu có đội vấp cờ `use_hold` (tiếp quản lượt giữ nếu có), lượt làm bị từ chối | `2b3ab099` (bỏ qua `use_hold` khi có đội, chỉ từ chối `require_hold`) | T8, T51 trên `2b264122` |
| Engine của lượt review không dựng được: hàng ghi lý do chung, và chờ kiểm lại so giờ kho (giờ thật) với giờ lần thức, nên lượt review thử dựng lại ngay | `2b3ab099` (lý do `engine_not_ready`; chờ theo hẹn `review_recheck` cùng đồng hồ với lần thức) | T53, T65 trên `2b264122` |

Output: `a5-control-team-on-3c290b5c.txt`, `a5-control-budget-on-2b264122.txt` (thư mục bằng chứng, ngoài git).

## Test cũ phải sửa vì hành vi đổi theo thiết kế

- `test_resonance_a3_learning.py`: phiên bản chính sách nhịp tim `heartbeat.v2` thành `heartbeat.v3` (thiết kế mục 10); kiểm thêm hai lớp của A3 giữ nguyên.
- `test_resonance_a2_ui.js`: số nhãn lý do thức trên thẻ 24 thành 30 (sáu mã A5).
- `tests/python/route_table.json`: thêm đúng một route ở cuối (`POST /resonance/agents/reviewer`), thứ tự route cũ không đổi.

## Smoke giao diện trên sandbox (engine giả)

Server sandbox cổng 7788 chạy mã của worktree; state và brain tạm (trong `.playwright-mcp/sbx`, đã gitignore, đường ngắn để tránh giới hạn 260 ký tự của Windows), nhịp Cộng hưởng chạy thật, `main._resonance_engine` thay bằng engine giả hai vai đọc kịch bản từ một file điều khiển. Chromium qua Playwright, tiếng Việt, desktop 1366x860 và khổ hẹp 375x812. Bật Cộng hưởng và chọn người review làm trên giao diện; mục tiêu gieo bằng `form_goal` thật (giả lập lượt chat lập mục tiêu, không có lượt chat thật).

Đạt, đối chiếu kho:
- Ô Người review chỉ liệt kê trợ lý đã bật Cộng hưởng (không có "Trợ lý tắt"); chọn xong host lưu cặp theo mã.
- Mục tiêu 1: bấm Cho phép trên thẻ; lượt làm đăng bản đầu, review "cần sửa"; thẻ hiện "Làm: nguoi-lam · Review: nguoi-duyet", "Bản đã review: 7cdeda8d · Cần sửa (vòng 1/2)", "Đang chờ nguoi-lam sửa theo góp ý", "Lượt còn: làm 3/4 · review 3/4" và góp ý. Lượt sửa đăng bản mới, review đạt, mục tiêu đạt; lượt (2, 2, 4); file đích là bản sửa.
- Mục tiêu 2: tắt người review trước nhịp đầu: `blocked/reviewer_off`, 0 lượt model; thẻ có hai nút. Bấm Bật lại người review, hộp xác nhận thật nói rõ "tính một lượt review", đồng ý: mục tiêu thức lại, làm, review, đạt; lượt (1, 1, 2).
- Mục tiêu 3: người review tắt, bấm Bỏ yêu cầu review: Huỷ ở hộp xác nhận không gửi gì (kho không đổi); Đồng ý: thẻ "Đã bỏ yêu cầu review", mục tiêu chốt theo luật thường với 1 lượt làm, 0 lượt review.
- Khổ 375 px: thẻ hiện đủ dòng đội, không cuộn ngang (`scrollWidth = innerWidth = 375`).

Ảnh: `a5-s01-reviewer-picker.png`, `a5-s02-needs-changes.png`, `a5-s03-reviewer-off.png`, `a5-s04-narrow-375.png`.

Chưa quan sát trên giao diện (đã có test hành vi): file sửa tay trên thẻ (T10, T55 tới T57), hết vòng (T4), hết lượt (T7, T8), review không đọc được (T5, T50). Lỗi console trong smoke là của trang có sẵn (`/tools/optional` 401, mã phiên cũ của sandbox trước 404), không liên quan A5.

## Ranh giới bằng chứng và giới hạn còn lại

- Mọi kiểm dùng engine giả; số lượt engine thật bằng 0. Chưa pilot, chưa đo VPS.
- Mục tiêu `maintain` không "kết thúc" nên A5 không chặn ở đó: review chỉ chặn chốt đạt và chuyển sang chờ người xác nhận của mục tiêu `achieve`. Ghi rõ để reviewer quyết có cần mở rộng không.
- Sau `team_detach`, lượt mới tính vào tổng của mục tiêu nhưng không vào `team_calls` (sổ vai giữ nguyên làm hồ sơ), đúng thiết kế mục 6.2.
- Lượt VIỆC của mục tiêu có đội khi engine không dựng được giữ hành vi A2 (kết sổ lỗi cố định `engine_blocked`) cộng hoàn phần maker; chỉ lượt REVIEW đi qua `_refund_not_run` đầy đủ. Hai đường đều hoàn đúng một lần.
