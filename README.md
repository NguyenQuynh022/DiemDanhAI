# 🎓 EduPortal — Hệ thống Quản lý Đào tạo & Điểm danh AI

Hệ thống quản lý học tập tích hợp nhận diện khuôn mặt AI và trợ lý ảo EduBot dành cho Sinh viên và Giảng viên.

## 📁 Cấu trúc thư mục dự án

```text
attendance_system/
├── app.py                      # App Factory khởi tạo Flask, Database & Blueprints
├── config.py                   # Cấu hình môi trường, MySQL, AI Provider & Session Cookie
├── extensions.py               # Khởi tạo SQLAlchemy & Flask-Login
├── run_admin.py                # Entrypoint Quản trị & Cổng thông tin (http://localhost:5000)
├── run_lecturer.py             # Entrypoint cổng Giảng viên (http://localhost:5001)
├── run_student.py              # Entrypoint cổng Sinh viên  (http://localhost:5002)
├── requirements.txt            # Danh sách thư viện Python
├── .env.example                # Mẫu cấu hình biến môi trường
│
├── models/                     # Tầng Database Models (SQLAlchemy ORM)
│   ├── user.py                 # Người dùng (student, lecturer, admin)
│   ├── class_model.py          # Lớp học phần & công thức tính điểm
│   ├── enrollment.py           # Đăng ký học phần
│   ├── session.py              # Buổi học cụ thể
│   ├── attendance.py           # Bản ghi điểm danh
│   ├── face_data.py            # Vector đặc trưng khuôn mặt (128D / Facenet)
│   ├── grade.py                # Điểm thành phần, tổng kết & xếp loại
│   ├── notification.py         # Thông báo hệ thống cho sinh viên
│   └── audit_log.py            # Lịch sử thao tác điểm của giảng viên
│
├── routes/                     # Tầng Controllers / Flask Blueprints
│   ├── auth_routes.py          # Đăng nhập, đăng xuất & xử lý lỗi HTTP
│   ├── attendance_routes.py    # Điểm danh AI, đăng ký khuôn mặt, mở/đóng ca học
│   ├── lecturer_routes.py      # Nghiệp vụ cổng Giảng viên
│   ├── student_routes.py       # Nghiệp vụ cổng Sinh viên
│   └── chatbot_routes.py       # API proxy gọi LLM (Groq / Anthropic / Gemini)
│
├── services/                   # Tầng Business Services & AI
│   ├── face_service.py         # Xử lý ảnh & so khớp khuôn mặt (dlib / DeepFace / OpenCV)
│   └── chatbot_prompt.py       # Xây dựng ngữ cảnh dữ liệu thực cho EduBot AI
│
├── utils/                      # Tiện ích dùng chung
│   ├── decorators.py           # Phân quyền (@student_required, @lecturer_required, ...)
│   └── timetable.py            # Quy đổi tiết học, tuần học & học kỳ
│
├── templates/                  # Giao diện HTML (Jinja2)
│   ├── base.html               # Layout nền tảng
│   ├── auth/                   # Trang đăng nhập
│   ├── lecturer/               # Giao diện cổng Giảng viên
│   ├── student/                # Giao diện cổng Sinh viên
│   ├── chatbot/                # Widget khung chat EduBot AI
│   └── errors/                 # Trang lỗi 403, 404
│
├── static/                     # Tài nguyên tĩnh
│   ├── js/                     # JavaScript xử lý lịch & giao diện
│   └── uploads/avatars/        # Ảnh đại diện người dùng tải lên
│
├── scripts/                    # Các script quản trị & tiện ích
│   ├── db/                     # Khởi tạo, migrate & seed dữ liệu mẫu
│   │   ├── migrate.py          # Cập nhật schema bảng/cột DB
│   │   ├── seed_curriculum.py  # Seed chương trình đào tạo đầy đủ 6 học kỳ
│   │   ├── seed_demo.py        # Seed dữ liệu demo gọn
│   │   ├── seed_full.py        # Seed dữ liệu cơ bản
│   │   ├── add_hk2_sessions.py # Bổ sung buổi học HK2-2025
│   │   └── fix_vietnamese.py   # Chuẩn hóa dấu tiếng Việt trong DB
│   └── dev/                    # Script truy vấn kiểm tra nhanh khi phát triển
│
├── tests/                      # Kiểm thử hệ thống
│   └── test_routes.py          # Kiểm tra kết nối DB, models, công thức điểm & routes
│
└── tools/                      # Công cụ chạy ngoài & triển khai tunnel
    ├── start_tunnel.ps1        # Script bật song song 2 cổng GV/SV + Cloudflare Tunnel
    └── cloudflared.exe         # Cloudflare Tunnel binary
```

## 🚀 Hướng dẫn chạy dự án

### 1. Cài đặt môi trường
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

### 2. Khởi tạo dữ liệu & Kiểm tra hệ thống
```powershell
python scripts/db/migrate.py
python scripts/db/seed_curriculum.py
python tests/test_routes.py
```

### 3. Chạy ứng dụng
- **Chạy cổng Giảng viên (`:5001`)**:
  ```powershell
  python run_lecturer.py
  ```
- **Chạy cổng Sinh viên (`:5002`)**:
  ```powershell
  python run_student.py
  ```
- **Chạy đồng thời kèm Cloudflare HTTPS Tunnel**:
  ```powershell
  .\tools\start_tunnel.ps1
  ```
