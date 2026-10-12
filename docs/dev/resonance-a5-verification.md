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

(Kết quả chạy và smoke: điền khi bàn giao.)
