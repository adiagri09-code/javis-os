# Thiết kế bổ sung thống nhất: reaction, heartbeat thích nghi, phán xử theo agent, học trong đội (T2-T4)

Ngày: 15/10/2026. Nền: `main` `1d1b52fa` (0.151.0). Lệnh gốc: `exports/reviews/GOAL-TEAM-CHAT-T1-T4-COMPLETE.md` (bản rà soát
2). Rà hiện trạng: bốn bản recon (T1, reaction, heartbeat, phán xử) tóm ở mục 1. T1 làm song song theo thiết kế team chat đã
duyệt (`2026-10-13-team-chat-design.md`) và không phụ thuộc tài liệu này.

Tài liệu này là **một** thiết kế cho toàn phần bổ sung, để review một lần. Mọi số trong tài liệu là **tham số khởi tạo có
phiên bản**, không phải kết luận nghiên cứu; chúng được kiểm bằng test đồng hồ giả và chỉ được chỉnh có bằng chứng.

## 0. Thay đổi so với tài liệu cũ (nói rõ, không âm thầm)

| Tài liệu cũ | Nói gì | Nay đổi thành | Vì sao |
|---|---|---|---|
| Spec Resonance 06/10 (`2026-10-06-javis-resonance-design.md`:251,261), roadmap 08/10 | Không gắn tần suất với điểm khen/chê | Nhịp CHỦ ĐỘNG của agent (lớp 3) thay đổi theo ước lượng hữu ích có giới hạn, độ tin và quay lại; lịch trách nhiệm (goal A2, hạn chót, Kanban, nhắc hẹn) **không** đổi theo điểm | GOAL 7.2, 7.3 |
| A3 (`docs/dev/resonance-a3-learning.md` "Những điều không bao giờ xảy ra") | Reaction không tạo lý do thức, không đổi lịch | Reaction hợp lệ trên agent bật Cộng hưởng tạo **một** lý do xem xét gom nhóm theo (agent, ngữ cảnh) và là đầu vào ước lượng hữu ích. Reaction trên agent tắt Cộng hưởng vẫn chỉ lưu và hiển thị | GOAL 6.2, 7.3 |
| A3 làn P | Đề xuất bài học trình bày, chủ duyệt mới áp | Khi Cộng hưởng bật, điều chỉnh trong **phạm vi tự học đã cấp** (nói/im, nhịp, bài học phạm vi nhóm) tự áp có trước/sau, quan sát và tự quay lại; thay đổi quyền, luật của chủ, phạm vi ngoài cấp vẫn chờ chủ | GOAL 8.2 |
| Team chat T1 (spec 13/10 :252, TC8) | Tin của agent không đánh thức ai | Tin của đồng đội/trưởng nhóm mở **lượt xem xét liên quan** chỉ qua sự kiện có cấu trúc (quan hệ việc, input_refs, lệnh `ask_peer`), có trần độ sâu và chống vòng; chữ `@` trong văn bản, trích dẫn và tag giả vẫn không mở gì | GOAL 8.1 |
| Team chat T1 | Bài học `JAVIS_LESSON` ghi vào bộ nhớ chung của agent | Bài học trong nhóm ghi vào kho bài học có **phạm vi nhóm**, có nguồn, lịch sử, thu hồi; chỉ đưa lên phạm vi chung qua tự rà soát có bằng chứng từ nhiều ngữ cảnh hoặc chủ duyệt | GOAL 7.5, 8.2 |
| Phán xử Zalo | Hai kết luận nói/im; không có sổ lượt | Ba kết luận nói/chờ/im (chờ có điều kiện gỡ); mọi lượt phán xử và tự rà soát vào sổ lượt chung | GOAL 8.1, 8.3 |
| Test emoji (`tests/python/test_icons.py`) | Sáu emoji chỉ được nằm trong `teams.js` | Sáu emoji chỉ được nằm trong **một** bảng dùng chung `dashboard/reactions.js`; mọi chỗ khác vẫn cấm | GOAL 6.1 |

## 1. Hiện trạng tóm tắt (bằng chứng ở các file recon trong gói review)

- **Team chat:** T0-T5 và 0.146.0 đã phát hành. R1-R9 đạt trên head (script reviewer, bản thích nghi engine giả). Thiếu: chốt
  quyền theo lượt (lượt cũ hưởng quyền cấp lại), lease bận/việc không gia hạn trong lượt dài, cap `running_jobs` > 1 không có
  hiệu lực, bảng giới hạn chưa đủ. Các mục này là việc của T1 (PR riêng).
- **Reaction:** sáu reaction có ở team chat (lưu, lý do, góp ý, chống trùng nonce, nhiều tab) nhưng **không** đánh thức ai, chỉ
  chủ được thả, nhật ký thiếu agent/việc/giá trị trước, không có trạng thái. Chat riêng: không có reaction trên câu trả lời
  agent; chỉ có cặp Hữu ích/Chưa ổn của A3 trên tin báo goal. Bong bóng chat chưa mang mã tin.
- **Heartbeat:** lớp 1 (lease) và lớp 2 (A2 theo goal) có. Lớp 3 (theo agent) **chưa có**. Không có sự kiện "đã xem". Sổ lượt
  rời rạc ở năm nơi.
