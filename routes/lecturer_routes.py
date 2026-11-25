from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import date, timedelta
from extensions import db
from models.class_model  import Class
from models.enrollment   import Enrollment
from models.session      import Session
from models.attendance   import Attendance
from models.user         import User
from utils.decorators    import lecturer_required

lecturer_bp = Blueprint('lecturer', __name__, url_prefix='/lecturer')


def _format_lecturer_sched(cls):
    DAYS_SHORT = ['Hai', 'Ba', 'Tư', 'Năm', 'Sáu', 'Bảy', 'CN']
    info = cls.schedule_info or {}
    if isinstance(info, dict) and 'day' in info:
        d_idx = int(info.get('day', 0))
        t_st  = int(info.get('tiet_start', 1))
        n_t   = int(info.get('num_tiet', 2))
        t_end = min(10, t_st + n_t - 1)
        d_str = DAYS_SHORT[d_idx] if 0 <= d_idx < len(DAYS_SHORT) else '?'
        return f"{d_str} / {t_st}→{t_end}"
    return "—"


@lecturer_bp.route('/dashboard')
@lecturer_bp.route('/schedule/detail')
@login_required
@lecturer_required
def dashboard():
    from utils.timetable import TIET_MAP, tiet_span, get_all_semesters, get_current_semester_id, resolve_viewing_week, format_class_weeks_range
    today = date.today()
    cur_sem_id = get_current_semester_id(today)
    selected_sem = request.args.get('semester', '').strip()

    # ── Lớp đang phụ trách ───────────────────────────────────────────────────
    if selected_sem:
        classes = Class.query.filter_by(
            lecturer_id=current_user.id, semester=selected_sem
        ).all()
    else:
        cur_classes = Class.query.filter_by(lecturer_id=current_user.id, semester=cur_sem_id).all()
        if cur_classes:
            classes = cur_classes
            selected_sem = cur_sem_id
        else:
            classes = Class.query.filter_by(
                lecturer_id=current_user.id, status='active'
            ).all()
            selected_sem = classes[0].semester if classes else cur_sem_id

    sem_num, sem_years = '2', '2025 - 2026'
    if selected_sem and '-' in selected_sem:
        hk_p, yr_p = selected_sem.split('-', 1)
        sem_num = '1' if hk_p == 'HK1' else '2'
        if yr_p.isdigit():
            sem_years = f"{yr_p} - {int(yr_p) + 1}"

    class_counts = {
        c.id: Enrollment.query.filter_by(class_id=c.id, status='enrolled').count()
        for c in classes
    }
    total_students = sum(class_counts.values())

    # ── Buổi học hôm nay ─────────────────────────────────────────────────────
    sessions_today = []
    today_class_ids = set()
    for cls in classes:
        for sess in Session.query.filter_by(class_id=cls.id, session_date=today).filter(Session.status != 'cancelled').all():
            present = Attendance.query.filter_by(
                class_id=cls.id, session_date=today, status='present'
            ).count()
            sessions_today.append((sess, cls, present, class_counts.get(cls.id, 0), format_class_weeks_range(cls), _format_lecturer_sched(cls)))
            today_class_ids.add(cls.id)
    sessions_today.sort(key=lambda x: x[0].start_time)
    total_present = sum(x[2] for x in sessions_today)

    # ── Lớp dạy các ngày khác trong tuần ─────────────────────────────────────
    other_classes_rows = []
    for cls in classes:
        if cls.id in today_class_ids:
            continue
        other_classes_rows.append({
            'cls': cls,
            'enrolled': class_counts.get(cls.id, 0),
            'weeks': format_class_weeks_range(cls),
            'room': cls.room or '—',
            'thu_tiet': _format_lecturer_sched(cls),
        })

    # ── Timetable tuần (luôn bắt đầu vào tuần đang học) ──────────────────────
    week_start, week_end, week_offset, week_num = resolve_viewing_week(
        selected_sem, request.args.get('week'), today
    )

    sess_q = (
        db.session.query(Session, Class)
        .join(Class, Class.id == Session.class_id)
        .filter(
            Class.lecturer_id == current_user.id,
            Session.session_date >= week_start,
            Session.session_date <= week_end,
            Session.status != 'cancelled',
        )
    )
    if selected_sem:
        sess_q = sess_q.filter(Class.semester == selected_sem)

    week_sessions = sess_q.order_by(Session.session_date, Session.start_time).all()

    timetable = {}
    occupied  = set()
    for sess, cls in week_sessions:
        day_idx = sess.session_date.weekday()
        if day_idx >= 6:
            continue
        t_start, span = tiet_span(sess.start_time, sess.end_time)
        if (day_idx, t_start) not in occupied:
            timetable[(day_idx, t_start)] = (sess, cls, span)
        for t in range(t_start, t_start + span):
            occupied.add((day_idx, t))

    all_semesters = get_all_semesters()

    return render_template('lecturer/dashboard.html',
        classes            = classes,
        other_classes_rows = other_classes_rows,
        selected_sem       = selected_sem,
        sem_num            = sem_num,
        sem_years          = sem_years,
        total_students     = total_students,
        class_counts       = class_counts,
        sessions_today     = sessions_today,
        total_present      = total_present,
        today              = today,
        timetable          = timetable,
        occupied           = occupied,
        tiet_map           = TIET_MAP,
        week_start         = week_start,
        week_end           = week_end,
        week_offset        = week_offset,
        week_num           = week_num,
        all_semesters      = all_semesters,
    )


