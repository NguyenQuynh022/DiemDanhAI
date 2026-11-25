from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from extensions import db
from models.user                import User
from models.class_model         import Class
from models.enrollment          import Enrollment
from models.session             import Session
from models.announcement        import Announcement
from models.notification        import Notification
from models.audit_log           import AuditLog
from models.registration_config import RegistrationConfig
from utils.decorators           import admin_required
from utils.timetable            import (
    get_all_semesters,
    get_current_semester_id,
    get_semester_bounds,
    schedules_conflict,
    generate_sessions_for_class,
    WEEKDAY_LABELS,
)
from utils.student_code  import (
    MAJOR_OPTIONS,
    COHORT_OPTIONS,
    normalize_student_code,
    validate_student_code,
    generate_next_student_code,
)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# ═══════════════════════════════════════════════════════════════════
# 1. DASHBOARD QUẢN TRỊ VIÊN
# ═══════════════════════════════════════════════════════════════════

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    total_students  = User.query.filter_by(role='student').count()
    total_lecturers = User.query.filter_by(role='lecturer').count()
    locked_users    = User.query.filter(User.status != 'active').count()
    total_classes   = Class.query.count()
    total_anns      = Announcement.query.count()

    recent_users = (
        User.query.filter(User.role.in_(['student', 'lecturer']))
        .order_by(User.created_at.desc())
        .limit(8)
        .all()
    )
    recent_anns = (
        Announcement.query
        .order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
        .limit(8)
        .all()
    )

    return render_template(
        'admin/dashboard.html',
        total_students=total_students,
        total_lecturers=total_lecturers,
        locked_users=locked_users,
        total_classes=total_classes,
        total_anns=total_anns,
        recent_users=recent_users,
        recent_anns=recent_anns,
    )


# ═══════════════════════════════════════════════════════════════════
# 2. QUẢN LÝ & CẤP TÀI KHOẢN + MÃ SINH VIÊN THEO KHÓA
# ═══════════════════════════════════════════════════════════════════

@admin_bp.route('/api/next-student-code')
@login_required
@admin_required
def api_next_student_code():
    """API trả về mã sinh viên gợi ý tiếp theo khi Admin chọn Khóa & Mã ngành."""
    cohort = request.args.get('cohort', '23').strip()
    major  = request.args.get('major', 'ITB').strip().upper()
    code   = generate_next_student_code(cohort=cohort, major=major)
    return jsonify({'ok': True, 'student_code': code, 'cohort': cohort, 'major': major})


@admin_bp.route('/users')
@login_required
@admin_required
def users_list():
    role_filter   = request.args.get('role', '').strip()
    status_filter = request.args.get('status', '').strip()
    cohort_filter = request.args.get('cohort', '').strip()
    q             = request.args.get('q', '').strip()

    query = User.query.filter(User.role.in_(['student', 'lecturer', 'admin']))

    if role_filter in ('student', 'lecturer', 'admin'):
        query = query.filter_by(role=role_filter)
    if status_filter in ('active', 'inactive', 'suspended'):
        query = query.filter_by(status=status_filter)
    if cohort_filter and cohort_filter.isdigit():
        query = query.filter(User.role == 'student', User.student_code.like(f"{cohort_filter}%"))
    if q:
        like_q = f"%{q}%"
        query = query.filter(
            (User.full_name.ilike(like_q)) |
            (User.username.ilike(like_q)) |
            (User.email.ilike(like_q)) |
            (User.student_code.ilike(like_q))
        )

    users = query.order_by(User.role, User.student_code, User.created_at.desc()).all()

    counts = {
        'all':      User.query.count(),
        'lecturer': User.query.filter_by(role='lecturer').count(),
        'student':  User.query.filter_by(role='student').count(),
        'locked':   User.query.filter(User.status != 'active').count(),
    }

    default_cohort = cohort_filter if cohort_filter in COHORT_OPTIONS else '23'
    suggested_mssv = generate_next_student_code(default_cohort, 'ITB')

    return render_template(
        'admin/users.html',
        users=users,
        counts=counts,
        role_filter=role_filter,
        status_filter=status_filter,
        cohort_filter=cohort_filter,
        q=q,
        cohort_options=COHORT_OPTIONS,
        major_options=MAJOR_OPTIONS,
        default_cohort=default_cohort,
        suggested_mssv=suggested_mssv,
    )


