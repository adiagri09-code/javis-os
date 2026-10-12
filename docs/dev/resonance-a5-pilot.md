# Resonance A5: kịch bản và bộ chạy pilot

**Trạng thái:** mã A5 đạt review mã vòng 2 tại `05e9b065` (Codex, 12/10/2026). **Pilot chưa chạy.** A5 chưa nghiệm thu cuối, chưa phát hành. Bộ chạy và dry ở đây không gọi model thật. Chỉ chạy real sau khi chủ dự án duyệt riêng đơn xin pilot ghim SHA cuối; review mã không cấp quyền đó.

Thiết kế: [2026-10-11-resonance-a5-maker-reviewer-design.md](../superpowers/specs/2026-10-11-resonance-a5-maker-reviewer-design.md). Biên bản kiểm mã: [resonance-a5-verification.md](resonance-a5-verification.md).

## Pilot chứng minh gì, và không chứng minh gì

Chứng minh bằng model thật, trên đường host thật (server thật, kho thật, nhịp Cộng hưởng thật, API thật của trang trợ lý và thẻ):

1. Việc nền của **vai làm** (agent làm, engine việc nền) viết một bản đạt kiểm khách quan. Host đăng đúng bytes vào file đích theo quyền A4 mà chủ đã cấp.
2. Việc nền của **vai review** (agent khác danh tính, lời dặn review, cùng engine việc nền theo thiết kế) đọc ảnh chụp của đúng bản đã tiếp nhận (hash, revision, mã reviewer đã ghim) và ra một kết luận đọc được.
3. Nhánh xảy ra thật được ghi đúng như nó xảy ra:
   - đạt ngay; hoặc
   - cần sửa, vai làm sửa theo góp ý, rồi review lại.

   Không ép nhánh, không chạy lại để có kết quả đẹp.
4. Giết rồi dựng lại server: không lượt nào được gọi thêm, kể cả thử gọi.

Không chứng minh:
- Bộ não chat tự định tuyến tới `javis_goal`: mục tiêu được lập bằng `form_goal` với đề xuất đóng băng, xem mục "Lập mục tiêu"; điểm này đã có ở pilot A4.
- Hai vai là hai model độc lập: theo thiết kế, hai vai dùng chung engine việc nền.
- Nhánh hai vòng sửa tới cùng, thử lại sau `unknown` hay sau lỗi engine: các nhánh đó cần thêm lượt hoặc hẹn một giờ, vượt trần pilot đề xuất. Chúng đã có test bằng engine giả.
- Hiệu năng hay độ trễ trên VPS: pilot chạy trên máy local.

## Kịch bản

**Đầu vào đóng băng** (`FROZEN` trong `tests/python/test_resonance_a5_pilot.py`), băm thành `frozen_sha256`. Real từ chối chạy nếu hash khác bộ đã duyệt.
- Hai trợ lý: `nguoi-lam-tom-tat` (làm) và `nguoi-duyet-tom-tat` (review), thân file cố định.
- Lời giao (dữ liệu mô phỏng): bản tóm tắt cuộc họp ở `Inbox/tom-tat-hop-a5.md`, có mục Kết luận và mục Việc tiếp theo (mỗi việc một dòng, có người phụ trách và hạn), kèm nội dung họp.
- Đề xuất mục tiêu: hai tiêu chí `artifact_contract` trên file đích, phải có "Kết luận" và "Việc tiếp theo"; `achieve/delivery`.

**Lập mục tiêu.** Không dùng lượt chat. Bộ chạy gọi `form_goal` với lời giao và đề xuất đóng băng, trong phiên của agent làm. Đây đúng là hàm mà tool `javis_goal` và route `/goal-requests` dùng, và không gọi model. `/goal-requests` không dùng được vì nó để bộ lập mục tiêu gọi một lượt model và tự đặt tiêu chí, nên tiêu chí không đóng băng được. Đây là gieo trạng thái bằng hàm host thật, không phải engine giả.

**Các bước:**

