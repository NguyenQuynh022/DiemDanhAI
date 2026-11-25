import os
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from datetime import date, timedelta
from extensions import db
from models.class_model         import Class
from models.enrollment          import Enrollment
from models.session             import Session
from models.grade               import Grade
from models.attendance          import Attendance
from models.notification        import Notification
from models.registration_config import RegistrationConfig
from utils.decorators           import student_required

student_bp = Blueprint('student', __name__, url_prefix='/student')

def _format_class_schedule(cls):
    DAYS_SHORT = ['Hai', 'Ba', 'Tư', 'Năm', 'Sáu', 'Bảy', 'CN']
    info = cls.schedule_info or {}
    if isinstance(info, dict) and 'day' in info:
        d_idx = int(info.get('day', 0))
        t_st  = int(info.get('tiet_start', 1))
        n_t   = int(info.get('num_tiet', 2))
        t_end = min(10, t_st + n_t - 1)
        d_str = DAYS_SHORT[d_idx] if 0 <= d_idx < len(DAYS_SHORT) else '?'
        return d_idx, f"{d_str} / {t_st}→{t_end}"
    return -1, "—"


@student_bp.route('/dashboard')
@student_bp.route('/schedule/detail')
@login_required
@student_required
def dashboard():
    from utils.timetable import get_all_semesters, get_current_semester_id, format_class_weeks_range
    sid   = current_user.id
    today = date.today()
    cur_sem = get_current_semester_id(today)
    sel_sem = request.args.get('semester', '').strip()

    q_cls = (
        db.session.query(Class)
        .join(Enrollment, Enrollment.class_id == Class.id)
        .filter(Enrollment.student_id == sid, Enrollment.status == 'enrolled')
    )
    if sel_sem:
        enrolled_classes = q_cls.filter(Class.semester == sel_sem).all()
    else:
        cur_classes = q_cls.filter(Class.semester == cur_sem).all()
        if cur_classes:
            enrolled_classes = cur_classes
            sel_sem = cur_sem
        else:
            active_cls = q_cls.filter(Class.status == 'active').all()
            enrolled_classes = active_cls if active_cls else q_cls.all()
            sel_sem = enrolled_classes[0].semester if enrolled_classes else cur_sem

    # Xác định nhãn học kỳ hiển thị trên tiêu đề
    sem_num, sem_years = '2', '2025 - 2026'
    if sel_sem and '-' in sel_sem:
        hk_p, yr_p = sel_sem.split('-', 1)
        sem_num = '1' if hk_p == 'HK1' else '2'
        if yr_p.isdigit():
            sem_years = f"{yr_p} - {int(yr_p) + 1}"

    today_sessions = (
        db.session.query(Session, Class).join(Class, Class.id == Session.class_id)
        .join(Enrollment, Enrollment.class_id == Class.id)
        .filter(
            Enrollment.student_id == sid,
            Enrollment.status == 'enrolled',
            Session.session_date == today,
            Session.status != 'cancelled',
        )
        .order_by(Session.start_time).all()
    )
    today_class_ids = {cls.id for _, cls in today_sessions}

    # Xây dựng dữ liệu bảng "Lịch học ngày hôm nay" và "Lịch học các ngày khác!"
    today_rows = []
    for sess, cls in today_sessions:
        _, thu_tiet = _format_class_schedule(cls)
        today_rows.append({
            'cls': cls,
            'sess': sess,
            'weeks': format_class_weeks_range(cls),
            'room': sess.room or cls.room or '—',
            'thu_tiet': thu_tiet,
        })

    other_rows = []
    for cls in enrolled_classes:
        if cls.id in today_class_ids:
            continue
        _, thu_tiet = _format_class_schedule(cls)
        other_rows.append({
            'cls': cls,
            'weeks': format_class_weeks_range(cls),
            'room': cls.room or '—',
            'thu_tiet': thu_tiet,
        })

    attended_count = Attendance.query.filter_by(student_id=sid, status='present').count()
    unread_count   = Notification.query.filter_by(user_id=sid, is_read=False).count()
    return render_template('student/dashboard.html',
        enrolled_classes=enrolled_classes,
        today_sessions=today_sessions,
        today_rows=today_rows,
        other_rows=other_rows,
        sel_sem=sel_sem,
        sem_num=sem_num,
        sem_years=sem_years,
        all_semesters=get_all_semesters(),
        attended_count=attended_count,
        unread_count=unread_count,
        today=today,
    )


