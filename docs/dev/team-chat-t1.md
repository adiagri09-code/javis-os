# Nhóm chat team T1: lõi nhóm chat, Quyền giới hạn (0.111.0)

Spec: [2026-10-13-team-chat-design.md](../superpowers/specs/2026-10-13-team-chat-design.md) (D1 tới D7 đã chốt ngày 13/10/2026). Kế hoạch: [2026-10-13-team-chat-t1.md](../superpowers/plans/2026-10-13-team-chat-t1.md), phán quyết R1 tới R3 ở đó.

## Luồng hữu ích đầu tiên

1. Chủ tạo nhóm ở trang **Nhóm** (thanh bên, nhóm Năng lực, cạnh Cộng sự): tên, mô tả, thành viên, trưởng nhóm.
2. Tin không @ thì trưởng nhóm trả lời (D1). Chọn @ từ gợi ý thì chỉ người được gọi trả lời, theo thứ tự @; người sau thấy câu trả lời của người trước.
3. Bật **Giao việc** thì tin thành một việc nhóm trong hàng đợi (D2). Không @: trưởng nhóm lập kế hoạch, giao từng phần, rồi tổng hợp. Có @: người được gọi làm thẳng.
4. Hàng đợi có **Ưu tiên** / **Bỏ ưu tiên**, đánh số đúng thứ tự chạy. Việc bị chặn rời chỗ chạy, hiện ở "Bị chặn, chờ bạn" kèm lý do, có tin vào hộp thư.
5. Kết quả về đúng nhóm, mỗi tin có tác giả, vai, nhãn việc và trạng thái bằng chữ; bản cuối có nhãn "Kết quả việc".

## Bản đồ mã

| Phần | File | Việc |
|---|---|---|
| Danh tính | `server/resonance_store.py` (`agent_register`), `server/main.py` (`save_agent`) | Mã bền cho thành viên, không bật Cộng hưởng. Tạo agent trùng slug trả 409, không ghi đè |
| Kho nhóm | `server/team_store.py` (`team.sqlite3`) | Nhóm, thành viên, sự kiện, bước nội bộ, sổ lượt, khoá bận; `set_caps`, `log_event` |
| Tin có người gửi | `server/sessions.py` | Cột `author_kind`, `author_ref`, `client_msg_id` (duy nhất trong phiên), `reply_to`, `task_id`, `step_id`, `meta_json`; ẩn `team:` và `teammate:` khỏi lịch sử chat; sổ quyết định; tin theo việc |
| Hàng đợi | `server/task_store.py` (làn `team` của `kanban.sqlite3`) | `enqueue_team` (khoá = tin nguồn, không gộp theo tiêu đề), `team_queue`, `team_priority` (CAS `queue_version`, 409), `claim_team_next` (một việc chạy mỗi nhóm, cùng giao dịch), chặn, gỡ chặn, xong, huỷ, sửa yêu cầu, khôi phục. Mã bảng Việc cũ bỏ qua mọi dòng `lane='team'` |
| Bộ chạy | `server/team_runner.py` | Định tuyến, lượt trả lời, việc nhóm (`plan`, `work`, `help`, `synthesize`), khối `JAVIS_TEAM`, trần, chống vòng, đầu ra muộn, khoá bận FIFO, sổ lượt, huỷ giữa lượt, phục hồi sau restart |
| Route | `server/team_api.py`, nối ở cuối `server/main.py` | `/teams/*` (19 route), vòng điều phối 5 giây, nhắc việc chặn quá 24 giờ, engine chỉ chữ, hộp thư, gói WS `team_message` / `team_state` |
| Giao diện | `dashboard/teams.js`, `console.js`, `index.html`, `console.css`, `app.js`, i18n | Trang Nhóm ba cột, ngăn kéo dưới 1060px, một cột dưới 760px |
| Nâng, hạ | `server/team_migration.py`, `tools/team_chat_restore_pre.py` | Snapshot `.pre-0.111.0` của `kanban.sqlite3` và `conversations.db`, công cụ khôi phục |

## Khối JAVIS_TEAM (phán quyết R1)

Agent điều phối bằng khối do host đọc ở cuối câu trả lời:

```
<!-- JAVIS_TEAM: {"op": "assign", "agent": "<mã hay slug>", "brief": "..."} -->
<!-- JAVIS_TEAM: {"op": "request_help", "agent": "<mã hay slug>", "question": "..."} -->
<!-- JAVIS_TEAM: {"op": "propose_job", "title": "...", "brief": "..."} -->
```

| Vai của lượt | Op dùng được |
|---|---|
| Trưởng nhóm trả lời trò chuyện | `propose_job` (thành thẻ, chủ bấm Tạo việc mới có việc) |
| Thành viên trả lời trò chuyện | Không có |
| Lập kế hoạch | `assign` |
| Làm, Hỗ trợ | `request_help` (một người mỗi lượt) |
| Tổng hợp | Không có |

Op sai (JSON hỏng, op lạ, người ngoài nhóm, nhờ ngược, quá độ sâu) bị bỏ, ghi chú hiện dưới tin; không có lượt nào ngoài trần.

## Trần (D7, chỉnh ở tab Cài đặt của nhóm)

12 lượt mỗi việc; 8 bước mỗi việc; độ sâu nhờ hỗ trợ 2; không nhờ ngược; 2 lượt liền cùng kết quả thì dừng (`no_progress`); 3 @ mỗi tin; 100 lượt mỗi nhóm mỗi ngày (tính cả lượt trò chuyện); 1 việc chạy mỗi nhóm; 2 nhóm chạy cùng lúc; 1 lượt cùng lúc mỗi agent (D3); chờ khoá bận 30 phút. Trần kiểm TRƯỚC khi giữ chỗ lượt, nên chạm trần không gọi model.

## Sổ lượt

Một dòng mỗi lời gọi model. Lỗi trước mốc gọi engine thì hoàn (`refunded`). Sau mốc thì tính, kể cả lỗi, bị huỷ giữa lượt (`interrupted`), restart (`interrupted`, không tự chạy lại).

## Giới hạn đã biết của T1

- **Lượt nhóm chỉ chữ** (R3): không đọc, ghi file, không MCP, không `javis_goal`. Mở công cụ cùng cổng quyền theo nhóm để T3.
- **Không resume mạch thành viên:** mỗi lượt là một lời gọi mới mang khối nhóm (20 tin mới nhất kể từ lượt trước của agent, tối đa 8.000 ký tự; sổ quyết định; đầu vào của bước).
- **Không stream từng chữ** (R2): câu trả lời về khi xong.
- **Chưa có reaction** (T2), **chưa có Toàn quyền** (T3).
- **Chat riêng 1:1 với agent không lấy khoá bận:** một agent có thể cùng lúc chạy một lượt nhóm và một lượt chat riêng.
- **Bỏ qua thẻ đề xuất** chỉ ẩn trong tab đang mở.
- Route ghi gọi kho trên vòng sự kiện (mỗi lệnh một ghi có chỉ mục); route đọc chạy trong luồng phụ. Đo ở T4.

## Review cuối (người review mới, model mạnh nhất)

Kết luận "sẵn sàng sau khi sửa": 0 lỗi nghiêm trọng, 5 lỗi quan trọng, đã sửa hết, mỗi lỗi có test đỏ trước rồi xanh.
- Trưởng nhóm giao theo tên hiển thị ("Minh") bị bỏ và việc báo xong khi chưa ai làm: giờ khớp cả tên, không phân biệt hoa thường; mọi lệnh giao đều hỏng thì việc bị chặn.
- Sửa yêu cầu của việc @ nhiều người chỉ làm lại phần một người: giờ mọi người được giao còn thiếu kết quả bản mới đều làm lại.
- Tạm dừng rồi tiếp tục ngay làm kẹt nhóm; lỗi bất ngờ để việc treo `team_running`; vòng nền chạy phục hồi nhầm ở máy cài mới: đều đã sửa.
- Sửa thêm (nâng mức theo tác động): lượt trả lời không chạy khi nhóm đã tạm dừng, lưu trữ huỷ cả việc đang treo, bước không tiến triển thành bước lỗi để Chạy lại, khoá bận không kẹt khi huỷ, phiên nhóm không hiện trong ô tìm của khung chat chính.
- Để lại (ghi trong sổ phán quyết): bài học từ lượt đến muộn vẫn ghi vào bộ nhớ agent; trần ngày có thể vượt vài lượt khi nhiều lượt cùng lúc; khoá bận không gia hạn sau 15 phút; chữ lý do từ server chỉ có tiếng Việt; dựng tên thành viên tốn đọc file mỗi lượt (đo ở T4).