| Bước | Server | Việc | Lượt model |
|---|---|---|---|
| 0 | không | Cổng chi phí (trần pilot ≤ số đã duyệt, đủ cho nhánh ngắn nhất), tạo sổ (từ chối nếu đã có), cổng engine và xác thực (engine việc nền đúng cấu hình đã duyệt; `claude auth status` là gói thuê bao gốc; không có apiKeyHelper, env chọn nhà cung cấp hay settings do quản trị đặt) | 0 |
| A | nhịp tạm dừng, trần kho 0, trần sổ 0 | Bật hai trợ lý qua `/resonance/agents/toggle`. Chọn người review qua `/resonance/agents/reviewer`. Lập mục tiêu (`form_goal`). Cho phép phạm vi qua lệnh `approve_scope` của thẻ. Kiểm đội đã gắn (ghim mã reviewer, 8 lượt chia 4/4, hai vòng), phạm vi đã cấp, chưa có file đích | 0 |
| B | nhịp chạy, trần kho = trần tổng pilot, trần sổ theo vai | Tiền điều kiện (hai trợ lý còn bật, đội còn ghim đúng mã, không kiểm nào hỏng), cổng token (còn ít nhất 30 phút). Quan sát tới khi mục tiêu kết thúc, sổ đóng, hay không còn lịch làm việc trong 5 phút và không có lượt đang chạy; trần thời gian 30 phút | theo nhánh, tối đa 4 |
| C | nhịp chạy, trần kho = số đã dùng, trần sổ 0 | Chờ khoảng 95 giây (hơn ba nhịp). Sổ không có lượt hay lần thử mới; hành động và hàng review không đổi. Tạm dừng mục tiêu nếu còn mở | 0 |

**Nhánh có thể xảy ra** (bộ chạy đọc từ kho, ghi `branch`):

| Nhánh | Diễn biến | Lượt làm / review | Kết cục |
|---|---|---|---|
| `pass_first` | Làm, review pass, chốt đạt | 1 / 1 | `succeeded` |
| `one_fix_then_pass` | Làm, review cần sửa, sửa theo góp ý, review pass, chốt đạt | 2 / 2 | `succeeded` |
| `pilot_cap_after_two_reviews` | Hai lần cần sửa; lượt sửa thứ hai bị trần pilot chặn, không gọi model. Lớp chặn trước là trần kho, chặn ngay lúc giữ chỗ (`blocked/budget`, dry thấy đúng như vậy). Nếu trần kho không chặn thì sổ pilot chặn trước khi dựng engine (`blocked/engine_blocked`, host hoàn lượt) | 2 / 2 | mục tiêu mở, tạm dừng |
| `review_unknown` | Review không đọc được; host hẹn thử lại sau một giờ, pilot không chờ | 1 / 1 | mục tiêu mở, tạm dừng |
| `maker_error` | Lượt làm đầu lỗi; sổ đóng | 1 / 0 | mục tiêu mở, tạm dừng |
| `no_review`, `other` | Không khớp các nhánh trên; ghi nguyên, không suy diễn | tối đa 2 / 2 | tạm dừng |

## Hạn mức

| | Sản phẩm (A5, không đổi) | Pilot đề xuất |
|---|---|---|
| Tổng lượt việc nền của mục tiêu | 8 | 4 |
| Vai làm | 4 | 2 |
| Vai review | 4 | 2 |
| Vòng sửa | 2 | 1 vòng trọn (vòng sửa thứ hai bị trần pilot chặn) |
| Lượt chat | không áp dụng | 0 |

Đơn vị là **lượt engine cấp host**: một lần dựng engine cho một lượt làm hay review. Không phải request nội bộ của SDK, cũng không phải token.

Các lớp chặn (không lớp nào thay lớp nào):
- **Sổ lượt theo vai của pilot** (`tests/python/_a5_pilot_ledger.py`, launcher `tests/python/_a5_pilot_server.py`).
  - Giữ chỗ và fsync TRƯỚC khi dựng engine cho mỗi lượt.
  - Có trần vai, trần tổng và trần theo giai đoạn (A và C là 0).
  - Lượt lỗi, huỷ, ngoại lệ, không dựng được hay thiếu khung kết thúc vẫn tính, và sổ đóng ngay.
  - Bị chặn thì không chạm hàm dựng engine thật; host hoàn lượt theo đường not-run của A5. Sổ chỉ ghi một sự kiện `refused`.
  - Sổ đã có thì từ chối chạy; sổ hỏng thì không cấp lượt và không ghi đè.
- **Trần kho** `JAVIS_RESONANCE_CALL_CEILING`, áp cho mọi tiến trình server.
- **Trần sản phẩm** của đội (8, 4/4, hai vòng).
- **Hậu kiểm.** Sổ pilot phải khớp sổ vai của kho (`team_calls`) và `calls_used`; mỗi hàng review tính (`charged=1`) ứng với một lượt reviewer. Sổ thiếu, hỏng hay lệch là **chưa xác minh**, không bao giờ là 0.

Không thử lại, không nâng trần, không chuyển sang API trả phí. Settings của sandbox chỉ chép tên provider/model (`auxiliary`, `main`, `engine`, `claude_model`), không chép khoá hay chế độ xác thực.

## Bằng chứng mỗi điểm

