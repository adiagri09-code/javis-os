# Nhóm chat 0.142.0: hết im lặng, tạo nhóm kiểu Zalo, tab Công việc, Auto

Ngày 14/10/2026. Nhánh `claude/compassionate-wozniak-z5umfl`, PR [#651](https://github.com/blogminhquy/javis-os/pull/651).
Nền: `main` `063750a` (0.141.0). Số phiên bản giữ chỗ ngay đầu nhánh (commit đầu, PR nháp mang số 0.142.0).

Goal gốc nằm ở máy của chủ repo (`exports/reviews/team-chat-zalo-ux-2026-10-14/goal-claude-v2.txt`, `audit.md`, ảnh
01 tới 08). Phiên này chạy trong container đám mây nên không đọc được thư mục đó; làm theo đúng nội dung goal được dán
trong lệnh `/goal` cùng năm ảnh chụp đính kèm. PR #645 (đã đóng) không bị đụng tới.

## 1. Chat nhóm im lặng: nguyên nhân gốc đã xác minh

Hai lỗi chồng nhau:

1. **Lượt nhóm đi qua hợp đồng của Cộng hưởng.** `main._team_engine_for` dựng engine bằng `_resonance_engine`: model
   VIỆC NỀN, và `resonance.pick_text_only_link` chỉ nhận hai cơ chế chỉ chữ (Claude có cổng `can_use_tool`, engine API có
   `no_tools`). Máy để model việc nền là Codex thì mọi lượt bị chặn trước mốc gọi model.
   Tái hiện trên mã `origin/main` cũ (worktree tạm, settings: chính Claude, việc nền Codex):
   `EngineUnavailable: model việc nền chưa chạy được lượt chỉ chữ: {... 'blocked': 'engine openai-oauth còn công cụ
   native, chưa có cơ chế chỉ chữ được kiểm; Resonance M1 chỉ nhận Claude (cổng can_use_tool) và engine API (no_tools)'}`,
   `engine_started` chưa từng được gọi.
2. **Kết cục lỗi bị bỏ đi.** `team_api.teams_send` chạy `runner.run_replies(sub)` nền và không ai đọc kết quả; lượt lỗi
   chỉ còn trong sổ lượt, khung chat không có dòng nào.

## 2. Đã làm

| Mục | Thay đổi | File chính |
|---|---|---|
| Hợp đồng engine | `team_engine.py`: model của trợ lý, thiếu hay chưa cấu hình được thì model chính (ghi chú trên tin vì sao). Không dùng model việc nền, không chuỗi dự phòng, không nâng quyền | `server/team_engine.py`, `main._team_engine_for` |
| Codex chỉ chữ | Không profile `-p`, `mcp_servers={}`, `web_search="disabled"`, tắt công cụ native bằng `features.*=false`, LUÔN `--sandbox read-only` (kể cả `JAVIS_CODEX_SANDBOX=off`) | `team_engine.codex_text_only` |
| Grok, Antigravity | Chưa có cơ chế chỉ chữ được kiểm: báo lý do, không chạy thay bằng provider khác | `team_engine.build` |
| Kết cục lượt trả lời | Bảng `team_replies` (queued, running/answering, done, error + lý do), gói WS `team_replies`, trang tin kèm `replies`, Thử lại bằng CAS `error -> queued`, khởi động lại đổi lượt dở thành `error/restart` | `team_store.py`, `team_runner.py`, `team_api.py`, `teams.js` |
| Việc nền bị chặn | Thêm tin hệ thống ngay trong khung chat (ngoài hộp thư) | `team_runner._block` |
| @ theo agent_key | Trùng tên thì phải chọn trong gợi ý (mã ghi theo thứ tự chọn); gõ tay tên trùng thì không gọi ai và báo | `teams.js mentionScan` |
| Tạo, thêm nhóm | Hộp chọn kiểu Zalo, lớp phủ gắn vào `<body>` | `team-picker.js`, `teams.js`, `console.css` |
| Tab Công việc | `GET/POST /agents/{slug}/jobs`; gom theo agent_key, đọc bản ghi gốc; Giao việc tạo một việc Kanban mang khoá `agent:<mã>:<slug>:<nonce>` | `agent_jobs.py`, `main.py`, `tasks.py`, `task_store.py`, `agent-jobs.js`, `workspace.js` |
| Bỏ reviewer cố định | Mục tiêu mới không gắn đội; migration một lần cho mục tiêu cũ | `resonance_store.py`, `resonance_api.py`, `resonance-agent.js`, `chat-resonance.js` |
| Auto | Đổi tên hiển thị, công tắc trong thẻ, mục trong menu ba chấm dùng chung `doiAuto` | i18n, `resonance-agent.js`, `workspace.js`, `console.css` |

### Bằng chứng Codex chỉ chữ (Codex CLI 0.153.4, bản Docker đang ghim)

Chạy `codex exec` thật trỏ vào một máy chủ Responses giả trên máy (không gọi OpenAI), ghi lại thân request:

- Mặc định: công cụ gửi cho model là `exec_command, write_stdin, request_user_input, apply_patch, view_image, get_goal,
  create_goal, update_goal, tool_search, web_search`.
- Với cờ của `codex_text_only`: chỉ còn `request_user_input` (chỉ dùng được ở Plan mode) và `apply_patch`.
- Máy chủ giả trả một `apply_patch` ghi file NGOÀI thư mục làm việc: Codex từ chối ở tầng chính sách (`patch rejected:
  writing is blocked by read-only sandbox; rejected by user approval settings`), file không được tạo.
- Tên `features.*` lạ với một bản Codex bị bỏ qua (đã thử), nên danh sách dư không làm hỏng bản khác.

### Tab Công việc: nguồn và trạng thái

- **Nhóm:** việc giao thẳng (`assignee_key`), việc điều phối (`coordinator_key`, bước plan, synthesize), và việc chỉ
  làm một bước con hay hỗ trợ (bước `work`, `help` trong `team_steps`). Tiến độ là số bước thật, vị trí thật trong hàng
  của nhóm, Huỷ đi route huỷ của nhóm.
- **Chat riêng:** việc Kanban có `chat_id` là phiên `agent:<slug>` đã ghim đúng mã (phiên ghim mã cũ cùng slug bị loại),
  và việc giao bằng nút Giao việc. Metadata của việc Kanban bị ghi đè khi việc chạy xong, nên quyền sở hữu nằm ở khoá
  idempotency (bền suốt đời việc). Tiêu đề kèm tên trợ lý để Kanban không gộp hai việc cùng chữ của hai trợ lý.
- **Auto:** mục tiêu của trợ lý (`goal_agents`) và mục tiêu cũ trợ lý đang là người review. Mã lý do `review_removed`,
  `paused` hiện bằng lời thường.
- **Hàng chờ trung thực:** brain tắt "AI tự vận hành" thì việc giao trực tiếp ghi rõ chỉ nằm chờ; chân tab nêu trần
  việc nền chạy cùng lúc (`JAVIS_KANBAN_MAX_WORKERS`).
- Việc Kanban giao cho trợ lý chạy với vai của trợ lý (lời nhắc như ở quy trình, nối vào lời nhắc hệ thống). Engine,
  quyền và trần của Kanban giữ nguyên. Đọc tab không tạo gì; chat thường không tự tạo việc.

### Migration bỏ người review cố định

Chạy một lần khi mở kho (dòng `review_migrations`), chép trước `resonance.sqlite3.pre-0.142.0`:

- Mọi cặp `team_pairs` tắt (`enabled=0`, tăng `config_version`), dòng giữ nguyên.
- Mỗi mục tiêu còn đội `active`: đội `detached` bởi `host:review_removed`, sự kiện `team_detached` ghi trạng thái chạy và
  lý do chặn trước đó, lý do thức của vai review chốt `superseded`. Mục tiêu đang mở bị **tạm dừng**, chặn thuộc đội gỡ
  về `ready`.
- Không dùng lại `team_detach` của chủ: lệnh đó hẹn thức ngay, và lần thức đó chốt theo luật A4, có thể kết thúc
  `succeeded` mà không ai review (test A5 T24, T46 khẳng định đúng điều này).
- Không xoá gì: `reviews`, `team_calls`, `goal_events`, bản nộp và file đích giữ nguyên. Chủ thấy mục tiêu ở ngăn Cần
  bạn và trên thẻ: Tiếp tục, sửa, huỷ, hay giao một việc kiểm chứng.

## 3. Kiểm

**Test mới:**
- `tests/python/test_team_chat_0142.py`: chọn model, dựng engine từng provider, Codex `read-only` khi tắt sandbox, kết
  cục lượt (chờ, đang trả lời, xong, lỗi), một lượt lỗi không mất lượt sau, Thử lại không nhân đôi tin, lượt hay kết
  quả, gửi lại cùng `client_msg_id`, nhóm tạm dừng, khởi động lại, việc bị chặn có tin trong chat.
- `tests/python/test_agent_jobs_0142.py`: route thật, vai trong việc nhóm (giao, điều phối, hỗ trợ), huỷ một việc không
  đụng việc khác, Giao việc chống trùng, không gộp theo tiêu đề giữa hai trợ lý, phiên chat riêng, vai khi chạy, không
  nguồn nào lỗi ngầm.
- `tests/python/test_review_removed_0142.py`: kho thời A5 có mục tiêu đang chờ review, giả lập kho trước 0.142.0, mở
  bằng mã mới; không tự đạt kể cả khi thức lại, lịch sử giữ nguyên, có bản sao, chạy lại không đổi gì.
- `tests/js/test_team_chat_0142.js`: @ trùng tên, dòng trạng thái lượt, hộp chọn, tab Công việc, Auto.

**Test cũ cập nhật theo thiết kế mới** (ghi rõ vì sao trong từng file): `test_team_t1_review.py` (điểm thay engine),
`test_teams_ui.js`, `test_workspace.js`, `test_tab_thu_muc.js`, `test_team_t0_toggle.js`, `test_resonance_a5_ui.js`,
`test_resonance_a5_api.py` (route đặt reviewer trả 410), `test_resonance_a5_team.py` (T31: đường `javis_goal` thật không
gắn đội), `test_resonance_a5_rollback.py` và helper `_resonance_team.py` (bật lại việc gắn đội để dựng kho thời A5).

**Kết quả trên container:** `tests/run.py --js` 187/187. `tests/run.py --py` 503/512 lần đầu; 9 file đỏ đều không do
thay đổi này (thiếu `pytest` trong `.venv` cho 7 file, `test_khoi_dong_nhe` đo thời gian lúc máy đang chạy nặng, và
`test_icons` bắt hai ký tự dự phòng trong `team-picker.js`, đã sửa). Cài `pytest` rồi chạy lại cả 9: xanh.

**Smoke trình duyệt thật** (Chromium qua Playwright, sandbox cổng 7788, state và brain tạm, model chính Claude `haiku`
thật, model việc nền đặt Codex để tái hiện ca lỗi gốc, không Telegram, Zalo hay kênh ngoài nào):

- 1366x860: tạo nhóm qua hộp chọn (tìm "muc tieu" ra Coach, lọc tag rồi đổi tag vẫn giữ người đã chọn, Điều phối mặc định
  là người đầu tiên), vào chat ngay. Tin thường: trưởng nhóm trả lời bằng model thật. @One khi có hai trợ lý tên One: chọn
  bản B, đúng bản B trả lời. Trợ lý có model không tồn tại: dòng "Chưa trả lời được" kèm câu lỗi thật và nút Thử lại;
  bấm Thử lại chạy đúng một lượt. Giao việc ngắn: kết quả về khung chat với nhãn "Kết quả việc", và hiện ở tab Công việc
  ngăn Đã xong. Tải lại trang: trạng thái lượt còn nguyên. Giao việc từ tab Công việc khi AI tự vận hành tắt: ghi rõ chỉ
  nằm chờ. Công tắc Auto trên thẻ và mục Auto trong menu ba chấm.
- 768x1024: khung chat nhóm, hộp chọn giữa màn hình.
- 375x812: hộp chọn đầy màn hình, footer cố định ở đáy (737 tới 806 trên 812), không tràn ngang; vùng chạm công tắc
  Auto 87x44; tab Công việc trong ngăn kéo phải.
- Lỗi tìm được nhờ smoke và đã sửa: lớp phủ hộp chọn bị thanh trên của app che trên điện thoại (nay gắn vào `<body>`),
  chi tiết lỗi hiện "(success)" thay vì câu lỗi thật, nhãn việc đã xong chỉ còn mã sau khi tải lại, ghi chú thừa dấu
  chấm, "Nhóm Nhóm ..." ở nguồn của việc.

## 4. Hạn chế còn lại

- Smoke với provider thật chỉ có Claude (container không có đăng nhập ChatGPT). Đường Codex được kiểm bằng Codex CLI thật
  với máy chủ Responses giả, không phải một lượt ChatGPT thật.
- Grok Build và Antigravity chưa chạy được lượt nhóm: còn công cụ đọc native (Grok) hay MCP dùng chung file của máy
  (`agy`). Trợ lý đặt hai model này dùng model chính, kèm ghi chú trên tin.
- `apply_patch` của Codex không tắt được bằng cờ; lớp chặn là `--sandbox read-only` cộng kiểm sự kiện công cụ của
  `TextOnlyOutcome`.
- Việc giao bằng nút Giao việc chạy trên engine việc nền của Kanban (giữ nguyên quyền và trần), với vai của trợ lý; nó
  không dùng model riêng của trợ lý như lượt chat nhóm.
- Quyền "Không giới hạn lượt" cũ ghi `aux` không còn khớp lượt nào (lượt nhóm nay ghi provider thật): trần về mức của
  nhóm, tức chặt hơn.
- Chưa merge, chưa triển khai VPS.
