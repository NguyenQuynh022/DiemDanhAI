from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from extensions import login_manager
from models.user import User
from models.announcement import Announcement

auth_bp = Blueprint('auth', __name__)


# ── User loader cho Flask-Login ───────────────────────────────
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ── Redirect sau login theo role ──────────────────────────────
def redirect_by_role(user):
    if user.role == 'student':
        return redirect(url_for('student.dashboard'))
    elif user.role == 'lecturer':
        return redirect(url_for('lecturer.dashboard'))
    elif user.role == 'admin':
        return redirect(url_for('admin.dashboard'))
    return redirect(url_for('auth.portal_home'))


# ── CỔNG THÔNG TIN ĐÀO TẠO CÔNG KHAI (TRANG CHỦ GIỐNG HÌNH 1) ─
@auth_bp.route('/')
@auth_bp.route('/portal')
def portal_home():
    q   = request.args.get('q', '').strip()
    cat = request.args.get('category', '').strip()

    base_q = Announcement.query.filter_by(is_published=True)
    if q:
        like_q = f"%{q}%"
        base_q = base_q.filter(
            (Announcement.title.ilike(like_q)) | (Announcement.content.ilike(like_q))
        )

    if cat in ('academic', 'finance', 'exam', 'scholarship', 'general'):
        filtered_anns = (
            base_q.filter_by(category=cat)
            .order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
            .all()
        )
    else:
        filtered_anns = None

    academic_anns = (
        base_q.filter(Announcement.category.in_(['academic', 'exam', 'scholarship', 'general']))
        .order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
        .limit(12)
        .all()
    )
    finance_anns = (
        base_q.filter_by(category='finance')
        .order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
        .limit(8)
        .all()
    )

    return render_template(
        'portal/home.html',
        academic_anns=academic_anns,
        finance_anns=finance_anns,
        filtered_anns=filtered_anns,
        cat=cat,
        q=q,
    )


@auth_bp.route('/portal/announcement/<int:ann_id>')
def announcement_detail(ann_id):
    ann = Announcement.query.filter_by(id=ann_id, is_published=True).first_or_404()
    related = (
        Announcement.query
        .filter(Announcement.is_published.is_(True), Announcement.id != ann.id)
        .order_by(Announcement.created_at.desc())
        .limit(6)
        .all()
    )
    return render_template('portal/announcement_detail.html', ann=ann, related=related)


# ── CHẶN TUYỆT ĐỐI TỰ ĐĂNG KÝ TÀI KHOẢN ───────────────────────
@auth_bp.route('/register', methods=['GET', 'POST'])
@auth_bp.route('/signup', methods=['GET', 'POST'])
def register_blocked():
    flash(
        'Hệ thống không cho phép tự đăng ký tài khoản. '
        'Tài khoản Giảng viên và Sinh viên do Phòng Đào tạo (Admin) cấp phát.',
        'warning',
    )
    return redirect(url_for('auth.login'))


# ── Login ─────────────────────────────────────────────────────
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect_by_role(current_user)

    role_hint = request.args.get('role', '')

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        if not username or not password:
            flash('Vui lòng nhập đầy đủ tài khoản và mật khẩu.', 'danger')
            return render_template('auth/login.html', role_hint=role_hint)

        user = User.query.filter_by(username=username).first()

        if user is None or not user.check_password(password):
            flash('Tài khoản hoặc mật khẩu không đúng.', 'danger')
            return render_template('auth/login.html', role_hint=role_hint)

        if user.status != 'active':
            flash('Tài khoản của bạn đã bị tạm khóa. Vui lòng liên hệ Phòng Đào tạo (Admin).', 'warning')
            return render_template('auth/login.html', role_hint=role_hint)

        login_user(user, remember=remember)
        flash(f'Chào mừng, {user.full_name}!', 'success')

        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect_by_role(user)

    return render_template('auth/login.html', role_hint=role_hint)


# ── Logout ────────────────────────────────────────────────────
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Đã đăng xuất thành công.', 'info')
    return redirect(url_for('auth.portal_home'))


# ── Error handlers ────────────────────────────────────────────
@auth_bp.app_errorhandler(401)
def unauthorized(e):
    flash('Bạn cần đăng nhập để truy cập trang này.', 'warning')
    return redirect(url_for('auth.login'))


@auth_bp.app_errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403


@auth_bp.app_errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404