| Điều cần chứng minh | Bằng chứng (`a5-pilot-real-main.json` và các file kèm) |
|---|---|
| Người làm | Hành động `work` mang `agent_key` của agent làm, `role=maker`, mốc `engine_at`; dòng sổ `maker` với provider/model; đầu ra `a5-maker-<n>.md` |
| Người review | Hành động `review` và hàng `reviews` mang mã reviewer đã ghim (khác mã agent làm), `role=reviewer`, mốc `engine_at`; dòng sổ `reviewer`; đầu ra thô `a5-reviewer-<n>.txt` (đọc từ bằng chứng đã mã hoá của host); kết luận, tiêu chí, góp ý trong `store_B.reviews` |
| Đúng hash, revision | `bundle_ref` mang đúng revision, mốc đăng, hash, mã reviewer. Hash là bytes chuẩn hoá của một đầu ra lượt làm. Ảnh chụp reviewer đã đọc băm lại đúng hash. Chốt đạt: file đích đúng bytes bản được review pass, cùng revision |
| Vòng sửa (nếu xảy ra) | Hàng `needs_changes`, lượt làm sau đó, lượt review mới trên bộ ghim mới |
| Dựng lại không gọi thêm | `restart`: không có dòng sổ, sự kiện, hành động hay hàng review mới |
| Không đụng file khác | Ảnh chụp brain trước và sau giai đoạn B: chỉ file đích đổi; ghi chú cũ còn nguyên |

Kết luận của lần chạy real là `pending_content_review` (kỹ thuật đạt, chờ người đọc nội dung), `technical_failed` hay `stopped`. Không có kết luận "đạt" tự động về nội dung.

## Dry

`JAVIS_RESONANCE_A5_PILOT=dry python tests/python/test_resonance_a5_pilot.py` chạy 12 ca, mỗi ca một tiến trình con với server thật. Dry chặn đường tới engine thật ngay từ cấu hình và đường gọi, không chỉ đếm sau khi chạy:
- settings dùng provider không tồn tại (`pilot-dry`);
- launcher thay hàm dựng engine việc nền bằng engine giả đọc kịch bản; hàm dựng "thật" là bẫy;
- không có lượt chat nào.

Mỗi ca còn xác minh sổ lượt engine của chính server sandbox (`usage.json` và `usage-events.jsonl`) bằng 0.

| Ca | Kỳ vọng |
|---|---|
| `main_pass`, `main_fix` | Nhánh `pass_first` (1, 1), `one_fix_then_pass` (2, 2); mọi kiểm bằng chứng đạt |
| `fix_cap` | `pilot_cap_after_two_reviews` (2, 2); lượt sửa thứ ba bị trần kho chặn lúc giữ chỗ (`blocked/budget`), không gọi |
| `ledger_cap` | Như `fix_cap` nhưng trần kho nâng lên 8 (chỉ dry): sổ pilot chặn lượt sửa thứ ba trước khi dựng engine (`refused cap_maker`), host hoàn lượt (làm còn 2 lượt đã dùng), `blocked/engine_blocked` |
| `review_unknown`, `maker_error` | Đúng nhánh; không thử lại; dựng lại không gọi thêm |
| `cost` | Hạn mức đã duyệt nhỏ hơn trần pilot: dừng trước mọi lượt |
| `auth` | Xác thực không phải gói thuê bao: dừng trước mọi lượt |
| `ledger_exists` | Sổ có từ trước: dừng, không đặt lại |
| `precondition` | Người review bị tắt giữa A và B: dừng trước việc nền |
| `ledger_corrupt` | Sổ hỏng trước B: không cấp lượt nào, dừng, sổ chưa xác minh |
| `tripwire` | Đường dựng engine "thật" bị gọi ở dry: bẫy ghi sự kiện, dừng |

Logic sổ (trần, sổ đóng, sổ hỏng, kết cục từng lượt, phân nhánh) có test riêng không cần server: `tests/python/test_resonance_a5_pilot_gate.py`.

## Chạy real (chỉ sau khi được duyệt)

```bash
JAVIS_RESONANCE_A5_PILOT=real JAVIS_RESONANCE_PILOT_SETTINGS=<settings.json thật> JAVIS_RESONANCE_A5_OUT=<thư mục mới> JAVIS_RESONANCE_A5_APPROVED='{"aux": {"provider": "anthropic-cli", "model": "sonnet"}}' JAVIS_RESONANCE_A5_MAX_CALLS=4 JAVIS_RESONANCE_A5_INPUTS_SHA=<frozen_sha256> python tests/python/test_resonance_a5_pilot.py
```

Đúng một lần, trên một bản checkout sạch ở SHA đã duyệt. Báo cáo ghi `commit` và `server_dirty`; khác SHA đã duyệt hay cây bẩn thì kết quả không dùng được.