## Nâng, hạ phiên bản

- Lần đầu 0.111.0 mở `kanban.sqlite3` và `conversations.db` có từ trước, mỗi kho được chụp một bản `<tên>.pre-0.111.0` bằng SQLite backup, trước khi thêm cột. Kho mới tinh thì không chụp.
- **Hạ về 0.109.0:** tắt Javis, chạy `python tools/team_chat_restore_pre.py --yes`. Kho hiện tại được giữ ở `<tên>.post-0.111.0-<thời điểm>`. Việc Kanban và tin chat sau lúc nâng không còn trong kho chạy.
- **Hạ không khôi phục:** mã cũ không bao giờ nhặt việc nhóm, nhưng trang Việc hiện các dòng `team_*` với trạng thái lạ và phiên `team:` hiện như phiên thường.
- `team.sqlite3` để nguyên; mã cũ không đọc.

## Kiểm

| Lệnh | Kết quả |
|---|---|
| `tests/python/test_team_identity.py` | Mã bền không bật Cộng hưởng; tạo trùng slug 409, file cũ không đổi |
| `tests/python/test_team_store.py` | 24 ca: nhóm, thành viên, trưởng nhóm, bước CAS, sổ lượt, khoá bận |
| `tests/python/test_team_messages.py` | Người gửi, chống gửi trùng, phân trang, ẩn khỏi lịch sử chat |
| `tests/python/test_team_queue.py` | 33 ca: TC9, TC14 tới TC18 (ví dụ A, C, B), cách ly bảng Việc |
| `tests/python/test_team_runner.py` | 65 ca, engine giả: TC6 tới TC13, TC17 tới TC23, khối JAVIS_TEAM sai khuôn, huỷ giữa lượt |
| `tests/python/test_team_api.py` | 40 ca trên app thật với engine giả: route, 409, đề xuất, sổ quyết định, xoá agent rồi tạo lại (TC5), lưu trữ |
| `tests/js/test_teams_ui.js` | 53 ca: danh sách, tin, hàng đợi, khung soạn, cài đặt, chỗ nối, CSS, i18n |
| `tests/python/test_team_rollback.py` | 15 ca với mã 0.109.0 thật (`bfb1c29f`): snapshot, hạ có và không khôi phục, nâng lại |
| `python tests/run.py --js` | 186/186 |

**Smoke giao diện** (sandbox cổng 7788, state trong worktree). Trần lượt ngày của nhóm đặt 0 trước khi gửi gì, nên không lượt nào tới engine thật; sổ lượt cuối buổi 0 dòng. Ảnh ở `exports/reviews/team-t1-smoke/`, ngoài repo.
- Tạo nhóm qua form; trưởng nhóm, số thành viên hiện ở đầu khung chat.
- Tin thường: lưu, báo "Nhóm đã dùng hết lượt hôm nay", không ai trả lời.
- @ gõ "mi" hiện gợi ý Minh; chọn thì thành thẻ; bật Giao việc thì gợi ý "Tạo 1 việc · giao cho Minh · vào cuối hàng (vị trí 1)".
- Việc chạm trần, vào "Bị chặn, chờ bạn" kèm lý do và nút Cho chạy tiếp.
- Tạm dừng nhóm, thêm B rồi C, bấm Ưu tiên C: C lên vị trí 1 với nhãn "Ưu tiên" có icon sao và nút Bỏ ưu tiên.
- 375px: danh sách là trang đầu; khung chat toàn màn, đầu khung hai hàng; cài đặt trượt lên, nền đặc; không cuộn ngang; nút 44px.
- Smoke tìm ra và đã sửa: nút ẩn vẫn hiện (`.ws-btn` đè `hidden`), cột cài đặt trống khi chưa mở nhóm, đầu khung chat bị ép trên điện thoại, ngăn kéo trong suốt, nút quay lại hẹp hơn 44px.
