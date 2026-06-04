from functools import wraps
from flask import abort
from flask_login import current_user


def role_required(*roles):
    """
    Decorator kiểm tra role của user hiện tại.
    Dùng: @role_required('lecturer')  hoặc  @role_required('student', 'admin')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            if current_user.status != 'active':
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def student_required(f):
    return role_required('student')(f)


def lecturer_required(f):
    return role_required('lecturer')(f)


def admin_required(f):
    return role_required('admin')(f)
