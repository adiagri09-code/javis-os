# Resonance A5: một agent làm, một agent review (thiết kế)

**Trạng thái:** bản thiết kế vòng 1, **chờ review thiết kế**. Chưa có mã A5, chưa gọi model thật, chưa merge, không đụng VPS. Các mặc định ở mục 16 là đề xuất có lý do, chưa phải quyết định đã duyệt; mục 16.2 gom những điểm cần chủ dự án quyết.

- **Nhánh:** `claude/resonance-a5-maker-reviewer`, PR nháp #616, giữ số **0.97.0**.
- **Nền:** `main` `dc18942e` (0.96.1). A1 0.87.0, A2 0.88.0, A3 0.89.0, A4 0.96.0 (`d36ebb3e`) đã phát hành.
- **Đầu vào:** [lộ trình agent](2026-10-08-resonance-agent-scope-roadmap.md) mục 7 và 8; [thiết kế A4](2026-10-10-resonance-a4-handoff-grants-design.md) (bất biến 5, mục 5.4 `narrow`, mục 12.5 các ca để lại cho A5); [thiết kế A3](2026-10-09-resonance-a3-feedback-learning-design.md) mục 16; mã hiện tại của `server/resonance*.py`, `server/main.py` (workflow, `_resonance_engine`), `server/workflow_graph.py`, `server/agent_runtime.py`.
- **Mức bằng chứng:** đọc mã và tài liệu. Chưa chạy thử gì cho A5. Số dòng mã dẫn theo `dc18942e`.

## 1. Mục tiêu và ngoài phạm vi

Lộ trình (mục 7): "một agent làm và một agent review, một goal chịu trách nhiệm cuối"; review gắn đúng hash và revision; reviewer không tự sửa tiêu chí; hạn mức chung có chia phần; bản đổi sau review phải được review lại; owner dừng thì cả hai dừng; không tự sinh agent mới để vượt chốt.

**Người dùng thấy:**
- Trên trang một agent đã bật Cộng hưởng, chủ dự án chọn một agent khác làm **người review**. Từ đó mục tiêu mới của agent này đi qua review trước khi được coi là đạt.
- Thẻ mục tiêu cho biết ai đang làm, ai đang review, bản nào (mã ngắn của bản) đã được review, kết luận, vì sao đang chờ, và lượt còn lại của từng vai.
- Review đòi sửa thì agent làm tự sửa theo góp ý, có giới hạn số vòng. Hết vòng hay hết lượt thì dừng và báo, không tự nới.

**Giữ nguyên:**
- Chat thường vẫn là chat thường; không áp Cộng hưởng hay review lên cuộc trò chuyện không có mục tiêu.
- Hợp đồng nộp và đăng của A4 (`javis_submit_deliverable`, `host_publish` bốn bước, quyền theo phạm vi D1) không đổi.
- Nhịp tim A2 (thức có lý do, không hỏi model định kỳ) và vòng phản hồi A3 (reaction không đổi lịch, không thay kết luận) không đổi.
- Tiêu chí `human_confirmation` và guard giữ nguyên quyền phủ quyết.

**Ngoài phạm vi:**
- Đội hơn hai agent, agent tự sinh agent, supervisor tổng quát, mục tiêu con.
- Giao việc từ chat thường chưa được chốt; thay đổi hành vi file đích có sẵn (`target_occupied`); tối ưu VPS; tự sửa mã sản phẩm.
- Review chạy trong lượt chat (reviewer chỉ chạy ở việc nền).
- Lệnh nâng hạn mức (hiện chưa có; xem 16.2).

## 2. Hiện trạng: dùng lại và khoảng trống

| Cần cho A5 | Đã có | Ở đâu | Khoảng trống |
|---|---|---|---|
| Danh tính agent do host cấp | `agent_key`, `config_version`, `agent_gate` | `resonance_store.py` `agent_set_enabled` (:492), `resonance.py` `agent_gate` (:502), `_agent_block` (:680) | Chưa có vai thứ hai trên một mục tiêu; `assign_goal` (:2114) chỉ gán một agent |
| Giữ chỗ lượt trước khi gọi, ghi bền | `begin_action` trong `BEGIN IMMEDIATE`, `_ReservedCall`, `release_call`, `abort_action`, `_reconcile` | `resonance_store.py` :1439, :1148, :1856; `resonance.py` :1897, :2213 | Chưa chia phần theo vai |
| Trần chung | `call_ceiling`, `_under_ceiling` | `resonance_store.py` :32, :53 | Dùng nguyên |
| Đánh thức có lý do | `wake_reasons`, `CLASSES`, `HB.decide`, `auto_allowed` | `resonance_heartbeat.py` :40, :112, :130 | Chưa có mã lý do review |
| Chống chạy chồng | lease mục tiêu, CAS `claim_wake`, CAS revision | `resonance_store.py` :1424, :1341 | Dùng nguyên: cả hai vai dùng chung một lease mục tiêu |
| Đánh giá theo revision | `evaluate_artifact`, `Assessment` met/not_met/unknown, `_human_verdict` gắn sha | `resonance.py` :1578, :1074, :1559 | Chưa có điều kiện review |
| Engine việc nền chỉ chữ | `_resonance_engine`, `pick_text_only_link`, `SYSTEM_PROMPT` | `main.py` :2039; `resonance.py` :181, :46 | Dùng nguyên cho cả hai vai |
| Bằng chứng | `_ResonanceEvidence`, `_put_evidence` lỗi thì None | `main.py` :2280; `resonance.py` :1525 | Dùng nguyên |
| Quyền ghi theo phạm vi | grants root/revision, bindings, `authority_clock` | `resonance_store.py` A4 | Reviewer không nhận quyền ghi nào |
| Reviewer trong workflow | `verify_agent`, JSON `{pass, reason, fixes}`, vòng sửa | `main.py` :9157-9205, :9622-9669 | KHÔNG dùng nguyên khối (xem dưới) |

