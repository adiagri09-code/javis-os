# Tag của agent (0.98.0)

Agent được phân loại bằng **nhiều tag** thay cho một nhóm. Quyết định của chủ dự án: "Tag thực sự: mỗi agent gắn được nhiều tag, nhóm cũ chuyển thành một tag."

**Chỉ agent đổi.** Workflow và skill giữ trường `group` và hợp đồng hiện có. Nhóm Zalo, nhóm chat của team và đội làm/review của Cộng hưởng là ba khái niệm khác, không liên quan tới tag:
- **Tag** chỉ để phân loại và tìm agent (Marketing, Viết nội dung, Kỹ thuật).
- **Nhóm chat** là nơi người dùng và nhiều agent trò chuyện. Gắn tag không thêm ai vào nhóm chat.
- **Đội thực hiện** (Cộng hưởng A5, đang thiết kế) là maker và reviewer của một mục tiêu. Tag không chọn reviewer, không cấp quyền, không bật Cộng hưởng, không đổi hạn mức, không mở lượt model.

## Hợp đồng dữ liệu

### Frontmatter của `agents/<slug>.md`

```yaml
tags:
- Marketing
- Viết nội dung
```

- `tags` là **nguồn chuẩn** khi khoá này có mặt, kể cả `tags: []` (người dùng đã bỏ hết tag).
- File cũ **chưa có khoá `tags`**: đọc `group` thật trong frontmatter. `group` là chuỗi không rỗng thì thành đúng một tag (`group: Chung` thật thì thành tag "Chung"). Không có `group` hay `group` rỗng thì chưa có tag. Không suy ra tag từ nhãn "Chung" mà API cũ tự điền.
- `tags` là chuỗi đơn (người hay model ghi tay `tags: Marketing`) thì đọc thành một tag. Phần tử không phải chuỗi, rỗng sau chuẩn hoá thì bỏ qua khi đọc.
- **Gương `group`** (để hạ phiên bản vẫn có nhãn): mỗi lần ghi chuẩn, `group` = tag đầu tiên; không còn tag thì xoá khoá `group`. Khi đã có `tags`, mã 0.98.0 trở đi KHÔNG đọc `group` của agent.
- Ghi bằng `yaml.safe_dump` như mọi frontmatter khác, đọc bằng `fastyaml.safe_load`: danh sách ra danh sách, chuỗi có ký tự đặc biệt được trích dẫn.

### Chuẩn hoá và trùng

- Unicode NFC; bỏ ký tự điều khiển; gộp mọi khoảng trắng liên tiếp thành một dấu cách; cắt hai đầu.
- Rỗng sau chuẩn hoá: không phải tag. Dài quá 40 ký tự: từ chối (`tag_too_long`). Quá 20 tag một agent: từ chối (`too_many_tags`).
- **Khoá so trùng** = dạng chuẩn hoá rồi `casefold()`: "Marketing" và "marketing" là một tag, giữ cách viết gặp trước. Dấu tiếng Việt là một phần của tag: "Viết" và "Viet" là hai tag khác nhau. Tìm kiếm không dấu chỉ để tìm, không gộp tag.
- Phía giao diện chỉ hiển thị cách viết server trả về, không tự chuẩn hoá lại.

### API