@student_bp.route('/classes')
@login_required
@student_required
def my_classes():
    """Trang Lớp học phần riêng biệt: liệt kê tất cả lớp học phần đã đăng ký theo học kỳ."""
    from utils.timetable import get_all_semesters, get_current_semester_id, format_class_weeks_range
    sid = current_user.id
    cur_sem = get_current_semester_id()
    sel_sem = request.args.get('semester', '').strip() or cur_sem

    enrolls = (
        db.session.query(Enrollment, Class)
        .join(Class, Class.id == Enrollment.class_id)
        .filter(
            Enrollment.student_id == sid,
            Enrollment.status.in_(['enrolled', 'completed']),
            Class.semester == sel_sem,
        )
        .order_by(Class.course_code, Class.class_name)
        .all()
    )
    grades_map = {
        g.class_id: g
        for g in Grade.query.filter_by(student_id=sid).all()
    }
    rows = []
    for enroll, cls in enrolls:
        _, thu_tiet = _format_class_schedule(cls)
        att_total = Attendance.query.filter_by(student_id=sid, class_id=cls.id).count()
        att_pres  = Attendance.query.filter(
            Attendance.student_id == sid,
            Attendance.class_id == cls.id,
            Attendance.status.in_(['present', 'late']),
        ).count()
        rows.append({
            'cls': cls,
            'credits': int((cls.schedule_info or {}).get('credits', 2)),
            'weeks': format_class_weeks_range(cls),
            'thu_tiet': thu_tiet,
            'att_str': f"{att_pres}/{att_total}" if att_total else "—",
            'grade': grades_map.get(cls.id),
        })

    hk_p, yr_p = (sel_sem.split('-', 1) + ['2026'])[:2]
    sem_num   = '1' if hk_p == 'HK1' else '2'
    sem_years = f"{yr_p} - {int(yr_p) + 1}" if yr_p.isdigit() else sel_sem

    return render_template(
        'student/classes.html',
        rows=rows,
        sel_sem=sel_sem,
        sem_num=sem_num,
        sem_years=sem_years,
        all_semesters=get_all_semesters(),
    )


@student_bp.route('/schedule/all-courses')
@login_required
@student_required
def all_courses_schedule():
    """
    Trang 'THỜI KHÓA BIỂU - DANH SÁCH LỚP HỌC PHẦN' (Thời khóa biểu toàn khóa):
    Tra cứu toàn bộ các lớp học phần mở trong toàn trường theo Học kỳ, Năm học, Thứ, Giảng viên, Học phần.
    """
    from sqlalchemy import func
    from models.user import User
    from utils.timetable import (
        get_current_semester_id,
        format_class_weeks_csv,
        format_full_tkb_slot,
    )

    cur_sem = get_current_semester_id()
    def_hk, def_yr = (cur_sem.split('-', 1) + ['2026'])[:2]

    # Hỗ trợ cả đồng bộ từ dropdown ?semester=HK1-2026 trên topbar lẫn form lọc HK + Năm học riêng
    sem_arg = request.args.get('semester', '').strip()
    if sem_arg and '-' in sem_arg:
        hk_default, yr_default = sem_arg.split('-', 1)
    else:
        hk_default, yr_default = def_hk, def_yr

    hk          = request.args.get('hk', hk_default).strip().upper()
    year        = request.args.get('year', yr_default).strip()
    day_filter  = request.args.get('day', '').strip()
    scope       = request.args.get('scope', 'all').strip()  # 'all' (Học phần, Nhóm lớp) hoặc 'mine' (Lớp của tôi)
    lecturer_q  = request.args.get('lecturer_q', '').strip()
    course_q    = request.args.get('course_q', '').strip()

    if hk not in ('HK1', 'HK2'):
        hk = def_hk
    if not year.isdigit():
        year = def_yr
    target_sem = f"{hk}-{year}"

    # Danh sách năm học có trong hệ thống (từ 2023 đến năm hiện tại)
    today_yr = date.today().year
    academic_years = [str(y) for y in range(today_yr, 2022, -1)]

    query = (
        db.session.query(Class, User)
        .outerjoin(User, User.id == Class.lecturer_id)
        .filter(Class.semester == target_sem, Class.status != 'cancelled')
    )
    if scope == 'mine':
        query = query.join(
            Enrollment,
            (Enrollment.class_id == Class.id)
            & (Enrollment.student_id == current_user.id)
            & (Enrollment.status == 'enrolled'),
        )
    if lecturer_q:
        query = query.filter(User.full_name.ilike(f"%{lecturer_q}%"))
    if course_q:
        like_c = f"%{course_q}%"
        query = query.filter((Class.course_name.ilike(like_c)) | (Class.class_name.ilike(like_c)) | (Class.course_code.ilike(like_c)))

    raw_items = query.order_by(Class.course_name, Class.class_name).all()

    # Lọc theo Thứ nếu chọn cụ thể (0..6)
    if day_filter != '' and day_filter.isdigit():
        want_day = int(day_filter)
        raw_items = [
            (c, gv) for c, gv in raw_items
            if isinstance(c.schedule_info, dict) and c.schedule_info.get('day') is not None and int(c.schedule_info.get('day')) == want_day
        ]

    class_ids = [c.id for c, _ in raw_items]
    enroll_counts = {}
    sess_dates_by_cls = {}
    if class_ids:
        for cid, cnt in (
            db.session.query(Enrollment.class_id, func.count(Enrollment.id))
            .filter(Enrollment.class_id.in_(class_ids), Enrollment.status == 'enrolled')
            .group_by(Enrollment.class_id)
            .all()
        ):
            enroll_counts[cid] = cnt

        for cid, sdate in (
            db.session.query(Session.class_id, Session.session_date)
            .filter(Session.class_id.in_(class_ids), Session.status != 'cancelled')
            .order_by(Session.session_date)
            .all()
        ):
            sess_dates_by_cls.setdefault(cid, []).append(sdate)

    rows = []
    for cls, gv in raw_items:
        grp_suffix = cls.class_name.split('-')[-1].lstrip('0') if '-' in cls.class_name else ''
        display_name = f"{cls.course_name} ({grp_suffix or cls.class_name})"
        enrolled_n = enroll_counts.get(cls.id, 0)
        rows.append({
            'cls': cls,
            'display_name': display_name,
            'lecturer_name': gv.full_name if gv else '—',
            'tkb_str': format_full_tkb_slot(cls),
            'room': cls.room or '—',
            'weeks_csv': format_class_weeks_csv(cls, sess_dates_by_cls.get(cls.id, [])),
            'siso': enrolled_n if enrolled_n > 0 else (cls.max_students or 45),
        })

    return render_template(
        'student/schedule_all_courses.html',
        rows=rows,
        hk=hk,
        year=year,
        sel_sem=target_sem,
        day_filter=day_filter,
        scope=scope,
        lecturer_q=lecturer_q,
        course_q=course_q,
        academic_years=academic_years,
    )