@lecturer_bp.route('/schedule')
@login_required
@lecturer_required
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
    today = date.today()
    all_semesters = get_all_semesters()
    cur_sem_id    = get_current_semester_id(today)
    selected_sem  = request.args.get('semester', '').strip()
    view_mode     = request.args.get('view', '').strip()
    if view_mode == 'detail':
        return redirect(url_for('lecturer.dashboard', semester=selected_sem) if selected_sem else url_for('lecturer.dashboard'))
    is_expanded   = (view_mode == 'expanded')

    if not selected_sem:
        has_cur = Class.query.filter_by(lecturer_id=current_user.id, semester=cur_sem_id).first()
        if has_cur:
            selected_sem = cur_sem_id
        else:
            active_cls = Class.query.filter_by(lecturer_id=current_user.id, status='active').first()
            selected_sem = active_cls.semester if active_cls else cur_sem_id

    # Luôn mở vào đúng tuần đang học
    week_start, week_end, week_offset, week_num = resolve_viewing_week(
        selected_sem, request.args.get('week'), today
    )

    week_sessions = (
        db.session.query(Session, Class)
        .join(Class, Class.id == Session.class_id)
        .filter(
            Class.lecturer_id == current_user.id,
            Class.semester == selected_sem,
            Session.session_date >= week_start,
            Session.session_date <= week_end,
            Session.status != 'cancelled',
        )
        .order_by(Session.session_date, Session.start_time)
        .all()
    )

    timetable = {}
    occupied  = set()
    for sess, cls in week_sessions:
        day_idx = sess.session_date.weekday()
        if day_idx >= 6:
            continue
        t_start, span = tiet_span(sess.start_time, sess.end_time)
        if (day_idx, t_start) not in occupied:
            timetable[(day_idx, t_start)] = (sess, cls, span)
        for t in range(t_start, t_start + span):
            occupied.add((day_idx, t))

    all_weeks_data = []
    if is_expanded:
        all_sem_sessions = (
            db.session.query(Session, Class)
            .join(Class, Class.id == Session.class_id)
            .filter(
                Class.lecturer_id == current_user.id,
                Class.semester == selected_sem,
            )
            .order_by(Session.session_date, Session.start_time)
            .all()
        )
        all_weeks_data = build_semester_weeks_timetables(selected_sem, all_sem_sessions)

    week_cancelled = (
        db.session.query(Session, Class)
        .join(Class, Class.id == Session.class_id)
        .filter(
            Class.lecturer_id == current_user.id,
            Class.semester == selected_sem,
            Session.session_date >= week_start,
            Session.session_date <= week_end,
            Session.status == 'cancelled',
        )
        .order_by(Session.session_date, Session.start_time)
        .all()
    )

    all_classes = Class.query.filter_by(lecturer_id=current_user.id, semester=selected_sem).all()

    return render_template('lecturer/schedule.html',
        timetable=timetable,
        occupied=occupied,
        tiet_map=TIET_MAP,
        week_start=week_start,
        week_end=week_end,
        week_offset=week_offset,
        week_num=week_num,
        today=today,
        all_semesters=all_semesters,
        selected_semester=selected_sem,
        sem_heading=format_semester_heading(selected_sem),
        is_expanded=is_expanded,
        all_weeks_data=all_weeks_data,
        week_cancelled=week_cancelled,
        all_classes=all_classes,
    )


