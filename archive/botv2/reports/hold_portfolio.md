# Danh mục Hold (DCA)

## Mô tả

Danh mục **Hold** dùng chiến lược **DCA (Dollar Cost Averaging)** – mua định kỳ với số tiền cố định, không cần timing thị trường.

## Tham số tối ưu (chạy `python -m botv2.run_dca` để cập nhật)

- **$10/ngày**: Mua vào giờ tối ưu (UTC) mỗi ngày
- **$100/tuần**: Mua vào ngày + giờ tối ưu (UTC) mỗi tuần
- **Tỷ lệ BTC/ETH**: Grid search từ 0% đến 100% BTC (phần còn lại ETH)

## Điểm mua tốt

- **Thời điểm**: Ngày và giờ UTC tối ưu từ DCA optimizer (xem `dca_results.md`)
- **Tỷ lệ**: BTC/ETH theo kết quả optimize (thường 60–80% BTC)

## Cách sử dụng

1. Chạy `python -m botv2.run_dca` để tối ưu và ghi `dca_results.md`
2. Áp dụng: mỗi ngày/tuần mua theo số tiền và thời điểm đã tối ưu
3. Chỉ spot (BTC, ETH); không leverage

## Phù hợp

- Nhà đầu tư dài hạn, ít thời gian theo dõi
- Muốn giảm rủi ro timing
- Chấp nhận biến động, không cần active trading
