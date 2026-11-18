# Báo cáo Day 09 — Nguyễn Văn Nhật, 2A202603278

## 1. Kết luận trước
**Hold** (mã thoát 10). Pipeline nhận 224 ảnh, loại 22 và xuất **202/224 ảnh** dưới dạng bản nháp `clean_v1`. Sau duyệt mô phỏng, còn 0 lỗi bắt buộc và **62/202 ảnh có cảnh báo (30,7%)**, vượt ngưỡng Hold 10% (`08_summary.json`).

## 2. Lỗi và phân việc
Số đếm theo mã lấy từ 455 dòng phát hiện trong `02_error_list_v1.csv`. Một ảnh hoặc dòng nhãn có thể có nhiều phát hiện.

| Mã lỗi và số phát hiện | Ai xử lý | Cách xử lý |
|---|---|---|
| `DUP_IMAGE_EXACT` 8, `LEAK_TEST` 5, `DUP_IMAGE_NEAR` 4, `BAD_SIZE` 3, `CORRUPT_IMAGE` 2 | Máy | Loại 22/224 ảnh ở bước nhận dữ liệu. |
| `DUP_BOX` 7, `BAD_CLASS_ID` 6, `BOX_ZERO` 4, `BAD_FORMAT` 3 | Máy | Xóa 20 dòng nhãn lỗi theo số dòng gốc. |
| `BOX_OUT_OF_IMAGE` 8, `BAD_CLASS_NAME` 2 | Máy | Cắt 8 khung về biên ảnh và chuẩn hóa tên lớp trong một lần ghi YAML. |
| `MISSING_LABEL_FILE` 6 | Người | Sáu ảnh cần được gán nhãn. |
| `POSSIBLE_MISSING` 267, `POSSIBLE_LOOSE_BOX` 58, `POSSIBLE_FALSE_POS` 25, `POSSIBLE_WRONG_CLASS` 22 | Người | Đối chiếu vật thể với khung và lớp trên ảnh. |
| `EMPTY_LABEL` 12, `BOX_TINY` 6, `BOX_HUGE` 3, `CLASS_RARE` 4 | Người | Kiểm khung và ảnh nền. Xem riêng 4 cảnh báo cấp tập dữ liệu về lớp hiếm. |

Hàng đợi cộng trọng số cho từng cảnh báo, có xét độ tin cậy khi có, rồi xếp theo tổng điểm giảm dần. `NEEDS_LABEL` có trọng số 10. `img_0160` đứng đầu với 109,727 điểm do có nhiều cờ thiếu khung và nhầm lớp. Duyệt mô phỏng **80/147 ảnh**, gồm **74/80 ảnh có cảnh báo ngữ nghĩa**, bao phủ **301/371 dòng `POSSIBLE_*`** ở vòng 2. Đây là số cờ được đưa vào duyệt. Ví dụ khi xem ảnh, học viên ghi nhận `img_0001` thiếu khung `person`. Vòng 1 cũng ghi hai cờ `POSSIBLE_MISSING` cho ảnh này.

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | 12 | Trùng gần: 1,00 / 0,50 → 1,00 / 0,67 (3/6 → 4/6) | Giữ precision trên calib và gắn cờ thêm hai cặp trong phép so nội bộ tập raw. |
| `second_opinion.conf` | 0.25 | 0.10 | Khung lỏng: 0,29 / 0,40 → 0,38 / 0,60 (2/5 → 3/5). Thiếu khung: 0,50 / 1,00 → 0,40 / 1,00 (8/8 ở cả hai ngưỡng). | Chấp nhận thêm 4 cờ thiếu khung sai (8 → 12) để phát hiện thêm 1/5 ca khung lỏng. Recall nhầm lớp giữ ở 5/6. |

Ở ngưỡng 16, calibration ghi precision 1,00 và recall 5/6 cho ảnh trùng gần. Khi thử ngưỡng này chỉ giữa các ảnh raw, 2 trong 3 cặp gắn cờ thêm so với ngưỡng 12 là ảnh khác cảnh: `img_0011` (tennis) và `img_0008` (trượt tuyết), `img_0177` (lướt sóng) và `img_0113` (người ngồi ăn). Ngưỡng 12 giảm rủi ro loại nhầm và chấp nhận bỏ sót cặp ảnh cùng cảnh `img_0084`–`img_0074` có khoảng cách 16.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
Chạy `python -m pipeline.run --budget 0` với thư mục báo cáo và xuất riêng. Kết quả **Rework**, mã thoát **20**. Còn 6 lỗi bắt buộc và 136/202 ảnh có cảnh báo (67,3%). Pipeline ghi “KHÔNG xuất” và `Test-Path` trả về `False` cho thư mục xuất của lần chạy này.

Hai điểm mù quan sát được:

- **Ảnh gần trùng vượt ngưỡng.** Cặp cùng cảnh `img_0084`–`img_0074` có khoảng cách pHash 16 nên lọt qua ngưỡng 12 trong phép so nội bộ raw.
- **Sai ngữ nghĩa có thể lọt qua.** Học viên ghi nhận khung số 2 ở `img_0002` gán túi đồ thành `person` và khung số 1 ở `img_0003` gán bus thành truck. Vòng 1 không ghi cờ `POSSIBLE_*` nào cho hai ảnh này.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
**Chưa chạy.** Buổi này tập trung hoàn thành pipeline QC và kiểm chứng cửa chặn. Chưa có kết quả mAP để so sánh `raw` và `clean`.

## 6. Quyết định và ghi chú AI
Giữ **Hold**. Duyệt tiếp các ảnh còn cảnh báo và chạy lại QC. Với 202 ảnh, Release cần 0 lỗi bắt buộc và tối đa 20 ảnh còn cảnh báo chưa xử lý.

- **Yêu cầu AI:** triển khai từng module QC theo docstring và test của repo, rồi chạy kiểm chứng.
- **Cách kiểm:** đọc diff, chạy test từng module, chạy bộ 79 test, sweep trên bộ calibration có lỗi chèn và kiểm chứng gate bằng `--budget 0`.
- **Một lần AI sai:** lệnh test ban đầu dùng lại đường dẫn `--basetemp` cố định. Pytest cố xóa thư mục cũ và gặp `WinError 5`. Đổi sang đường dẫn mới cho mỗi lượt chạy đã khắc phục lỗi.
