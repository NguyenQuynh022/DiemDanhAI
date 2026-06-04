from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, login_manager
from models.user import User

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
    return redirect(url_for('auth.login'))


# ── Login ─────────────────────────────────────────────────────
@auth_bp.route('/', methods=['GET', 'POST'])
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Nếu đã đăng nhập thì chuyển hướng luôn
    if current_user.is_authenticated:
        return redirect_by_role(current_user)

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        if not username or not password:
            flash('Vui lòng nhập đầy đủ tài khoản và mật khẩu.', 'danger')
            return render_template('auth/login.html')

        user = User.query.filter_by(username=username).first()

        if user is None or not user.check_password(password):
            flash('Tài khoản hoặc mật khẩu không đúng.', 'danger')
            return render_template('auth/login.html')

        if user.status != 'active':
            flash('Tài khoản của bạn đã bị khoá. Liên hệ quản trị viên.', 'warning')
            return render_template('auth/login.html')

        login_user(user, remember=remember)
        flash(f'Chào mừng, {user.full_name}!', 'success')

        # Nếu có "next" param thì dùng, không thì redirect theo role
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect_by_role(user)

    return render_template('auth/login.html')


# ── Logout ────────────────────────────────────────────────────
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Đã đăng xuất thành công.', 'info')
    return redirect(url_for('auth.login'))


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
