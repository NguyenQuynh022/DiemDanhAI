"""
scripts/db/setup_current_semester_courses.py
Đồng bộ chuẩn lịch học kỳ theo quy định mới (không mất dữ liệu cũ):
  - HK1: bắt đầu Tháng 8 -> kết thúc Tháng 12
  - HK2: bắt đầu Tháng 2 -> kết thúc Tháng 5
  - Khởi tạo đợt mở Đăng ký tín chỉ & các môn học phần cho kỳ hiện tại (HK1-2026: 08/2026 -> 12/2026):
    + Học từ Thứ 2 -> Thứ 6 (day 0..4), trung bình 2 tín chỉ/môn
    + Xếp lịch giảng viên hợp lý, trải đều các ngày, không trùng ca, không trùng phòng
    + Khởi tạo đăng ký mẫu hợp lệ (4-5 môn, trong khoảng 3-7 môn, không trùng lịch, không trùng môn) cho sinh viên
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import random
from datetime import date
from app import create_app
from extensions import db
from models import User, Class, Enrollment, Session, Attendance, RegistrationConfig
from utils.timetable import (
    get_current_semester_id,
    schedules_conflict,
    generate_sessions_for_class,
)

app = create_app()

# 8 học phần mở trong HK1-2026 (trung bình 2 tín chỉ/môn, học Thứ 2 -> Thứ 6)
HK1_2026_SUBJECTS = [
    ("CS801", "Phát triển ứng dụng AI",          2, 2, "P.A1"),
    ("CS802", "An toàn và Bảo mật hệ thống",     2, 2, "P.A2"),
    ("CS803", "Điện toán đám mây",               2, 2, "P.B1"),
    ("CS804", "Quản trị dự án phần mềm",         2, 2, "K.B3"),
    ("IT805", "Xử lý ngôn ngữ tự nhiên",         2, 2, "V.A2"),
    ("IT806", "Thị giác máy tính",               2, 2, "Lab.1"),
    ("PL807", "Chủ nghĩa xã hội khoa học",       2, 2, "K.C1"),
    ("SE808", "Kiến trúc phần mềm hiện đại",     2, 2, "P.B2"),
]

CANDIDATE_SLOTS = [(d, ts) for d in range(5) for ts in (1, 3, 6, 8)]  # Thứ 2..6 (0..4) × 4 ca/ngày = 20 ca

with app.app_context():
    today   = date.today()
    cur_sem = get_current_semester_id(today)
    random.seed(2026)

    # 1. Đóng các học kỳ cũ đã qua (như HK2-2025 kết thúc tháng 5/2026)
    past_active = Class.query.filter(Class.semester != cur_sem, Class.status == 'active').all()
    for c in past_active:
        c.status = 'closed'

    # 2. Khởi tạo cấu hình Đăng ký tín chỉ (Mặc định ĐÓNG, chỉ khi Admin mở mới đăng ký được)
    admin = User.query.filter_by(role='admin').first()
    reg_cfg = RegistrationConfig.query.filter_by(semester=cur_sem).first()
    if not reg_cfg:
        reg_cfg = RegistrationConfig(
            semester=cur_sem,
            is_open=False,
            min_courses=3,
            max_courses=7,
            note=f'Đợt đăng ký tín chỉ {cur_sem} (Tháng 8 → Tháng 12, tối thiểu 3 môn, tối đa 7 môn)',
            updated_by=admin.id if admin else None,
        )
        db.session.add(reg_cfg)

    lecturers = User.query.filter_by(role='lecturer', status='active').order_by(User.id).all()
    students  = User.query.filter_by(role='student', status='active').order_by(User.id).all()

    existing_cur = Class.query.filter_by(semester=cur_sem).count()
    if existing_cur == 0 and lecturers:
        gv_classes: dict[int, list[dict]] = {gv.id: [] for gv in lecturers}
        gv_days:    dict[int, set[int]]   = {gv.id: set() for gv in lecturers}
        room_slots: set[tuple]            = set()
        created_by_course: dict[str, list[Class]] = {}

        # Mỗi môn mở 3 nhóm lớp trải đều Thứ 2 -> Thứ 6 để SV thoải mái lựa chọn không lo kẹt lịch
        for s_idx, (code, name, credits, num_tiet, room_prefix) in enumerate(HK1_2026_SUBJECTS):
            created_by_course[code] = []
            for grp in range(1, 4):
                class_name = f"{code}-0{grp}"
                room       = f"{room_prefix}0{grp}"

                # Chọn giảng viên có tải ít nhất hiện tại
                gv = min(lecturers, key=lambda g: (len(gv_classes[g.id]), g.id))

                # Ưu tiên ngày GV chưa dạy & rải đều các thứ T2..T6
                ordered_slots = sorted(
                    CANDIDATE_SLOTS,
                    key=lambda sl: (
                        1 if sl[0] in gv_days[gv.id] else 0,
                        (sl[0] + s_idx + grp) % 5,
                        sl[1],
                    ),
                )

                chosen_day, chosen_ts = 0, 1
                for d, ts in ordered_slots:
                    cand = {'day': d, 'tiet_start': ts, 'num_tiet': num_tiet, 'credits': credits}
                    if any(schedules_conflict(cand, ex) for ex in gv_classes[gv.id]):
                        continue
                    if (room, d, ts) in room_slots:
                        continue
                    chosen_day, chosen_ts = d, ts
                    break

                sched = {'day': chosen_day, 'tiet_start': chosen_ts, 'num_tiet': num_tiet, 'credits': credits}
                gv_classes[gv.id].append(sched)
                gv_days[gv.id].add(chosen_day)
                room_slots.add((room, chosen_day, chosen_ts))

                cls = Class(
                    class_name=class_name,
                    course_name=name,
                    course_code=code,
                    lecturer_id=gv.id,
                    semester=cur_sem,
                    room=room,
                    schedule_info=sched,
                    formula_config={'attendance': 0.10, 'assignment': 0.10, 'midterm': 0.30, 'final': 0.50},
                    max_students=40,
                    status='active',
                )
                db.session.add(cls)
                db.session.flush()

                # Sinh toàn bộ buổi học Tháng 8 -> Tháng 12 (T2 -> T6)
                sess_list = generate_sessions_for_class(cls, today=today)
                for s in sess_list:
                    db.session.add(s)
                created_by_course[code].append(cls)

        db.session.flush()

        # Đăng ký mẫu hợp lệ cho từng Sinh viên: 5 môn (nằm trong chuẩn 3..7 môn),
        # không trùng môn, không trùng lịch học, để SV vừa có lịch học tuần này vừa còn slot đăng ký thêm tới 7 môn!
        course_codes = list(created_by_course.keys())
        for sv in students:
            picked_classes: list[Class] = []
            shuffled_codes = course_codes[:]
            random.shuffle(shuffled_codes)

            for code in shuffled_codes:
                if len(picked_classes) >= 5:
                    break
                options = created_by_course[code][:]
                random.shuffle(options)
                for cand_cls in options:
                    if not any(schedules_conflict(cand_cls.schedule_info, pc.schedule_info) for pc in picked_classes):
                        picked_classes.append(cand_cls)
                        db.session.add(Enrollment(
                            student_id=sv.id,
                            class_id=cand_cls.id,
                            enrolled_by=sv.id,
                            status='enrolled',
                        ))
                        break

            # Sinh điểm danh cho các buổi đã qua trước ngày hôm nay của kỳ hiện tại
            for pc in picked_classes:
                past_sessions = Session.query.filter(
                    Session.class_id == pc.id,
                    Session.session_date < today,
                ).all()
                for ps in past_sessions:
                    r = random.random()
                    st = 'present' if r < 0.86 else ('late' if r < 0.93 else 'absent')
                    db.session.add(Attendance(
                        student_id=sv.id,
                        class_id=pc.id,
                        session_id=ps.id,
                        session_date=ps.session_date,
                        status=st,
                        method='face' if st == 'present' else 'manual',
                        face_score=round(random.uniform(0.86, 0.98), 4) if st == 'present' else None,
                    ))

        db.session.commit()
        print(f"✅ Đã mở {len(HK1_2026_SUBJECTS) * 3} lớp học phần cho {cur_sem} (T8→T12, Thứ 2→Thứ 6, 2 TC/môn)!")
    else:
        db.session.commit()
        print(f"✓ Học kỳ {cur_sem} đã có {existing_cur} lớp học phần.")
