# ALICE Vendor Test7 — Galaxy S8+ / Exynos 8895

Toàn bộ cây file của ảnh `vendor-OneUI8-S8Plus-Test7-Camera-Bixby(1).img`, giữ nguyên nội dung và lưu riêng metadata để build lại. Đây là vendor binary đã trích xuất, không phải mã nguồn C/C++ của Samsung.

- `baseline/test7`: bản chuẩn, giữ nguyên sau import.
- `work/camera-sim`: bắt đầu từ đúng commit của baseline; mọi sửa đổi/build thực hiện ở đây.
- `main`: trang dẫn đến hai nhánh.

## Đã kiểm chứng

- 1.158 file thường, 187 symlink, 84 thư mục; tổng 1.429 inode.
- Ảnh đầu vào: 481.640.448 byte.
- SHA-256 ảnh: `4368eefcc7c4a8d7dc7b1d61e2116a80daef31f10a134d2853f7c63259224437`.
- Dựng lại bằng erofs-utils 1.8.6 cho ảnh **giống từng byte**. Báo cáo: `metadata/baseline-build-verification.json`.
- Đã đối chiếu nội dung, symlink, mode, UID/GID, mtime, số liên kết và xattr SELinux của ảnh dựng lại.
- Chưa kiểm tra khởi động, camera hoặc hai SIM trên máy thật. Import này chưa sửa HAL/RIL/kernel.

Ảnh vừa khôi phục có cùng hash với ảnh đã đối chiếu ZIP ở phiên trước. ZIP `02-ALICE-Vendor-Test7-Camera-Bixby.zip` hiện không truy cập lại được; `metadata/input-provenance.json` phân biệt rõ kết quả kiểm tra hiện tại với kết quả lưu từ phiên trước. Không thay bằng ZIP khác. Nếu có ZIP gốc, có thể tự kiểm tra bằng lệnh bên dưới.

## Build trên Linux x86-64

Cần Python 3, Git, `dpkg-deb`, và môi trường chạy được gói erofs-utils Debian amd64 (đã kiểm tra trên glibc 2.39).

```bash
git clone --branch work/camera-sim https://github.com/HaloT455/Vendor-45-.git
cd Vendor-45-
python3 tools/setup_erofs.py
python3 tools/build_vendor.py --verify-only
python3 tools/build_vendor.py
```

Ảnh kết quả: `out/vendor.img`; báo cáo: `out/vendor.report.json`. Script từ chối ghi đè ảnh đã tồn tại; dùng `--output out/vendor-next.img` cho lần khác.

Sau khi sửa nội dung file trên nhánh làm việc:

```bash
python3 tools/build_vendor.py --allow-file-changes --output out/vendor-edited.img
```

Thêm/xóa đường dẫn, sửa symlink hoặc quyền/nhãn phải cập nhật manifest một cách có chủ đích trên nhánh làm việc. Script dừng khi cây file không khớp manifest. Thông số build giữ định dạng EROFS cũ, UUID và thời gian gốc; ảnh không được vượt kích thước baseline.

## Metadata gốc

`metadata/vendor-image-manifest.json` lưu đầy đủ metadata và hash từng file. Các file `vendor_fs_config`, `vendor_file_contexts`, `SHA256SUMS` hỗ trợ kiểm tra. Quyền thư mục trên máy Git chỉ phục vụ đọc/sửa; khi build, quyền lấy từ manifest.

Ảnh gốc có `/vendor/etc/init` với mode `0000`, UID 0/GID 2000. Giá trị này được giữ nguyên trong baseline và ảnh dựng lại; mọi đánh giá/sửa giá trị đó phải nằm trên nhánh làm việc.

## Đối chiếu ZIP khi có file gốc

```bash
python3 tools/compare_package.py /duong/dan/02-ALICE-Vendor-Test7-Camera-Bixby.zip
```

Script kiểm tra SHA-256 ZIP, CRC các entry, checksum trong gói, hash ảnh và sáu file payload so với vendor. Không flash thiết bị.
