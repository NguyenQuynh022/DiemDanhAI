"""
fix_vietnamese.py — Sửa tên môn học sang tiếng Việt có dấu
Chạy: python fix_vietnamese.py
"""
from app import create_app
from extensions import db
from models.class_model import Class
from models.user import User

app = create_app()

with app.app_context():
    updates = {
        'Lap trinh Python': 'Lập trình Python',
        'Co so du lieu':    'Cơ sở dữ liệu',
        'Mang may tinh':    'Mạng máy tính',
        'Nguyen Van An':    'Nguyễn Văn An',
        'Le Thi Thu':       'Lê Thị Thu',
        'Tran Thi Binh':    'Trần Thị Bình',
        'Le Hong Cuong':    'Lê Hồng Cường',
        'Pham Thi Dung':    'Phạm Thị Dung',
        'Nguyen Van Hung':  'Nguyễn Văn Hùng',
        'Hoang Thi My':     'Hoàng Thị Mỹ',
        'Quan tri vien':    'Quản trị viên',
    }

    # Fix class names
    for cls in Class.query.all():
        if cls.course_name in updates:
            cls.course_name = updates[cls.course_name]

    # Fix user names
    for user in User.query.all():
        if user.full_name in updates:
            user.full_name = updates[user.full_name]

    db.session.commit()
    print("✅ Đã sửa tên tiếng Việt!")

    # Verify
    for cls in Class.query.all():
        print(f"  Lớp: {cls.class_name} — {cls.course_name}")
