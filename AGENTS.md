# Quy tắc bộ vendor chuẩn

- `baseline/test7` giữ nguyên sau lần import đầu tiên. Không sửa hoặc build trên nhánh này.
- Sửa và build trên `work/camera-sim` hoặc nhánh `work/*` tách từ baseline.
- Metadata trong `metadata/vendor-image-manifest.json` là metadata của ảnh, không lấy quyền/UID/GID của máy Git thay thế.
- Không sửa nhánh chuẩn để làm mất khác biệt với ảnh đầu vào, kể cả metadata có vẻ bất thường.
- Bất kỳ thay đổi HAL/RIL/kernel nào phải có lý do, diff và kiểm chứng phù hợp. Không kết luận camera/SIM đã hoạt động chỉ từ kiểm tra offline.
- Đây là cây file vendor và binary đã trích xuất; không phải mã nguồn C/C++ của Samsung.
