# Ghi chú phân tích · Day 04

Họ và tên: Vũ Văn Bình
MSSV: 2A202603831

## 1. Case được chọn

- ID case: H1.
- Câu trả lời của agent: Tôi tóm tắt lần 1 như sau: agent mô tả incident GitHub
  h02n9572mx9y và Cloudflare yaa0witbl2me, nhận diện link đến incident
  GitHub xr3myzj7ms51 nhưng chưa đọc nội dung tại link trước khi kết luận.
- Điểm ở lần chạy 1: 60/100.

## 2. Bằng chứng trong trace

Tôi đọc trace H1 trong `eval_before.json` và thấy agent chỉ đọc hai incident
ban đầu. Tôi trích rút gọn bằng chứng như sau:

```text
step 1: get_incident_details(provider="github", incident_id="h02n9572mx9y")
step 1: get_incident_details(provider="cloudflare", incident_id="yaa0witbl2me")
GitHub update: Please refer to the combined summary in this related incident:
https://www.githubstatus.com/incidents/xr3myzj7ms51
step 2: finish="stop", không có tool calls
Không có lần gọi get_incident_details cho xr3myzj7ms51.
grade.mechanical.violations:
  ["Cần tool calls ở ít nhất 2 model steps khác nhau."]
grade.mechanical.score_cap: 60
```

Tôi cho rằng nguyên nhân có thể là model dừng sau khi đọc các incident ban đầu; loop mới
kiểm tra URL nguồn, chưa kiểm tra incident được liên kết có được đọc theo
mục tiêu điều tra hay chưa. Vì thế câu trả lời thiếu bằng chứng về nguyên nhân.

## 3. Thay đổi đã thực hiện

- Sửa gì, ở đâu: Tôi bổ sung trong `agent.py` kiểm tra incident liên quan chưa
  đọc khi câu hỏi cần theo link hoặc tìm nguyên nhân. ID lấy từ URL trong
  update thực tế, không hard-code. Nếu còn link chưa được thử đọc, ghi event
  `validation_unread_incidents` và yêu cầu model gọi tool trong `max_steps`.
  Sau đó nhắc trả lời toàn bộ câu hỏi, đối chiếu các incident và dẫn nguồn.
  Tôi bổ sung lời nhắc khi status tool lỗi, xử lý ngoại lệ tool, yêu cầu kiểm tra
  cả status và incident khi được hỏi outage; làm rõ giới hạn snapshot,
  khoảng thời gian tìm kiếm và nội dung update bị cắt. Giữ kiểm tra URL nguồn.
- Vì sao chọn thay đổi này: Tôi thấy H1/H6 chưa đọc incident được liên kết; H2 chưa
  gọi `get_status`; H7 vẫn kết luận operational dù timeout. Các thay đổi
  giúp tôi giải quyết thiếu sót quan sát được trong trace của lần chạy đầu.
  Tôi kiểm tra offline sau thay đổi và có 41/41 tests đạt.

Với phần bonus, tôi bổ sung `bonus_policy.py` và kết nối
`tools.schemas`/`tools.system_prompt` trong `agent.py` để dùng 5 provider.
Tôi giới hạn 3 lần 429 liên tiếp/provider, đọc Retry-After dạng giây hoặc
HTTP-date và đặt tổng budget chờ 5 giây/run. Nếu vượt budget, tôi chấp
nhận kết quả từng phần thay vì suy đoán trạng thái.

Tôi theo dõi offset, total_updates và các trang đã đọc; khi câu hỏi cần
timeline hoặc phạm vi ảnh hưởng, loop yêu cầu đọc tiếp trang còn thiếu
trong max_steps. Tôi lược trường distractors khỏi context gửi model nhưng
giữ nguyên trong trace. Tôi không sửa fixture, dataset hoặc grading.

Tôi thấy B6 thiếu bước lấy chi tiết incident, B10 chỉ nói sẽ retry mà
chưa gọi lại tool. Tôi thêm `validation_pending_bonus_actions` để yêu cầu
thực hiện bước còn thiếu trước completed. Tôi lấy tham số từ dữ liệu
quan sát, không hard-code ID. Sau mở rộng, tôi kiểm tra được 49/49 tests
trong `tests/` và 3/3 tests trong `bonus/` đều đạt.

## 4. So sánh hai lần chạy

Tôi chạy đủ 22/22 case trong mỗi lần, giữ cùng cấu hình: agent và judge dùng
`openai/gpt-4.1-mini`, `max_steps=8`, dataset `core` trên snapshot cố định.