@lecturer_bp.route('/schedule/all-courses')
@login_required
@lecturer_required
def all_courses_schedule():
    """Trang 'THỜI KHÓA BIỂU - DANH SÁCH LỚP HỌC PHẦN' dành cho Giảng viên tra cứu toàn trường."""
    from sqlalchemy import func
    from utils.timetable import (
        get_current_semester_id,
        format_class_weeks_csv,
        format_full_tkb_slot,
    )

    cur_sem = get_current_semester_id()
    def_hk, def_yr = (cur_sem.split('-', 1) + ['2026'])[:2]

    sem_arg = request.args.get('semester', '').strip()
    if sem_arg and '-' in sem_arg:
        hk_default, yr_default = sem_arg.split('-', 1)
    else:
        hk_default, yr_default = def_hk, def_yr

    hk          = request.args.get('hk', hk_default).strip().upper()
    year        = request.args.get('year', yr_default).strip()
    day_filter  = request.args.get('day', '').strip()
    scope       = request.args.get('scope', 'all').strip()
    lecturer_q  = request.args.get('lecturer_q', '').strip()
    course_q    = request.args.get('course_q', '').strip()

    if hk not in ('HK1', 'HK2'):
        hk = def_hk
    if not year.isdigit():
        year = def_yr
    target_sem = f"{hk}-{year}"

    today_yr = date.today().year
    academic_years = [str(y) for y in range(today_yr, 2022, -1)]

    query = (
        db.session.query(Class, User)
        .outerjoin(User, User.id == Class.lecturer_id)
        .filter(Class.semester == target_sem, Class.status != 'cancelled')
    )
    if scope == 'mine':
        query = query.filter(Class.lecturer_id == current_user.id)
    if lecturer_q:
        query = query.filter(User.full_name.ilike(f"%{lecturer_q}%"))
    if course_q:
        like_c = f"%{course_q}%"
        query = query.filter((Class.course_name.ilike(like_c)) | (Class.class_name.ilike(like_c)) | (Class.course_code.ilike(like_c)))

    raw_items = query.order_by(Class.course_name, Class.class_name).all()

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
        'lecturer/schedule_all_courses.html',
        rows=rows,
        hk=hk,
        year=year,
        selected_sem=target_sem,
        day_filter=day_filter,
        scope=scope,
        lecturer_q=lecturer_q,
        course_q=course_q,
        academic_years=academic_years,
    )


@lecturer_bp.route('/classes')
@login_required
@lecturer_required
def class_list():
    classes    = Class.query.filter_by(lecturer_id=current_user.id)\
        .order_by(Class.created_at.desc()).all()
    class_data = [
        (c, Enrollment.query.filter_by(class_id=c.id, status='enrolled').count())
        for c in classes
    ]
    return render_template('lecturer/class_list.html', class_data=class_data)


@lecturer_bp.route('/classes/<int:class_id>/students')
@login_required
@lecturer_required
def class_students(class_id):
    from services.email_service import is_smtp_configured
    cls = Class.query.filter_by(id=class_id, lecturer_id=current_user.id).first_or_404()
    enrollments = (
        db.session.query(Enrollment, User)
        .join(User, User.id == Enrollment.student_id)
        .filter(Enrollment.class_id == class_id, Enrollment.status == 'enrolled')
        .order_by(User.full_name)
        .all()
    )
    student_emails = [stu.email.strip() for _, stu in enrollments if stu.email and '@' in stu.email]
    upcoming_sessions = (
        Session.query
        .filter(Session.class_id == class_id, Session.status == 'scheduled')
        .order_by(Session.session_date)
        .limit(12)
        .all()
    )
    return render_template(
        'lecturer/class_students.html',
        cls=cls,
        enrollments=enrollments,
        student_emails=student_emails,
        upcoming_sessions=upcoming_sessions,
        smtp_ready=is_smtp_configured(),
    )


