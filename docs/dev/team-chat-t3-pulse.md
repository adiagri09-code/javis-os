# T3 phần P: nhịp thích nghi lớp 3 (0.156.0)

Thiết kế gốc: `docs/superpowers/specs/2026-10-15-team-adaptive-design.md` mục 2, 3, 5, 6, 9, 9.1, 10, 12, 13. Hợp đồng với phần
J (phán xử) và L (học): `docs/dev/team-chat-t3-contract.md`. Phần này không tự gọi model nào trong test; mọi đường qua
`main.py` chặn engine thật ngay lúc dựng.

## 1. Bản đồ mã

| Phần | File | Việc |
|---|---|---|
| Chính sách thuần + kho | `server/agent_pulse.py` | `pulse.v1`: bậc, trạng thái, `decide`, `score`, `compute_k`, `attribute`, `effective_due`; bảng và thao tác kho (`record_signal`, `wake`, `set_state`, `evaluate`, `view`, `record_contrib`, cơ hội, đã xem, thay đổi chính sách) |
| Host | `server/agent_pulse_host.py` | nhịp 30 giây (`PulseHost.tick`), lần thức, lượt quét, bộ chuyển tới `agent_judge` và `agent_budget`, sổ đăng ký mục hiển thị và lý do, route |
| Bộ chiếu | `server/feedback_projector.py` | `record_pulse_signal` (móc T2 đã nối), `record_task_event`, `pulse_wake`, `void_task_event`, thay tín hiệu khi đổi reaction |
| Nhóm | `server/team_runner.py`, `server/team_api.py` | tín hiệu chấp nhận đề xuất, chốt quyết định, sửa sau kết quả, huỷ; thức khi chủ @ hay giao việc; dòng `max_tier`, dự trữ 20% trong bảng giới hạn |
| Kho Cộng hưởng | `server/resonance_store.py` | mở kho là tạo bảng nhịp và nâng cấp một lần; bật lại từ `off` về B3 |
| Máy chủ | `server/main.py` | `_pulse_tick` trong `_scheduler_loop` (cờ bận riêng), phụ thuộc thật, thức khi chủ nhắn chat riêng, xoá agent thì `void` tín hiệu, đăng ký route |
| Giao diện | `dashboard/agent-pulse.js`, `dashboard/pulse-seen.js`, `workspace.js`, `teams.js`, `console.css`, i18n | bảng Nhịp trên thẻ trợ lý và dòng thành viên, sổ `window.JavisPulseParts`, sự kiện đã xem |

## 2. Chính sách `pulse.v1`

Bậc: B0 15 phút, B1 1 giờ, B2 4 giờ, B3 1 ngày, B4 3 ngày, B5 1 tuần, B6 2 tuần, B7 1 tháng, bậc 8 là ngủ đông (không lịch).
Khởi tạo B3. Trạng thái theo bậc: `active` B0-B2, `awake` B3-B4, `slowed` B5-B7, `hibernating` bậc 8; ngoài ra `waiting_owner`,
`paused`, `off` do chủ hay host đặt và chỉ dừng phần chủ động.

Mỗi kỳ đánh giá (`decide`):

1. `dwell = max(2 x khoảng, 1 ngày)` tính từ lần đổi bậc trước (hay mốc bật lại): chưa đủ thì giữ.
2. Lên một bậc khi `u ≥ +0.25` và `new ≥ 1.0`, không nhanh hơn `max_tier` (mặc định B1; chỉ chủ đặt, tới B0).
3. Xuống một bậc (`unhelpful`) khi `u ≤ -0.25` và `new ≥ 1.0`; từ B7 không vào ngủ đông bằng luật này.
4. Xuống một bậc (`low_demand`, không ghi là agent sai) khi không có cơ hội chưa tiêu thụ lúc này và một trong hai:
   (A) không tín hiệu tương tác mới từ lần đổi trước và không cơ hội trong hai lần khoảng; (B) tín hiệu tương tác và cơ hội
   gần nhất đều cũ hơn `max(4 x khoảng, 3 ngày)`.
5. Còn lại giữ. Hysteresis: đổi chiều chỉ sau ít nhất một kỳ giữ.

