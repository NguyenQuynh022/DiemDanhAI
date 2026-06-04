import os
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models.attendance   import Attendance
from models.class_model  import Class
from models.enrollment   import Enrollment
from models.session      import Session
from models.face_data    import FaceData
from models.user         import User
from utils.decorators    import student_required, lecturer_required

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')


# ═══════════════════════════════════════════════════════════════════
# SINH VIÊN — Trang điểm danh
# ═══════════════════════════════════════════════════════════════════

@attendance_bp.route('/checkin')
@login_required
@student_required
def checkin_page():
    sid   = current_user.id
    today = date.today()

    sessions_today = (
        db.session.query(Session, Class)
        .join(Class, Class.id == Session.class_id)
        .join(Enrollment, Enrollment.class_id == Class.id)
        .filter(
            Enrollment.student_id == sid,
            Session.session_date  == today,
            Session.status.in_(['scheduled', 'ongoing']),
        )
        .order_by(Session.start_time)
        .all()
    )

    has_face = FaceData.query.filter_by(student_id=sid).first() is not None
    checked_sessions = set(
        a.session_id for a in
        Attendance.query.filter_by(student_id=sid, session_date=today).all()
        if a.session_id
    )

    from services.face_service import get_backend_info
    return render_template('student/checkin.html',
        sessions_today   = sessions_today,
        has_face         = has_face,
        checked_sessions = checked_sessions,
        backend_info     = get_backend_info(),
        today            = today,
    )


@attendance_bp.route('/checkin/submit', methods=['POST'])
@login_required
@student_required
def checkin_submit():
    from services.face_service import decode_image, encode_face, compare_faces

    data       = request.get_json()
    image_b64  = data.get('image')
    session_id = data.get('session_id')
    class_id   = data.get('class_id')

    if not all([image_b64, session_id, class_id]):
        return jsonify({'ok': False, 'msg': 'Thiếu dữ liệu'}), 400

    sid = current_user.id

    # 1. SV có enrolled trong lớp không?
    enroll = Enrollment.query.filter_by(
        student_id=sid, class_id=class_id, status='enrolled'
    ).first()
    if not enroll:
        return jsonify({'ok': False, 'msg': 'Bạn không thuộc lớp này'}), 403

    # 2. Buổi học hợp lệ và đang ONGOING?
    sess = Session.query.get(session_id)
    if not sess or sess.class_id != int(class_id):
        return jsonify({'ok': False, 'msg': 'Buổi học không hợp lệ'}), 400
    if sess.status != 'ongoing':
        return jsonify({
            'ok':  False,
            'msg': 'Giảng viên chưa mở điểm danh cho buổi học này.',
        }), 403

    # 3. SV đã điểm danh buổi này chưa?
    existing = Attendance.query.filter_by(
        student_id=sid, class_id=class_id,
        session_date=sess.session_date,
    ).first()
    if existing:
        return jsonify({
            'ok':     False,
            'msg':    'Bạn đã điểm danh buổi này rồi',
            'status': existing.status,
        }), 400

    # 4. Khuôn mặt đã đăng ký?
    face_data = FaceData.query.filter_by(student_id=sid).first()
    if not face_data:
        return jsonify({'ok': False, 'msg': 'Chưa đăng ký khuôn mặt'}), 400

    # 5. Nhận diện khuôn mặt
    try:
        img_np       = decode_image(image_b64)
        new_emb, err = encode_face(img_np)
        if err:
            return jsonify({'ok': False, 'msg': err}), 400
    except Exception as e:
        return jsonify({'ok': False, 'msg': f'Lỗi xử lý ảnh: {e}'}), 400

    is_match, score, err = compare_faces(face_data.embedding, new_emb)
    if err:
        return jsonify({'ok': False, 'msg': err}), 400
    if not is_match:
        return jsonify({
            'ok':    False,
            'msg':   f'Không nhận diện được (độ khớp: {score:.1%})',
            'score': float(score),
        }), 400

    # ── Ghi điểm danh ────────────────────────────────────────────
    db.session.add(Attendance(
        student_id   = sid,
        class_id     = int(class_id),
        session_id   = int(session_id),
        session_date = sess.session_date,
        status       = 'present',
        checkin_time = datetime.utcnow(),
        method       = 'face',
        face_score   = score,
    ))
    db.session.commit()
    return jsonify({
        'ok':    True,
        'msg':   f'Điểm danh thành công! Độ khớp: {score:.1%}',
        'score': float(score),
        'time':  datetime.now().strftime('%H:%M:%S'),
    })


# ═══════════════════════════════════════════════════════════════════
# SINH VIÊN — Polling trạng thái buổi học
# ═══════════════════════════════════════════════════════════════════