@admin_bp.route('/users/create', methods=['POST'])
@login_required
@admin_required
def create_user():
    role         = request.form.get('role', 'student').strip()
    full_name    = request.form.get('full_name', '').strip()
    username     = request.form.get('username', '').strip()
    password     = request.form.get('password', '').strip()
    email        = request.form.get('email', '').strip() or None
    phone        = request.form.get('phone', '').strip() or None
    cohort       = request.form.get('cohort', '').strip()
    major        = request.form.get('major', 'ITB').strip().upper()
    raw_mssv     = request.form.get('student_code', '').strip()
    bio          = request.form.get('bio', '').strip() or None

    if role not in ('student', 'lecturer'):
        flash('Vai trò tài khoản không hợp lệ.', 'danger')
        return redirect(url_for('admin.users_list'))

    if not full_name or not username or not password:
        flash('Vui lòng nhập đầy đủ Họ tên, Tên đăng nhập và Mật khẩu cấp ban đầu.', 'danger')
        return redirect(url_for('admin.users_list'))

    if len(password) < 6:
        flash('Mật khẩu cấp ban đầu phải từ 6 ký tự trở lên.', 'danger')
        return redirect(url_for('admin.users_list'))

    if User.query.filter_by(username=username).first():
        flash(f'Tên đăng nhập "{username}" đã tồn tại trên hệ thống.', 'danger')
        return redirect(url_for('admin.users_list', role=role))

    if email and User.query.filter_by(email=email).first():
        flash(f'Email "{email}" đã được sử dụng cho tài khoản khác.', 'danger')
        return redirect(url_for('admin.users_list', role=role))

    if role == 'student':
        # Nếu Admin để trống ô MSSV thì hệ thống tự động cấp mã tiếp theo theo Khóa & Ngành
        if not raw_mssv and cohort:
            student_code = generate_next_student_code(cohort=cohort, major=major)
        else:
            student_code = raw_mssv

        ok, err_msg = validate_student_code(student_code, expected_cohort=cohort or None)
        if not ok:
            flash(err_msg, 'danger')
            return redirect(url_for('admin.users_list', role='student'))

        student_code = normalize_student_code(student_code)
        if User.query.filter_by(student_code=student_code).first():
            flash(f'Mã số sinh viên "{student_code}" đã được cấp cho sinh viên khác.', 'danger')
            return redirect(url_for('admin.users_list', role='student'))
    else:
        student_code = None

    new_user = User(
        username=username,
        full_name=full_name,
        role=role,
        email=email,
        phone=phone,
        student_code=student_code,
        bio=bio,
        status='active',
    )
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.flush()

    db.session.add(AuditLog(
        actor_id=current_user.id,
        action_type='user_create',
        target_type='user',
        target_id=new_user.id,
        new_value={
            'username': username,
            'role': role,
            'full_name': full_name,
            'student_code': student_code,
        },
        ip_address=request.remote_addr,
    ))
    db.session.commit()

    if role == 'student':
        flash(
            f'✅ Đã cấp tài khoản Sinh viên Khóa {student_code[:2]}: {full_name} — MSSV: {student_code} ({username}).',
            'success',
        )
    else:
        flash(f'✅ Đã cấp tài khoản Giảng viên mới: {full_name} ({username}).', 'success')
    return redirect(url_for('admin.users_list', role=role))