`new = Σ w·share·decay` của tín hiệu sau `max(last_change_at, resumed_at)` (không tính tín hiệu khởi tạo ngữ cảnh). "Tương tác"
không gồm `seen_ignored`.

Công thức (6.3): `decay = 0.5^(tuổi ngày / 21)` (tuổi âm kẹp 0); `estimate = Σ w·share·v·decay / (Σ w·share·decay + 2)`;
`n_eff = Σ w·share·decay`; `confidence = n_eff / (n_eff + 4)`; `u = estimate x confidence`. Cá nhân hoá chỉ cho reaction
không lý do: `p_s(e) = (số lần e + 3)/(n + 18)`, `k = clamp(1 + 0.3 x (1/6 - p_s)/(1/6) x n/(n + 20), 0.75, 1.25)`, `n` là số
reaction không lý do của người đó trong loại ngữ cảnh (nhóm hay chat riêng), đếm mỗi nguồn một lần, tính lại mỗi kỳ.

Tín hiệu (6.1): ❤️ +0.8 w1, 😮 +0.6 w1, 👍 +0.4 w1, 😂 +0.2 w0.5, 😢 -0.2 w0.4, 😡 -0.4 w0.4; có lý do thì lý do thắng emoji
(đúng ý +0.8, quá dài -0.3, sai dữ kiện/thiếu ý/khó hiểu/lạc đề -0.6, w1, nhiều lý do lấy trung bình); trục nói/im và góp ý
chữ không tạo tín hiệu; chấp nhận đề xuất/chốt quyết định +0.6 w0.8; sửa sau kết quả, huỷ, bác đề xuất -0.4 w0.8; kiểm
khách quan ±0.5 w0.8 (mục 2a); tin chủ động đã xem, qua 24 giờ không tương tác -0.15 w0.6; reaction của agent không bao giờ. `pulse_signals` UNIQUE `(source_ref, agent_key)`; thay reaction thì dòng cũ `superseded_by`, xoá tin/agent thì `void`.

## 2a. Kiểm khách quan và đề xuất: sự kiện host nào được tính

- **Kiểm khách quan (±0.5 w 0.8), chỉ kết luận CUỐI**, một tín hiệu mỗi (mục tiêu, revision), nguồn `obj:<goal_id>:<revision>`:
  - đạt: `GoalStore.finish(..., "succeeded")`, tức A2 vừa đánh giá `met`, mọi guard `clear`, không ở bước khám phá, và (mục tiêu
    có đội) review A5 `pass` hợp lệ; đây là nơi duy nhất đóng mục tiêu là đạt;
  - không đạt: `GoalStore.finish(..., "failed")` (API có, hiện chưa đường nào gọi), hay revision bị gác `blocked/budget` trong
    `_settle` khi kiểm cuối là `not_met` (hết sạch lượt, không còn lần thử nào); kết luận `unknown` không tính;
  - KHÔNG tính: mọi `add_assessment` trong vòng làm việc (`not_met` trung gian), hạn chót qua (chỉ báo), chủ huỷ.
  - Cùng revision về sau có kết luận cuối khác (chủ nới hạn mức rồi đạt): sửa giá trị của chính tín hiệu đó, vẫn một dòng.
  - Người nhận: agent của mục tiêu (`goal_agents`), ngữ cảnh `dm:<agent_key>`, chỉ khi bật Cộng hưởng. Mục tiêu A2 có một tác
    giả sản phẩm, không có bước tổng hợp, nên luật 6.5 thu về tác giả.
  - Việc nhóm: host KHÔNG có kiểm khách quan khi chốt việc (`team_finish` chỉ ghi kết quả), nên không có tín hiệu kiểm.
