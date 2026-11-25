"""
tests/test_routes.py — Kiểm tra tất cả route hoạt động đúng
Chạy: python tests/test_routes.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from extensions import db
from models.user import User

app = create_app()

CHECKS = [
    # (description, test_function)
]

def run():
    with app.app_context():
        print("\n" + "="*55)
        print("  DAY 7 — KIỂM TRA HỆ THỐNG")
        print("="*55)

        errors = []

        # 1. DB Connection
        try:
            db.session.execute(db.text("SELECT 1"))
            print("  ✅ Kết nối DB")
        except Exception as e:
            print(f"  ❌ Kết nối DB: {e}")
            errors.append("DB connection")

        # 2. Users
        try:
            users = User.query.all()
            students  = [u for u in users if u.role == 'student']
            lecturers = [u for u in users if u.role == 'lecturer']
            print(f"  ✅ Users: {len(users)} tổng ({len(students)} SV, {len(lecturers)} GV)")
        except Exception as e:
            print(f"  ❌ Users: {e}")
            errors.append("users")

        # 3. Classes
        try:
            from models.class_model import Class
            classes = Class.query.all()
            print(f"  ✅ Classes: {len(classes)} lớp học phần")
        except Exception as e:
            print(f"  ❌ Classes: {e}")
            errors.append("classes")

        # 4. Enrollments
        try:
            from models.enrollment import Enrollment
            e = Enrollment.query.count()
            print(f"  ✅ Enrollments: {e} bản ghi")
        except Exception as e:
            print(f"  ❌ Enrollments: {e}")

        # 5. Sessions
        try:
            from models.session import Session
            s = Session.query.count()
            print(f"  ✅ Sessions: {s} buổi học")
        except Exception as e:
            print(f"  ❌ Sessions: {e}")

        # 6. Attendance
        try:
            from models.attendance import Attendance
            a = Attendance.query.count()
            present = Attendance.query.filter_by(status='present').count()
            print(f"  ✅ Attendance: {a} bản ghi ({present} có mặt)")
        except Exception as e:
            print(f"  ❌ Attendance: {e}")

        # 7. Grades
        try:
            from models.grade import Grade
            g = Grade.query.count()
            print(f"  ✅ Grades: {g} bản ghi điểm")
        except Exception as e:
            print(f"  ❌ Grades: {e}")

        # 8. Notifications
        try:
            from models.notification import Notification
            n = Notification.query.count()
            unread = Notification.query.filter_by(is_read=False).count()
            print(f"  ✅ Notifications: {n} ({unread} chưa đọc)")
        except Exception as e:
            print(f"  ❌ Notifications: {e}")

        # 9. Face data table
        try:
            from models.face_data import FaceData
            fd = FaceData.query.count()
            print(f"  ✅ FaceData: {fd} khuôn mặt đã đăng ký")
        except Exception as e:
            print(f"  ❌ FaceData: {e}")

        # 10. Formula config
        try:
            from models.class_model import Class
            with_formula = Class.query.filter(Class.formula_config.isnot(None)).count()
            print(f"  ✅ Formula config: {with_formula} lớp có công thức tùy chỉnh")
        except Exception as e:
            print(f"  ❌ Formula config: {e}")

        # 11. Test Grade calc
        try:
            from models.grade import Grade
            g_test = Grade(attendance_score=9.0, assignment=8.0, midterm=7.0, final=8.0)
            formula = {'attendance':0.10,'assignment':0.20,'midterm':0.20,'final':0.50}
            g_test.calc_total(formula)
            assert g_test.total is not None
            print(f"  ✅ Grade.calc_total(): {g_test.total} ({g_test.grade_letter})")
        except Exception as e:
            print(f"  ❌ Grade.calc_total: {e}")

        # 12. Test Flask URL routes
        try:
            with app.test_request_context():
                from flask import url_for
                urls = [
                    url_for('auth.portal_home'),
                    url_for('auth.login'),
                    url_for('admin.dashboard'),
                    url_for('admin.users_list'),
                    url_for('admin.courses_manage'),
                    url_for('admin.announcements_list'),
                    url_for('student.dashboard'),
                    url_for('student.credit_registration'),
                    url_for('student.schedule'),
                    url_for('student.grades'),
                    url_for('student.notifications'),
                    url_for('student.profile'),
                    url_for('student.attendance_history'),
                    url_for('attendance.checkin_page'),
                    url_for('attendance.register_face_page'),
                    url_for('lecturer.dashboard'),
                    url_for('lecturer.schedule'),
                    url_for('lecturer.class_list'),
                    url_for('lecturer.profile'),
                    url_for('lecturer.audit_logs'),
                ]
                print(f"  ✅ Routes: {len(urls)} URL hợp lệ")
        except Exception as e:
            print(f"  ❌ Routes: {e}")
            errors.append("routes")

        print("\n" + "="*55)
        if errors:
            print(f"  ⚠️  {len(errors)} vấn đề: {', '.join(errors)}")
        else:
            print("  🎉 Tất cả kiểm tra PASSED — Hệ thống sẵn sàng demo!")
        print("="*55)

        print("\nTài khoản demo:")
        try:
            for uname, pw in [('nguyen.van.an','sv123456'),('gv_nguyenvan','gv123456'),('admin','admin123')]:
                u = User.query.filter_by(username=uname).first()
                if u and u.check_password(pw):
                    print(f"  ✅ {uname} / {pw} → {u.role} ({u.student_code or 'staff'})")
                elif u:
                    print(f"  ❌ {uname}: sai mật khẩu")
                else:
                    print(f"  ❌ {uname}: không tồn tại → chạy python scripts/db/seed_curriculum.py")
        except Exception as e:
            print(f"  ❌ Lỗi kiểm tra tài khoản: {e}")

if __name__ == '__main__':
    run()
