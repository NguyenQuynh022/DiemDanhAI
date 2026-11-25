"""
scripts/db/seed_announcements.py — Nạp dữ liệu thông báo mẫu cho Cổng thông tin Đào tạo
Không xóa dữ liệu người dùng hay lớp học hiện có.
Chạy: python scripts/db/seed_announcements.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from datetime import datetime
from app import create_app
from extensions import db
from models.announcement import Announcement
from models.user import User

app = create_app()

SAMPLE_ANNOUNCEMENTS = [
    # Thông báo từ Phòng Đào tạo
    (
        "THÔNG BÁO V/v tổ chức kiểm tra đánh giá năng lực tiếng Anh đầu vào bổ sung cho sinh viên đại học hình thức đào tạo chính quy khóa tuyển sinh năm 2026",
        "academic",
        True,
        True,
        datetime(2026, 11, 23, 8, 30),
        "Phòng Đào tạo thông báo kế hoạch tổ chức kiểm tra đánh giá năng lực tiếng Anh đầu vào bổ sung cho sinh viên chính quy khóa 2026.\n\n"
        "1. Đối tượng: Sinh viên khóa tuyển sinh 2026 chưa tham dự đợt 1.\n"
        "2. Hình thức: Thi trực tuyến tập trung tại phòng máy Khu K.\n"
        "3. Sinh viên đăng nhập vào Cổng Sinh viên bằng tài khoản do Phòng Đào tạo cấp để xem lịch thi và phòng thi chi tiết.",
    ),
    (
        "Lịch thi kết thúc học phần Khóa 23,24_Đợt 1_Học kỳ 1 năm học 2026-2027 - Hệ Đại học",
        "exam",
        False,
        False,
        datetime(2026, 11, 19, 14, 0),
        "Phòng Khảo thí & Đảm bảo chất lượng công bố Lịch thi kết thúc học phần Đợt 1 Học kỳ 1 năm học 2026-2027.\n"
        "Sinh viên kiểm tra kỹ ngày thi, ca thi và mang theo thẻ sinh viên khi vào phòng thi.",
    ),
    (
        "[THÔNG BÁO] Về việc nghỉ Ngày Văn hóa Việt Nam năm 2026",
        "academic",
        False,
        False,
        datetime(2026, 11, 18, 9, 0),
        "Nhà trường thông báo lịch nghỉ học và làm việc nhân dịp Ngày Văn hóa Việt Nam năm 2026 tới toàn thể cán bộ, giảng viên và sinh viên các khóa.",
    ),
    (
        "THÔNG BÁO VỀ HÌNH THỨC NỘP HỌC PHÍ TẠM THỜI",
        "academic",
        False,
        False,
        datetime(2026, 11, 12, 10, 15),
        "Hướng dẫn hình thức nộp học phí trực tuyến qua cổng thanh toán ngân hàng liên kết dành cho sinh viên đại học hệ chính quy.",
    ),
    (
        "[CTSV] Thông báo về việc nộp hồ sơ đăng ký xét học bổng “Agribank Nam Đà Nẵng - Chắp cánh ước mơ” năm 2026",
        "scholarship",
        False,
        False,
        datetime(2026, 11, 8, 15, 0),
        "Phòng Công tác Sinh viên thông báo chương trình học bổng tài trợ từ Agribank Nam Đà Nẵng dành cho sinh viên có hoàn cảnh khó khăn vươn lên đạt thành tích học tập khá, giỏi.",
    ),
    (
        "[CTSV] Thông báo về việc nộp hồ sơ đăng ký xét học bổng Keidanren & JCCI năm 2026",
        "scholarship",
        False,
        False,
        datetime(2026, 11, 8, 11, 0),
        "Thông báo tiếp nhận hồ sơ xét cấp học bổng Keidanren & JCCI năm 2026 cho sinh viên khối ngành Công nghệ thông tin và Truyền thông.",
    ),
    (
        "Thông báo nhận hồ sơ xét công nhận đạt đầu ra về ngoại ngữ, trình độ đại học, hệ chính quy",
        "academic",
        False,
        False,
        datetime(2026, 11, 5, 8, 45),
        "Sinh viên đã có chứng chỉ ngoại ngữ quốc tế hợp lệ nộp hồ sơ xét công nhận chuẩn đầu ra tại Phòng Đào tạo theo đúng thời gian quy định.",
    ),
    (
        "Thông báo Lịch thi kết thúc các học phần Thực tập, Đề án HKI - Năm học: 2026-2027",
        "exam",
        False,
        False,
        datetime(2026, 10, 21, 16, 0),
        "Lịch báo cáo và chấm điểm các học phần Đồ án cơ sở, Đồ án chuyên ngành và Thực tập thực tế Học kỳ 1 năm học 2026-2027.",
    ),
    # Thông báo về Kế hoạch Tài chính
    (
        "THÔNG BÁO VỀ HÌNH THỨC NỘP HỌC PHÍ TẠM THỜI",
        "finance",
        False,
        True,
        datetime(2026, 11, 12, 10, 0),
        "Phòng Kế hoạch - Tài chính thông báo hướng dẫn sinh viên thực hiện đóng học phí học kỳ qua hệ thống thanh toán VietQR / Ngân hàng liên kết.",
    ),
    (
        "Thông báo về việc thu tiền bảo hiểm y tế và bảo hiểm thân thể năm 2027 đối với sinh viên",
        "finance",
        False,
        False,
        datetime(2026, 10, 21, 9, 30),
        "Thông báo mức đóng và thời hạn tham gia Bảo hiểm Y tế bắt buộc năm 2027 đối với sinh viên hệ đại học chính quy toàn trường.",
    ),
    (
        "Thông báo thu học phí học kỳ 1 năm học 2026 – 2027 (đợt 1) đối với trình độ đại học & thạc sĩ",
        "finance",
        False,
        False,
        datetime(2026, 10, 10, 8, 0),
        "Kế hoạch thu học phí đợt 1 năm học 2026 - 2027 căn cứ theo số tín chỉ học phần sinh viên đã được phân lớp.",
    ),
]

with app.app_context():
    admin = User.query.filter_by(role='admin').first()
    author_id = admin.id if admin else None

    if Announcement.query.count() == 0:
        for title, cat, is_new, is_pinned, dt, content in SAMPLE_ANNOUNCEMENTS:
            db.session.add(Announcement(
                title=title,
                category=cat,
                is_new=is_new,
                is_pinned=is_pinned,
                is_published=True,
                author_id=author_id,
                created_at=dt,
                updated_at=dt,
                content=content,
            ))
        db.session.commit()
        print(f"✅ Đã thêm {len(SAMPLE_ANNOUNCEMENTS)} thông báo mẫu lên Cổng thông tin Đào tạo!")
    else:
        print(f"✓ Bảng announcements đã có {Announcement.query.count()} thông báo — giữ nguyên.")