**Vì sao không chạy review qua workflow:** bước `verify_agent` hiện tại đọc kết luận từ chữ tự do bằng regex, thiếu JSON hay lỗi engine đều tính là **đạt** (`main.py` :9179, :9187, :9645, :9653); bước review không đạt vẫn hoàn tất và chuyển tiếp; không đếm lượt gọi, không chạm trần Resonance; chạy engine của agent có công cụ và nhà cung cấp dự phòng. A5 chỉ dùng lại **lời dặn review** ("mặc định coi kết quả là sai") và **mẫu góp ý cho vòng sửa** (bản trước kèm lý do và cách sửa). Kết luận đọc theo kiểu đóng khi lỗi, lượt đi qua sổ Resonance.

**Hai sự thật phải nói rõ:**
- Việc nền KHÔNG chạy bằng engine của agent: cả lượt làm và lượt review đều chạy bằng model "việc nền" chung của người dùng, chỉ chữ, không công cụ (`resonance.py` :527-529). Mặc định **hai vai dùng cùng một model**; khác nhau ở danh tính, lời dặn vai và dữ liệu được thấy, không phải ở bộ não độc lập (xem 16.2, điểm Q3).
- Lời nhắc việc nền hiện không đưa nội dung file agent vào (`_work_prompt`, `resonance.py` :1862). A5 thêm phần mô tả vai của reviewer (thân file agent, có giới hạn độ dài, đánh dấu là dữ liệu). Phía agent làm giữ nguyên như hiện tại.

## 3. Bất biến

1. **Host quyết định ai làm gì.** Vai, `agent_key` và `config_version` của mỗi vai do host ghim lúc gán mục tiêu; lời model không đổi được vai, tiêu chí, quyền hay hạn mức.
2. **Review gắn đúng bản.** Một kết luận review chỉ có giá trị cho đúng bộ (`goal_id`, `revision`, sha bản, hash tiêu chí, `reviewer_agent_key`, `reviewer_config_version`). Đổi bất kỳ thành phần nào thì kết luận cũ không dùng để chốt.
3. **Review không thay phủ quyết.** Review đạt không xoá guard, không thay `human_confirmation`, không bù cho tiêu chí khách quan chưa đạt.
4. **Đóng khi lỗi.** Không đọc được kết luận, lỗi engine, lỗi lưu bằng chứng, dữ liệu lệch đều là `unknown`, không bao giờ là đạt.
5. **Một sổ, chia phần.** Mọi lượt của hai vai đi qua `begin_action` và trần chung; mỗi vai có phần riêng; giữ chỗ trước khi gọi; chỉ hoàn khi chắc engine chưa chạy; không tự nới.
6. **Dừng thắng.** Tạm dừng, huỷ, thu hồi quyền, tắt agent có hiệu lực cho cả hai vai theo phạm vi; lượt cũ không hưởng quyền cấp lại.

## 4. Mô hình đội

### 4.1 Hai vai

| Vai | Là ai | Được làm | Không được |
|---|---|---|---|
| Làm (`maker`) | Agent chịu trách nhiệm cuối của mục tiêu, đúng là agent của `goal_agents` | Lập và sửa mục tiêu trong chat (A1), nộp bản (A4), làm việc nền | Tự chấm đạt; đổi người review |
| Review (`reviewer`) | Một agent Cộng hưởng khác cùng brain, do chủ dự án chọn | Đọc ảnh chụp bản đã nộp và tiêu chí, trả kết luận | Ghi file, nộp bản, sửa tiêu chí, quyền hay hạn mức, chạy trong chat |

Reviewer không có grant nào (không root, không revision). Mọi hành động có tác động vẫn đi qua cổng A4 của vai làm.

### 4.2 Chọn hai agent và bật chế độ đội

- Chủ dự án bật trên trang agent làm: ô **Người review** liệt kê các agent đã bật Cộng hưởng trong cùng brain, trừ chính nó. Chọn một agent là bật chế độ đội cho agent này; bỏ chọn là tắt. Không có ô cài đặt nào khác (hạn mức và số vòng dùng mặc định, mục 6).
- Lưu ở bảng `team_pairs` (mục 9), chỉ chủ dự án đổi được (Principal `owner`), mỗi lần đổi tăng `config_version` của cặp.
- **Ghim lúc gán:** khi `assign_goal` gán mục tiêu cho agent làm và cặp đang bật, host ghi `goal_team` trong cùng giao dịch, ghim `reviewer_agent_key` và `reviewer_config_version`. Đổi cặp sau đó không ảnh hưởng mục tiêu đang chạy.
- **Tách đội khỏi một mục tiêu:** lệnh chủ dự án `team_detach` chuyển `goal_team.status` sang `detached` và ghi sự kiện; từ đó mục tiêu chốt theo luật A4 như cũ. A5 không hỗ trợ gắn lại hay đổi reviewer giữa chừng.

### 4.3 Reviewer được thấy gì