- **Phán xử:** bộ phán xử Zalo tách được "được gọi" khỏi "có nên nói", có học theo ca, tự rà soát có trước/sau và tự quay
  lại, nhưng gắn chặt bot/kênh, chỉ hai kết luận, không sổ lượt, kho ca lấy chéo mọi chat (rò ngữ cảnh nếu dùng nguyên cho
  agent nhiều nhóm).
- **Học:** bài học agent trộn mọi ngữ cảnh, không nguồn, không thu hồi; đồng đội không có kênh góp ý.

## 2. Khái niệm chung

- **Agent:** định danh bền `agent_key` do host cấp (`resonance_agents`). Mọi bảng mới khoá theo `agent_key`, không theo slug.
- **Ngữ cảnh (`context_ref`):** `team:<team_id>` hoặc `dm:<session_id>` (chat riêng với agent). Phần chung theo agent dùng
  `context_ref = "*"`. Dữ liệu, quyết định, bài học và nhịp có phạm vi ngữ cảnh; không đưa nội dung của ngữ cảnh này vào
  prompt ngữ cảnh khác.
- **Sự kiện nguồn:** mọi tác động (lý do thức, tín hiệu hữu ích, ghi nhận đóng góp, bài học) trỏ về một `source_ref` duy nhất
  (vd `rx:dm:<log_id>`, `rx:team:<log_id>`, `decision:<id>`, `step:<id>`). Một nguồn chỉ có một tác động mỗi loại (UNIQUE).
- **Cộng hưởng (công tắc theo agent) và phạm vi:**

| Năng lực | Cộng hưởng tắt | Cộng hưởng bật |
|---|---|---|
| Trả lời lời gọi trực tiếp, làm việc được giao, việc nhóm | Có | Có |
| Phán xử nói/chờ/im trong nhóm đang tham gia (chính sách hiện có, đóng băng) | Có | Có |
| Lưu và hiển thị reaction | Có | Có |
| Lý do xem xét từ reaction, học chính sách, tự rà soát | Không | Có |
| Heartbeat thích nghi (nhịp chủ động, ngủ, tự tìm việc) | Không | Có |
| Nhắc tiếp chủ động trong chat riêng | Không | Có |

  Bật lại: ghi `resumed_at`; phản hồi trước mốc chỉ là **bằng chứng/ngữ cảnh**, không tạo lượt bù, không đặt lại ngân sách.

## 3. Sổ lượt chung theo agent (nền cho T2-T4)

Bảng mới `agent_calls` trong `resonance.sqlite3` (cùng kho với `resonance_agents`):

`id, agent_key, brain_id, context_ref, purpose (reply|step|judge|review|proactive|learn|goal), reason_ref UNIQUE, engine, model,
status (reserved|running|ok|error|refunded), tokens_in, tokens_out, cost_usd, mirror_ref, created_at, settled_at`

- Một `reason_ref` chỉ mở **một** lượt (UNIQUE): lý do goal A2, lý do chủ động lớp 3 và lý do reaction cùng nguồn không thể
  nhân thành ba lượt (GOAL 12.15).
- Lượt nhóm vẫn ghi `team_turns` (trần ngày của nhóm giữ nguyên) và ghi **bản phản chiếu** vào `agent_calls`
  (`mirror_ref = team_turn:<id>`), để thẻ agent đếm đúng tổng. Goal A2 ghi `mirror_ref = goal_call:<id>`. Lượt phán xử, tự
  rà soát, chủ động là lượt riêng ghi thẳng vào `agent_calls` và tính vào trần tương ứng (mục 9).
- Giữ chỗ trước, chốt sau, hoàn khi chưa tới mốc gọi engine (cùng hợp đồng R4 của T1). Restart: lượt `reserved` cũ hơn mốc khởi
  động được hoàn; `running` thành `error/interrupted`, không chạy lại tự động.

## 4. T2: sáu reaction ở chat riêng và chat nhóm

### 4.1 Dữ liệu

- **Bảng dùng chung cho chat riêng** `dm_reactions` trong `conversations.db` (cùng kho tin nhắn, để join theo `message_id` bền):
  `session_id, message_id, reactor, source_kind (owner|leader|member), agent_key, agent_config_version, value (like|heart|
  haha|wow|sad|angry|NULL), reasons_json, axis (speak_ok|should_speak|should_silent|''), comment, content_sha, status, status_reason,
  goal_id, revision, updated_at, PRIMARY KEY(session_id, message_id, reactor)`; nhật ký `dm_reaction_log` gồm cả giá trị trước,
  `nonce UNIQUE`, `effect_refs_json`.
- **Team giữ bảng hiện có** và thêm cột qua `ALTER`: `source_kind`, `axis`, `status`, `status_reason`; `team_reaction_log` thêm
  `agent_key`, `task_id`, `prev_value`, `effect_refs_json`. Không đổi khoá, không đổi ngữ nghĩa thay-cả-trạng-thái và luật
  nonce của T2.
- `content_sha` tính trên **nội dung đã lưu** (sau khi bỏ khối điều khiển). Client gửi kèm `seen_sha` (sha nội dung đang
  hiển thị); lệch thì lưu cờ `stale=1` và vẫn nhận (chủ thả lên bản cũ là sự thật cần giữ).
