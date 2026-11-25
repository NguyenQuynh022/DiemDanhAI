import os
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models.attendance   import Attendance
from models.class_model  import Class
from models.enrollment   import Enrollment
from models.session      import Session
from models.face_data    import FaceData, FaceSample
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
            Enrollment.status     == 'enrolled',
            Session.session_date  == today,
            Session.status.in_(['scheduled', 'ongoing']),
        )
        .order_by(Session.start_time)
        .all()
    )

    has_face = False
    face_rec = FaceData.query.filter_by(student_id=sid).first()
    if face_rec and face_rec.embedding_model == 'sface_onnx_128d':
        has_face = True
    checked_sessions = set(
        a.session_id for a in
        Attendance.query.filter_by(student_id=sid, session_date=today).all()
        if a.session_id
    )

    from services.face_service import get_backend_info
    return render_template('student/checkin.html',
        sessions_today   = sessions_today,
        has_face         = has_face,
        face_rec         = face_rec,
        checked_sessions = checked_sessions,
        backend_info     = get_backend_info(),
        today            = today,
    )


@attendance_bp.route('/checkin/submit', methods=['POST'])
@login_required
@student_required
def checkin_submit():
    from services.face_service import (
        decode_image,
        verify_liveness_sequence,
        verify_student_identity,
        append_attendance_ai_log_csv,
    )

    data           = request.get_json() or {}
    frames_b64     = data.get('frames') or []
    single_img     = data.get('image')
    challenge_mode = data.get('challenge_mode', 'head_turn')
    session_id     = data.get('session_id')
    class_id       = data.get('class_id')

    if not frames_b64 and single_img:
        frames_b64 = [single_img]

    if not session_id or not class_id or not frames_b64:
        return jsonify({'ok': False, 'msg': 'Thiếu dữ liệu khung hình trực tiếp hoặc mã buổi học.'}), 400

    sid = current_user.id

    # 1. SV có enrolled trong lớp không?
    enroll = Enrollment.query.filter_by(
        student_id=sid, class_id=class_id, status='enrolled'
    ).first()
    if not enroll:
        return jsonify({'ok': False, 'msg': 'Bạn không thuộc lớp học phần này.'}), 403

    # 2. Buổi học hợp lệ và đang ONGOING?
    sess = Session.query.get(session_id)
    cls  = Class.query.get(class_id)
    if not sess or not cls or sess.class_id != int(class_id):
        return jsonify({'ok': False, 'msg': 'Buổi học không hợp lệ.'}), 400
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
            'msg':    'Bạn đã điểm danh buổi này rồi.',
            'status': existing.status,
        }), 400

    # 4. Khuôn mặt đã đăng ký trong CSDL MySQL chưa?
    face_data = FaceData.query.filter_by(student_id=sid).first()
    if not face_data:
        return jsonify({'ok': False, 'msg': 'Bạn chưa đăng ký dữ liệu khuôn mặt trong CSDL!'}), 400

    # 5. Giải mã chuỗi khung hình trực tiếp & Kiểm tra CHỐNG GIẢ MẠO NGƯỜI THẬT (Liveness + Anti-Spoofing)
    try:
        frames_rgb = [decode_image(f) for f in frames_b64[:8]]
    except Exception as e:
        return jsonify({'ok': False, 'msg': f'Lỗi giải mã luồng video: {e}'}), 400

    live_res = verify_liveness_sequence(frames_rgb, challenge_mode=challenge_mode)
    if not live_res['is_live']:
        append_attendance_ai_log_csv(
            student_id=sid,
            student_code=current_user.student_code or '',
            full_name=current_user.full_name,
            class_name=cls.class_name,
            session_id=sess.id,
            cosine_score=0.0,
            model_prob=0.0,
            liveness_score=live_res['liveness_score'],
            accepted=False,
            note=f"SPOOF_BLOCKED: {live_res['reason']}",
        )
        return jsonify({
            'ok':       False,
            'msg':      live_res['reason'],
            'liveness': live_res['liveness_score'],
            'spoof':    True,
        }), 400

    # 6. Xác thực danh tính bằng Model AI đã train (.pkl từ .csv) + Vector mẫu CSDL MySQL
    id_res = verify_student_identity(
        student_id=sid,
        probe_embedding=live_res['mean_embedding'],
        stored_db_bytes=face_data.embedding,
    )
    if id_res.get('err'):
        return jsonify({'ok': False, 'msg': id_res['err']}), 400

    if not id_res['is_match']:
        append_attendance_ai_log_csv(
            student_id=sid,
            student_code=current_user.student_code or '',
            full_name=current_user.full_name,
            class_name=cls.class_name,
            session_id=sess.id,
            cosine_score=id_res['cosine_score'],
            model_prob=id_res['model_prob'],
            liveness_score=live_res['liveness_score'],
            accepted=False,
            note=id_res.get('reject_msg') or 'IDENTITY_MISMATCH',
        )
        return jsonify({
            'ok':       False,
            'msg':      id_res.get('reject_msg') or f"Không nhận diện đúng khuôn mặt (Độ khớp: {id_res['display_score']:.1%})",
            'score':    id_res['display_score'],
            'liveness': live_res['liveness_score'],
        }), 400

    # ── 7. Ghi điểm danh vào CSDL MySQL & File CSV Nhật ký AI ────────────────
    final_score = id_res['display_score']
    db.session.add(Attendance(
        student_id   = sid,
        class_id     = int(class_id),
        session_id   = int(session_id),
        session_date = sess.session_date,
        status       = 'present',
        checkin_time = datetime.utcnow(),
        method       = 'face',
        face_score   = final_score,
        note         = f"SFace128D cos={id_res['cosine_score']:.3f} svm={id_res['model_prob']:.2f} live={live_res['liveness_score']:.2f}",
    ))
    db.session.commit()

    append_attendance_ai_log_csv(
        student_id=sid,
        student_code=current_user.student_code or '',
        full_name=current_user.full_name,
        class_name=cls.class_name,
        session_id=sess.id,
        cosine_score=id_res['cosine_score'],
        model_prob=id_res['model_prob'],
        liveness_score=live_res['liveness_score'],
        accepted=True,
        note='VERIFIED_LIVE_HUMAN',
    )

    return jsonify({
        'ok':       True,
        'msg':      f"Điểm danh người thật thành công! Độ khớp AI: {final_score:.1%} · Liveness: {live_res['liveness_score']:.0%}",
        'score':    final_score,
        'liveness': live_res['liveness_score'],
        'time':     datetime.now().strftime('%H:%M:%S'),
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
    sid = current_user.id
    face_rec = FaceData.query.filter_by(student_id=sid).first()
    has_face = bool(face_rec and face_rec.embedding_model == 'sface_onnx_128d')
    sample_count = FaceSample.query.filter_by(student_id=sid).count()
    from services.face_service import get_backend_info
    return render_template('student/register_face.html',
        has_face=has_face,
        face_rec=face_rec,
        sample_count=sample_count,
        backend_info=get_backend_info(),
    )


@attendance_bp.route('/register-face/submit', methods=['POST'])
@login_required
@student_required
def register_face_submit():
    """
    Đăng ký sinh trắc học đa góc mặt (Multi-Angle Live Enrollment):
      1. Nhận chuỗi 5 khung hình sống (Chính diện, Hơi nghiêng trái, Hơi nghiêng phải, Cười nhẹ / Biểu cảm tự nhiên).
      2. Kiểm tra Liveness & Anti-Spoofing (chặn tuyệt đối đăng ký bằng ảnh chụp/điện thoại!).
      3. Lưu đầy đủ từng vector mẫu 128D vào bảng `face_samples` + vector trung tâm vào `face_data` trong MySQL.
      4. Đồng bộ ngay ra `face_embeddings.csv` & `face_registry.csv` và TỰ ĐỘNG TRAIN lại Model AI `face_classifier.pkl`!
    """
    import pickle
    import numpy as np
    from services.face_service import (
        decode_image,
        detect_and_extract_sface,
        analyze_passive_antispoof,
        verify_liveness_sequence,
        train_face_recognition_model,
    )

    data       = request.get_json() or {}
    frames_b64 = data.get('frames') or []
    poses      = data.get('poses') or []
    single_img = data.get('image')

    if not frames_b64 and single_img:
        frames_b64 = [single_img]
        poses = ['frontal']

    if not frames_b64:
        return jsonify({'ok': False, 'msg': 'Không nhận được dữ liệu khung hình từ camera.'}), 400

    try:
        frames_rgb = [decode_image(b64) for b64 in frames_b64[:8]]
    except Exception as e:
        return jsonify({'ok': False, 'msg': f'Lỗi xử lý khung hình: {e}'}), 400

    # Nếu gửi từ 3 khung hình trở lên -> chạy kiểm định Liveness người thật nghiêm ngặt
    liveness_score = 0.90
    if len(frames_rgb) >= 3:
        live_check = verify_liveness_sequence(frames_rgb, challenge_mode='auto')
        if not live_check['is_live']:
            return jsonify({'ok': False, 'msg': live_check['reason']}), 400
        liveness_score = live_check['liveness_score']

    extracted_samples = []
    for idx, frm in enumerate(frames_rgb):
        emb, meta, err = detect_and_extract_sface(frm)
        if err or emb is None:
            return jsonify({'ok': False, 'msg': f'Mẫu góc chụp #{idx + 1}: {err}'}), 400
        p_score, warns = analyze_passive_antispoof(frm, meta)
        if p_score < 0.50:
            return jsonify({
                'ok': False,
                'msg': f'Mẫu #{idx + 1} không đạt chuẩn người thật: {warns[0] if warns else "Nghi ngờ ảnh tĩnh/màn hình"}',
            }), 400
        pose_lbl = poses[idx] if idx < len(poses) else f'angle_{idx + 1}'
        extracted_samples.append((pose_lbl, emb, float(meta['det_score']), p_score))

    # Đảm bảo tất cả các góc chụp đều thuộc về CÙNG 1 NGƯỜI đang đăng ký
    ref_vec = extracted_samples[0][1]
    for idx, (_pl, vec, _ds, _ps) in enumerate(extracted_samples[1:], start=2):
        if float(np.dot(ref_vec, vec)) < 0.50:
            return jsonify({
                'ok': False,
                'msg': f'Mẫu góc #{idx} không đồng nhất với khuôn mặt đầu tiên. Vui lòng chỉ để 1 mình bạn trước camera!',
            }), 400

    sid = current_user.id
    # Kiểm tra chống trùng lặp: Không cho phép 1 khuôn mặt đăng ký hộ cho tài khoản sinh viên khác!
    other_faces = FaceData.query.filter(
        FaceData.student_id != sid,
        FaceData.embedding_model == 'sface_onnx_128d',
    ).all()
    mean_vec = np.mean(np.stack([x[1] for x in extracted_samples], axis=0), axis=0).astype(np.float32)
    mean_vec /= max(1e-8, float(np.linalg.norm(mean_vec)))

    for ofd in other_faces:
        try:
            ovec = np.asarray(pickle.loads(ofd.embedding), dtype=np.float32).reshape(-1)
            if ovec.shape[0] == 128:
                sim_other = float(np.dot(mean_vec, ovec / max(1e-8, float(np.linalg.norm(ovec)))))
                if sim_other >= 0.62:
                    return jsonify({
                        'ok': False,
                        'msg': '🚫 Khuôn mặt này đã được đăng ký cho một mã sinh viên khác trên hệ thống! Nghiêm cấm đăng ký hộ.',
                    }), 400
        except Exception:
            continue

    # 1. Lưu toàn bộ các mẫu góc mặt vào bảng `face_samples` trong CSDL MySQL
    FaceSample.query.filter_by(student_id=sid).delete(synchronize_session=False)
    for pose_lbl, vec, det_sc, _ps in extracted_samples:
        db.session.add(FaceSample(
            student_id=sid,
            pose_label=pose_lbl,
            embedding=pickle.dumps(vec),
            quality_score=det_sc,
        ))

    # 2. Lưu vector trung tâm chuẩn 128D vào bảng `face_data` trong CSDL MySQL
    avg_det_conf = float(np.mean([x[2] for x in extracted_samples]))
    existing = FaceData.query.filter_by(student_id=sid).first()
    if existing:
        existing.embedding       = pickle.dumps(mean_vec)
        existing.embedding_model = 'sface_onnx_128d'
        existing.image_count     = len(extracted_samples)
        existing.confidence      = round(avg_det_conf, 4)
        existing.liveness_score  = round(liveness_score, 4)
        existing.is_trained      = False
        existing.updated_at      = datetime.utcnow()
    else:
        db.session.add(FaceData(
            student_id      = sid,
            embedding       = pickle.dumps(mean_vec),
            embedding_model = 'sface_onnx_128d',
            image_count     = len(extracted_samples),
            confidence      = round(avg_det_conf, 4),
            liveness_score  = round(liveness_score, 4),
            is_trained      = False,
        ))
    db.session.commit()

    # 3. Xuất đồng bộ ra `face_embeddings.csv` + `face_registry.csv` và Train lại Model AI ngay lập tức!
    train_info = train_face_recognition_model()

    return jsonify({
        'ok': True,
        'msg': (
            f'✅ Đã lưu {len(extracted_samples)} góc khuôn mặt vào CSDL MySQL, cập nhật file CSV '
            f'và huấn luyện xong Model AI (Tổng {train_info.get("num_students", 1)} SV · Liveness {liveness_score:.0%})!'
        ),
        'samples_saved': len(extracted_samples),
        'train_info': train_info,
    })


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