"""
scripts/db/seed_demo.py — Dữ liệu demo đầy đủ cho Day 7 demo
Chạy: python scripts/db/seed_demo.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app import create_app
from extensions import db
from models.user         import User
from models.class_model  import Class
from models.enrollment   import Enrollment
from models.session      import Session
from models.grade        import Grade
from models.attendance   import Attendance
from models.notification import Notification
from datetime import date, time, timedelta
import random

app = create_app()

with app.app_context():
    db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 0"))
    for tbl in ['audit_logs','notifications','attendance','face_data','grades','enrollments','sessions','classes','users']:
        try: db.session.execute(db.text(f"DELETE FROM {tbl}"))
        except: pass
    db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 1"))
    db.session.commit()
    print("Cleared.")

    # === USERS ===
    users_data = [
        dict(username="admin",        full_name="Quan tri vien",      role="admin",    email="admin@edu.vn",       student_code=None,      password="admin123"),
        dict(username="gv_nguyenvan", full_name="Nguyen Van An",       role="lecturer", email="nguyenvanan@edu.vn", student_code=None,      password="gv123456",
             phone="0901234567", bio="Giang vien khoa CNTT, chuyen nganh AI va Machine Learning. 10 nam kinh nghiem giang day."),
        dict(username="gv_lethithu",  full_name="Le Thi Thu",          role="lecturer", email="lethithu@edu.vn",    student_code=None,      password="gv123456",
             phone="0912345678", bio="Giang vien mon Co so du lieu va Lap trinh Web."),
        dict(username="sv_tranthib",  full_name="Tran Thi Binh",       role="student",  email="tranthib@edu.vn",    student_code="23ITB001", password="sv123456", phone="0987654321"),
        dict(username="sv_lehongc",   full_name="Le Hong Cuong",        role="student",  email="lehongc@edu.vn",     student_code="23ITB002", password="sv123456", phone="0976543210"),
        dict(username="sv_phamthid",  full_name="Pham Thi Dung",        role="student",  email="phamthid@edu.vn",    student_code="23ITB003", password="sv123456", phone="0965432109"),
        dict(username="sv_nguyenvh",  full_name="Nguyen Van Hung",      role="student",  email="nguyenvh@edu.vn",    student_code="24AI001",  password="sv123456"),
        dict(username="sv_hoangmy",   full_name="Hoang Thi My",         role="student",  email="hoangmy@edu.vn",     student_code="24AI002",  password="sv123456"),
    ]
    objs = {}
    for u in users_data:
        obj = User(username=u['username'], full_name=u['full_name'], role=u['role'],
                   email=u['email'], student_code=u.get('student_code'),
                   phone=u.get('phone'), bio=u.get('bio'))
        obj.set_password(u['password'])
        db.session.add(obj)
        objs[u['username']] = obj
    db.session.commit()
    print(f"Created {len(objs)} users.")

    gv1 = objs['gv_nguyenvan']
    gv2 = objs['gv_lethithu']
    students = [objs[k] for k in ['sv_tranthib','sv_lehongc','sv_phamthid','sv_nguyenvh','sv_hoangmy']]

    # === CLASSES ===
    # schedule_info format: {"day": int 0-4 (0=T2..4=T6), "tiet_start": int 1-10,
    #                         "num_tiet": int, "credits": int}
    # Phải khớp với utils/timetable.py TIET_MAP và tiet_span()
    cls1 = Class(class_name="CNTT01", course_name="Lap trinh Python", course_code="CS301",
                 lecturer_id=gv1.id, semester="HK1-2024", room="P201",
                 # Thứ 2 (day=0), tiết 1-3 (07:30-10:20), 3 tín chỉ
                 schedule_info={"day": 0, "tiet_start": 1, "num_tiet": 3, "credits": 3},
                 formula_config={"attendance":0.10,"assignment":0.20,"midterm":0.20,"final":0.50})
    cls2 = Class(class_name="CNTT02", course_name="Co so du lieu",   course_code="CS302",
                 lecturer_id=gv2.id, semester="HK1-2024", room="P202",
                 # Thứ 3 (day=1), tiết 3-5 (09:30-12:20), 3 tín chỉ
                 schedule_info={"day": 1, "tiet_start": 3, "num_tiet": 3, "credits": 3},
                 formula_config={"attendance":0.10,"assignment":0.10,"midterm":0.30,"final":0.50})
    cls3 = Class(class_name="CNTT03", course_name="Mang may tinh",   course_code="CS303",
                 lecturer_id=gv1.id, semester="HK2-2024", room="P301",
                 # Thứ 4 (day=2), tiết 6-8 (13:00-15:50), 3 tín chỉ
                 schedule_info={"day": 2, "tiet_start": 6, "num_tiet": 3, "credits": 3},
                 formula_config={"attendance":0.10,"assignment":0.10,"midterm":0.30,"final":0.50})
    db.session.add_all([cls1, cls2, cls3])
    db.session.commit()
    print("Created 3 classes.")

    # === ENROLLMENTS ===
    for sv in students:
        for cls in [cls1, cls2]:
            db.session.add(Enrollment(student_id=sv.id, class_id=cls.id, enrolled_by=gv1.id))
    # Only 3 students in cls3
    for sv in students[:3]:
        db.session.add(Enrollment(student_id=sv.id, class_id=cls3.id, enrolled_by=gv1.id))
    db.session.commit()
    print("Created enrollments.")

    # === SESSIONS — 8 tuần qua ===
    today = date.today()
    all_sessions = []

    # Khớp với TIET_MAP trong utils/timetable.py
    TIET_TIME = {
        1: (time(7,30),  time(8,20)),   2: (time(8,30),  time(9,20)),
        3: (time(9,30),  time(10,20)),  4: (time(10,30), time(11,20)),
        5: (time(11,30), time(12,20)),  6: (time(13,0),  time(13,50)),
        7: (time(14,0),  time(14,50)),  8: (time(15,0),  time(15,50)),
        9: (time(16,0),  time(16,50)), 10: (time(17,0),  time(17,50)),
    }

    def make_sessions(cls, weeks=8):
        """Đọc weekday và giờ từ schedule_info — đảm bảo khớp với timetable.py"""
        info       = cls.schedule_info or {}
        weekday    = info.get('day', 0)           # 0=T2 … 4=T6
        tiet_start = info.get('tiet_start', 1)
        num_tiet   = info.get('num_tiet', 2)
        tiet_end   = min(tiet_start + num_tiet - 1, 10)
        start_t    = TIET_TIME[tiet_start][0]
        end_t      = TIET_TIME[tiet_end][1]

        sessions = []
        for w in range(-weeks, 1):
            week_monday = today - timedelta(days=today.weekday()) + timedelta(weeks=w)
            d = week_monday + timedelta(days=weekday)
            if d > today:
                continue
            status = 'completed' if d < today else 'ongoing'
            s = Session(class_id=cls.id, session_date=d,
                        start_time=start_t, end_time=end_t,
                        room=cls.room, status=status)
            db.session.add(s)
            sessions.append((s, d))
        return sessions

    sess_cls1 = make_sessions(cls1)           # T2, tiết 1-3
    sess_cls2 = make_sessions(cls2)           # T3, tiết 3-5
    sess_cls3 = make_sessions(cls3, weeks=4)  # T4, tiết 6-8
    db.session.commit()
    print(f"Created sessions: cls1={len(sess_cls1)}, cls2={len(sess_cls2)}, cls3={len(sess_cls3)}")

    # === ATTENDANCE — realistic patterns ===
    random.seed(42)
    attendance_patterns = {
        'sv_tranthib': 0.95,  # chăm chỉ
        'sv_lehongc':  0.80,  # khá
        'sv_phamthid': 0.70,  # trung bình
        'sv_nguyenvh': 0.60,  # hay vắng
        'sv_hoangmy':  0.85,  # khá
    }

    def make_attendance(sessions_list, enrollments_students, cls):
        for sess, d in sessions_list:
            if d >= today: continue
            for sv in enrollments_students:
                rate = attendance_patterns.get(sv.username, 0.8)
                r = random.random()
                if r < rate:
                    status = 'present' if r < rate*0.9 else 'late'
                    db.session.add(Attendance(
                        student_id=sv.id, class_id=cls.id,
                        session_id=sess.id, session_date=d,
                        status=status, method='face' if r < 0.7 else 'manual',
                        face_score=round(random.uniform(0.82, 0.98), 4) if r < 0.7 else None,
                        checkin_time=None
                    ))
                else:
                    db.session.add(Attendance(
                        student_id=sv.id, class_id=cls.id,
                        session_id=sess.id, session_date=d,
                        status='absent', method='manual'
                    ))

    make_attendance(sess_cls1, students,    cls1)
    make_attendance(sess_cls2, students,    cls2)
    make_attendance(sess_cls3, students[:3], cls3)
    db.session.commit()
    print("Created attendance records.")

    # === GRADES ===
    grade_data = {
        'sv_tranthib': (9.0, 8.5, 10.0, 9.5),
        'sv_lehongc':  (7.0, 6.5,  7.5, 8.0),
        'sv_phamthid': (6.0, 5.5,  6.5, 7.0),
        'sv_nguyenvh': (5.5, 5.0,  5.5, 6.0),
        'sv_hoangmy':  (8.0, 7.5,  8.0, 8.5),
    }
    for uname, (att, asg, mid, fin) in grade_data.items():
        sv = objs[uname]
        for cls, formula in [(cls1, cls1.formula_config), (cls2, cls2.formula_config)]:
            g = Grade(student_id=sv.id, class_id=cls.id,
                      attendance_score=att, assignment=asg,
                      midterm=mid, final=fin, updated_by=gv1.id)
            g.calc_total(formula)
            db.session.add(g)
    db.session.commit()
    print("Created grades.")

    # === NOTIFICATIONS ===
    for sv in students:
        db.session.add(Notification(
            user_id=sv.id,
            title=f"Diem mon {cls1.course_name} da duoc cap nhat",
            content="Giang vien da nhap diem cuoi ky. Vao muc Diem so de xem chi tiet.",
            related_type='grade', related_id=cls1.id
        ))
        db.session.add(Notification(
            user_id=sv.id,
            title="Ban da duoc them vao lop CNTT01",
            content=f"Ban duoc dang ky vao lop {cls1.class_name} — {cls1.course_name}.",
            related_type='enrollment', related_id=cls1.id, is_read=True
        ))
    db.session.commit()
    print("Created notifications.")

    print("\n" + "="*50)
    print("DEMO SEED HOAN TAT!")
    print("="*50)
    print("\nTai khoan demo:")
    print("  Sinh vien : sv_tranthib / sv123456")
    print("  Giang vien: gv_nguyenvan / gv123456")
    print("  Admin     : admin / admin123")