@lecturer_bp.route('/classes/<int:class_id>/send-email', methods=['POST'])
@login_required
@lecturer_required
def send_class_email(class_id):
    """
    Giảng viên gửi Email & Thông báo học vụ đến TẤT CẢ sinh viên đang theo học trong lớp học phần.
    """
    from models.notification import Notification
    from models.audit_log import AuditLog
    from services.email_service import send_class_bulk_email

    cls = Class.query.filter_by(id=class_id, lecturer_id=current_user.id).first_or_404()
    subject      = request.form.get('subject', '').strip()
    message_body = request.form.get('message', '').strip()
    cancel_sess_id = request.form.get('cancel_session_id', type=int)

    if not subject or not message_body:
        flash('Vui lòng nhập đầy đủ Tiêu đề và Nội dung email gửi sinh viên.', 'danger')
        return redirect(url_for('lecturer.class_students', class_id=class_id))

    enrollments = (
        db.session.query(Enrollment, User)
        .join(User, User.id == Enrollment.student_id)
        .filter(Enrollment.class_id == class_id, Enrollment.status == 'enrolled')
        .all()
    )
    if not enrollments:
        flash('Lớp học phần hiện chưa có sinh viên nào đăng ký để nhận thông báo.', 'warning')
        return redirect(url_for('lecturer.class_students', class_id=class_id))

    # Tùy chọn: Nếu giảng viên chọn kèm "Báo nghỉ buổi học" -> đánh dấu Session = cancelled để hiện lên TKB!
    cancelled_info_str = ''
    if cancel_sess_id:
        sess_obj = Session.query.filter_by(id=cancel_sess_id, class_id=cls.id).first()
        if sess_obj:
            sess_obj.status = 'cancelled'
            cancelled_info_str = f" (Đã cập nhật Báo nghỉ ngày {sess_obj.session_date.strftime('%d/%m/%Y')} lên Thời khóa biểu)"

    # 1. Lưu đồng thời vào Hộp thư Thông báo học vụ trên hệ thống cho 100% sinh viên trong lớp
    notif_title = f"✉️ [{cls.class_name}] {subject}"
    notif_body  = f"Giảng viên {current_user.full_name} gửi lớp {cls.course_name} ({cls.class_name}):\n{message_body}"
    recipient_emails = []

    for _, student in enrollments:
        if student.email and '@' in student.email:
            recipient_emails.append(student.email.strip())
        db.session.add(Notification(
            user_id=student.id,
            title=notif_title,
            content=notif_body,
            related_type='schedule' if cancel_sess_id else 'class_email',
            related_id=cls.id,
        ))

    # 2. Gửi Email thực qua SMTP tới toàn bộ địa chỉ email của sinh viên trong lớp
    smtp_ok, sent_cnt, smtp_msg = send_class_bulk_email(
        lecturer_name=current_user.full_name,
        lecturer_email=current_user.email,
        cls_name=cls.class_name,
        course_name=cls.course_name,
        subject=subject,
        body_text=message_body,
        recipient_emails=recipient_emails,
    )

    db.session.add(AuditLog(
        actor_id=current_user.id,
        action_type='class_email_send',
        target_type='class',
        target_id=cls.id,
        new_value={
            'class_name': cls.class_name,
            'subject': subject,
            'students_count': len(enrollments),
            'emails_count': len(recipient_emails),
            'smtp_sent': smtp_ok,
        },
        ip_address=request.remote_addr,
    ))
    db.session.commit()

    if smtp_ok:
        flash(
            f'✅ Đã gửi Email thành công đến {sent_cnt} sinh viên và thông báo cho toàn bộ {len(enrollments)} SV lớp {cls.class_name}!{cancelled_info_str}',
            'success',
        )
    else:
        flash(
            f'📨 Đã gửi thông báo đến toàn bộ {len(enrollments)} sinh viên lớp {cls.class_name}{cancelled_info_str}. Lưu ý Email ngoài: {smtp_msg}',
            'info',
        )
    return redirect(url_for('lecturer.class_students', class_id=class_id))


@lecturer_bp.route('/classes/<int:class_id>/students/add', methods=['POST'])
@login_required
@lecturer_required
def add_student(class_id):
    cls     = Class.query.filter_by(id=class_id, lecturer_id=current_user.id).first_or_404()
    ident   = request.form.get('identifier', '').strip()
    student = User.query.filter(
        (User.student_code == ident.upper()) | (User.username == ident),
        User.role == 'student',
    ).first()

    if not student:
        flash('Không tìm thấy sinh viên.', 'danger')
        return redirect(url_for('lecturer.class_students', class_id=class_id))

    existing = Enrollment.query.filter_by(student_id=student.id, class_id=class_id).first()
    if existing:
        if existing.status == 'enrolled':
            flash(f'{student.full_name} đã có trong lớp.', 'warning')
        else:
            existing.status = 'enrolled'
            db.session.commit()
            flash(f'Đã thêm lại {student.full_name}.', 'success')
        return redirect(url_for('lecturer.class_students', class_id=class_id))

    from models.notification import Notification
    db.session.add(Enrollment(
        student_id=student.id, class_id=class_id, enrolled_by=current_user.id,
    ))
    db.session.add(Notification(
        user_id      = student.id,
        title        = 'Bạn đã được thêm vào lớp học',
        content      = f'Bạn được thêm vào lớp {cls.class_name} — {cls.course_name}.',
        related_type = 'enrollment',
        related_id   = class_id,
    ))
    db.session.commit()
    flash(f'Đã thêm {student.full_name} vào lớp.', 'success')
    return redirect(url_for('lecturer.class_students', class_id=class_id))


