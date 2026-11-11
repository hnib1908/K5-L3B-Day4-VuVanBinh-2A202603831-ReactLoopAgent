# Ghi chú phân tích · Day 04

Họ và tên:
MSSV:

## 1. Case được chọn

- ID case: H1.
- Câu trả lời của agent: (Tóm tắt lần 1) Agent mô tả incident GitHub
  h02n9572mx9y và Cloudflare yaa0witbl2me, nhận diện link đến incident
  GitHub xr3myzj7ms51 nhưng chưa đọc nội dung tại link trước khi kết luận.
- Điểm ở lần chạy 1: 60/100.

## 2. Bằng chứng trong trace

Trace H1 trong `eval_before.json` cho thấy agent chỉ đọc hai incident ban đầu.
Dưới đây là phần trích rút gọn:

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

Nguyên nhân có thể: model dừng sau khi đọc các incident ban đầu; loop mới
kiểm tra URL nguồn, chưa kiểm tra incident được liên kết có được đọc theo
mục tiêu điều tra hay chưa. Vì thế câu trả lời thiếu bằng chứng về nguyên nhân.

## 3. Thay đổi đã thực hiện

- Sửa gì, ở đâu: Trong `agent.py`, bổ sung kiểm tra incident liên quan chưa
  đọc khi câu hỏi cần theo link hoặc tìm nguyên nhân. ID lấy từ URL trong
  update thực tế, không hard-code. Nếu còn link chưa được thử đọc, ghi event
  `validation_unread_incidents` và yêu cầu model gọi tool trong `max_steps`.
  Sau đó nhắc trả lời toàn bộ câu hỏi, đối chiếu các incident và dẫn nguồn.
  Bổ sung lời nhắc khi status tool lỗi, xử lý ngoại lệ tool, yêu cầu kiểm tra
  cả status và incident khi được hỏi outage; làm rõ giới hạn snapshot,
  khoảng thời gian tìm kiếm và nội dung update bị cắt. Giữ kiểm tra URL nguồn.
- Vì sao chọn thay đổi này: H1/H6 chưa đọc incident được liên kết; H2 chưa
  gọi `get_status`; H7 vẫn kết luận operational dù timeout. Các thay đổi
  giải quyết thiếu sót quan sát được trong trace của lần chạy đầu.
  Kiểm tra offline sau thay đổi: 41/41 tests đạt.

## 4. So sánh hai lần chạy

Hai lần chạy đều chấm đủ 22/22 case, cùng cấu hình: agent và judge dùng
`openai/gpt-4.1-mini`, `max_steps=8`, dataset `core` trên snapshot cố định.

| Chỉ số | `eval_before.json` | `eval_after.json` |
|---|---|---|
| Điểm tổng | 92,23/100 | 99,05/100 |
| Điểm case đã chọn | H1: 60/100 | H1: 100/100 |
| Số model calls | Agent: 48 | Agent: 54 |
| Token, chi phí nếu có | Agent: 39.394; judge: 32.949; chưa có chi phí tiền | Agent: 78.843; judge: 35.912; chưa có chi phí tiền |

- Lỗi đã giải quyết: H1 đọc thêm incident liên quan ở step 3 sau các calls
  ở step 1, không còn vi phạm mechanical; điểm tăng 60 → 100. H2 gọi cả
  `get_status` và `get_incident_details`, tăng 50 → 100. H6 đọc incident
  gộp và nêu dữ liệu bị cắt, tăng 60 → 94. H7 không còn kết luận Cloudflare
  operational khi timeout, tăng 75 → 100. Tổng điểm tăng 6,82; lần 2 không
  có mechanical violations. Agent dùng thêm 6 model calls và 39.449 token.
- Lỗi còn lại hoặc mới xuất hiện: A5 giảm 88 → 85, cần nêu rõ giới hạn
  tìm trong 50 incident gần nhất khi hỏi danh sách cả năm và dẫn URL nguồn.
  H6 còn 94 điểm, cần tách rõ nguyên nhân, ảnh hưởng và phần bị cắt;
  tránh gọi toàn bộ dữ liệu incident là giả lập chỉ vì có mục nhiễu giả lập.
  H1 vẫn có câu suy diễn nguyên nhân nội bộ của Cloudflare, trong khi tool
  chủ yếu nêu tác động lên hàng đợi build; cần phân biệt tác động với nguyên nhân.

## 5. Giới hạn

Điểm judge là ước lượng và có thể sai hoặc thiên lệch, nhất là khi agent
và judge dùng cùng model. Điểm cao không chứng minh mọi câu trong answer
đều có căn cứ; cần đọc trace và kết quả tool để kiểm tra lại.

Snapshot chỉ phản ánh dữ liệu đã lưu, không xác nhận trạng thái dịch vụ
hiện tại. Tìm kiếm chỉ bao phủ 50 incident gần nhất/provider, trả tối đa
5 mục khớp; chi tiết incident cũng có thể bị lược bỏ hoặc cắt updates.

Mỗi phiên bản chỉ chạy một lần nên chưa chứng minh độ ổn định hoặc tách
riêng tác dụng của từng thay đổi. Tests offline kiểm tra contract của loop,
không đo chất lượng model thật; kiểm tra URL không bảo đảm mọi nhận định
đều đúng. Điểm eval khác điểm chấm bài lab cuối cùng.