Host dựng đầu vào review từ dữ liệu của chính host, không cho reviewer đọc file hay công cụ:
- Hiểu biết mục tiêu và tiêu chí của revision hiện tại (đánh dấu là dữ liệu). Bỏ qua tiêu chí `human_confirmation` (người dùng tự xác nhận).
- Ràng buộc người dùng đã nêu.
- **Ảnh chụp bản được review**: đọc từ bằng chứng đã lưu của bản nộp đã tiếp nhận (A4 `adopt_submission`), không đọc lại file đích. Giới hạn `REVIEW_INPUT_MAX_CHARS` (đề xuất 60.000), kiểm trước khi giữ chỗ; dài hơn thì không cắt, không gọi engine, kết luận `unknown/too_large`.
- Mô tả vai của reviewer: thân file `agents/<slug>.md`, tối đa 4.000 ký tự, đánh dấu là dữ liệu.
- Không thấy: lịch sử chat, lời nhắc của agent làm, kết luận review cũ (tránh neo theo kết luận trước), đường dẫn ngoài brain.

## 5. Vòng làm và review

### 5.1 Trạng thái của đội trên một revision

Trạng thái của mục tiêu vẫn là `run_state`/`block_reason` hiện có; A5 thêm lý do chờ và lý do chặn mới, không thêm máy trạng thái song song.

| Trạng thái quan sát được | Nghĩa | Vào khi | Ra khi |
|---|---|---|---|
| `working` | Agent làm đang có lượt | Lý do làm việc hiện có (A2), hoặc `review_changes` | Lượt xong, bản được tiếp nhận |
| `waiting/review_pending` | Bản đạt kiểm khách quan, chờ review | `_settle` thấy tiêu chí khách quan đạt mà chưa có review hợp lệ | Lý do `review_due` được phục vụ |
| `reviewing` | Reviewer đang có lượt | Hành động `review` bắt đầu | Kết luận được ghi |
| `waiting/review_changes` | Review đòi sửa, chờ lượt làm | Kết luận `needs_changes` còn vòng | Lượt làm mới |
| `waiting/human_confirmation` | Review đạt, còn chờ chủ xác nhận | Có tiêu chí `human_confirmation` | Như A4 hiện tại |
| `succeeded` | Đạt | Khách quan đạt, review hợp lệ đạt, xác nhận người (nếu có) đạt | Cuối |
| `blocked/review_rounds` | Hết vòng sửa | `needs_changes` khi đã dùng đủ `max_rounds` | Chủ dự án tách đội, huỷ, hay sửa mục tiêu |
| `blocked/review_unknown` | Review không ra kết luận sau số lần thử | `unknown` lặp quá `ERROR_MAX_FAILS` của reviewer | Như trên |
| `blocked/budget_maker`, `blocked/budget_reviewer` | Hết phần lượt của một vai | `begin_action` không giữ được chỗ cho vai đó | Như trên |
| `blocked/reviewer_off` (và `reviewer_missing`, `reviewer_changed`, `reviewer_retired`) | Agent review không dùng được | Cổng vai review (mục 7.3) | Agent bật lại đúng phiên bản; hay tách đội |

Sơ đồ chuyển (một revision):

```
lượt làm -> bản tiếp nhận -> kiểm khách quan
   kiểm khách quan not_met  -> lượt làm (luật A2 như cũ, phần lượt của vai làm)
   kiểm khách quan unknown  -> chờ/thử lại như cũ, không review
   kiểm khách quan met      -> có review hợp lệ cho bộ hiện tại?
        có, pass            -> human_confirmation? -> waiting_human : succeeded
        có, needs_changes   -> còn vòng? -> review_changes -> lượt làm : blocked/review_rounds
        có, unknown         -> còn lần thử? -> review_due : blocked/review_unknown
        chưa có             -> review_due -> lượt review -> ghi kết luận -> quay lại kiểm
```

Thứ tự này cố ý: **review chỉ chạy trên bản đã đạt kiểm khách quan**, nên không tốn lượt review cho bản còn thiếu ý kiểm được bằng code.

### 5.2 Hợp đồng lượt review

**Đầu vào** (mục 4.3) cùng lời dặn cố định của host:
- Mặc định coi bản là chưa đạt; chỉ kết luận `pass` khi mọi tiêu chí đều đạt rõ ràng.
- Chỉ trả về MỘT đối tượng JSON, không gì khác.

**Đầu ra hợp lệ duy nhất:**

```json
{"verdict": "pass" | "needs_changes",
 "criteria": [{"index": 0, "ok": true, "reason": "..."}],
 "fixes": "..."}
```