@attendance_bp.route('/api/session/<int:session_id>/student-status')
@login_required
@student_required
def student_session_status(session_id):
    """
    SV polling để biết GV đã mở điểm danh chưa.
    Trả về: status buổi học + SV đã điểm danh chưa.
    """
    sess = Session.query.get_or_404(session_id)
    sid  = current_user.id

    # Kiểm tra SV có thuộc lớp này không
    enroll = Enrollment.query.filter_by(
        student_id=sid, class_id=sess.class_id, status='enrolled'
    ).first()
    if not enroll:
        return jsonify({'ok': False, 'msg': 'Không có quyền truy cập'}), 403

    # Đã điểm danh chưa?
    checked = Attendance.query.filter_by(
        student_id   = sid,
        class_id     = sess.class_id,
        session_date = sess.session_date,
    ).first()

    return jsonify({
        'ok':           True,
        'session_id':   session_id,
        'status':       sess.status,
        'is_checked':   checked is not None,
        'check_status': checked.status if checked else None,
    })


# ═══════════════════════════════════════════════════════════════════
# SINH VIÊN — Đăng ký khuôn mặt
# ═══════════════════════════════════════════════════════════════════

@attendance_bp.route('/register-face')
@login_required
@student_required
def register_face_page():
    has_face = FaceData.query.filter_by(student_id=current_user.id).first() is not None
    from services.face_service import get_backend_info
    return render_template('student/register_face.html',
        has_face=has_face, backend_info=get_backend_info()
    )


@attendance_bp.route('/register-face/submit', methods=['POST'])
@login_required
@student_required
def register_face_submit():
    from services.face_service import decode_image, encode_face, get_backend_info

    data      = request.get_json()
    image_b64 = data.get('image')
    if not image_b64:
        return jsonify({'ok': False, 'msg': 'Không nhận được ảnh'}), 400

    try:
        img_np      = decode_image(image_b64)
        emb_bytes, err = encode_face(img_np)
        if err:
            return jsonify({'ok': False, 'msg': err}), 400
    except Exception as e:
        return jsonify({'ok': False, 'msg': f'Lỗi xử lý ảnh: {e}'}), 400

    info     = get_backend_info()
    sid      = current_user.id
    existing = FaceData.query.filter_by(student_id=sid).first()
    if existing:
        existing.embedding       = emb_bytes
        existing.embedding_model = info['backend']
        existing.image_count     = (existing.image_count or 0) + 1
        existing.updated_at      = datetime.utcnow()
    else:
        db.session.add(FaceData(
            student_id      = sid,
            embedding       = emb_bytes,
            embedding_model = info['backend'],
        ))
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'Đăng ký khuôn mặt thành công!'})


# ═══════════════════════════════════════════════════════════════════
# GIẢNG VIÊN — Mở / Đóng buổi điểm danh
# ═══════════════════════════════════════════════════════════════════

@attendance_bp.route('/lecturer/session/<int:session_id>/open', methods=['POST'])
@login_required
@lecturer_required
def open_session(session_id):
    sess = Session.query.get_or_404(session_id)
    Class.query.filter_by(id=sess.class_id, lecturer_id=current_user.id).first_or_404()

    if sess.status == 'ongoing':
        return jsonify({'ok': True, 'msg': 'Buổi học đã đang mở', 'status': 'ongoing'})
    if sess.status == 'completed':
        return jsonify({'ok': False, 'msg': 'Buổi học đã kết thúc, không thể mở lại'}), 400

    sess.status = 'ongoing'
    db.session.commit()
    return jsonify({
        'ok':     True,
        'msg':    '✅ Đã mở điểm danh — sinh viên có thể điểm danh ngay bây giờ.',
        'status': 'ongoing',
    })


@attendance_bp.route('/lecturer/session/<int:session_id>/close', methods=['POST'])
@login_required
@lecturer_required
def close_session(session_id):
    sess = Session.query.get_or_404(session_id)
    cls  = Class.query.filter_by(id=sess.class_id, lecturer_id=current_user.id).first_or_404()

    if sess.status == 'completed':
        return jsonify({'ok': True, 'msg': 'Buổi học đã kết thúc', 'status': 'completed'})

    # Ghi 'absent' cho SV chưa điểm danh
    enrolled_ids = [
        e.student_id for e in
        Enrollment.query.filter_by(class_id=cls.id, status='enrolled').all()
    ]
    attended_ids = {
        a.student_id for a in
        Attendance.query.filter_by(
            class_id=cls.id, session_date=sess.session_date
        ).all()
    }
    absent_count = 0
    for sv_id in enrolled_ids:
        if sv_id not in attended_ids:
            db.session.add(Attendance(
                student_id   = sv_id,
                class_id     = cls.id,
                session_id   = sess.id,
                session_date = sess.session_date,
                status       = 'absent',
                method       = 'manual',
                checkin_time = datetime.utcnow(),
            ))
            absent_count += 1

    sess.status = 'completed'
    db.session.commit()
    return jsonify({
        'ok':           True,
        'msg':          f'✅ Đã đóng điểm danh. Ghi vắng {absent_count} sinh viên.',
        'status':       'completed',
        'absent_count': absent_count,
    })