@admin_bp.route('/users/<int:user_id>/update', methods=['POST'])
@login_required
@admin_required
def update_user(user_id):
    u = User.query.get_or_404(user_id)

    full_name    = request.form.get('full_name', '').strip()
    email        = request.form.get('email', '').strip() or None
    phone        = request.form.get('phone', '').strip() or None
    cohort       = request.form.get('cohort', '').strip()
    raw_mssv     = request.form.get('student_code', '').strip()
    new_password = request.form.get('new_password', '').strip()
    bio          = request.form.get('bio', '').strip() or None

    if full_name:
        u.full_name = full_name

    if email and email != u.email:
        if User.query.filter(User.email == email, User.id != u.id).first():
            flash(f'Email "{email}" đã tồn tại ở tài khoản khác.', 'danger')
            return redirect(url_for('admin.users_list', role=u.role))
        u.email = email
    elif email is None:
        u.email = None

    u.phone = phone
    if u.role == 'lecturer':
        u.bio = bio

    if u.role == 'student':
        ok, err_msg = validate_student_code(raw_mssv, expected_cohort=cohort or None)
        if not ok:
            flash(err_msg, 'danger')
            return redirect(url_for('admin.users_list', role='student'))

        student_code = normalize_student_code(raw_mssv)
        if student_code != u.student_code:
            if User.query.filter(User.student_code == student_code, User.id != u.id).first():
                flash(f'MSSV "{student_code}" đã được cấp cho sinh viên khác.', 'danger')
                return redirect(url_for('admin.users_list', role='student'))
            u.student_code = student_code

    if new_password:
        if len(new_password) < 6:
            flash('Mật khẩu đặt lại phải có ít nhất 6 ký tự.', 'danger')
            return redirect(url_for('admin.users_list', role=u.role))
        u.set_password(new_password)

    db.session.add(AuditLog(
        actor_id=current_user.id,
        action_type='user_update',
        target_type='user',
        target_id=u.id,
        new_value={
            'username': u.username,
            'student_code': u.student_code,
            'reset_pw': bool(new_password),
        },
        ip_address=request.remote_addr,
    ))
    db.session.commit()
    flash(f'Đã cập nhật tài khoản {u.full_name} ({u.student_code or u.username}).', 'success')
    return redirect(url_for('admin.users_list', role=request.args.get('role', '')))