@lecturer_bp.route('/classes/<int:class_id>/students/<int:student_id>/remove', methods=['POST'])
@login_required
@lecturer_required
def remove_student(class_id, student_id):
    cls     = Class.query.filter_by(id=class_id, lecturer_id=current_user.id).first_or_404()
    enroll  = Enrollment.query.filter_by(student_id=student_id, class_id=class_id).first_or_404()
    student = User.query.get(student_id)

    from models.notification import Notification
    enroll.status = 'dropped'
    db.session.add(Notification(
        user_id      = student_id,
        title        = 'Bạn đã bị xóa khỏi lớp học',
        content      = f'Bạn bị xóa khỏi lớp {cls.class_name} — {cls.course_name}.',
        related_type = 'enrollment',
        related_id   = class_id,
    ))
    db.session.commit()
    flash(f'Đã xóa {student.full_name} khỏi lớp.', 'success')
    return redirect(url_for('lecturer.class_students', class_id=class_id))


@lecturer_bp.route('/classes/<int:class_id>/grades')
@login_required
@lecturer_required
def class_grades(class_id):
    cls = Class.query.filter_by(id=class_id, lecturer_id=current_user.id).first_or_404()
    enrollments = (
        db.session.query(Enrollment, User)
        .join(User, User.id == Enrollment.student_id)
        .filter(Enrollment.class_id == class_id, Enrollment.status == 'enrolled')
        .order_by(User.full_name)
        .all()
    )
    from models.grade import Grade
    grades_map = {g.student_id: g for g in Grade.query.filter_by(class_id=class_id).all()}
    return render_template('lecturer/class_grades.html',
        cls=cls, enrollments=enrollments, grades_map=grades_map,
    )


@lecturer_bp.route('/classes/<int:class_id>/grades/save', methods=['POST'])
@login_required
@lecturer_required
def save_grade(class_id):
    cls = Class.query.filter_by(id=class_id, lecturer_id=current_user.id).first_or_404()
    from models.grade        import Grade
    from models.notification import Notification
    from models.audit_log    import AuditLog

    student_id = request.form.get('student_id', type=int)
    att = request.form.get('attendance_score', type=float)
    asg = request.form.get('assignment',       type=float)
    mid = request.form.get('midterm',          type=float)
    fin = request.form.get('final',            type=float)

    if not student_id:
        return jsonify({'ok': False, 'msg': 'Thiếu student_id'}), 400
    if fin is None:
        return jsonify({'ok': False, 'msg': 'Điểm cuối kỳ bắt buộc'}), 400
    if not Enrollment.query.filter_by(
        student_id=student_id, class_id=class_id, status='enrolled'
    ).first():
        return jsonify({'ok': False, 'msg': 'Sinh viên không thuộc lớp này'}), 403

    grade   = Grade.query.filter_by(student_id=student_id, class_id=class_id).first()
    old_val = None

    if grade:
        old_val = {
            'attendance': float(grade.attendance_score or 0),
            'assignment': float(grade.assignment or 0),
            'midterm':    float(grade.midterm or 0),
            'final':      float(grade.final or 0),
            'total':      float(grade.total or 0),
        }
        grade.attendance_score = att
        grade.assignment       = asg
        grade.midterm          = mid
        grade.final            = fin
        grade.updated_by       = current_user.id
    else:
        grade = Grade(
            student_id=student_id, class_id=class_id,
            attendance_score=att, assignment=asg,
            midterm=mid, final=fin, updated_by=current_user.id,
        )
        db.session.add(grade)

    grade.calc_total(cls.formula_config)
    db.session.flush()

    new_val = {
        'attendance': float(grade.attendance_score or 0),
        'assignment': float(grade.assignment or 0),
        'midterm':    float(grade.midterm or 0),
        'final':      float(grade.final or 0),
        'total':      float(grade.total or 0),
    }
    db.session.add(AuditLog(
        actor_id    = current_user.id,
        action_type = 'grade_update',
        target_type = 'grade',
        target_id   = grade.id,
        old_value   = old_val,
        new_value   = new_val,
    ))
    db.session.add(Notification(
        user_id      = student_id,
        title        = f'Điểm môn {cls.course_name} đã được cập nhật',
        content      = (f'CC:{att or "—"} BT:{asg or "—"} '
                        f'GK:{mid or "—"} CK:{fin} '
                        f'→ Tổng:{grade.total} ({grade.grade_letter})'),
        related_type = 'grade',
        related_id   = class_id,
    ))
    db.session.commit()
    return jsonify({
        'ok':          True,
        'total':       float(grade.total) if grade.total else None,
        'grade_letter': grade.grade_letter,
    })


