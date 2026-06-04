import os
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from datetime import date, timedelta
from extensions import db
from models.class_model  import Class
from models.enrollment   import Enrollment
from models.session      import Session
from models.grade        import Grade
from models.attendance   import Attendance
from models.notification import Notification
from utils.decorators    import student_required

student_bp = Blueprint('student', __name__, url_prefix='/student')

@student_bp.route('/dashboard')
@login_required
@student_required
def dashboard():
    sid   = current_user.id
    today = date.today()
    enrolled_classes = (
        db.session.query(Class).join(Enrollment, Enrollment.class_id == Class.id)
        .filter(Enrollment.student_id == sid, Enrollment.status == 'enrolled', Class.status == 'active').all()
    )
    today_sessions = (
        db.session.query(Session, Class).join(Class, Class.id == Session.class_id)
        .join(Enrollment, Enrollment.class_id == Class.id)
        .filter(Enrollment.student_id == sid, Session.session_date == today, Session.status != 'cancelled')
        .order_by(Session.start_time).all()
    )
    attended_count = Attendance.query.filter_by(student_id=sid, status='present').count()
    unread_count   = Notification.query.filter_by(user_id=sid, is_read=False).count()
    return render_template('student/dashboard.html',
        enrolled_classes=enrolled_classes, today_sessions=today_sessions,
        attended_count=attended_count, unread_count=unread_count, today=today)

@student_bp.route('/schedule')
@login_required
@student_required
def schedule():
    from utils.timetable import TIET_MAP, tiet_span, get_all_semesters, get_semester_start
    sid         = current_user.id
    today       = date.today()
    week_offset = int(request.args.get('week', 0))
    week_start  = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    week_end    = week_start + timedelta(days=6)

    # Get selected semester or choose the most relevant semester for this student
    all_semesters = get_all_semesters()
    selected_sem = request.args.get('semester', '')

    semester_order = {sem_id: idx for idx, (sem_id, *_rest) in enumerate(all_semesters)}
    def choose_latest_semester(semesters):
        semesters = [sem for sem in semesters if sem in semester_order]
        if not semesters:
            return None
        return max(semesters, key=lambda sem: semester_order[sem])

    if not selected_sem:
        # Prefer semester that has sessions this week, then latest enrolled semester.
        week_semesters = [sem for sem, in db.session.query(Class.semester)
            .join(Enrollment, Enrollment.class_id == Class.id)
            .join(Session, Session.class_id == Class.id)
            .filter(
                Enrollment.student_id == sid,
                Enrollment.status == 'enrolled',
                Class.status == 'active',
                Session.session_date >= week_start,
                Session.session_date <= week_end,
            ).distinct().all()]

        enrolled_semesters = [sem for sem, in db.session.query(Class.semester)
            .join(Enrollment, Enrollment.class_id == Class.id)
            .filter(
                Enrollment.student_id == sid,
                Enrollment.status == 'enrolled',
                Class.status == 'active',
            ).distinct().all()]

        selected_sem = choose_latest_semester(week_semesters) or choose_latest_semester(enrolled_semesters)
        if not selected_sem and all_semesters:
            selected_sem = all_semesters[-1][0]
    elif selected_sem not in semester_order and all_semesters:
        selected_sem = all_semesters[-1][0]

    # Calculate semester start for week number calculation
    if selected_sem:
        sem_start = get_semester_start(selected_sem)
    else:
        # Fallback to current semester calculation
        if today.month >= 8:
            sem_start = date(today.year, 8, 1)
            sem_start = sem_start + timedelta(days=(7 - sem_start.weekday()) % 7)
        else:
            sem_start = date(today.year - 1, 12, 1)
            sem_start = sem_start + timedelta(days=(7 - sem_start.weekday()) % 7)
    
    week_num = max(1, ((week_start - sem_start).days // 7) + 1)

    # Query sessions filtered by selected semester and active classes
    sessions = (
        db.session.query(Session, Class)
        .join(Class, Class.id == Session.class_id)
        .join(Enrollment, Enrollment.class_id == Class.id)
        .filter(Enrollment.student_id == sid,
                Enrollment.status == 'enrolled',
                Class.status == 'active',
                Class.semester == selected_sem,
                Session.session_date >= week_start,
                Session.session_date <= week_end,
                Session.status != 'cancelled')
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

    return render_template('student/schedule.html',
        timetable=timetable, occupied=occupied,
        week_start=week_start, week_end=week_end,
        week_offset=week_offset, today=today,
        week_num=week_num,
        tiet_map=TIET_MAP,
        all_semesters=all_semesters,
        selected_semester=selected_sem,
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
                  .filter(Enrollment.student_id == sid).all())
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
