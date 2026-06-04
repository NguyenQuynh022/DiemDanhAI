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

app = create_app()

with app.app_context():
    db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 0"))
    for tbl in ['audit_logs','notifications','attendance','face_data','grades','enrollments','sessions','classes','users']:
        db.session.execute(db.text(f"DELETE FROM {tbl}"))
    db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 1"))
    db.session.commit()
    print("Cleared.")

    # Users
    users_data = [
        dict(username="admin",        full_name="Quan tri vien", role="admin",    email="admin@edu.vn",       student_code=None,      password="admin123"),
        dict(username="gv_nguyenvan", full_name="Nguyen Van An", role="lecturer", email="nguyenvanan@edu.vn", student_code=None,      password="gv123456"),
        dict(username="sv_tranthib",  full_name="Tran Thi Binh", role="student",  email="tranthib@edu.vn",    student_code="2021001", password="sv123456"),
        dict(username="sv_lehongc",   full_name="Le Hong Cuong", role="student",  email="lehongc@edu.vn",     student_code="2021002", password="sv123456"),
        dict(username="sv_phamthid",  full_name="Pham Thi Dung", role="student",  email="phamthid@edu.vn",    student_code="2021003", password="sv123456"),
    ]
    user_objs = {}
    for u in users_data:
        obj = User(username=u['username'], full_name=u['full_name'], role=u['role'], email=u['email'], student_code=u['student_code'])
        obj.set_password(u['password'])
        db.session.add(obj)
        user_objs[u['username']] = obj
    db.session.commit()
    print("Users created.")

    gv  = user_objs['gv_nguyenvan']
    sv1 = user_objs['sv_tranthib']
    sv2 = user_objs['sv_lehongc']
    sv3 = user_objs['sv_phamthid']

    # Classes
    cls1 = Class(class_name="CNTT01", course_name="Lap trinh Python", course_code="CS301",
                 lecturer_id=gv.id, semester="HK1-2024", room="P201",
                 schedule_info={"days":["Mon","Thu"],"start":"07:30","end":"09:30"})
    cls2 = Class(class_name="CNTT02", course_name="Co so du lieu", course_code="CS302",
                 lecturer_id=gv.id, semester="HK1-2024", room="P202",
                 schedule_info={"days":["Tue","Fri"],"start":"09:45","end":"11:45"})
    db.session.add_all([cls1, cls2])
    db.session.commit()
    print("Classes created.")

    # Enrollments
    for sv in [sv1, sv2, sv3]:
        db.session.add(Enrollment(student_id=sv.id, class_id=cls1.id, enrolled_by=gv.id))
        db.session.add(Enrollment(student_id=sv.id, class_id=cls2.id, enrolled_by=gv.id))
    db.session.commit()
    print("Enrollments created.")

    # Sessions (past 4 weeks Mon/Thu for cls1)
    today = date.today()
    sessions = []
    for w in range(-3, 1):
        mon = today - timedelta(days=today.weekday()) + timedelta(weeks=w)
        thu = mon + timedelta(days=3)
        for d in [mon, thu]:
            s = Session(class_id=cls1.id, session_date=d,
                        start_time=time(7,30), end_time=time(9,30),
                        room="P201", status='completed' if d < today else 'scheduled')
            db.session.add(s)
            sessions.append((s, d))
    db.session.commit()
    print("Sessions created.")

    # Attendance for sv1 (all present), sv2 (1 absent), sv3 (2 absent)
    for i, (sess, d) in enumerate(sessions):
        if d >= today: continue
        db.session.add(Attendance(student_id=sv1.id, class_id=cls1.id, session_id=sess.id,
            session_date=d, status='present', method='face', face_score=0.9823))
        status2 = 'absent' if i == 2 else 'present'
        db.session.add(Attendance(student_id=sv2.id, class_id=cls1.id, session_id=sess.id,
            session_date=d, status=status2, method='face', face_score=0.9412 if status2=='present' else None))
        status3 = 'absent' if i in [1,3] else 'present'
        db.session.add(Attendance(student_id=sv3.id, class_id=cls1.id, session_id=sess.id,
            session_date=d, status=status3, method='manual' if status3=='present' else 'face'))
    db.session.commit()
    print("Attendance created.")

    # Grades
    for sv, asg, mid, fin in [(sv1,8.5,7.5,8.0),(sv2,7.0,6.5,7.5),(sv3,6.0,5.5,6.5)]:
        g = Grade(student_id=sv.id, class_id=cls1.id, assignment=asg, midterm=mid, final=fin, updated_by=gv.id)
        g.calc_total()
        db.session.add(g)
    db.session.commit()
    print("Grades created.")

    # Notifications
    for sv in [sv1, sv2, sv3]:
        db.session.add(Notification(user_id=sv.id, title="Diem mon Lap trinh Python da duoc cap nhat",
            content="Giang vien da cap nhat diem cuoi ky. Vui long kiem tra bang diem.",
            related_type='grade', related_id=cls1.id))
        db.session.add(Notification(user_id=sv.id, title="Ban da duoc them vao lop CNTT01",
            content="Ban duoc them vao lop Lap trinh Python (CNTT01).",
            related_type='enrollment', related_id=cls1.id, is_read=True))
    db.session.commit()
    print("Notifications created.")
    print("\nDone! All demo data seeded successfully.")
