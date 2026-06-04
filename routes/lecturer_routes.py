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


@lecturer_bp.route('/dashboard')
@login_required
@lecturer_required
def dashboard():
    from utils.timetable import TIET_MAP, tiet_span, get_all_semesters
    today = date.today()

    # ── Lớp đang phụ trách ───────────────────────────────────────────────────
    classes = Class.query.filter_by(
        lecturer_id=current_user.id, status='active'
    ).all()

    class_counts = {
        c.id: Enrollment.query.filter_by(class_id=c.id, status='enrolled').count()
        for c in classes
    }
    total_students = sum(class_counts.values())

    # ── Buổi học hôm nay ─────────────────────────────────────────────────────
    sessions_today = []
    for cls in classes:
        for sess in Session.query.filter_by(class_id=cls.id, session_date=today).all():
            present = Attendance.query.filter_by(
                class_id=cls.id, session_date=today, status='present'
            ).count()
            sessions_today.append((sess, cls, present, class_counts.get(cls.id, 0)))
    sessions_today.sort(key=lambda x: x[0].start_time)
    total_present = sum(x[2] for x in sessions_today)

    # ── Timetable tuần ───────────────────────────────────────────────────────
    week_offset = int(request.args.get('week', 0))
    week_start  = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    week_end    = week_start + timedelta(days=6)   # T2→CN (CN luôn trống vì seed không tạo buổi CN)

    # Số tuần trong học kỳ
    sem_start = date(today.year, 8, 1) if today.month >= 8 else date(today.year - 1, 12, 1)
    if sem_start.weekday() != 0:
        sem_start += timedelta(days=(7 - sem_start.weekday()) % 7)
    week_num = max(1, ((week_start - sem_start).days // 7) + 1)

    # Query sessions trong tuần T2→T7 (week_end = T7, không gồm CN)
    week_sessions = (
        db.session.query(Session, Class)
        .join(Class, Class.id == Session.class_id)
        .filter(
            Class.lecturer_id == current_user.id,
            Session.session_date >= week_start,
            Session.session_date <= week_end,
            Session.status != 'cancelled',
        )
        .order_by(Session.session_date, Session.start_time)
        .all()
    )

    # Build timetable
    # key   = (day_idx, tiet_start)  — day_idx: 0=T2 .. 5=T7
    # value = (session, class, span)
    timetable = {}
    occupied  = set()
    for sess, cls in week_sessions:
        day_idx = sess.session_date.weekday()
        if day_idx >= 6:                              # bỏ qua CN — không có cột
            continue
        t_start, span = tiet_span(sess.start_time, sess.end_time)
        if (day_idx, t_start) not in occupied:        # bỏ qua nếu bị rowspan che
            timetable[(day_idx, t_start)] = (sess, cls, span)
        for t in range(t_start, t_start + span):
            occupied.add((day_idx, t))

    all_semesters = get_all_semesters()

    return render_template('lecturer/dashboard.html',
        classes        = classes,
        total_students = total_students,
        class_counts   = class_counts,
        sessions_today = sessions_today,
        total_present  = total_present,
        today          = today,
        timetable      = timetable,
        occupied       = occupied,
        tiet_map       = TIET_MAP,
        week_start     = week_start,
        week_end       = week_end,
        week_offset    = week_offset,
        week_num       = week_num,
        all_semesters  = all_semesters,
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
    cls = Class.query.filter_by(id=class_id, lecturer_id=current_user.id).first_or_404()
    enrollments = (
        db.session.query(Enrollment, User)
        .join(User, User.id == Enrollment.student_id)
        .filter(Enrollment.class_id == class_id, Enrollment.status == 'enrolled')
        .order_by(User.full_name)
        .all()
    )
    return render_template('lecturer/class_students.html', cls=cls, enrollments=enrollments)


@lecturer_bp.route('/classes/<int:class_id>/students/add', methods=['POST'])
@login_required
@lecturer_required
def add_student(class_id):
    cls     = Class.query.filter_by(id=class_id, lecturer_id=current_user.id).first_or_404()
    ident   = request.form.get('identifier', '').strip()
    student = User.query.filter(
        (User.student_code == ident) | (User.username == ident),
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