**Đọc kết luận (đóng khi lỗi):**
1. Bỏ một lớp rào ```` ```json ```` nếu có; phần còn lại phải là đúng một đối tượng JSON. Không dò regex trong chữ tự do.
2. `verdict` thuộc hai giá trị trên; `criteria` phủ đúng mọi chỉ số tiêu chí đã gửi, mỗi mục có `ok` kiểu bool.
3. `pass` mà có mục `ok: false`, hay `needs_changes` mà mọi mục `ok: true` và `fixes` rỗng: mâu thuẫn, thành `unknown/inconsistent`.
4. Sai bất kỳ điều nào: `unknown/parse_error`. Lỗi engine: `unknown/engine_error`. Lưu bằng chứng hỏng: `unknown/storage_error`.
5. Trường lạ bị bỏ qua và ghi vào sự kiện; không trường nào đổi được tiêu chí, quyền, hạn mức hay vai.

**Ghim:** hành động `review` ghi khi bắt đầu đúng bộ (`goal_id`, `revision`, `submission_id`, `artifact_sha`, `criteria_hash`, `reviewer_agent_key`, `reviewer_config_version`). `criteria_hash` là sha256 của JSON chuẩn hoá các tiêu chí của revision (host giữ, không từ model).

**Ghi kết luận** (một giao dịch `BEGIN IMMEDIATE`): CAS hàng `reviews` từ `running` sang `done` theo `action_id`; kiểm lại bộ ghim so với hành động; lệch thì ghi `review_mismatch`, kết luận không được dùng. Ghi lần hai cùng `action_id` bị bỏ qua (kết quả gửi lại không nhân đôi).

### 5.3 Góp ý quay lại agent làm

- Kết luận `needs_changes` thêm lý do `review_changes` (lớp AUTO, phần lượt của vai làm, `source_ref` là id review; trùng thì gộp như A2).
- Lượt làm kế tiếp dùng `_work_prompt` hiện có, thêm khối "Người review góp ý (dữ liệu)": các tiêu chí `ok: false` với lý do, và `fixes` (tối đa 4.000 ký tự). Bản trước đi qua `prev_text` như hiện tại.
- Trong chat, agent làm thấy góp ý trên thẻ (mục 11); lượt chat không tự mở.

### 5.4 Số vòng và kết thúc

- `max_rounds` mặc định 2 (bản đầu cộng hai lần sửa theo review), ghim trong `goal_team` lúc gán.
- Mỗi kết luận `needs_changes` hợp lệ trên revision hiện tại tính một vòng. Revision mới (chủ dự án sửa mục tiêu trong chat) đếm lại vòng từ 0 nhưng **không** hoàn lượt đã dùng.
- Hết vòng: `blocked/review_rounds`, tin `goal.review_exhausted` (loại phải gửi). Không tự nới vòng, không tự đổi reviewer.

### 5.5 Review cũ

Review hợp lệ cho bản hiện tại chỉ khi khớp cả bộ ghim với trạng thái lúc chốt: revision hiện tại, sha của bản đang đăng (cùng sha mà `_human_verdict` dùng), hash tiêu chí hiện tại, reviewer và phiên bản đã ghim trong `goal_team`. Các trường hợp làm review cũ hết giá trị:
- bản bị sửa sau review (chủ dự án sửa tay, A4 tiếp nhận tại chỗ, hay bản mới): sha đổi;
- revision đổi khi đang review: kết luận ghi nhưng mang revision cũ;
- tiêu chí đổi: hash đổi;
- reviewer đổi cấu hình: `reviewer_config_version` lệch.

Review cũ vẫn giữ trong hồ sơ, không xoá.

## 6. Hạn mức chia phần

- **Một sổ:** `goals.budget_calls` và `calls_used` như hiện tại, cùng trần `JAVIS_RESONANCE_CALL_CEILING`.
- **Chia phần:** bảng `team_calls(goal_id, role, cap, used)`. Đề xuất mặc định cho mục tiêu có đội: `budget_calls = 8`, vai làm 4 (bản đầu, hai lần sửa, một lần thử lại lỗi), vai review 4 (ba bản, một lần thử lại `unknown`). Mục tiêu không có đội giữ `GOAL_DEFAULT_CALLS = 6`.
- **Giữ chỗ:** trong cùng giao dịch `begin_action`, sau kiểm trần và `calls_used < budget_calls`, thêm `UPDATE team_calls SET used = used + 1 WHERE goal_id = ? AND role = ? AND used < cap`. Hỏng ở bất kỳ bước nào thì không giữ chỗ nào, trả lý do `budget_maker` hay `budget_reviewer`.
- **Hoàn:** mọi đường hoàn hiện có (`release_call` trước khi gọi engine, `abort_action` khi huỷ trước engine) hoàn cả hai bộ đếm trong cùng giao dịch. Engine có thể đã chạy (huỷ giữa lượt, mất kết quả, khởi động lại khi đang `running`): không hoàn.
- **Dự trữ A2:** `auto_allowed` giữ một lượt dự trữ theo vai: lượt AUTO của vai nào chỉ chạy khi vai đó còn ít nhất hai lượt, trừ lượt review đầu tiên của một bản (lớp START của review).
- **Lượt chat** của agent làm không tính vào sổ mục tiêu (như hiện tại). Review của bản nộp từ chat tính vào phần vai review.
- Hết phần: chặn và báo (mục 5.1). Không tự nâng trần, không tạo agent thay thế.

## 7. Quyền, engine và giới hạn phải nói thật

### 7.1 Cái gì được thực thi ở đâu

| Giới hạn | Thực thi bởi | Mức chắc chắn |
|---|---|---|
| Reviewer không gọi công cụ, không đọc ghi file, không chạy lệnh | Engine việc nền dựng chỉ chữ, chặn công cụ, thư mục làm việc rỗng; `pick_text_only_link` trả None nếu không chặn được | Thực thi bằng cấu hình engine, như mọi lượt việc nền hiện nay |
| Lời reviewer không thành sản phẩm | Hành động `review` không có đường nộp: host chỉ đọc kết luận, không gọi `submission_from_output` | Thực thi bằng mã host |
| Reviewer không đổi tiêu chí, quyền, hạn mức, vai | Đầu ra chỉ có ba trường; host bỏ qua mọi trường khác | Thực thi bằng mã host |
| Agent làm chỉ ghi vào phạm vi được cho phép | Grant và binding A4 | Như A4: trong hợp đồng host. Lượt chat của engine CLI có công cụ gốc (Bash, Write); hub không chặn được công cụ gốc (thiết kế A4 mục 6.3) |
| Review gắn đúng bản | Ghim và CAS trong kho | Thực thi bằng mã host |

### 7.2 Không hứa quá

- Hai vai mặc định cùng một model việc nền; độc lập ở vai và dữ liệu, không ở bộ não.
- Review là ý kiến của model, có thể sai; nó không thay kiểm khách quan, guard hay xác nhận của người.
- A5 không làm engine nào có sandbox rộng hơn hiện nay. Engine khác Claude Code chỉ được kiểm bằng engine giả cho tới khi có pilot riêng.

### 7.3 Cổng vai review

Mỗi lần đánh thức có hành động, `_gate` hiện có kiểm agent làm. A5 thêm kiểm agent review của `goal_team` đang `active` bằng `agent_gate(reviewer_agent_key, reviewer_config_version)`: không đạt thì `blocked/reviewer_<lý do>` với hẹn kiểm lại `agent_recheck` như agent làm. Lượt review đang chạy mà reviewer đổi phiên bản: kết luận ghi nhưng là review cũ (mục 5.5).

## 8. Dừng, tắt, huỷ, thu hồi

| Thao tác của chủ dự án | Vai làm | Vai review | Lượt đang chạy |
|---|---|---|---|
| Tạm dừng mục tiêu | Không đánh thức `work` | Không đánh thức `review` (cùng điều kiện `paused`) | Chạy hết; kết quả ghi; không chốt đạt khi đang dừng (như hiện tại) |
| Huỷ mục tiêu | Dừng hẳn | Dừng hẳn | Trước engine: `abort_action`, hoàn lượt; có thể đã chạy: không hoàn, kết quả không dùng |
| Thu hồi quyền ghi (A4) | Như A4: bản chưa commit thành `stale`, binding `dead`, mục tiêu tạm dừng | Không có quyền để thu hồi; bị dừng theo mục tiêu | Như A4 |
| Cấp lại quyền | Lượt cũ không hưởng quyền mới (A4 `authority_clock`) | Review cũ còn giá trị nếu bộ ghim vẫn khớp; bản mới cần review mới | |
| Tắt agent làm | `blocked/agent_off` như A1 | Không chạy (mục tiêu bị chặn) | Như A1 |
| Tắt agent review | Không được chốt đạt | `blocked/reviewer_off` | Kết luận của lượt đang chạy ghi nhưng là review cũ nếu phiên bản đổi |
| `team_detach` | Tiếp tục theo luật A4 | Không còn vai | Lượt review đang chạy: kết quả ghi, không dùng |
| Guard chặn | Như hiện tại | Không review khi bị chặn | Review không xoá guard |

## 9. Kho

### 9.1 Bảng mới (chỉ thêm bảng, không thêm cột vào bảng trước A1)

```sql
CREATE TABLE IF NOT EXISTS team_pairs (
  maker_agent_key TEXT PRIMARY KEY, brain_id TEXT NOT NULL,
  reviewer_agent_key TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
  config_version INTEGER NOT NULL DEFAULT 1, updated_at REAL NOT NULL, by TEXT NOT NULL,
  CHECK (maker_agent_key <> reviewer_agent_key));