@admin_bp.route('/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def toggle_user_status(user_id):
    u = User.query.get_or_404(user_id)
    if u.id == current_user.id:
        flash('Không thể tự khóa tài khoản Quản trị viên đang đăng nhập.', 'warning')
        return redirect(url_for('admin.users_list'))

    old_status = u.status
    u.status = 'suspended' if u.status == 'active' else 'active'

    db.session.add(AuditLog(
        actor_id=current_user.id,
        action_type='user_status_change',
        target_type='user',
        target_id=u.id,
        old_value={'status': old_status},
        new_value={'status': u.status},
        ip_address=request.remote_addr,
    ))
    db.session.commit()

    msg = f'Đã mở khóa tài khoản {u.username}.' if u.status == 'active' else f'🔒 Đã khóa tài khoản {u.username}.'
    flash(msg, 'success' if u.status == 'active' else 'warning')
    return redirect(request.referrer or url_for('admin.users_list'))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    u = User.query.get_or_404(user_id)
    if u.id == current_user.id or u.role == 'admin':
        flash('Không thể xóa tài khoản Quản trị viên.', 'danger')
        return redirect(url_for('admin.users_list'))

    if u.role == 'lecturer' and Class.query.filter_by(lecturer_id=u.id).count() > 0:
        flash(
            f'Giảng viên {u.full_name} đang đứng lớp học phần. Hãy khóa tài khoản thay vì xóa để bảo toàn dữ liệu lớp.',
            'warning',
        )
        return redirect(url_for('admin.users_list', role='lecturer'))

    uname = u.username
    fname = u.full_name
    db.session.delete(u)
    db.session.commit()
    flash(f'🗑 Đã xóa vĩnh viễn tài khoản {fname} ({uname}).', 'info')
    return redirect(request.referrer or url_for('admin.users_list'))


# ═══════════════════════════════════════════════════════════════════
# 3. QUẢN LÝ THÔNG BÁO ĐÀO TẠO & TÀI CHÍNH (HIỂN THỊ TRANG CHỦ)
# ═══════════════════════════════════════════════════════════════════

@admin_bp.route('/announcements')
@login_required
@admin_required
def announcements_list():
    cat = request.args.get('category', '').strip()
    query = Announcement.query
    if cat in ('academic', 'finance', 'exam', 'scholarship', 'general'):
        query = query.filter_by(category=cat)

    announcements = query.order_by(
        Announcement.is_pinned.desc(),
        Announcement.created_at.desc(),
    ).all()

    return render_template(
        'admin/announcements.html',
        announcements=announcements,
        cat_filter=cat,
    )


@admin_bp.route('/announcements/create', methods=['POST'])
@login_required
@admin_required
def create_announcement():
    title          = request.form.get('title', '').strip()
    category       = request.form.get('category', 'academic').strip()
    content        = request.form.get('content', '').strip()
    is_new         = request.form.get('is_new') == 'on'
    is_pinned      = request.form.get('is_pinned') == 'on'
    notify_student = request.form.get('notify_students') == 'on'

    if not title:
        flash('Tiêu đề thông báo không được để trống.', 'danger')
        return redirect(url_for('admin.announcements_list'))

    if category not in ('academic', 'finance', 'exam', 'scholarship', 'general'):
        category = 'academic'

    ann = Announcement(
        title=title,
        content=content or title,
        category=category,
        is_new=is_new,
        is_pinned=is_pinned,
        is_published=True,
        author_id=current_user.id,
    )
    db.session.add(ann)
    db.session.flush()

    if notify_student:
        active_students = User.query.filter_by(role='student', status='active').all()
        for sv in active_students:
            db.session.add(Notification(
                user_id=sv.id,
                title=title,
                content=(content[:240] + '...') if content and len(content) > 240 else (content or 'Xem chi tiết trên Cổng thông tin Đào tạo.'),
                related_type='system',
                related_id=ann.id,
            ))

    db.session.commit()
    flash('📢 Đã đăng tải thông báo lên Cổng thông tin Đào tạo!', 'success')
    return redirect(url_for('admin.announcements_list'))


@admin_bp.route('/announcements/<int:ann_id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_announcement(ann_id):
    ann = Announcement.query.get_or_404(ann_id)
    title    = request.form.get('title', '').strip()
    category = request.form.get('category', ann.category).strip()
    content  = request.form.get('content', '').strip()

    if title:
        ann.title = title
    if category in ('academic', 'finance', 'exam', 'scholarship', 'general'):
        ann.category = category
    ann.content      = content
    ann.is_new       = request.form.get('is_new') == 'on'
    ann.is_pinned    = request.form.get('is_pinned') == 'on'
    ann.is_published = request.form.get('is_published') == 'on'

    db.session.commit()
    flash('Đã cập nhật nội dung thông báo.', 'success')
    return redirect(url_for('admin.announcements_list'))


@admin_bp.route('/announcements/<int:ann_id>/toggle-publish', methods=['POST'])
@login_required
@admin_required
def toggle_announcement(ann_id):
    ann = Announcement.query.get_or_404(ann_id)
    ann.is_published = not ann.is_published
    db.session.commit()
    flash('Đã hiển thị thông báo trên cổng.' if ann.is_published else 'Đã ẩn thông báo khỏi cổng công khai.', 'info')
    return redirect(url_for('admin.announcements_list'))


@admin_bp.route('/announcements/<int:ann_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_announcement(ann_id):
    ann = Announcement.query.get_or_404(ann_id)
    db.session.delete(ann)
    db.session.commit()
    flash('🗑 Đã xóa thông báo.', 'info')
    return redirect(url_for('admin.announcements_list'))


# ═══════════════════════════════════════════════════════════════════
# 4. QUẢN LÝ ĐĂNG KÝ TÍN CHỈ, MỞ LỚP HỌC PHẦN & XẾP LỊCH GIẢNG VIÊN
# ═══════════════════════════════════════════════════════════════════

STANDARD_ROOMS = [
    'P.A101', 'P.A102', 'P.A103', 'P.B201', 'P.B202', 'P.B203',
    'K.A105', 'K.A106', 'K.B204', 'V.A201', 'V.A202', 'Lab.1', 'Lab.2',
]


def _find_optimal_lecturer_slot(semester: str, lecturer_id: int, num_tiet: int = 2):
    """
    Thuật toán xếp lịch tự động cho Giảng viên trong khoảng Thứ 2 → Thứ 6 (day 0..4):
      1. Ưu tiên ngày trong tuần (0..4) mà Giảng viên chưa có tiết dạy nào (trải đều lịch).
      2. Không trùng ca dạy hiện có của Giảng viên trong học kỳ.
      3. Tự động chọn phòng học còn trống ở khung giờ đó.
    """
    sem_classes = Class.query.filter_by(semester=semester).filter(Class.status != 'cancelled').all()
    lect_classes = [c for c in sem_classes if c.lecturer_id == lecturer_id]

    lect_days_count = {d: 0 for d in range(5)}
    for c in lect_classes:
        info = c.schedule_info or {}
        d = info.get('day')
        if d is not None and 0 <= int(d) <= 4:
            lect_days_count[int(d)] += 1

    # Sắp xếp ngày ưu tiên ngày ít tiết dạy nhất của GV (Thứ 2 -> Thứ 6)
    candidate_days = sorted(range(5), key=lambda d: (lect_days_count[d], d))
    candidate_tiets = [1, 3, 6, 8]  # Ca 1 (T1-2), Ca 2 (T3-4), Ca 3 (T6-7), Ca 4 (T8-9)

    for d in candidate_days:
        for ts in candidate_tiets:
            cand_sched = {'day': d, 'tiet_start': ts, 'num_tiet': num_tiet}
            # Kiểm tra GV có bị trùng lịch không
            if any(schedules_conflict(cand_sched, c.schedule_info) for c in lect_classes):
                continue
            # Tìm phòng trống ở slot này
            busy_rooms = {
                (c.room or '').upper()
                for c in sem_classes
                if schedules_conflict(cand_sched, c.schedule_info)
            }
            free_room = next((r for r in STANDARD_ROOMS if r.upper() not in busy_rooms), STANDARD_ROOMS[0])
            return d, ts, free_room

    return 0, 1, STANDARD_ROOMS[0]


@admin_bp.route('/api/suggest-schedule')
@login_required
@admin_required
def api_suggest_schedule():
    semester    = request.args.get('semester', get_current_semester_id()).strip()
    lecturer_id = request.args.get('lecturer_id', type=int)
    num_tiet    = request.args.get('num_tiet', 2, type=int)
    if not lecturer_id:
        return jsonify({'ok': False, 'msg': 'Thiếu lecturer_id'}), 400

    day, tiet_start, room = _find_optimal_lecturer_slot(semester, lecturer_id, num_tiet)
    return jsonify({
        'ok': True,
        'day': day,
        'day_label': WEEKDAY_LABELS.get(day, 'Thứ 2'),
        'tiet_start': tiet_start,
        'room': room,
    })


@admin_bp.route('/courses')
@login_required
@admin_required
def courses_manage():
    all_semesters = get_all_semesters(include_next=True)
    cur_sem       = get_current_semester_id()
    selected_sem  = request.args.get('semester', cur_sem).strip() or cur_sem

    reg_cfg = RegistrationConfig.query.filter_by(semester=selected_sem).first()
    if not reg_cfg:
        # Mặc định ĐÓNG hoàn toàn — chỉ khi Admin chủ động mở mới cho phép đăng ký
        reg_cfg = RegistrationConfig(
            semester=selected_sem,
            is_open=False,
            min_courses=3,
            max_courses=7,
            note=f'Đợt đăng ký tín chỉ {selected_sem} (Tối thiểu 3 môn, tối đa 7 môn)',
        )
        db.session.add(reg_cfg)
        db.session.commit()

    classes = (
        Class.query.filter_by(semester=selected_sem)
        .order_by(Class.course_code, Class.class_name)
        .all()
    )
    enroll_counts = {
        c.id: Enrollment.query.filter_by(class_id=c.id, status='enrolled').count()
        for c in classes
    }

    lecturers = User.query.filter_by(role='lecturer', status='active').order_by(User.full_name).all()
    # Thống kê tải giảng dạy của từng GV trong kỳ đang chọn
    lect_workload = {}
    for gv in lecturers:
        gv_cls = [c for c in classes if c.lecturer_id == gv.id and c.status != 'cancelled']
        days_set = sorted({int(c.schedule_info.get('day', 0)) for c in gv_cls if c.schedule_info and c.schedule_info.get('day') is not None})
        lect_workload[gv.id] = {
            'count': len(gv_cls),
            'days': [WEEKDAY_LABELS.get(d, '?') for d in days_set],
        }

    sem_start, sem_end = get_semester_bounds(selected_sem)

    return render_template(
        'admin/courses.html',
        all_semesters=all_semesters,
        selected_sem=selected_sem,
        sem_start=sem_start,
        sem_end=sem_end,
        reg_cfg=reg_cfg,
        classes=classes,
        enroll_counts=enroll_counts,
        lecturers=lecturers,
        lect_workload=lect_workload,
        rooms=STANDARD_ROOMS,
        weekday_labels=WEEKDAY_LABELS,
    )


@admin_bp.route('/courses/registration-toggle', methods=['POST'])
@login_required
@admin_required
def toggle_registration():
    from datetime import datetime
    semester    = request.form.get('semester', get_current_semester_id()).strip()
    action      = request.form.get('action', 'toggle').strip()
    min_courses = request.form.get('min_courses', 3, type=int)
    max_courses = request.form.get('max_courses', 7, type=int)
    open_from_s = request.form.get('open_from', '').strip()
    open_until_s = request.form.get('open_until', '').strip()
    note        = request.form.get('note', '').strip()

    min_courses = max(1, min(min_courses, 7))
    max_courses = max(min_courses, min(max_courses, 10))

    def _parse_dt(val: str):
        if not val:
            return None
        for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                return datetime.strptime(val, fmt)
            except ValueError:
                continue
        return None

    dt_from  = _parse_dt(open_from_s)
    dt_until = _parse_dt(open_until_s)
    if dt_from and dt_until and dt_until <= dt_from:
        flash('Thời gian kết thúc đăng ký phải lớn hơn thời gian bắt đầu.', 'danger')
        return redirect(url_for('admin.courses_manage', semester=semester))

    cfg = RegistrationConfig.query.filter_by(semester=semester).first()
    if not cfg:
        cfg = RegistrationConfig(semester=semester, is_open=False)
        db.session.add(cfg)

    if action == 'open':
        # Đóng các kỳ khác để tại 1 thời điểm chỉ mở 1 học kỳ đăng ký chính thức rõ ràng
        RegistrationConfig.query.filter(RegistrationConfig.semester != semester).update({'is_open': False})
        cfg.is_open = True
    elif action == 'close':
        cfg.is_open = False
    elif action == 'save_window':
        # Chỉ lưu cập nhật khung thời gian và số môn tối thiểu/tối đa, giữ nguyên trạng thái đóng/mở
        pass
    else:
        cfg.is_open = not cfg.is_open
        if cfg.is_open:
            RegistrationConfig.query.filter(RegistrationConfig.semester != semester).update({'is_open': False})

    cfg.open_from   = dt_from
    cfg.open_until  = dt_until
    cfg.min_courses = min_courses
    cfg.max_courses = max_courses
    if note:
        cfg.note = note
    cfg.updated_by = current_user.id
    db.session.commit()

    if cfg.is_active_now:
        window_txt = ''
        if cfg.open_from or cfg.open_until:
            f_str = cfg.open_from.strftime('%H:%M %d/%m/%Y') if cfg.open_from else 'ngay bây giờ'
            u_str = cfg.open_until.strftime('%H:%M %d/%m/%Y') if cfg.open_until else 'khi Admin đóng'
            window_txt = f' · Thời gian: {f_str} → {u_str}'
        flash(f'🟢 Đã MỞ cổng đăng ký tín chỉ học kỳ {semester} ({cfg.min_courses}–{cfg.max_courses} môn{window_txt}).', 'success')
    elif cfg.is_open:
        flash(f'🕒 Đã bật lịch đăng ký kỳ {semester}. {cfg.status_reason}', 'info')
    else:
        flash(f'🔒 Đã ĐÓNG cổng đăng ký tín chỉ học kỳ {semester}. Sinh viên không thể đăng ký hoặc hủy môn.', 'warning')
    return redirect(url_for('admin.courses_manage', semester=semester))


@admin_bp.route('/courses/create', methods=['POST'])
@login_required
@admin_required
def create_course_class():
    semester      = request.form.get('semester', get_current_semester_id()).strip()
    course_code   = request.form.get('course_code', '').strip().upper()
    course_name   = request.form.get('course_name', '').strip()
    class_name    = request.form.get('class_name', '').strip().upper()
    lecturer_id   = request.form.get('lecturer_id', type=int)
    credits       = request.form.get('credits', 2, type=int)
    num_tiet      = request.form.get('num_tiet', 2, type=int)
    max_students  = request.form.get('max_students', 45, type=int)
    auto_schedule = request.form.get('auto_schedule') == 'on'

    if not course_code or not course_name or not lecturer_id:
        flash('Vui lòng nhập đầy đủ Mã học phần, Tên môn học và Giảng viên phụ trách.', 'danger')
        return redirect(url_for('admin.courses_manage', semester=semester))

    credits  = max(1, min(credits, 4))
    num_tiet = max(2, min(num_tiet, 4))

    # Tự đặt mã lớp nếu để trống (VD: CS801 -> CS801-01, CS801-02...)
    if not class_name:
        existing_cnt = Class.query.filter_by(semester=semester, course_code=course_code).count()
        class_name = f"{course_code}-{existing_cnt + 1:02d}"

    if Class.query.filter_by(semester=semester, class_name=class_name).first():
        flash(f'Mã lớp "{class_name}" đã tồn tại trong học kỳ {semester}.', 'danger')
        return redirect(url_for('admin.courses_manage', semester=semester))

    if auto_schedule:
        day, tiet_start, room = _find_optimal_lecturer_slot(semester, lecturer_id, num_tiet)
    else:
        day        = request.form.get('day', 0, type=int)
        tiet_start = request.form.get('tiet_start', 1, type=int)
        room       = request.form.get('room', 'P.A101').strip()

    # Ràng buộc học từ Thứ 2 đến Thứ 6 (day 0..4)
    if day < 0 or day > 4:
        flash('Lịch học chính khóa chỉ được phép xếp từ Thứ 2 đến Thứ 6.', 'danger')
        return redirect(url_for('admin.courses_manage', semester=semester))

    if tiet_start < 1 or tiet_start + num_tiet - 1 > 10:
        flash('Tiết bắt đầu và số tiết vượt quá khung 10 tiết/ngày.', 'danger')
        return redirect(url_for('admin.courses_manage', semester=semester))

    new_sched = {'day': day, 'tiet_start': tiet_start, 'num_tiet': num_tiet, 'credits': credits}

    # Kiểm tra trùng lịch dạy của Giảng viên trong cùng học kỳ
    sem_classes = Class.query.filter_by(semester=semester).filter(Class.status != 'cancelled').all()
    for c in sem_classes:
        if c.lecturer_id == lecturer_id and schedules_conflict(new_sched, c.schedule_info):
            gv = User.query.get(lecturer_id)
            flash(
                f'❌ Trùng lịch giảng viên: {gv.full_name if gv else "GV"} đã có lớp {c.class_name} '
                f'vào {WEEKDAY_LABELS[day]} (Tiết {c.schedule_info.get("tiet_start")}).',
                'danger',
            )
            return redirect(url_for('admin.courses_manage', semester=semester))

        if (c.room or '').upper() == room.upper() and schedules_conflict(new_sched, c.schedule_info):
            flash(
                f'❌ Trùng phòng học: Phòng {room} đã được xếp cho lớp {c.class_name} vào khung giờ này.',
                'danger',
            )
            return redirect(url_for('admin.courses_manage', semester=semester))

    cls = Class(
        class_name=class_name,
        course_name=course_name,
        course_code=course_code,
        lecturer_id=lecturer_id,
        semester=semester,
        room=room,
        schedule_info=new_sched,
        formula_config={'attendance': 0.10, 'assignment': 0.10, 'midterm': 0.30, 'final': 0.50},
        max_students=max_students,
        status='active',
    )
    db.session.add(cls)
    db.session.flush()

    # Tự động sinh các buổi học xuyên suốt học kỳ (HK1: T8->T12, HK2: T2->T5)
    sessions = generate_sessions_for_class(cls)
    for s in sessions:
        db.session.add(s)

    db.session.commit()
    flash(
        f'✅ Đã mở lớp {class_name} ({course_name} · {credits} TC) — '
        f'{WEEKDAY_LABELS[day]}, Tiết {tiet_start}→{tiet_start + num_tiet - 1}, Phòng {room} ({len(sessions)} buổi).',
        'success',
    )
    return redirect(url_for('admin.courses_manage', semester=semester))


@admin_bp.route('/courses/<int:class_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_course_class(class_id):
    cls = Class.query.get_or_404(class_id)
    sem = cls.semester
    enrolled_cnt = Enrollment.query.filter_by(class_id=cls.id, status='enrolled').count()
    if enrolled_cnt > 0:
        flash(
            f'Lớp {cls.class_name} đang có {enrolled_cnt} sinh viên đăng ký nên không thể xóa trực tiếp.',
            'warning',
        )
        return redirect(url_for('admin.courses_manage', semester=sem))

    cname = cls.class_name
    db.session.delete(cls)
    db.session.commit()
    flash(f'🗑 Đã xóa lớp học phần {cname}.', 'info')
    return redirect(url_for('admin.courses_manage', semester=sem))


# ═══════════════════════════════════════════════════════════════════
# 5. QUẢN LÝ DỮ LIỆU KHUÔN MẶT CSDL, DATASET .CSV & HUẤN LUYỆN MODEL AI
# ═══════════════════════════════════════════════════════════════════

@admin_bp.route('/face-ai')
@login_required
@admin_required
def face_ai_manage():
    from models.face_data import FaceData, FaceSample
    from services.face_service import (
        get_backend_info,
        sync_face_datasets_to_csv,
        EMBEDDINGS_CSV_PATH,
        REGISTRY_CSV_PATH,
        AI_LOGS_CSV_PATH,
    )
    import csv

    sync_info = sync_face_datasets_to_csv()
    backend_info = get_backend_info()

    face_records = (
        db.session.query(FaceData, User)
        .join(User, User.id == FaceData.student_id)
        .order_by(FaceData.updated_at.desc())
        .all()
    )
    sample_counts = {
        sid: cnt
        for sid, cnt in db.session.query(FaceSample.student_id, db.func.count(FaceSample.id))
        .group_by(FaceSample.student_id)
        .all()
    }

    recent_ai_logs = []
    if AI_LOGS_CSV_PATH.exists():
        try:
            with open(AI_LOGS_CSV_PATH, 'r', encoding='utf-8-sig') as fp:
                all_rows = list(csv.DictReader(fp))
                recent_ai_logs = list(reversed(all_rows[-25:]))
        except Exception:
            recent_ai_logs = []

    return render_template(
        'admin/face_ai.html',
        backend_info=backend_info,
        sync_info=sync_info,
        face_records=face_records,
        sample_counts=sample_counts,
        recent_ai_logs=recent_ai_logs,
        total_students=User.query.filter_by(role='student').count(),
    )


@admin_bp.route('/face-ai/train', methods=['POST'])
@login_required
@admin_required
def train_face_ai():
    from services.face_service import train_face_recognition_model
    res = train_face_recognition_model()
    if res.get('trained'):
        flash(
            f"✅ Đã đồng bộ CSV và huấn luyện thành công Model AI cho {res.get('num_students')} sinh viên "
            f"({res.get('num_raw_samples')} mẫu gốc → {res.get('num_augmented_samples')} mẫu train · Độ chính xác CV: {res.get('accuracy')}%).",
            'success',
        )
    else:
        flash(f"ℹ️ Đã đồng bộ CSV. {res.get('msg', 'Chưa có mẫu chuẩn 128D để train.')}", 'info')
    return redirect(url_for('admin.face_ai_manage'))


@admin_bp.route('/face-ai/download/<string:csv_kind>')
@login_required
@admin_required
def download_face_csv(csv_kind):
    from services.face_service import (
        sync_face_datasets_to_csv,
        EMBEDDINGS_CSV_PATH,
        REGISTRY_CSV_PATH,
        AI_LOGS_CSV_PATH,
    )
    sync_face_datasets_to_csv()
    mapping = {
        'embeddings': (EMBEDDINGS_CSV_PATH, 'face_embeddings.csv'),
        'registry':   (REGISTRY_CSV_PATH,   'face_registry.csv'),
        'logs':       (AI_LOGS_CSV_PATH,       'attendance_ai_logs.csv'),
    }
    if csv_kind not in mapping:
        flash('Loại file CSV không hợp lệ.', 'danger')
        return redirect(url_for('admin.face_ai_manage'))

    fpath, fname = mapping[csv_kind]
    if not fpath.exists():
        fpath.write_text('timestamp,note\n', encoding='utf-8-sig')
    return send_file(fpath, as_attachment=True, download_name=fname, mimetype='text/csv')