@student_bp.route('/classes/<int:class_id>/timeline')
@login_required
@student_required
def class_timeline(class_id):
    """Trang Xem lịch trình giảng dạy chi tiết từng buổi học của lớp học phần (xem được cho mọi lớp trên TKB toàn khóa)."""
    from utils.timetable import get_semester_start
    sid = current_user.id
    cls = Class.query.get_or_404(class_id)
    is_enrolled = Enrollment.query.filter_by(student_id=sid, class_id=class_id, status='enrolled').first() is not None
    sessions = Session.query.filter_by(class_id=class_id).order_by(Session.session_date, Session.start_time).all()
    att_map  = {
        a.session_date: a
        for a in Attendance.query.filter_by(student_id=sid, class_id=class_id).all()
    } if is_enrolled else {}
    sem_start = get_semester_start(cls.semester)
    base_mon  = sessions[0].session_date - timedelta(days=sessions[0].session_date.weekday()) if (sessions and sessions[0].session_date < sem_start) else sem_start
    _, thu_tiet = _format_class_schedule(cls)

    session_rows = []
    for idx, s in enumerate(sessions, start=1):
        wk = max(1, ((s.session_date - base_mon).days // 7) + 1)
        session_rows.append({
            'stt': idx,
            'week': wk,
            'sess': s,
            'att': att_map.get(s.session_date),
        })

    return render_template(
        'student/class_timeline.html',
        cls=cls,
        is_enrolled=is_enrolled,
        thu_tiet=thu_tiet,
        session_rows=session_rows,
        today=date.today(),
    )

@student_bp.route('/schedule')
@login_required
@student_required
def schedule():
    from utils.timetable import (
        TIET_MAP,
        tiet_span,
        get_all_semesters,
        get_current_semester_id,
        resolve_viewing_week,
        format_semester_heading,
        build_semester_weeks_timetables,
    )
    sid         = current_user.id
    today       = date.today()
    all_semesters = get_all_semesters()
    cur_sem_id    = get_current_semester_id(today)
    selected_sem  = request.args.get('semester', '').strip()
    view_mode     = request.args.get('view', '').strip()
    if view_mode == 'detail':
        return redirect(url_for('student.dashboard', semester=selected_sem) if selected_sem else url_for('student.dashboard'))
    is_expanded   = (view_mode == 'expanded')

    semester_order = {sem_id: idx for idx, (sem_id, *_rest) in enumerate(all_semesters)}
    if not selected_sem:
        has_cur = (
            db.session.query(Class.id)
            .join(Enrollment, Enrollment.class_id == Class.id)
            .filter(Enrollment.student_id == sid, Enrollment.status == 'enrolled', Class.semester == cur_sem_id)
            .first()
        )
        if has_cur:
            selected_sem = cur_sem_id
        else:
            enrolled_sems = [
                sem for sem, in db.session.query(Class.semester)
                .join(Enrollment, Enrollment.class_id == Class.id)
                .filter(Enrollment.student_id == sid, Enrollment.status == 'enrolled')
                .distinct().all()
                if sem in semester_order
            ]
            selected_sem = max(enrolled_sems, key=lambda s: semester_order[s]) if enrolled_sems else cur_sem_id

    # Luôn mở vào đúng TUẦN ĐANG HỌC (nếu là học kỳ hiện tại) hoặc tuần 1 của kỳ được chọn
    week_start, week_end, week_offset, week_num = resolve_viewing_week(
        selected_sem, request.args.get('week'), today
    )

    sessions = (
        db.session.query(Session, Class)
        .join(Class, Class.id == Session.class_id)
        .join(Enrollment, Enrollment.class_id == Class.id)
        .filter(
            Enrollment.student_id == sid,
            Enrollment.status == 'enrolled',
            Class.semester == selected_sem,
            Session.session_date >= week_start,
            Session.session_date <= week_end,
            Session.status != 'cancelled',
        )
        .order_by(Session.session_date, Session.start_time).all()
    )

    timetable = {}
    occupied  = set()
    for sess, cls in sessions:
        day_idx = sess.session_date.weekday()
        t_start, span = tiet_span(sess.start_time, sess.end_time)
        if (day_idx, t_start) not in timetable:
            timetable[(day_idx, t_start)] = (sess, cls, span)
        for t in range(t_start, t_start + span):
            occupied.add((day_idx, t))

    all_weeks_data = []
    if is_expanded:
        all_sem_sessions = (
            db.session.query(Session, Class)
            .join(Class, Class.id == Session.class_id)
            .join(Enrollment, Enrollment.class_id == Class.id)
            .filter(
                Enrollment.student_id == sid,
                Enrollment.status == 'enrolled',
                Class.semester == selected_sem,
            )
            .order_by(Session.session_date, Session.start_time)
            .all()
        )
        all_weeks_data = build_semester_weeks_timetables(selected_sem, all_sem_sessions)

    week_cancelled = (
        db.session.query(Session, Class)
        .join(Class, Class.id == Session.class_id)
        .join(Enrollment, Enrollment.class_id == Class.id)
        .filter(
            Enrollment.student_id == sid,
            Enrollment.status == 'enrolled',
            Class.semester == selected_sem,
            Session.session_date >= week_start,
            Session.session_date <= week_end,
            Session.status == 'cancelled',
        )
        .order_by(Session.session_date, Session.start_time)
        .all()
    )

    return render_template('student/schedule.html',
        timetable=timetable, occupied=occupied,
        week_start=week_start, week_end=week_end,
        week_offset=week_offset, today=today,
        week_num=week_num,
        tiet_map=TIET_MAP,
        all_semesters=all_semesters,
        selected_semester=selected_sem,
        sem_heading=format_semester_heading(selected_sem),
        is_expanded=is_expanded,
        all_weeks_data=all_weeks_data,
        week_cancelled=week_cancelled,
        sem_classes=db.session.query(Class).join(Enrollment, Enrollment.class_id == Class.id)
            .filter(Enrollment.student_id == sid, Enrollment.status == 'enrolled', Class.semester == selected_sem).all(),
    )

@student_bp.route('/grades')
@login_required
@student_required
def grades():
    sid = current_user.id
    sel_sem = request.args.get('semester', '')

    # Lấy tất cả điểm đã có
    all_grades = (
        db.session.query(Grade, Class)
        .join(Class, Class.id == Grade.class_id)
        .filter(Grade.student_id == sid)
        .order_by(Class.semester, Class.course_name).all()
    )

    sems_with_grades = sorted(set(cls.semester for _, cls in all_grades))

    if sel_sem:
        grade_data = [(g, cls) for g, cls in all_grades if cls.semester == sel_sem]
    else:
        grade_data = all_grades

    # Tổng kết từng học kỳ (like image 8)
    sem_summary = []
    cum_credits = 0
    cum_sum4    = 0.0
    cum_sum10   = 0.0
    for i, sem in enumerate(sems_with_grades):
        sem_grades = [(g, cls) for g, cls in all_grades if cls.semester == sem]
        tc_dk = sum(
            int(cls.schedule_info.get('credits', 3)) if cls.schedule_info else 3
            for _, cls in sem_grades
        )
        valid = [(g, cls) for g, cls in sem_grades if g.total is not None]
        if valid:
            # Điểm 10 (trung bình)
            d10 = round(sum(float(g.total) for g, _ in valid) / len(valid), 2)
            # Điểm 4 (quy đổi)
            d4  = round(sum(_to_grade4(float(g.total)) for g, _ in valid) / len(valid), 2)
            xl  = _xep_loai(d10)
        else:
            d10 = d4 = 0.0; xl = '—'

        cum_credits += tc_dk
        cum_sum4    += d4 * tc_dk
        cum_sum10   += d10 * tc_dk
        d4_tl  = round(cum_sum4  / cum_credits, 2) if cum_credits else 0
        d10_tl = round(cum_sum10 / cum_credits, 2) if cum_credits else 0

        sem_summary.append({
            'stt':       i + 1,
            'semester':  sem,
            'sem_label': _sem_label(sem),
            'tc_dk':     tc_dk,
            'diem4':     d4,
            'diem10':    d10,
            'diem_hb':   d10,
            'tc_tl_hk':  tc_dk,
            'xep_loai':  xl,
            'diem4_tl':  d4_tl,
            'diem10_tl': d10_tl,
            'tc_tich_luy': cum_credits,
        })

    gpa10 = round(cum_sum10 / cum_credits, 2) if cum_credits else None
    gpa4  = round(cum_sum4  / cum_credits, 2) if cum_credits else None

    return render_template('student/grades.html',
        grade_data=grade_data,
        sems_with_grades=sems_with_grades,
        sel_sem=sel_sem,
        sem_summary=sem_summary,
        gpa10=gpa10, gpa4=gpa4,
        total_credits=cum_credits,
    )

def _to_grade4(d10):
    if d10 >= 9.0: return 4.0
    if d10 >= 8.5: return 3.7
    if d10 >= 8.0: return 3.5
    if d10 >= 7.0: return 3.0
    if d10 >= 6.5: return 2.5
    if d10 >= 5.5: return 2.0
    if d10 >= 5.0: return 1.5
    if d10 >= 4.0: return 1.0
    return 0.0

def _xep_loai(d10):
    if d10 >= 9.0: return 'Xuất sắc'
    if d10 >= 8.0: return 'Giỏi'
    if d10 >= 7.0: return 'Khá'
    if d10 >= 5.0: return 'Trung bình'
    return 'Yếu'

def _sem_label(sem_id):
    hk, year = sem_id.split('-')
    n = '1' if hk == 'HK1' else '2'
    y2 = int(year)
    return f"Học kỳ {n}, năm {y2} - {y2+1}" 

@student_bp.route('/notifications')
@login_required
@student_required
def notifications():
    page   = request.args.get('page', 1, type=int)
    notifs = (Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .paginate(page=page, per_page=15, error_out=False))
    return render_template('student/notifications.html', notifs=notifs)

@student_bp.route('/notifications/read/<int:nid>', methods=['POST'])
@login_required
@student_required
def mark_read(nid):
    n = Notification.query.filter_by(id=nid, user_id=current_user.id).first_or_404()
    n.is_read = True
    db.session.commit()
    return jsonify({'ok': True})

@student_bp.route('/notifications/read-all', methods=['POST'])
@login_required
@student_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'ok': True})