- **Nguồn phản hồi do host gán:** `owner` qua route dashboard (cookie); `leader`/`member` chỉ qua lệnh có cấu trúc trong lượt
  của agent (`{"op":"react","message_id":..,"value":..}`), host lấy danh tính từ lượt đang chạy. Agent không thả lên tin của
  chính mình. Reaction của agent **không** vào ước lượng hữu ích (chống tự thưởng, mục 6.5); chỉ là góp ý cộng tác.

### 4.2 Giao diện

- Bảng sáu emoji, `nextReaction`, chip, bộ chọn và nhấn giữ chuyển vào **một** module `dashboard/reactions.js`, dùng cho
  `teams.js` và chat riêng (`app.js` bong bóng trả lời, bong bóng đang stream sau khi chốt, lịch sử).
- Bong bóng mang `data-mid`: lịch sử lấy `m.id`; lượt mới nhận `message_id` qua gói `turn_saved` phát **sau** `_persist_turn`
  (hàm trả mã tin đã lưu). Trước khi có mã: nút reaction ẩn, không cho thả lên tin chưa lưu.
- Lý do chất lượng (sáu lý do T2) và trục thứ hai "Đáng lẽ nên nói" / "Nên im (chen ngang)" là hai nhóm chip riêng; góp ý chữ
  tuỳ chọn. Không lý do nào bắt buộc.
- Nhiều tab: gói WS `chat_reaction {session_id, message_id, state}` (chat riêng) và `team_message` (đã có); khung lọc theo việc
  của nhóm cũng nhận gói (sửa lỗ hổng recon).
- Trạng thái hiển thị dưới chip, chỉ theo host: Đã nhận, Chờ xem xét, Đang xem xét, Đã điều chỉnh, Không cần đổi (kèm lý do
  ngắn). Agent tắt Cộng hưởng: chỉ "Đã nhận (Cộng hưởng tắt: chỉ lưu)".
- Điện thoại: nút luôn hiện (hover: none), vùng chạm 44px, chữ 16px.

### 4.3 Hiệu lực

- Ghi reaction và tác động trong **một giao dịch**: nếu agent bật Cộng hưởng và `created_at >= resumed_at` thì upsert **một** lý
  do xem xét đang chờ cho (agent, ngữ cảnh) (`agent_wake_reasons`, chỉ mục duy nhất trên `(agent_key, context_ref, code) WHERE
  status='pending'`); lý do gom danh sách `source_refs`. Nhiều lần bấm liên tiếp: một lý do, không lượt model nào trong lúc bấm.
- Đổi/bỏ reaction: nhật ký ghi trước/sau; nếu lý do còn chờ thì bỏ nguồn đó khỏi lý do (lý do rỗng thì chuyển `superseded`);
  nếu đã xem xét thì tín hiệu cũ được đánh `superseded_by` và lần tính sau dùng giá trị mới (mục 6.4). Không giữ tác động kép.
- Emoji không chốt đạt, không đổi ưu tiên, không cấp quyền, không đổi trạng thái việc/goal (test kiểu TC29 cho cả chat riêng).
- Phản hồi vào lượt kế tiếp của agent trong **đúng ngữ cảnh** như khối phản hồi T2 (`_feedback_lines`), có ghi chú emoji là
  cảm xúc. Chat riêng thêm cùng khối vào lời nhắc của lượt `agent:<slug>` kế tiếp.
- Ranh giới T2/T3: T2 tạo lý do và trạng thái "Chờ xem xét"; bộ xử lý lý do thật (lần xem xét, quyết định giữ/hỏi/sửa/rút kinh
  nghiệm) là T3. Gói nghiệm thu cuối chạy xuyên T2 → T3 trên host thật với engine giả.

## 5. T3: heartbeat thích nghi (lớp 3)

### 5.1 Một nơi quyết định lịch

Lớp 1 (lease) và lớp 2 (goal A2) giữ nguyên. Lớp 3 là module thuần mới `server/agent_pulse.py` (policy `pulse.v1`) và kho
trong `resonance.sqlite3`. Lịch chạy là **một bước** thêm vào `_resonance_tick` (sau `resonance.tick`), không scheduler thứ hai.
Hàm `effective_due(agent, context)` hợp nhất: lịch chủ động lớp 3, lý do xem xét đang chờ (`agent_wake_reasons`), và **không**
đụng `wake_reasons` của goal. Lịch trách nhiệm (goal, hạn chót, Kanban, nhắc hẹn) chạy theo nguồn của nó, không bị lớp 3 làm
chậm; lớp 3 chỉ quyết định khi nào agent **tự** xem xét/chủ động.

### 5.2 Trạng thái và chuyển trạng thái (theo agent x ngữ cảnh)

Thang nhịp (bậc): `B0 15 phút, B1 1 giờ, B2 4 giờ, B3 1 ngày, B4 3 ngày, B5 1 tuần, B6 2 tuần, B7 1 tháng`, trên B7 là ngủ đông
(không có lịch chủ động, chỉ thức theo sự kiện). Bậc khởi tạo B3 (1 ngày) cho ngữ cảnh mới; thẻ agent hiển thị bậc từng ngữ cảnh.