# ═══════════════════════════════════════════════════════════════════
# GIẢNG VIÊN — Theo dõi điểm danh theo lớp
# ═══════════════════════════════════════════════════════════════════

@attendance_bp.route('/lecturer/class/<int:class_id>')
@login_required
@lecturer_required
def lecturer_attendance(class_id):
    cls = Class.query.filter_by(id=class_id, lecturer_id=current_user.id).first_or_404()

    all_sessions = (
        Session.query
        .filter_by(class_id=class_id)
        .order_by(Session.session_date.desc(), Session.start_time)
        .all()
    )

    selected_sid     = request.args.get('session_id', type=int)
    if not selected_sid and all_sessions:
        selected_sid = all_sessions[0].id
    selected_session = Session.query.get(selected_sid) if selected_sid else None

    enrollments = (
        db.session.query(Enrollment, User)
        .join(User, User.id == Enrollment.student_id)
        .filter(Enrollment.class_id == class_id, Enrollment.status == 'enrolled')
        .order_by(User.full_name)
        .all()
    )

    att_map = {}
    if selected_session:
        records = Attendance.query.filter_by(
            class_id     = class_id,
            session_date = selected_session.session_date,
        ).all()
        att_map = {r.student_id: r for r in records}

    stats = {}
    for enroll, student in enrollments:
        total   = Attendance.query.filter_by(student_id=student.id, class_id=class_id).count()
        present = Attendance.query.filter_by(student_id=student.id, class_id=class_id, status='present').count()
        stats[student.id] = {
            'total':   total,
            'present': present,
            'rate':    round(present / total * 100, 1) if total > 0 else 0,
        }

    from collections import defaultdict
    DAYS = ['Thứ 2', 'Thứ 3', 'Thứ 4', 'Thứ 5', 'Thứ 6', 'Thứ 7', 'Chủ nhật']
    sessions_by_day = defaultdict(list)
    for s in all_sessions:
        sessions_by_day[DAYS[s.session_date.weekday()]].append(s)

    return render_template('lecturer/attendance.html',
        cls              = cls,
        all_sessions     = all_sessions,
        sessions_by_day  = dict(sessions_by_day),
        selected_session = selected_session,
        enrollments      = enrollments,
        att_map          = att_map,
        stats            = stats,
        DAYS             = DAYS,
        today            = date.today(),
    )


@attendance_bp.route('/lecturer/manual', methods=['POST'])
@login_required
@lecturer_required
def manual_checkin():
    data       = request.get_json()
    student_id = data.get('student_id')
    class_id   = data.get('class_id')
    session_id = data.get('session_id')
    status     = data.get('status', 'present')

    Class.query.filter_by(id=class_id, lecturer_id=current_user.id).first_or_404()
    sess = Session.query.get(session_id)
    if not sess:
        return jsonify({'ok': False, 'msg': 'Buổi học không hợp lệ'}), 400

    existing = Attendance.query.filter_by(
        student_id   = student_id,
        class_id     = class_id,
        session_date = sess.session_date,
    ).first()
    if existing:
        existing.status = status
        existing.method = 'manual'
    else:
        db.session.add(Attendance(
            student_id   = student_id,
            class_id     = class_id,
            session_id   = session_id,
            session_date = sess.session_date,
            status       = status,
            method       = 'manual',
            checkin_time = datetime.utcnow(),
        ))
    db.session.commit()
    return jsonify({'ok': True, 'msg': f'Đã cập nhật: {status}'})


# ═══════════════════════════════════════════════════════════════════
# GIẢNG VIÊN — API trạng thái buổi học (live monitor)
# ═══════════════════════════════════════════════════════════════════

@attendance_bp.route('/api/session/<int:session_id>/status')
@login_required
@lecturer_required
def session_status(session_id):
    sess = Session.query.get_or_404(session_id)
    Class.query.filter_by(id=sess.class_id, lecturer_id=current_user.id).first_or_404()

    records        = Attendance.query.filter_by(class_id=sess.class_id, session_date=sess.session_date).all()
    total_enrolled = Enrollment.query.filter_by(class_id=sess.class_id, status='enrolled').count()

    return jsonify({
        'session_status': sess.status,
        'present':  sum(1 for r in records if r.status == 'present'),
        'late':     sum(1 for r in records if r.status == 'late'),
        'absent':   total_enrolled - len(records),
        'total':    total_enrolled,
        'records':  [{
            'student_id': r.student_id,
            'status':     r.status,
            'method':     r.method,
            'time':       r.checkin_time.strftime('%H:%M:%S') if r.checkin_time else None,
            'score':      float(r.face_score) if r.face_score else None,
        } for r in records],
        'updated_at': datetime.now().strftime('%H:%M:%S'),
    })