@student_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@student_required
def profile():
    from models.user import User
    user = User.query.get(current_user.id)
    if request.method == 'POST':
        phone   = request.form.get('phone', '').strip()
        email   = request.form.get('email', '').strip()
        new_pw  = request.form.get('new_password', '')
        conf_pw = request.form.get('confirm_password', '')
        if phone: user.phone = phone
        if email: user.email = email
        if new_pw:
            if new_pw != conf_pw:
                flash('Mật khẩu xác nhận không khớp.', 'danger')
                return redirect(url_for('student.profile'))
            if len(new_pw) < 6:
                flash('Mật khẩu phải ít nhất 6 ký tự.', 'danger')
                return redirect(url_for('student.profile'))
            user.set_password(new_pw)
        db.session.commit()
        flash('Cập nhật thành công!', 'success')
        return redirect(url_for('student.profile'))
    return render_template('student/profile.html', user=user)

@student_bp.route('/attendance')
@login_required
@student_required
def attendance_history():
    sid      = current_user.id
    class_id = request.args.get('class_id', type=int)
    query = (db.session.query(Attendance, Class).join(Class, Class.id == Attendance.class_id)
             .filter(Attendance.student_id == sid))
    if class_id:
        query = query.filter(Attendance.class_id == class_id)
    records    = query.order_by(Attendance.session_date.desc()).all()
    my_classes = (db.session.query(Class).join(Enrollment, Enrollment.class_id == Class.id)
                  .filter(Enrollment.student_id == sid, Enrollment.status.in_(['enrolled', 'completed'])).all())
    return render_template('student/attendance.html',
        records=records, my_classes=my_classes, selected_class=class_id)