| Trạng thái | Nghĩa | Vào khi | Ra khi |
|---|---|---|---|
| `active` | bậc B0-B2 | ước lượng hữu ích cao và đủ tin | tụt bậc dưới B2 |
| `awake` | bậc B3-B4 | mặc định, hoặc vừa thức lại | lên/xuống bậc |
| `slowed` | bậc B5-B7 | ít nhu cầu hoặc tương tác chủ động không hữu ích có bằng chứng | lên bậc |
| `hibernating` | quá B7 | B7 qua hai kỳ liền không cơ hội/không tín hiệu | sự kiện thức |
| `waiting_owner` | chờ chủ quyết | phán xử/việc cần chủ | chủ trả lời, huỷ |
| `paused` | chủ tạm dừng | chủ bấm Tạm dừng | chủ bấm Tiếp |
| `off` | Cộng hưởng tắt | tắt | bật (về `awake` B3, ghi `resumed_at`) |

**Thức lại** (về `awake`, bậc tối đa B3, giữ nguyên ký ức và lịch sử): chủ nhắn/gọi trực tiếp agent trong ngữ cảnh, giao việc
mới, reaction mới hợp lệ, sự kiện liên quan có cấu trúc (mục 7.5). Thức không đặt lại ước lượng; chỉ đặt lại đồng hồ quan sát.

### 5.3 Điều chỉnh nhịp có giới hạn

Mỗi **kỳ đánh giá** (khi tới lịch chủ động, hoặc khi lý do xem xét được phục vụ), tính `u = estimate * confidence` (mục 6):

- `u >= +0.25`: lên **một** bậc (nhịp dày hơn), không quá trần bậc được cấp (`max_tier`, mặc định B1; Toàn quyền/chủ có thể cấp
  B0).
- `u <= -0.25` (có bằng chứng tương tác chủ động không hữu ích): xuống **một** bậc.
- Không tín hiệu và không cơ hội trong hai lần khoảng hiện tại: xuống một bậc với lý do `low_demand` (ít nhu cầu, **không**
  ghi là agent sai).
- Ngược lại giữ bậc.
- **Ổn định:** tối đa một bước mỗi kỳ; sau một lần đổi chiều phải qua ít nhất một kỳ giữ nguyên mới đổi chiều lại (hysteresis);
  một reaction đơn lẻ chỉ đóng góp giới hạn (mục 6.2) nên không thể đẩy từ ngủ tháng lên chạy liên tục. Thức lại do sự kiện chỉ
  về B3, không về B0.
- Mỗi lần đổi bậc ghi `agent_pulse_events` (trước/sau, nguồn, `policy_version`, `u`, lý do). Chủ có thể **quay lại** một thay
  đổi (khôi phục bậc trước) hoặc **đặt lại** ngữ cảnh về khởi tạo; cả hai ghi sự kiện.

### 5.4 Lưu bền và restart

Bảng `agent_pulse(agent_key, context_ref, state, tier, interval_s, next_due_at, estimate, confidence, n_eff, last_eval_at,
last_change_dir, last_change_at, resumed_at, max_tier, policy_version, updated_at, PK(agent_key, context_ref))`. Nhận lịch bằng
CAS (giống `claim_wake` A2): chết giữa chừng thì lịch tự tới hạn lại; một lần tới hạn chỉ có một `reason_ref` trong sổ lượt.

### 5.5 Lần thức: kiểm bằng code trước, model sau

`Thức không đồng nghĩa gọi model. Gọi model không đồng nghĩa gửi tin.` Mỗi lần thức phân loại:

1. **Chỉ code:** cập nhật ước lượng từ tín hiệu mới, tính bậc, kiểm việc đã giao (hạn chót gần, việc bị chặn có dữ kiện mới, đề
   xuất chờ chủ quá lâu). Không có gì: ghi `wake_log` (mục `no_action`) và ngủ tới lịch kế.
2. **Cần model suy xét:** chỉ khi có lý do cụ thể (reaction gom chờ, việc có dữ kiện mới, phát hiện cơ hội từ nguồn đã giao). Giữ
   chỗ sổ lượt (purpose `proactive` hoặc `review`) rồi mới gọi.
3. **Có việc cần làm:** trong quyền đã cấp thì đưa qua hàng đợi chung (Kanban/làn team) với nguồn; chưa có quyền thì ghi **đề
   xuất có nguồn** cho chủ/trưởng nhóm (thẻ đề xuất có sẵn).
4. **Có điều đáng nói:** qua phán xử của agent (mục 7) trước khi gửi.
5. **Không làm phiền ai:** im, ghi lý do vào nhật ký quyết định (không ra chat).

Tự tìm việc chỉ trong phạm vi đã giao: goal của agent, việc nhóm agent là thành viên, cam kết đã ghi, nguồn dữ liệu đã kết nối
cho agent. Không tạo việc để giữ mình hoạt động; một lần thức tạo tối đa một đề xuất hoặc một việc.

## 6. T3: ước lượng hữu ích

### 6.1 Tín hiệu (`pulse_signals`, một dòng một sự kiện nguồn)

