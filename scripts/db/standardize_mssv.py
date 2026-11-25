"""
scripts/db/standardize_mssv.py — Chuẩn hóa toàn bộ MSSV hiện có trong DB sang chuẩn
<2 số Khóa><Mã ngành IN HOA><Số TT> (<= 8 ký tự, VD: 23ITB001) mà không mất dữ liệu học tập.
Chạy: python scripts/db/standardize_mssv.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app import create_app
from extensions import db
from models.user import User
from utils.student_code import validate_student_code

app = create_app()

MAJORS_ROTATION = ['ITB', 'ITB', 'AI', 'SE', 'CE']

with app.app_context():
    students = User.query.filter_by(role='student').order_by(User.id).all()
    updated = 0
    for idx, sv in enumerate(students, start=1):
        ok, _ = validate_student_code(sv.student_code)
        if ok:
            continue
        # Sinh viên trong curriculum bắt đầu từ HK1-2023 => Khóa 23
        major = 'ITB' if idx <= 10 else ('AI' if idx <= 20 else ('SE' if idx <= 25 else 'CE'))
        new_code = f"23{major}{idx:03d}"
        # Đảm bảo không trùng
        while User.query.filter(User.student_code == new_code, User.id != sv.id).first():
            idx += 1
            new_code = f"23{major}{idx:03d}"
        old_code = sv.student_code
        sv.student_code = new_code
        updated += 1
        print(f"  ✅ {sv.full_name:22s}: {str(old_code):10s} -> {new_code}")

    db.session.commit()
    print(f"\n✅ Hoàn tất chuẩn hóa {updated}/{len(students)} mã sinh viên!")
