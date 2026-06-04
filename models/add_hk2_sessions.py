"""
add_hk2_sessions.py — Chỉ thêm buổi học HK2-2025 (tháng 3 → tháng 6/2026)
Không xóa dữ liệu cũ, không ảnh hưởng các học kỳ khác.
Chạy: python add_hk2_sessions.py
"""
from app import create_app
from extensions import db
from models.class_model import Class
from models.session     import Session
from datetime import date, time, timedelta

app = create_app()

TIET_TIME = {
    1:(time(7,30),time(8,20)),   2:(time(8,30),time(9,20)),
    3:(time(9,30),time(10,20)),  4:(time(10,30),time(11,20)),
    5:(time(11,30),time(12,20)), 6:(time(13,0),time(13,50)),
    7:(time(14,0),time(14,50)),  8:(time(15,0),time(15,50)),
    9:(time(16,0),time(16,50)),  10:(time(17,0),time(17,50)),
}

SEM_START = date(2026, 3, 2)   # Thứ 2 đầu tiên tháng 3/2026
SEM_END   = date(2026, 6, 30)

with app.app_context():
    today = date.today()

    classes = Class.query.filter_by(semester='HK2-2025').all()
    if not classes:
        print("❌ Không tìm thấy lớp HK2-2025. Chạy seed_curriculum.py trước.")
        exit()

    print(f"📚 Tìm thấy {len(classes)} lớp HK2-2025")
    total_added = 0
    total_existed = 0

    for cls in classes:
        info = cls.schedule_info or {}
        weekday    = info.get('day', 0)
        tiet_start = info.get('tiet_start', 1)
        num_tiet   = info.get('num_tiet', 2)

        start_t = TIET_TIME[tiet_start][0]
        end_t   = TIET_TIME[min(tiet_start + num_tiet - 1, 10)][1]

        # Kiểm tra buổi đã có
        existing_dates = set(
            s.session_date for s in
            Session.query.filter_by(class_id=cls.id).all()
        )

        added = 0
        actual_week = 0
        week_offset = 0

        while actual_week < 15:
            week_mon  = SEM_START + timedelta(weeks=week_offset)
            sess_date = week_mon + timedelta(days=weekday)
            week_offset += 1

            if sess_date.weekday() >= 5:       # Bỏ T7, CN
                continue
            if sess_date.month < 3:            # Bỏ tháng 2
                continue
            if sess_date > SEM_END:            # Không qua tháng 6
                break
            if week_offset > 30:
                break

            actual_week += 1

            if sess_date in existing_dates:
                total_existed += 1
                continue

            status = (
                'completed' if sess_date < today else
                'ongoing'   if sess_date == today else
                'scheduled'
            )

            db.session.add(Session(
                class_id    = cls.id,
                session_date= sess_date,
                start_time  = start_t,
                end_time    = end_t,
                room        = cls.room,
                status      = status,
            ))
            added += 1
            total_added += 1

        if added > 0:
            print(f"  ✅ {cls.course_name} ({cls.class_name}): +{added} buổi "
                  f"({SEM_START.strftime('%d/%m')} → {SEM_END.strftime('%d/%m/%Y')})")

    db.session.commit()
    print(f"\n{'='*50}")
    print(f"✅ Hoàn tất!")
    print(f"  Thêm mới : {total_added} buổi")
    print(f"  Đã có   : {total_existed} buổi (giữ nguyên)")
    print(f"  Khoảng  : Tháng 3 → Tháng 6/2026 (15 tuần)")
    print(f"{'='*50}")

    # Xác nhận lại
    total_sessions = Session.query.join(Class, Class.id == Session.class_id)\
        .filter(Class.semester == 'HK2-2025').count()
    first = Session.query.join(Class, Class.id == Session.class_id)\
        .filter(Class.semester == 'HK2-2025')\
        .order_by(Session.session_date).first()
    last  = Session.query.join(Class, Class.id == Session.class_id)\
        .filter(Class.semester == 'HK2-2025')\
        .order_by(Session.session_date.desc()).first()
    if first and last:
        print(f"\n  📅 Buổi đầu : {first.session_date.strftime('%d/%m/%Y')}")
        print(f"  📅 Buổi cuối: {last.session_date.strftime('%d/%m/%Y')}")
        print(f"  📊 Tổng buổi HK2-2025: {total_sessions}")