| Nguồn | Giá trị khởi tạo (giả thuyết) | Ghi chú |
|---|---|---|
| Reaction ❤️ / 😮 / 😂 / 👍 | +1.0 / +0.8 / +0.5 / +0.4 | thứ tự GOAL là giả thuyết; cá nhân hoá ở 6.3 |
| Reaction 😢 / 😡 không lý do chất lượng | -0.2 / -0.4, độ tin thấp | có thể là cảm xúc về sự việc, không mặc định chê agent |
| Reaction kèm lý do chất lượng | theo lý do: đúng ý +0.8; sai dữ kiện, thiếu ý, khó hiểu, lạc đề -0.6; quá dài -0.3 | lý do là đánh giá agent, độ tin cao |
| Trục nói/im | không vào ước lượng nội dung | dạy phán xử (mục 7.6), tách trục |
| Chấp nhận đề xuất, chốt quyết định, dùng kết quả có sự kiện | +0.6 | chỉ khi có sự kiện host |
| Sửa yêu cầu sau kết quả, huỷ, bác đề xuất, thu hồi | -0.4 | có sự kiện host |
| Kiểm khách quan đạt / không đạt (assessment, review) | +0.5 / -0.5 | |
| Tin **chủ động** đã được xem, qua cửa sổ 24 giờ không tương tác | -0.15 | chỉ khi có sự kiện "đã xem" (6.2) |
| Tin chủ động chưa có bằng chứng xem | 0, `unknown` | không phạt |
| Im lặng / quan sát | không tạo tín hiệu | không phạt |
| Việc bắt buộc đã giao | không tạo tín hiệu "bị bỏ qua" | |
| Reaction của agent khác | 0 (chỉ cộng tác) | chống tự thưởng |

### 6.2 Sự kiện "đã xem"

Mới: dashboard gửi `POST /seen {context_ref, message_ids}` khi tin của agent nằm trong khung nhìn ít nhất 1,5 giây và tab đang
hiển thị (cả nhóm lẫn chat riêng); host ghi `message_seen` (một dòng mỗi tin, lần đầu). Không có sự kiện này thì "chưa biết".

### 6.3 Công thức (pulse.v1)

- Mỗi tín hiệu có `value v ∈ [-1, 1]`, trọng số nguồn `w` (chủ 1.0; kiểm khách quan 0.8; sự kiện hệ thống 0.6), và suy giảm theo
  thời gian nửa đời **21 ngày**.
- **Cá nhân hoá theo người phản hồi:** với người phản hồi r và giá trị e, `v_r(e) = v0(e) * k_r(e)`, trong đó
  `k_r(e) = clamp(1 + 0.5 * (1 - f_r(e)/f̄_r) * n_r/(n_r + 20), 0.6, 1.4)`: emoji người đó dùng thường xuyên mang ít thông tin
  hơn, emoji hiếm mang nhiều hơn, nhưng chỉ khi đủ mẫu (`n_r` lớn so với 20) và luôn bị kẹp 0.6-1.4 (không thành điểm vô hạn,
  không dùng độ hiếm đơn độc làm kết luận).
- `estimate = Σ w·v·decay / Σ w·decay` (khi không có tín hiệu: 0); `n_eff = Σ w·decay`; `confidence = n_eff/(n_eff + 4)`.
- Mỗi sự kiện nguồn đóng góp tối đa |w·v| ≤ 1 trước suy giảm.
- Thay/bỏ reaction: dòng cũ `superseded_by`; lần tính sau dùng dòng mới. Xoá nguồn (xoá tin, xoá agent): dòng chuyển `void`, ghi
  sự kiện. Không cộng dồn.
- Tách theo ngữ cảnh: ước lượng tính riêng từng `context_ref`; bản tổng hợp `*` chỉ để hiển thị và làm giá trị khởi tạo cho ngữ
  cảnh mới (kéo về 0 theo hệ số 0.5). Phản hồi tốt ở nhóm A không nâng bậc ở nhóm B.
- Không tối ưu số tim, số tin, số lượt: tin không có tín hiệu thì không có điểm; nói nhiều không tạo điểm.

### 6.4 Đối chứng và quay lại

Mọi lần đổi bậc và mọi thay đổi chính sách ghi trước/sau. Sau mỗi thay đổi có **cửa sổ quan sát** (tối thiểu 5 tín hiệu mới
hoặc 14 ngày): nếu `estimate` sau thấp hơn trước quá 0.3 với `confidence ≥ 0.5`, tự quay lại bản trước và ghi lý do. Không tuyên
bố cải thiện khi chưa qua cửa sổ.

### 6.5 Ghi nhận đóng góp (`pulse_contrib`)

- Chuỗi đóng góp do host ghi: bước làm/hỗ trợ (`team_steps`) với `input_refs`, tin tổng hợp trỏ về các bước đã dùng, câu trả lời
  trỏ về tin được trích.
- Phản hồi của chủ trên **bản tổng hợp**: tác giả tổng hợp nhận 0.4; 0.6 chia cho các bước có bằng chứng đã được dùng (theo
  `input_refs` của tổng hợp), chia đều giữa các bước đó; bước không được dùng không nhận gì. Tổng phân bổ một sự kiện nguồn = 1.
  Không chia đều cả nhóm, không mặc định trưởng nhóm nhận nhiều nhất.
- Một sự kiện nguồn chỉ phân bổ một lần: trích dẫn, chuyển tiếp, tổng hợp nhiều tầng không nhân điểm (tầng trên chỉ phân bổ
  phần của nó theo cùng nguồn).
- Agent không tự nhận công: đóng góp chỉ từ chuỗi host ghi; agent nói "tôi đã làm" không tạo dòng.
- Điểm hữu ích không thành quyền: chỉ ảnh hưởng bậc nhịp trong `max_tier` đã cấp.

## 7. T3: bộ phán xử của từng agent

### 7.1 Kiến trúc