- **Đề xuất** (`pulse_proposals`): lượt quét `propose` ghi sổ (nguồn, phiên bản). Cùng nguồn cùng phiên bản đã có đề xuất (chờ,
  đã nhận, đã bác) thì không đề xuất lại (5.5). Chủ quyết:
  - nhóm: thẻ trong khung chat (nút Tạo việc là nhận, +0.6, xếp việc vào hàng đợi chung của nhóm như cũ; nút Bỏ qua nay là bác,
    `POST /teams/{id}/messages/{mid}/reject`, -0.4); trạng thái ghi lên tin nên mọi tab thấy, thẻ hết nút;
  - bảng Nhịp: `POST /agents/{slug}/pulse/proposals/{id}/accept|reject`. Chat riêng: nhận thành việc giao cho trợ lý như nút
    Giao việc (Kanban, báo về chat riêng, khoá chống trùng `pp<id>`), +0.6; bác -0.4. Đề xuất trong nhóm từ bảng Nhịp đi đúng
    đường thẻ nhóm. Đã quyết rồi: 409.
  - Trưởng nhóm có Toàn quyền tự xếp việc được (enqueue của lượt quét) nên không cần duyệt đề xuất của chính mình.

## 3. Vectơ đồng hồ giả (`tests/python/test_agent_pulse_policy.py`, đều xanh)

| Kịch bản | Số đo trong test | Kết quả |
|---|---|---|
| 1 ❤️ | k 0.9962, u 0.0531 | giữ B3 |
| 2 ❤️ | k 0.9864, u 0.1315 | giữ B3 |
| 5 ❤️ ở ngày 0,5..2,5 | ngày 2: u 0.2494 (giữ); ngày 3: k 0.935, u 0.2861 | lên B2 đúng một lần, không lên B1 |
| 5 ❤️ cách nhau 3,5 ngày | u 0.2481 ở ngày 14 + 8 giờ, lớn nhất cả dải < 0.25 | giữ B3 suốt đợt |
| 10 ❤️ trong 1 phút | k 0.8214, u 0.3912 | B2 ở kỳ sau dwell, kỳ sau nữa không lên |
| rồi 10 ❤️ mỗi 1,4 ngày | | tới B1, không bao giờ B0, im lâu thì chậm lại |
| 3 👍 1 ❤️ 1 😮 | k 0.997 / 0.966 / chưa dùng 1.013 | k luôn trong 0.75-1.25 |
| Im lặng từ B3 | | ngày 2 B4, 8 B5, 22 B6, 50 B7, 110 ngủ đông (ngày 30 B6, 90 B7, 180 ngủ đông) |
| 3 tin chủ động đã xem bị bỏ qua | u -0.0221 | không `unhelpful`; `low_demand` khi không có gì khác, giữ khi có cơ hội |
| 5 / 6 "sai dữ kiện" | u -0.2378 / -0.2697 | giữ / xuống B4 (`unhelpful`) |
| Im lặng đúng (có cơ hội, phán xử im) | estimate 0 | không phạt, không `low_demand` trong hai lần khoảng |
| Gọi trực tiếp lúc ngủ đông | | về B3 ngay, giữ ước lượng |

## 4. Host (`tests/python/test_agent_pulse_host.py`)

- `_scheduler_loop` tạo `_pulse_tick` mỗi 30 giây khi cờ bận của nó rảnh. Nhịp: chiếu outbox phản hồi (T2), tạo dòng ngữ cảnh
  theo phạm vi (mỗi 5 phút), quét `seen_ignored`, nhắc chờ chủ một lần sau 24 giờ, đóng cửa sổ thay đổi chính sách, tìm lịch
  tới hạn và nhận bằng CAS (`claim_token`, `claim_until` 10 phút), điều phối lý do cho phần đã đăng ký.
- Agent bận (khoá bận, việc nhóm chạy/xếp hàng, goal A2 đang chạy): dời đúng 60 giây, không nhận.
- Lần thức: lập cơ hội (việc nhóm của agent cũ hơn khoảng hiện tại, việc bị chặn có tin mới, đề xuất của trưởng nhóm chưa ai
  xử lý, goal của agent chờ chủ quá 24 giờ), lọc theo `pulse_opportunities` (tiêu thụ một lần cho tới phiên bản mới), đánh
  giá bậc, rồi chỉ khi có cơ hội mới (hay tới lượt quét giới hạn: mỗi 3 lần thức ở active/awake, tối đa một lần mỗi ngày mỗi
  ngữ cảnh) mới gọi model.