@student_bp.route('/profile/avatar', methods=['GET', 'POST'])
@login_required
@student_required
def upload_avatar():
    # GET requests (e.g. from browser prefetch) redirect to profile
    if request.method == 'GET':
        return redirect(url_for('student.profile'))
    from models.user import User
    try:
        ALLOWED = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        file = request.files.get('avatar')
        if not file or file.filename == '':
            flash('Chưa chọn file.', 'danger')
            return redirect(url_for('student.profile'))

        ext = ''
        if '.' in file.filename:
            ext = file.filename.rsplit('.', 1)[-1].lower()
        if ext not in ALLOWED:
            flash('Chỉ chấp nhận PNG, JPG, GIF, WEBP.', 'danger')
            return redirect(url_for('student.profile'))

        # Đọc toàn bộ file vào memory trước
        file_data = file.read()
        if len(file_data) > 5 * 1024 * 1024:
            flash('File quá lớn (tối đa 5MB).', 'danger')
            return redirect(url_for('student.profile'))
        if len(file_data) == 0:
            flash('File trống, vui lòng chọn lại.', 'danger')
            return redirect(url_for('student.profile'))

        # Tạo thư mục và lưu file
        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'avatars')
        os.makedirs(upload_dir, exist_ok=True)
        filename = f'user_{current_user.id}.{ext}'
        save_path = os.path.join(upload_dir, filename)
        with open(save_path, 'wb') as fp:
            fp.write(file_data)

        user = User.query.get(current_user.id)
        user.avatar = filename
        db.session.commit()
        flash('Cập nhật ảnh đại diện thành công!', 'success')
        return redirect(url_for('student.profile'))

    except Exception as e:
        db.session.rollback()
        flash(f'Lỗi khi tải ảnh lên: {str(e)}', 'danger')
        return redirect(url_for('student.profile'))