Module thuần mới `server/agent_judge.py`, tái dùng hình dạng của phán xử Zalo (tách "được gọi" khỏi "có nên nói", cổng thô, ca
học, ngưỡng có độ lệch theo ngữ cảnh, tự rà soát có trước/sau, quay lại) nhưng **không** gọi trực tiếp mã bot. Kho riêng
`agent_judge.sqlite3` (dữ liệu nội bộ của chủ, tách khỏi dữ liệu khách Zalo): `profiles(agent_key, role_text, eagerness,
role_hash)`, `decisions(id, agent_key, context_ref, source_event, verdict speak|wait|silent, address certain|none, score,
threshold, reason, silence_code, wait_until_json, ledger_ref, label, label_source, created_at)`, `offsets(agent_key, context_ref,
offset)`, `cases(agent_key, context_ref, text_sha, features, label, weight)`, `changes(...)` (khuôn `changes` Zalo),
`waits(decision_id, agent_key, context_ref, until_kinds, until_ts, status)`.

- Hồ sơ riêng từng agent (vai từ file agent, độ hăng hái), ngưỡng và ca **theo ngữ cảnh**: ca thô chỉ lấy từ cùng ngữ cảnh; ngữ
  cảnh khác chỉ góp bài học đã trừu tượng hoá (mục 8). Hai agent vai khác nhau có thể ra quyết định khác nhau cho cùng một tin.
- Kết quả chỉ là quyết định có cấu trúc `{verdict, score, reason, wait_until, ask_clarify}`; câu trả lời vẫn do agent tạo với
  persona của mình.

### 7.2 Chat nhóm

1. **Được gọi trực tiếp** (mentions có cấu trúc, ô điều phối của tin thường, việc giao): đi đường trả lời hiện có, không qua phán
   xử, ghi `decision` với `address=certain` để có lịch sử.
2. **Không được gọi:** với mỗi thành viên hoạt động còn lại, **lọc bằng code** (quan hệ với việc đang mở, câu hỏi chung cho nhóm,
   từ khoá vai, vừa có đóng góp liên quan); không qua cổng thì `silent` code `no_signal`, không gọi model.
3. Ứng viên qua cổng: **một** lời gọi model theo lô cho cả nhóm ứng viên trên tin đó (purpose `judge`, vào sổ lượt và trần ngày
   của nhóm), trả quyết định từng `agent_key`.
4. **Điều phối:** host giữ tối đa `K` người tự lên tiếng mỗi tin (mặc định 1, chủ đổi được trong Nâng cao), ưu tiên điểm cao và
   không trùng với người đã được gọi; không round-robin. Người được chọn chạy lượt `member_volunteer` (không có lệnh quản trị).
5. Lỗi phán xử, hết giờ, sai cấu trúc: ứng viên `silent` code `policy_error`; lời gọi trực tiếp không bị ảnh hưởng.

### 7.3 Chat riêng

Câu hỏi trực tiếp của chủ đi luồng trả lời thường (không bao giờ qua phán xử). Phán xử chỉ dùng cho **chủ động**: khi lần thức lớp
3 có điều muốn nói trong chat riêng (nhắc tiếp, hỏi thêm, báo kết quả việc nền), phán xử quyết nói/chờ/im trước khi gửi. Lỗi phán
xử: không gửi, ghi lý do, không mất câu hỏi nào.

### 7.4 Chờ và gỡ chờ

`wait` ghi `waits` với điều kiện gỡ: tin mới của chủ trong ngữ cảnh, người đang nói chốt lượt, việc liên quan đổi trạng thái, mốc
giờ. Gỡ chờ được xét ở các điểm hiện có (`_settle_reply_out`, chuyển trạng thái việc, vòng 5 giây của nhóm). Hết hạn: `silent`
có lý do, hoặc `ask_clarify` gửi trưởng nhóm/chủ một câu hỏi (một lần, có trần). Không chờ vô hạn, không quay vòng.

### 7.5 Lượt xem xét liên quan từ đồng đội

Sau khi `_accept` đăng tin của agent X, host sinh sự kiện `related_review` **chỉ** cho agent có quan hệ có cấu trúc: người nhận
việc/điều phối của việc đó, bước có `input_refs` trỏ tới tin của X, người nhờ hỗ trợ, hoặc lệnh `{"op":"ask_peer","agent_key":..}`
do host kiểm danh tính. Chặn: tự gọi mình, trích dẫn (khối trích bỏ trước khi xét), `@` trong văn bản, độ sâu ≤ 2 tính từ tin gốc
của chủ, một lượt xem xét mỗi (agent, tin gốc), không A→B→A, trần lượt của nhóm. Sự kiện đi qua phán xử của agent nhận như mục
7.2 (bước 2-5).

### 7.6 Dạy phán xử (trục nói/im tách trục nội dung)

- Nhãn từ chủ: chip "Đáng lẽ nên nói" / "Nên im (chen ngang)" trên tin, và **lịch sử quyết định** nói/chờ/im của agent theo nhóm
  (cả ca im không có tin) với nút sửa quyết định; lời nhắc "sao em không trả lời?" trong nhóm được gắn vào quyết định im gần nhất
  của agent đó (host khớp theo thời gian và người được nhắc, không giả tạo tin agent).
- Nhãn chỉ dịch ngưỡng theo ngữ cảnh (kẹp ±0.25, nửa đời 14 ngày như Zalo) và thêm ca; **không** đổi ước lượng nội dung. Một câu
  đúng nhưng chen ngang dạy "nên im"; một lần im bỏ lỡ dạy "nên nói".