@lecturer_bp.route('/classes/<int:class_id>/formula', methods=['POST'])
@login_required
@lecturer_required
def save_formula(class_id):
    cls = Class.query.filter_by(id=class_id, lecturer_id=current_user.id).first_or_404()
    try:
        att = float(request.form.get('w_attendance', 0))
        asg = float(request.form.get('w_assignment', 0))
        mid = float(request.form.get('w_midterm',    0))
        fin = float(request.form.get('w_final',      0))
        if abs(att + asg + mid + fin - 1.0) > 0.01:
            return jsonify({
                'ok':  False,
                'msg': f'Tổng phải = 100% (hiện: {(att+asg+mid+fin)*100:.0f}%)',
            }), 400
        cls.formula_config = {
            'attendance': att, 'assignment': asg,
            'midterm':    mid, 'final':      fin,
        }
        db.session.commit()
        return jsonify({'ok': True, 'msg': 'Đã lưu công thức!'})
    except Exception as e:
        return jsonify({'ok': False, 'msg': str(e)}), 400


@lecturer_bp.route('/classes/<int:class_id>/grades/<int:student_id>/delete', methods=['POST'])
@login_required
@lecturer_required
def delete_grade(class_id, student_id):
    Class.query.filter_by(id=class_id, lecturer_id=current_user.id).first_or_404()
    from models.grade     import Grade
    from models.audit_log import AuditLog

    grade = Grade.query.filter_by(student_id=student_id, class_id=class_id).first_or_404()
    db.session.add(AuditLog(
        actor_id    = current_user.id,
        action_type = 'grade_delete',
        target_type = 'grade',
        target_id   = grade.id,
        old_value   = {'total': float(grade.total or 0)},
        new_value   = None,
    ))
    db.session.delete(grade)
    db.session.commit()
    flash('Đã xóa điểm.', 'success')
    return redirect(url_for('lecturer.class_grades', class_id=class_id))


@lecturer_bp.route('/audit')
@login_required
@lecturer_required
def audit_logs():
    from models.audit_log import AuditLog
    logs = AuditLog.query.filter_by(actor_id=current_user.id)\
        .order_by(AuditLog.created_at.desc()).limit(100).all()
    return render_template('lecturer/audit_logs.html', logs=logs)


@lecturer_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@lecturer_required
def profile():
    user = User.query.get(current_user.id)
    if request.method == 'POST':
        phone  = request.form.get('phone',            '').strip()
        email  = request.form.get('email',            '').strip()
        bio    = request.form.get('bio',              '').strip()
        new_pw = request.form.get('new_password',     '')
        con_pw = request.form.get('confirm_password', '')

        if phone: user.phone = phone
        if email: user.email = email
        user.bio = bio

        if new_pw:
            if new_pw != con_pw:
                flash('Mật khẩu xác nhận không khớp.', 'danger')
                return redirect(url_for('lecturer.profile'))
            if len(new_pw) < 6:
                flash('Mật khẩu phải ít nhất 6 ký tự.', 'danger')
                return redirect(url_for('lecturer.profile'))
            user.set_password(new_pw)

        db.session.commit()
        flash('Cập nhật thành công!', 'success')
        return redirect(url_for('lecturer.profile'))

    return render_template('lecturer/profile.html',
        user        = user,
        class_count = Class.query.filter_by(lecturer_id=user.id).count(),
    )


@lecturer_bp.route('/public/<int:lecturer_id>')
@login_required
def lecturer_public(lecturer_id):
    lect    = User.query.filter_by(id=lecturer_id, role='lecturer').first_or_404()
    classes = Class.query.filter_by(lecturer_id=lecturer_id, status='active').all()
    return render_template('lecturer/public_profile.html', lect=lect, classes=classes)