# ── Liên hệ giảng viên ────────────────────────────────────────
@student_bp.route('/contact-lecturer/<int:lecturer_id>')
@login_required
@student_required
def contact_lecturer(lecturer_id):
    from models.user import User
    from models.class_model import Class
    lect = User.query.filter_by(id=lecturer_id, role='lecturer').first_or_404()
    # Chỉ cho xem GV của lớp sinh viên đang học
    my_class_ids = [e.class_id for e in current_user.enrollments if e.status == 'enrolled']
    teaches_me   = Class.query.filter(
        Class.lecturer_id == lecturer_id,
        Class.id.in_(my_class_ids)
    ).all()
    return render_template('student/contact_lecturer.html',
        lect=lect, teaches_me=teaches_me)


# ── Danh sách giảng viên có thể liên hệ ─────────────────────
@student_bp.route('/contact-lecturers')
@login_required
@student_required
def contact_lecturers_list():
    from models.user import User as UModel
    # Lấy GV của các lớp sinh viên đang học
    my_enrollments = [e for e in current_user.enrollments if e.status == 'enrolled']
    lect_ids = set()
    classes_by_lect = {}
    for enroll in my_enrollments:
        cls = enroll.class_ref
        if cls and cls.lecturer_id:
            lect_ids.add(cls.lecturer_id)
            classes_by_lect.setdefault(cls.lecturer_id, []).append(cls)

    lecturers = UModel.query.filter(UModel.id.in_(lect_ids)).all() if lect_ids else []
    return render_template('student/contact_lecturers_list.html',
        lecturers=lecturers, classes_by_lect=classes_by_lect)


# ═══════════════════════════════════════════════════════════════════
# ĐĂNG KÝ TÍN CHỈ (SINH VIÊN)
# - Chỉ thao tác được khi Admin MỞ đăng ký tín chỉ
# - Học từ Thứ 2 → Thứ 6
# - Tối thiểu 3 môn, tối đa 7 môn (trung bình ~2 tín chỉ/môn)
# - Không học trùng lặp môn (course_code) trong cùng 1 học kỳ
# - Không trùng lịch học (Thứ & Tiết) giữa các môn đã đăng ký
# ═══════════════════════════════════════════════════════════════════