- Cộng hưởng tắt: nhãn được lưu, ngưỡng không đổi (chính sách đóng băng); bật lại không phát lại.

## 8. T3: học trong đội

### 8.1 Kho bài học có phạm vi

Bảng `agent_lessons` trong `resonance.sqlite3`: `id, agent_key, scope (team:<id>|dm|*), kind (speak|method|presentation|collab),
text, source (owner|teammate|leader|self|review), source_refs_json, status (active|revoked|superseded|proposed), created_at,
revoked_at, revoked_by`, nhật ký `agent_lesson_events` (trước/sau).

- `JAVIS_LESSON` trong lượt nhóm ghi scope `team:<id>`, nguồn `self`, liên kết lượt/tin/revision; chỉ ghi khi đầu ra còn hợp lệ
  (giữ hợp đồng R3 T1). Lượt nhóm chỉ nạp bài học scope `team:<id>` của nhóm đó và scope `*`.
- Bài học scope `*` (đi mọi ngữ cảnh) chỉ có qua: chủ dặn trong chat riêng (luật chủ, như hiện nay), hoặc tự rà soát thấy cùng bài
  học có bằng chứng ở ≥ 2 ngữ cảnh. Bộ nhớ `MEMORY.md` hiện có vẫn được đọc như trước; bài học mới có phạm vi không ghi vào đó.
- Thu hồi: chủ bấm thu hồi trên thẻ agent; trạng thái `revoked`, không nạp nữa, nhật ký giữ.

### 8.2 Góp ý của đồng đội

Lệnh có cấu trúc `{"op":"peer_feedback","message_id":..,"note":..}` trong lượt của agent: host gán nguồn `teammate`/`leader`, gắn
tin, sản phẩm, revision; đưa vào lượt kế tiếp của agent nhận trong đúng nhóm dưới mục "Góp ý của đồng đội (không phải yêu cầu của
chủ, không phải sự thật đã kiểm)". Không bao giờ thành luật của chủ; nhiều agent đồng ý không được coi là bằng chứng độc lập.
Kết quả đến muộn sau huỷ/sửa/bỏ thành viên/thu hồi quyền chỉ giữ làm bằng chứng.

### 8.3 Tự rà soát và tự áp dụng (Cộng hưởng bật)

- Chạy theo agent khi có đủ bằng chứng mới (≥ 6 nhãn nói/im mới, hoặc ≥ 5 tín hiệu hữu ích mới) và cách lần trước ≥ 24 giờ;
  purpose `review` trong sổ lượt. Một lần tối đa 3 thay đổi từ danh sách đóng: `offset_set` theo ngữ cảnh, `eagerness_set`,
  `lesson_add`/`lesson_remove` scope nhóm hoặc dm, `lesson_promote` lên `*` (cần bằng chứng ≥ 2 ngữ cảnh). Mỗi thay đổi phải dẫn mã
  quyết định/tín hiệu đã cho xem.
- Tự áp ngay trong phạm vi trên, ghi trước/sau; cửa sổ đánh giá: tỷ lệ lỗi (nhãn chen ngang + bỏ lỡ) sau tăng quá 0.15 với ≥ 6
  nhãn thì tự quay lại cả lần rà soát; không lặp thay đổi đã quay lại trong 14 ngày. Không đè thiết lập chủ đang giữ.
- Ngoài phạm vi (đổi quyền, luật chủ, sửa mã/skill/workflow, cấu trúc agent): chỉ ghi **đề xuất có phạm vi** cho chủ.

## 9. Trần và chi phí

- Lượt phán xử nhóm: tính vào trần ngày của nhóm (`daily_turns`) và sổ `agent_calls`. Lượt chủ động, xem xét, tự rà soát: trần
  ngày theo agent `agent_daily_calls` (mặc định 6, chủ đổi được; Toàn quyền không chạm trần này vì không phải trần nhóm) và trần
  chung server hiện có (`JAVIS_RESONANCE_CALL_CEILING`).
- Hết trần: lần thức chỉ chạy code, lý do giữ `pending`, hiển thị "Chờ hạn mức"; không mất phản hồi, không lượt bù hàng loạt khi
  qua ngày (mỗi lý do tối đa một lượt).

## 10. Giao diện (mục 11 GOAL)

Thẻ trợ lý (trang Cộng sự) và hàng thành viên trong ngăn Nhóm, dùng cùng API `GET /agents/{slug}/pulse`:

- Cộng hưởng bật/tắt (có sẵn); trạng thái (`active/awake/slowed/hibernating/waiting_owner/paused/off`) và bậc theo **từng ngữ
  cảnh** (chọn nhóm/chat riêng), lần xem xét gần nhất, lần dự kiến, lý do thức;
- lý do đổi nhịp gần đây (trước/sau, nguồn), phản hồi đã xử lý và trạng thái;
- bài học đang dùng theo phạm vi, nguồn, nút thu hồi;
- bộ phán xử: áp dụng ở đâu, quyết định nói/chờ/im gần đây (cả ca im) và nút sửa ("Đáng lẽ nên nói", "Nên im");
- việc đang làm/chờ/bị chặn (tab Công việc có sẵn).