CREATE TABLE IF NOT EXISTS goal_team (
  goal_id TEXT PRIMARY KEY, maker_agent_key TEXT NOT NULL,
  reviewer_agent_key TEXT NOT NULL, reviewer_config_version INTEGER NOT NULL,
  pair_config_version INTEGER NOT NULL, max_rounds INTEGER NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('active','detached')),
  created_at REAL NOT NULL, detached_at REAL);

CREATE TABLE IF NOT EXISTS team_calls (
  goal_id TEXT NOT NULL, role TEXT NOT NULL CHECK (role IN ('maker','reviewer')),
  cap INTEGER NOT NULL, used INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (goal_id, role),
  CHECK (used >= 0 AND used <= cap));

CREATE TABLE IF NOT EXISTS reviews (
  id TEXT PRIMARY KEY, goal_id TEXT NOT NULL, revision INTEGER NOT NULL,
  submission_id TEXT NOT NULL, artifact_sha TEXT NOT NULL, criteria_hash TEXT NOT NULL,
  reviewer_agent_key TEXT NOT NULL, reviewer_config_version INTEGER NOT NULL,
  action_id INTEGER NOT NULL UNIQUE, attempt INTEGER NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('running','done','failed','cancelled')),
  verdict TEXT CHECK (verdict IN ('pass','needs_changes','unknown')),
  reason_code TEXT, criteria_json TEXT, fixes TEXT, evidence_id TEXT,
  created_at REAL NOT NULL, finished_at REAL);