@student_bp.route('/registration')
@login_required
@student_required
def credit_registration():
    from utils.timetable import get_current_semester_id, format_semester_label, schedules_conflict, WEEKDAY_LABELS
    sid = current_user.id

    open_cfgs = RegistrationConfig.query.filter_by(is_open=True).all()
    active_cfg = next((c for c in open_cfgs if c.is_active_now), None)
    if active_cfg:
        reg_cfg = active_cfg
        target_sem = active_cfg.semester
    elif open_cfgs:
        reg_cfg = open_cfgs[0]
        target_sem = reg_cfg.semester
    else:
        target_sem = get_current_semester_id()
        reg_cfg = RegistrationConfig.query.filter_by(semester=target_sem).first()

    min_courses = reg_cfg.min_courses if reg_cfg else 3
    max_courses = reg_cfg.max_courses if reg_cfg else 7
    is_open     = bool(reg_cfg and reg_cfg.is_active_now)

    # Các lớp sinh viên đã đăng ký trong học kỳ này
    my_enrolled = (
        db.session.query(Enrollment, Class)
        .join(Class, Class.id == Enrollment.class_id)
        .filter(
            Enrollment.student_id == sid,
            Enrollment.status == 'enrolled',
            Class.semester == target_sem,
            Class.status == 'active',
        )
        .order_by(Class.course_code)
        .all()
    )
    my_classes      = [cls for _, cls in my_enrolled]
    my_class_ids    = {cls.id for cls in my_classes}
    my_course_codes = {cls.course_code for cls in my_classes if cls.course_code}
    total_credits   = sum(int((c.schedule_info or {}).get('credits', 2)) for c in my_classes)

    # Tất cả lớp học phần Admin đang mở trong kỳ (chỉ lấy các lớp học Thứ 2 -> Thứ 6)
    all_open_classes = (
        Class.query
        .filter_by(semester=target_sem, status='active')
        .order_by(Class.course_code, Class.class_name)
        .all()
    )

    available_rows = []
    for cls in all_open_classes:
        info = cls.schedule_info or {}
        day_val = info.get('day')
        if day_val is not None and int(day_val) > 4:
            continue  # Chỉ hiển thị các lớp chính khóa T2->T6

        cnt = Enrollment.query.filter_by(class_id=cls.id, status='enrolled').count()
        _, thu_tiet = _format_class_schedule(cls)
        credits = int(info.get('credits', 2))

        conflict_reason = None
        if cls.id in my_class_ids:
            state = 'enrolled'
        elif cls.course_code and cls.course_code in my_course_codes:
            state = 'same_course'
            conflict_reason = f'Đã đăng ký môn {cls.course_code}'
        elif cnt >= (cls.max_students or 60):
            state = 'full'
            conflict_reason = 'Đã hết chỗ'
        else:
            clashed = next((mc for mc in my_classes if schedules_conflict(info, mc.schedule_info)), None)
            if clashed:
                state = 'time_conflict'
                conflict_reason = f'Trùng lịch với {clashed.class_name}'
            elif len(my_classes) >= max_courses:
                state = 'max_reached'
                conflict_reason = f'Đã đạt tối đa {max_courses} môn'
            else:
                state = 'available'

        available_rows.append({
            'cls': cls,
            'enrolled_count': cnt,
            'credits': credits,
            'thu_tiet': thu_tiet,
            'state': state,
            'conflict_reason': conflict_reason,
        })

    return render_template(
        'student/registration.html',
        target_sem=target_sem,
        sem_label=format_semester_label(target_sem),
        is_open=is_open,
        reg_cfg=reg_cfg,
        min_courses=min_courses,
        max_courses=max_courses,
        my_classes=my_classes,
        total_credits=total_credits,
        available_rows=available_rows,
        format_sched=_format_class_schedule,
    )