| Đường | Agent | Ghi chú |
|---|---|---|
| `GET /agents`, `GET /agents/get` | Trả `tags` (danh sách đã chuẩn hoá) | Vẫn trả `group` = tag đầu tiên hoặc "Chung" cho trang cũ còn trong cache. Không gửi một request riêng cho từng agent |
| `POST /capability/meta`, `kind=agent` | `add_tags` (JSON danh sách): thêm vào tập hiện có. `remove_tags` (JSON danh sách): bỏ đúng các tag đó. `tags` (JSON danh sách): thay cả tập, `[]` là bỏ hết | Không gửi trường nào = giữ nguyên. Đọc và ghi trong một bước của server, nên hai tab thêm/bỏ khác tag không ghi đè nhau |
| `POST /capability/meta`, `kind=agent`, chỉ có `group` (client cũ) | Agent đang có từ hai tag trở lên: từ chối `409 stale_client` ("Trang đã cũ, tải lại trang"), không đổi gì. Có không quá một tag: `group` không rỗng thành đúng một tag, rỗng là bỏ tag (đúng nghĩa cũ "về Chưa xếp nhóm") | Không bao giờ âm thầm thay nhiều tag bằng một tag |
| `group` gửi cùng `tags`/`add_tags`/`remove_tags` | Từ chối `400 group_and_tags` | Luật xung đột rõ, không đoán |
| `POST /agents` (form sửa agent) | Không gửi `tags` = giữ nguyên tag. Gửi `tags` (JSON) = thay cả tập. `group` của client cũ theo đúng luật hàng trên | Agent mới không gửi tag thì `tags: []` |
| `POST /agents/tags/rename` (`brain`, `from`, `to`) | Đổi tên tag trên mọi agent đang có nó, giữ các tag khác. `to` trùng khoá với một tag đã có trên agent thì gộp, không nhân đôi | Trả `changed`, `failed`, `merged` (tên đích đã tồn tại trong brain). Có agent ghi lỗi thì `ok: false` kèm danh sách đã làm và chưa làm |
| `POST /agents/tags/delete` (`brain`, `tag`) | Gỡ nhãn đó khỏi mọi agent | Không xoá agent, phiên chat, mục tiêu hay đội. Trả như trên |
| `kind=workflow` | Không đổi; gửi tham số tag cho workflow bị từ chối `400` | |

Mọi tag thuộc phạm vi **một brain** (thư mục `agents/` của brain đó). Đổi tên hay xoá tag ở brain này không chạm brain khác.

## Chuyển đổi

- **Đọc tương thích, ghi chuẩn khi lưu.** Không có migration hàng loạt và không quét ghi lại file khi tải danh sách.
- Một agent cũ được ghi sang dạng chuẩn (`tags` + gương `group`) ở lần đầu có thao tác lưu chạm vào nó: Lưu form, ghim, gắn hay bỏ tag, đổi tên hay xoá tag. Ghi chuẩn hai lần cho cùng kết quả (lặp an toàn): tag đã có `tags` thì đọc `tags`, không đọc lại `group`.
- Mọi khoá frontmatter khác và thân prompt giữ nguyên (đọc rồi chỉ sửa khoá tag). Ghi nguyên tử bằng `_atomic_write_text`.

## Nhập, xuất, chỉ mục, tạo từ chat

- **Xuất** chép nguyên file agent: gói mới mang `tags`.
- **Nhập** ghi nguyên file: gói mới giữ đủ tag; gói cũ chỉ có `group` thì được đọc thành đúng một tag theo luật file cũ, và thành dạng chuẩn ở lần lưu đầu.
- **Chỉ mục** `Javis/index.md`: agent liệt kê một lần mỗi agent, kèm "tags: A, B"; workflow và skill vẫn chia theo nhóm.
- **Tạo agent từ chat** (`javis-builder`, `CLAUDE.md`): mẫu agent dùng `tags:` (danh sách), đọc các tag đang dùng trong `agents/*.md` trước khi chọn.

## Quay về

- **Hạ về 0.96.1 (mã cũ):** mã cũ đọc `group`, nên agent hiện dưới nhóm = tag đầu tiên (gương), agent không còn tag hiện là "Chung". Khoá `tags` còn nguyên trong file, mã cũ giữ nó khi lưu (đã giữ mọi khoá lạ từ 0.59.x). Đã kiểm trên trình duyệt với `main` 0.96.1 mở bản sao dữ liệu đã chuyển.
- **Giới hạn:** file agent có `tags` mà chưa từng được mã 0.98.0 lưu (người hay model ghi tay chỉ `tags`, hay gói nhập từ nơi khác) thì chưa có gương `group`, nên mã cũ hiện nó là "Chung" cho tới khi được lưu một lần bằng mã mới. Không mất tag.
- **Nâng lại 0.98.0:** `tags` là nguồn chuẩn. Thay đổi nhóm làm bằng mã cũ trong lúc hạ phiên bản (sửa `group`) **không** được đưa vào tag; muốn giữ thì gắn lại tag. Đây là giới hạn đã biết, đổi lại tag đã bỏ không bao giờ sống lại từ `group`.
- Không có bản sao file riêng: chuyển đổi chỉ thêm khoá `tags` và đồng bộ `group`, không xoá nội dung nào.