CREATE INDEX IF NOT EXISTS reviews_bundle ON reviews(goal_id, revision, artifact_sha, criteria_hash);
```

Hành động review dùng bảng `actions` hiện có với `kind = 'review'` (một giá trị mới của cột có sẵn, không đổi lược đồ).

### 9.2 Giao dịch và phục hồi

- **Gán đội:** trong giao dịch `assign_goal`, đọc `team_pairs` của agent làm; cặp bật và reviewer qua `_agent_block` thì ghi `goal_team` và hai dòng `team_calls`, đặt `budget_calls` theo mặc định đội. Reviewer không dùng được lúc gán: mục tiêu vẫn gán, `goal_team` vẫn ghi, và cổng 7.3 chặn ngay ở lần đánh thức đầu (chủ dự án thấy lý do), không lặng lẽ bỏ review.
- **Bắt đầu review:** `begin_action(kind='review')`: lease mục tiêu, kiểm cổng hai vai, trần, `calls_used`, `team_calls` vai review, chèn `reviews(status='running')` với bộ ghim, đặt hẹn `recovery`.
- **Xong review:** lưu bằng chứng (đầu ra thô) trước; rồi giao dịch ghi kết luận (mục 5.2), đóng hành động, thêm lý do kế tiếp (`settle`).
- **Khởi động lại:** `_reconcile` gặp hành động `review` còn `running`: `failed/interrupted`, lượt vẫn tính, `reviews.status = 'failed'`, kết luận `unknown/interrupted`, thêm `error_retry` cho vai review.
- **Lỗi lưu bằng chứng:** kết luận `unknown/storage_error`, lượt tính.

## 10. Lịch (A2) và phản hồi (A3)

- Mã lý do mới: `review_due` (lớp START khi là lần review đầu của một bộ ghim, AUTO khi là thử lại), `review_changes` (AUTO, vai làm). `CLASSES` thêm hai mã; không có lớp nào hỏi model định kỳ.
- `review_due` được thêm trong `_settle` khi khách quan đạt mà chưa có review hợp lệ; `source_ref` là `artifact_sha:criteria_hash`, nên cùng một bản không sinh hai lý do.
- Hai lần đánh thức đồng thời: CAS `claim_wake` và lease mục tiêu đảm bảo một hành động một lúc; vai làm và vai review không bao giờ chạy song song trên cùng mục tiêu.
- Reaction A3 trên thẻ review chỉ đổi cách trình bày tin (như mọi reaction), không đổi kết luận review, không đổi lịch.

## 11. Giao diện tối thiểu

- **Trang agent:** ô chọn **Người review** (mục 4.2), chỉ hiện khi agent đã bật Cộng hưởng.
- **Thẻ mục tiêu** (dùng khung thẻ A1 đến A4, thêm một dòng đội khi có `goal_team` đang `active`):
  - "Làm: <tên agent> · Review: <tên agent>";
  - "Bản đã review: <8 ký tự sha> · Đạt / Cần sửa (vòng 1/2) / Chưa rõ";
  - lý do chờ bằng câu người đọc ("Đang chờ <reviewer> xem bản <sha>", "Đang chờ <maker> sửa theo góp ý");
  - "Lượt còn: làm 3/4 · review 2/4".
- **Góp ý review** hiện trong phần mở rộng của thẻ (lý do theo tiêu chí và `fixes`), không thành tin chat riêng.
- Tin phải gửi mới: `goal.review_exhausted`, `goal.review_blocked` (gộp các lý do `blocked/review_*`, `blocked/budget_*`, `blocked/reviewer_*`). Không thêm trang đội riêng.

## 12. API, công cụ, file dự kiến

| Thay đổi | File |
|---|---|
| Bảng `_A5_SCHEMA`, nâng kho, snapshot `.pre-0.97.0` | `server/resonance_store.py` |
| `team_pair_set`/`team_pair_get`, `goal_team` trong `assign_goal`, `team_calls` trong `begin_action`/`release_call`/`abort_action`, `record_review`, `team_detach` | `server/resonance_store.py` |
| `_review_prompt`, `parse_review` (hàm thuần), cổng 7.3, nhánh team trong `_settle`, `_review_step`, `_reconcile` cho `review` | `server/resonance.py` |
| Mã lý do và lớp mới, dự trữ theo vai | `server/resonance_heartbeat.py` |
| `GET/PUT /resonance/agents/{slug}/reviewer`, lệnh `team_detach`, trường `team` trong goal view | `server/resonance_api.py` |
| Ô Người review; dòng đội trên thẻ | `dashboard/` (trang agent, `chat-resonance.js`) |
| Khôi phục về 0.96.1 | `tools/resonance_restore_pre_a5.py` |
| Test | `tests/python/test_resonance_a5_team.py`, `test_resonance_a5_rollback.py`, `tests/js/test_resonance_a5_ui.js` |

Không thêm công cụ cho model: reviewer không gọi công cụ; agent làm dùng `javis_submit_deliverable` như A4.

## 13. Nâng và hạ phiên bản

- **Lúc nâng:** lần đầu mã A5 mở kho có từ trước, `_backup_before("team_pairs", ".pre-0.97.0")` (cùng mẫu với A1 đến A4: có bảng mốc thì không chép lại) chép kho bằng SQLite backup API một lần, rồi tạo bảng A5. Mục tiêu cũ không có `goal_team`, chạy như A4.
- **Hạ đúng cách:** tắt Javis, chạy `tools/resonance_restore_pre_a5.py` (giữ bản kho hiện tại `post-0.97.0-<thời điểm>`, rồi ghi snapshot), chạy 0.96.1.
- **Hạ không khôi phục: không hỗ trợ.** Mã 0.96.1 bỏ qua bảng A5, nên mục tiêu có đội có thể được chốt đạt mà không có review, và hành động `kind='review'` còn `running` bị `_reconcile` cũ coi là lượt việc thường bị ngắt. Ghi rõ trong CHANGELOG.
- **Nâng lại sau khi mã cũ đã chạy:** snapshot đã có thì không chép lại; bảng A5 còn nguyên; mục tiêu đã chốt bởi mã cũ giữ nguyên trạng thái, không review hồi tố.

## 14. Hiệu năng

- Review không thêm vòng hỏi định kỳ: chỉ chạy khi `_settle` thêm `review_due`.
- Đọc kết luận và kiểm review hợp lệ là truy vấn theo chỉ mục `reviews_bundle`, trong cùng kết nối của `_settle`.
- Thẻ mục tiêu thêm một truy vấn `goal_team` và `team_calls` theo `goal_id` trong goal view có sẵn (đã chạy ở luồng phụ từ 0.88.5, #602); không thêm request từ trang.
- Đầu vào review lấy từ bằng chứng đã lưu, không đọc lại file lớn; giới hạn 60.000 ký tự.
- Kiểm: test đo thời gian goal view với 200 mục tiêu có đội nằm trong cùng ngưỡng với test hiệu năng Resonance hiện có (`test_resonance_perf.py`); event loop không bị chặn khi review đang chạy (đồng hồ hẹn 10 ms như test hiện có).

## 15. Ma trận nghiệm thu (trước khi code)

Đồng hồ giả, engine giả, không model thật. Mỗi ca có đối chứng hợp lệ. Cột "Lượt" là (làm, review) đã dùng khi kết thúc.

| Ca | Tình huống | Trạng thái cuối | Lượt | Quyền và tác động được phép |
|---|---|---|---|---|
| T1 | Làm, khách quan đạt, review `pass`, không có xác nhận người | `succeeded` | (1, 1) | Bản đăng theo A4; review không ghi gì |
| T2 | Như T1, có `human_confirmation` | `waiting/human_confirmation`, rồi `succeeded` khi chủ xác nhận đúng sha | (1, 1) | Như T1 |
| T3 | Review `needs_changes`, làm sửa, review bản mới `pass` | `succeeded`; hai hàng review gắn hai sha | (2, 2) | Góp ý vào lời nhắc làm; vòng 1/2 |
| T4 | Review `needs_changes` ba lần liên tiếp | `blocked/review_rounds`, tin `goal.review_exhausted` | (3, 3) | Không lượt thứ tư |
| T5 | Đầu ra review không phải JSON, JSON thiếu trường, `pass` mâu thuẫn | `unknown`, thử lại một lần, rồi `blocked/review_unknown` | (1, 2) | Không bao giờ coi là đạt |
| T6 | Lỗi engine ở lượt review | `unknown/engine_error`, như T5 | (1, 2) | Lượt tính nếu engine có thể đã chạy |
| T7 | Hết phần vai review khi còn phần vai làm | `blocked/budget_reviewer` | (k, 4) | Không mượn phần của vai làm |
| T8 | Hết phần vai làm trước khi có bản đạt | `blocked/budget_maker` | (4, k) | Không review bản chưa đạt khách quan |
| T9 | Trần chung chạm khi còn phần vai | Không giữ chỗ; chờ như hiện tại | không đổi | Trần thắng phần vai |
| T10 | Chủ dự án sửa tay file sau review `pass`, trước khi chốt | Review cũ hết giá trị; `review_due` cho sha mới | (1, 2) | Tiếp nhận tại chỗ theo A4 |
| T11 | Revision đổi trong lúc review chạy | Kết luận ghi với revision cũ, không dùng; review mới cho revision mới | (k, +1) | |
| T12 | Kết luận ghi về sai goal, sai reviewer, sai sha, sai hash tiêu chí | `review_mismatch`, không dùng | lượt tính | |
| T13 | Kết quả review được gửi lại hai lần | Một hàng `done`, lần hai bị bỏ qua | không đổi | |
| T14 | Khởi động lại sau mỗi bước: giữ chỗ, đang gọi engine, đã có đầu ra chưa ghi kết luận, đã ghi kết luận chưa `settle` | Phục hồi đúng mục 9.2; không mất lượt, không nhân đôi kết luận | đúng sổ | |
| T15 | Huỷ trước khi gọi engine review | `cancelled/not_run`, hoàn cả hai bộ đếm | (k, 0) | |
| T16 | Huỷ sau khi engine review có thể đã chạy | `failed/cancelled`, không hoàn | (k, 1) | Kết quả muộn không dùng |
| T17 | Thu hồi quyền ghi khi review đang chờ; cấp lại | Tạm dừng; sau cấp lại, review cũ dùng được nếu bộ ghim khớp; lượt làm cũ không hưởng quyền mới | không đổi | Theo A4 |
| T18 | Tắt agent review khi đang chờ review | `blocked/reviewer_off`, hẹn kiểm lại; bật lại đúng phiên bản thì tiếp | không đổi | |
| T19 | Đổi cấu hình agent review trong lúc review chạy | Kết luận là review cũ; `blocked/reviewer_changed` | (k, +1) | |
| T20 | Tắt agent làm | `blocked/agent_off` như A1; không review | không đổi | |
| T21 | Guard chặn bản đã review `pass` | `blocked/guard`; review không xoá guard | không đổi | `host_publish` không ghi |
| T22 | Hai lần đánh thức đồng thời (lý do làm và lý do review cùng đến hạn) | Một hành động chạy; cái kia chờ lease | đúng sổ | |
| T23 | Lỗi lưu bằng chứng của đầu ra review | `unknown/storage_error`, lượt tính | (k, +1) | |
| T24 | `team_detach` khi đang chờ review | Chốt theo luật A4; review đang chạy không dùng | không đổi | |
| T25 | Mục tiêu tạo khi cặp đã tắt | Không có `goal_team`; chạy như A4 | như A4 | |
| T26 | Reviewer cố trả trường đổi tiêu chí hay hạn mức | Trường bị bỏ qua, ghi sự kiện; kết luận chỉ từ ba trường | như T1 | |
| T27 | Bản nộp trong chat (A4) trên mục tiêu có đội | Đăng theo A4; review chạy ở việc nền, tính phần vai review | (0, 1) | |
| T28 | Bản quá `REVIEW_INPUT_MAX_CHARS` | `unknown/too_large`, kiểm trước khi giữ chỗ nên không tốn lượt, không gọi engine | (k, 0) | |
| T29 | Chat thường không có mục tiêu với agent có đội | Không tạo mục tiêu, không review | (0, 0) | |
| T30 | Nâng kho từ 0.96.1; khôi phục về 0.96.1 bằng script | Snapshot đúng một bản; mã 0.96.1 thật mở được kho khôi phục | | Ghi nhận giới hạn hạ không khôi phục |

## 16. Quyết định

### 16.1 Mặc định đề xuất (cần reviewer xác nhận)

| # | Quyết định | Lý do |
|---|---|---|
| D1 | Review chạy SAU khi đăng bản (luật A4 giữ nguyên), TRƯỚC khi chốt đạt | Không đổi hợp đồng A4 đã pilot; file đích là sản phẩm của chính chủ dự án; thẻ ghi rõ "chưa review". Phương án khác ở Q1 |
| D2 | Review chỉ chạy trên bản đã đạt kiểm khách quan | Không tốn lượt review cho lỗi code tự bắt được |
| D3 | Kết luận đóng khi lỗi; không đọc chữ tự do | Bước `verify_agent` hiện mặc định đạt khi lỗi |
| D4 | Reviewer chỉ thấy ảnh chụp từ bằng chứng, tiêu chí, ràng buộc, mô tả vai; không thấy chat hay review cũ | Giảm neo theo người làm và theo kết luận trước |
| D5 | Ghim reviewer lúc gán mục tiêu; đổi cặp không ảnh hưởng mục tiêu đang chạy; chỉ hỗ trợ tách đội | Bất biến 1; tránh đổi người chấm giữa chừng |
| D6 | `max_rounds = 2`, hạn mức đội 8 (làm 4, review 4) | Đủ cho bản đầu và hai lần sửa, mỗi vai một lần thử lại lỗi |
| D7 | Hai vai dùng chung lease mục tiêu, không chạy song song | Dùng lại A2; tránh review bản đang bị sửa |
| D8 | Xác nhận của chủ dự án không thay review; review không thay xác nhận | Hai quyền khác nhau (thiết kế A4 bất biến 5) |
| D9 | Reviewer tắt hay đổi cấu hình thì chặn mục tiêu, không lặng lẽ bỏ review | Dừng thắng; chủ dự án thấy lý do |
| D10 | Không có lượt review trong chat | Lượt chat dùng engine có công cụ gốc; không thực thi được "chỉ đọc" ở đó |

### 16.2 Cần anh quyết (ngắn)

- **Q1. Thời điểm review so với đăng.** Đề xuất: sau khi đăng, trước khi chốt (D1). Phương án khác: review trước khi đăng, file đích chỉ nhận bản đã review; đổi luồng A4 và chậm hơn mỗi bản một lượt review.
- **Q2. Hạn mức và số vòng mặc định.** Đề xuất: 8 lượt (làm 4, review 4), 2 vòng sửa. Có muốn ô chỉnh trên trang agent không? Đề xuất: không, theo nguyên tắc ít cài đặt.
- **Q3. Model của reviewer.** Hiện mọi việc nền dùng một model "việc nền" chung, nên hai vai mặc định cùng model. Đề xuất A5 giữ như vậy và nói rõ trên thẻ. Phương án khác: cho reviewer dùng một model việc nền khác (cần thêm lựa chọn model, nằm ngoài A5 tối thiểu).
- **Q4. Khi xác nhận của chủ dự án đến trước review.** Đề xuất: vẫn chờ review (D8). Phương án khác: xác nhận của chủ dự án trên đúng sha thì bỏ qua review.
- **Q5. Hết vòng hay hết lượt.** Đề xuất: chặn và báo, chủ dự án tách đội, huỷ hay sửa mục tiêu. Có cần thêm lệnh nâng hạn mức cho một mục tiêu không (hiện không có lệnh nào)?

## 17. Kế hoạch code và ranh giới bằng chứng

**Thứ tự (một PR #616, nhiều commit, review mã theo vòng như A4):**
1. Kho: `_A5_SCHEMA`, nâng kho và snapshot, `team_pairs`, `goal_team` trong `assign_goal`, `team_calls` trong giữ chỗ và hoàn; test kho (T7 đến T9, T14 phần kho, T15, T16, T30).
2. Review: `_review_prompt`, `parse_review` (test hàm thuần T5, T26, T28), `_review_step`, ghi kết luận có CAS (T12, T13), phục hồi (T14).
3. Chốt: nhánh team trong `_settle`, cổng 7.3, lý do mới trong A2 (T1 đến T4, T6, T10, T11, T17 đến T25, T27, T29).
4. API và giao diện: ô Người review, dòng đội trên thẻ, `team_detach` (test JS và smoke sandbox bằng engine giả).
5. Hiệu năng và hồi quy toàn bộ Resonance.

**Ranh giới bằng chứng:**
- Trước review mã: chỉ engine giả và đọc mã. Không thử engine thật không có key (có thể rơi về CLI đã đăng nhập sẵn).
- Pilot thật: đơn riêng sau khi mã đạt review, chủ dự án duyệt bằng lời của mình; đề xuất sẽ nêu số lượt cụ thể (dự kiến tối đa 1 lượt chat cộng phần việc nền của đội) và không dùng lại hạn mức pilot cũ.
- Một pilot không chứng minh mọi engine hay mọi kênh.