| Chỉ số | `eval_before.json` | `eval_after.json` |
|---|---|---|
| Điểm tổng | 92,23/100 | 99,05/100 |
| Điểm case đã chọn | H1: 60/100 | H1: 100/100 |
| Số model calls | Agent: 48 | Agent: 54 |
| Token, chi phí nếu có | Agent: 39.394; judge: 32.949; chưa có chi phí tiền | Agent: 78.843; judge: 35.912; chưa có chi phí tiền |

- Lỗi đã giải quyết: Tôi thấy H1 đọc thêm incident liên quan ở step 3 sau các calls
  ở step 1, không còn vi phạm mechanical; điểm tăng 60 → 100. H2 gọi cả
  `get_status` và `get_incident_details`, tăng 50 → 100. H6 đọc incident
  gộp và nêu dữ liệu bị cắt, tăng 60 → 94. H7 không còn kết luận Cloudflare
  operational khi timeout, tăng 75 → 100. Tổng điểm tăng 6,82; lần 2 không
  có mechanical violations. Agent dùng thêm 6 model calls và 39.449 token.
- Lỗi còn lại hoặc mới xuất hiện: Tôi thấy A5 giảm 88 → 85, cần nêu rõ giới hạn
  tìm trong 50 incident gần nhất khi hỏi danh sách cả năm và dẫn URL nguồn.
  H6 còn 94 điểm, cần tách rõ nguyên nhân, ảnh hưởng và phần bị cắt;
  tránh gọi toàn bộ dữ liệu incident là giả lập chỉ vì có mục nhiễu giả lập.
  H1 vẫn có câu suy diễn nguyên nhân nội bộ của Cloudflare, trong khi tool
  chủ yếu nêu tác động lên hàng đợi build; cần phân biệt tác động với nguyên nhân.

Tôi chạy riêng bộ bonus với agent và judge đều `gpt-4.1-mini`,
`max_steps=16`, dataset `bonus`. Tôi giữ báo cáo bonus đầu tại
`archive/bonus-first-run/eval_bonus.json` và kết quả cuối tại `eval_bonus.json`.

| Chỉ số bonus | Lần đầu | Sau cải tiến |
|---|---|---|
| Số case được chấm | 10/10 | 10/10 |
| Điểm tổng /100 | 90 | 99,2 |
| Điểm bonus tham khảo /15 | 13,5 | 14,88 |
| B6 | 50 | 100 |
| B10 | 50 | 96 |
| B5 | 100 | 96 |

Tôi ghi nhận điểm bonus tăng 9,2/100, tương ứng 1,38/15. Tôi kiểm tra
báo cáo cuối và không thấy mechanical violations ở cả 10 case. B6 đã
đọc chi tiết cả hai incident; B10 đã retry Vercel và kiểm tra đủ 5 provider.

Tôi vẫn thấy B5/B10 còn 96 điểm: câu trả lời cần mô tả rõ hơn việc phục
hồi sau INVALID_ARGUMENTS và số lần retry 429 thực tế. Tôi lưu ý lỗi định
dạng B5 là giả lập; tôi không khẳng định tham số ban đầu thực sự sai
nếu trace không chứng minh điều đó. Tôi không tự cộng điểm bonus vào
điểm bài chính vì điểm cuối do giảng viên đối chiếu và quyết định.

## 5. Giới hạn

Tôi xem điểm judge là ước lượng có thể sai hoặc thiên lệch, nhất là khi
agent và judge dùng cùng model. Tôi cần đối chiếu answer, trace và tool
results; điểm cao không chứng minh mọi nhận định đều có nguồn hỗ trợ.

Tôi dùng snapshot nên không xác nhận được trạng thái dịch vụ thực tế
hiện tại. Với bài chính, tool tìm trong 50 incident gần nhất và trả tối
đa 5 mục khớp. Với bonus, status tool trả tối đa 8 incident; timeline có
pagination và từng update vẫn có thể bị cắt. Tôi không coi số update
tổng là số update đã đọc hoặc tìm kiếm rỗng là không có incident.

Tôi mới chạy mỗi phiên bản một lần cho các báo cáo đầy đủ, chưa chứng
minh độ ổn định hay tách riêng tác dụng của từng thay đổi. Tôi không
coi kết quả chạy riêng từng case là điểm toàn bộ dataset. Tests offline
chỉ kiểm tra cơ chế loop, không chứng minh model luôn chống prompt
injection hoặc luôn tuân thủ lời nhắc về thiếu bằng chứng.

Tôi giới hạn retry và thời gian chờ để tránh gọi liên tục. Nếu API thật
cần chờ quá 5 giây, tôi chấp nhận báo kết quả từng phần. Tôi cần nộp kèm
`bonus_policy.py` vì `agent.py` import module này. Tôi giữ riêng hai báo
cáo bài chính và báo cáo bonus; điểm eval khác điểm bài lab cuối cùng.