- Lượt quét: thử khoá bận KHÔNG chờ trước (bận: dời 60 giây, không tốn lần thử), hỏi `agent_budget.try_spend` (chưa có module
  thì qua), giữ chỗ `agent_calls` purpose `scan`, `obligation = 0`, `reason_ref = pulse:<agent>:<ngữ cảnh>:<mốc>` TRƯỚC engine.
  Lịch đó đã có lượt tới model (khởi động lại) thì không chạy lần hai. Đầu ra `{"action": none|propose|enqueue|say}`; enqueue
  chỉ khi là trưởng nhóm có Toàn quyền, không thì thành đề xuất; quét giới hạn không có nguồn thì không tạo gì; `say` luôn qua
  `agent_judge.judge_proactive`, thiếu module thì `silent` với lý do `judge_unavailable`.
- Nghĩa vụ không đi qua lớp 3: test chạy bộ chạy nhóm thật với agent đang tạm dừng, ngủ đông, tắt nhịp và kiểm lời gọi trực
  tiếp và việc nhóm vẫn chạy.

## 5. Di trú và quay về

- Mở `resonance.sqlite3` bằng mã này: tạo `agent_pulse_events`, `pulse_signals`, `pulse_contrib`, `message_seen`,
  `pulse_opportunities`, `pulse_proactive`, `pulse_policy_changes`, `pulse_proposals`, `pulse_meta`, thêm cột có mặc định cho
  `agent_pulse`. Lần
  đầu (mốc `pulse_v1_upgraded_at`): mọi dòng nhịp về B3, `resumed_at = lúc nâng cấp`, agent tắt Cộng hưởng ở `off`; reaction cũ
  không thành tín hiệu.
- Quay về 0.154.x: bản cũ bỏ qua bảng và cột mới (cột đều có mặc định). Khôi phục hẳn dùng bản chụp `.pre-0.154.0` như T2.

## 6. Quyết định khi làm