Nút: Đánh thức, Tạm dừng/Tiếp, Đặt lại nhịp ngữ cảnh, Quay lại thay đổi. Chỉ hiển thị thành công sau khi host xác nhận. Hai ngôn
ngữ, màn hẹp, chữ ≥ 16px.

## 11. T4: lịch sử dài, hiệu năng, vận hành

- Đo bằng engine giả: nhiều nhóm, hàng nghìn tin, nhiều reaction, agent ngủ/thức, phán xử đồng thời; đo riêng API, độ trễ event
  loop, số lượt model giả, số đọc/ghi kho; trình duyệt (thời gian vẽ danh sách, nhiều tab).
- Kiểm: nhiều tab, mất kết nối, restart, huỷ, retry, rời nhóm, đổi trưởng nhóm, bật/tắt Cộng hưởng, thu hồi quyền.
- Nhóm bị chặn hay agent ngủ không chiếm suất của nhóm có việc. Kịch bản VPS chuẩn bị sẵn, **chưa chạy**.

## 12. Ma trận nghiệm thu (GOAL mục 12) → nơi kiểm

| Ca | Mốc | Test chính (host thật, engine giả) |
|---|---|---|
| 1 hai nhóm, tag | T1/T3 | `test_team_t1_goal.py` (tag), `test_agent_judge_scope.py` (ngữ cảnh, bài học) |
| 2 gọi trực tiếp/tự tham gia/im | T3 | `test_agent_judge_team.py` |
| 3 phân công, phản hồi, sửa bản | T1/T3 | test team hiện có + `test_team_peer_feedback.py` |
| 4 sáu reaction hai nơi | T2 | `test_dm_reactions.py`, `test_team_reactions.py` mở rộng, JS |
| 5 bật/tắt Cộng hưởng với feedback | T2/T3 | `test_feedback_wake.py` |
| 6 nhịp dài hạn, ít nhu cầu, im không phạt | T3 | `test_agent_pulse_policy.py` (đồng hồ giả) |
| 7 ngủ thức lại, tắt không tự bật, nghĩa vụ giữ | T3 | `test_agent_pulse_host.py` |
| 8, 28 ghi nhận đóng góp, không đếm trùng | T3 | `test_pulse_contrib.py` |
| 9 thay/bỏ reaction, xoá nguồn | T2/T3 | `test_dm_reactions.py`, `test_agent_pulse_policy.py` |
| 10 không vòng vô hạn, chờ chủ | T3 | `test_agent_judge_team.py`, `test_related_review.py` |
| 11 ưu tiên A→C→B, hai kick | T1 | `test_team_t1_goal.py` |
| 12 sửa/bỏ/đổi/thu hồi/huỷ | T1 | test team hiện có + chốt quyền theo lượt |
| 13 lỗi engine, restart, sổ lượt | T1/T3 | `test_agent_calls_ledger.py` |
| 14 khôi phục nhiều kho | T1 | test rollback hiện có (R9) |
| 15 ba lớp heartbeat không ba lượt | T3 | `test_agent_calls_ledger.py` (reason_ref) |
| 16 đồng hồ giả ngày/tuần/tháng | T3 | `test_agent_pulse_policy.py` |
| 17 phán xử/tự rà soát có sổ, nguồn, quay lại | T3 | `test_agent_judge_review.py` |
| 18 giao diện, hai ngôn ngữ, số đo | T3/T4 | JS + browser smoke + bench |
| 19 hồ sơ riêng từng agent | T3 | `test_agent_judge_team.py` |
| 20 chat riêng | T2/T3 | `test_agent_judge_dm.py` |
| 21 sửa ca im/chen ngang | T3 | `test_agent_judge_labels.py` |
| 22 cá nhân hoá, ít mẫu, emoji sự việc, chưa xem | T3 | `test_agent_pulse_policy.py` |
| 23 hoạt động ở A, ngủ ở B | T3 | `test_agent_pulse_host.py` |
| 24 tự tìm việc đúng quyền | T3 | `test_agent_pulse_host.py` |
| 25 bật lại không phát lại | T2/T3 | `test_feedback_wake.py` |
| 26 tự áp dụng, trước/sau, quay lại | T3 | `test_agent_judge_review.py`, `test_agent_lessons.py` |
| 27 tín hiệu đồng đội, trích dẫn, gỡ chờ | T3 | `test_related_review.py` |

## 13. Ngoài khả năng nền hiện tại, cần anh quyết (không tự thu hẹp)

1. **Chi phí phán xử khi Cộng hưởng tắt:** GOAL yêu cầu phán xử nói/im trong nhóm vẫn chạy khi tắt. Thiết kế giữ phần lọc bằng
   code cho mọi agent, nhưng lời gọi model theo lô chỉ chạy khi nhóm có ít nhất một ứng viên qua cổng; mặc định `K = 1`. Nếu anh
   muốn không tốn lượt nào cho agent tắt Cộng hưởng, có thể đặt "chỉ lọc bằng code khi tắt" (không gọi model).
2. **Sự kiện "đã xem":** cần dashboard gửi sự kiện tin nằm trong khung nhìn. Không theo dõi gì ngoài tin của agent trong Javis.
3. **Pilot chất lượng thảo luận/phán xử/học trên model thật:** chỉ chuẩn bị gói, chờ lệnh.
4. **Đo VPS:** chỉ chuẩn bị kịch bản, chờ lệnh.