@student_bp.route('/registration/enroll/<int:class_id>', methods=['POST'])
@login_required
@student_required
def enroll_credit_class(class_id):
    from utils.timetable import schedules_conflict
    sid = current_user.id
    cls = Class.query.get_or_404(class_id)

    cfg = RegistrationConfig.query.filter_by(semester=cls.semester).first()
    if not cfg or not cfg.is_active_now:
        reason = cfg.status_reason if cfg else 'Phòng Đào tạo (Admin) chưa mở đợt đăng ký tín chỉ cho học kỳ này.'
        flash(f'🔒 Không thể đăng ký: {reason}', 'warning')
        return redirect(url_for('student.credit_registration'))

    if cls.status != 'active':
        flash('Lớp học phần này không còn mở đăng ký.', 'danger')
        return redirect(url_for('student.credit_registration'))

    info = cls.schedule_info or {}
    if info.get('day') is not None and int(info.get('day')) > 4:
        flash('Chỉ được đăng ký các lớp học phần diễn ra từ Thứ 2 đến Thứ 6.', 'danger')
        return redirect(url_for('student.credit_registration'))

    my_classes = (
        db.session.query(Class)
        .join(Enrollment, Enrollment.class_id == Class.id)
        .filter(
            Enrollment.student_id == sid,
            Enrollment.status == 'enrolled',
            Class.semester == cls.semester,
            Class.status == 'active',
        )
        .all()
    )

    if any(c.id == cls.id for c in my_classes):
        flash(f'Bạn đã đăng ký lớp {cls.class_name} rồi.', 'info')
        return redirect(url_for('student.credit_registration'))

    if len(my_classes) >= cfg.max_courses:
        flash(f'Bạn chỉ được đăng ký tối đa {cfg.max_courses} môn trong một học kỳ.', 'danger')
        return redirect(url_for('student.credit_registration'))

    if cls.course_code and any(c.course_code == cls.course_code for c in my_classes):
        flash(f'Không được học trùng lặp môn {cls.course_name} ({cls.course_code}) trong cùng học kỳ.', 'danger')
        return redirect(url_for('student.credit_registration'))

    for c in my_classes:
        if schedules_conflict(info, c.schedule_info):
            flash(
                f'❌ Trùng lịch học với lớp {c.class_name} ({c.course_name}). Vui lòng chọn nhóm lớp khác!',
                'danger',
            )
            return redirect(url_for('student.credit_registration'))

    cur_cnt = Enrollment.query.filter_by(class_id=cls.id, status='enrolled').count()
    if cur_cnt >= (cls.max_students or 60):
        flash(f'Lớp {cls.class_name} đã đủ sĩ số tối đa ({cls.max_students} SV).', 'danger')
        return redirect(url_for('student.credit_registration'))

    existing_rec = Enrollment.query.filter_by(student_id=sid, class_id=cls.id).first()
    if existing_rec:
        existing_rec.status = 'enrolled'
    else:
        db.session.add(Enrollment(student_id=sid, class_id=cls.id, enrolled_by=sid, status='enrolled'))

    db.session.commit()
    new_total = len(my_classes) + 1
    if new_total < cfg.min_courses:
        flash(
            f'✅ Đã đăng ký {cls.course_name} ({cls.class_name}). '
            f'Lưu ý: Bạn mới đăng ký {new_total}/{cfg.min_courses} môn tối thiểu.',
            'warning',
        )
    else:
        flash(f'✅ Đăng ký thành công học phần {cls.course_name} ({cls.class_name})!', 'success')
    return redirect(url_for('student.credit_registration'))


@student_bp.route('/registration/drop/<int:class_id>', methods=['POST'])
@login_required
@student_required
def drop_credit_class(class_id):
    sid = current_user.id
    cls = Class.query.get_or_404(class_id)

    cfg = RegistrationConfig.query.filter_by(semester=cls.semester).first()
    if not cfg or not cfg.is_active_now:
        reason = cfg.status_reason if cfg else 'Cổng đăng ký tín chỉ đang đóng.'
        flash(f'🔒 Không thể hủy học phần: {reason}', 'warning')
        return redirect(url_for('student.credit_registration'))

    enroll = Enrollment.query.filter_by(student_id=sid, class_id=cls.id, status='enrolled').first()
    if not enroll:
        flash('Bạn chưa đăng ký lớp học phần này.', 'warning')
        return redirect(url_for('student.credit_registration'))

    active_cnt = (
        db.session.query(Enrollment.id)
        .join(Class, Class.id == Enrollment.class_id)
        .filter(
            Enrollment.student_id == sid,
            Enrollment.status == 'enrolled',
            Class.semester == cls.semester,
            Class.status == 'active',
        )
        .count()
    )
    if active_cnt <= cfg.min_courses:
        flash(
            f'⚠️ Không thể hủy thêm: Mỗi sinh viên phải duy trì tối thiểu {cfg.min_courses} môn học trong học kỳ '
            f'(Hãy đăng ký môn thay thế trước khi hủy môn này).',
            'warning',
        )
        return redirect(url_for('student.credit_registration'))

    enroll.status = 'dropped'
    db.session.commit()
    flash(f'Đã hủy đăng ký lớp {cls.class_name} ({cls.course_name}).', 'info')
    return redirect(url_for('student.credit_registration'))