1. **Luật `low_demand` (B):** đọc đúng chữ luật 4 (không tín hiệu mới từ lần đổi, không cơ hội trong hai lần khoảng) thì một
   reaction ngay sau lần đổi giữ bậc nhanh mãi mãi, trái câu "im lâu thì chậm lại". Thêm (B) "im quá `max(4 x khoảng, 3
   ngày)`". Ngưỡng 4 lần khoảng là để vectơ "5 ❤️ rải 2 tuần" (cách 3,5 ngày) vẫn giữ B3 và vectơ "10 ❤️ mỗi 1,4 ngày" vẫn tới B1.
2. **Ở B1-B2 agent dao động một bậc** khi tương tác thưa hơn dwell (luật A). Có hysteresis và dwell nên mỗi lần đổi cách nhau ít
   nhất một ngày; test ghim điều đó.
3. **Giá trị khởi tạo ngữ cảnh mới "0,5 x tổng hợp"** là một tín hiệu khởi tạo (`context_init`) mang ước lượng tổng hợp với
   `w = min(1, 0.5 x n_eff tổng hợp)`, suy giảm như tín hiệu khác, không phải bằng chứng mới, không vào `k`.
4. **Nhiều lý do chất lượng** trên một reaction: lấy trung bình giá trị.
5. **`k` chỉ đếm reaction không lý do** (reaction có lý do dùng giá trị của lý do, `k = 1`).
6. **Kiểm khách quan chỉ tính kết luận cuối** (mục 2a), không bao giờ đánh giá trung gian.
7. **Bỏ qua trên thẻ đề xuất nhóm nay là bác** (ghi máy chủ, -0.4); trước đây chỉ ẩn ở trang.
8. **Bỏ chốt rồi chốt lại** cùng tin không tính lại (nguồn đã `void` giữ chỗ UNIQUE), chống bấm qua lại để nâng điểm.
9. **Lý do lớp 3 khi tạm dừng:** host không điều phối lý do của ngữ cảnh `paused`/`off`; ngủ đông và chờ chủ vẫn được.
10. **`POST /seen`** nhận thêm `context_ref = "session:<mã phiên>"` (trang không biết `agent_key`); máy chủ đổi sang
    `dm:<agent_key>` và trả `agent: false` cho phiên không phải của trợ lý để trang thôi gửi.
11. **Đề xuất ở chat riêng** là một tin đề xuất có nguồn (chưa có thẻ riêng); ở nhóm là tin mang `proposal` (nút Tạo việc sẵn có).
12. **Không có `agent_budget`** (phần L chưa có) thì lượt quét không bị trần ngày; trần chung máy chủ và dự trữ 20% vẫn áp.
13. **Đặt lại nhịp ngữ cảnh** giữ lịch sử và ước lượng, chỉ đưa về B3 và coi bằng chứng trước mốc là cũ.
14. **Khoá bận khi chưa có kho nhóm:** khoá trong tiến trình (chưa có lượt nhóm nào để tranh khoá).

## 7. Chỗ phần J và L cắm vào

- `agent_pulse_host.register_view_part(name, fn(store, agent_key) -> dict)`: mục trong `GET /agents/{slug}/pulse` (`parts`).
- `window.JavisPulseParts.push({name, render(view) -> html})`: mục trên bảng Nhịp (tự escape).
- `agent_pulse_host.register_reason_handler(code, fn(host, reason))`: phục vụ `reaction_review` (L), `related_review`,
  `wait_unblocked` (J). Hàm tự nhận lý do bằng `WakeReasons.claim(reason_id, try_busy=..., release_busy=...)` với
  `host.busy_pair(agent_key)`.
- `agent_judge.judge_proactive(*, agent_key, context_ref, draft, source_event, engine)`: `engine` là hàm không đối số trả
  `(engine, model, run)` của host (dựng lười). Trả `Decision`; `speak` mới gửi.
- `agent_budget.try_spend(agent_key, purpose, at=None) -> (ok, reason)`: host gọi với purpose `scan` trước khi giữ chỗ.
- `agent_pulse.register_policy_reverter(kind, fn(change))`, `apply_policy_change`, `record_policy_labels`,
  `revert_policy_change`, `observe_policy_changes` (6.4).
- `agent_pulse.wake(store, agent_key, context_ref, why)` cho lượt xem xét liên quan và gỡ chờ; `agent_pulse.record_event(...)`
  ghi quyết định vào `agent_pulse_events`.

## 8. Kiểm

Engine giả ở mọi nơi; không lời gọi model thật. (Phiên làm việc không ghi được ra `exports/reviews/`, nên bằng chứng nằm ở đây.)

- `test_agent_pulse_policy.py` 100 kiểm, `test_agent_pulse_host.py` 66 kiểm (gồm chặn engine thật qua `main.py`, route,
  `POST /seen`, nhận/bác đề xuất), `test_pulse_contrib.py` 49 kiểm (gồm kiểm khách quan, bác đề xuất),
  `tests/js/test_agent_pulse_ui.js` 45 kiểm: đều xanh.
- `tests/run.py pulse team resonance feedback agent_calls i18n icons route_table`: 88/89, cái đỏ là `test_resonance_perf.py`
  (trễ event loop 0,114 giây > 0,1). So với `origin/claude/team-adaptive-t3` trong worktree sạch: bản gốc 4/4 xanh, nhánh 3/4 đỏ,
  nên là lỗi thật của nhánh: `GoalStore` dựng trong event loop ở GET đầu tiên và `agent_pulse.ensure` ghi nhiều lần. Sửa ở
  `865758bf` (kho đã đủ bảng thì không ghi gì; lần đầu tạo bảng trong một giao dịch): 4/4 xanh. Chạy lại `pulse feedback
  agent_calls team_adaptive rollback resonance_a1`: 20/20 xanh.
- `tests/run.py --js`: 193/193 xanh.
- Soi giao diện (khung tĩnh dùng đúng `console.css`, `style.css`, `agent-pulse.js`, i18n; phục vụ cục bộ; 375x812): tối và
  sáng, vi và en, không cuộn ngang (scrollWidth 375), chữ nhỏ nhất 16px, nút và ô chọn cao 44px. Chưa soi trên dashboard thật
  (sandbox cổng 7788) và chưa soi trên điện thoại thật.
