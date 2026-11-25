from .auth_routes       import auth_bp
from .student_routes    import student_bp
from .lecturer_routes   import lecturer_bp
from .attendance_routes import attendance_bp
from .chatbot_routes    import chatbot_bp
from .admin_routes      import admin_bp

__all__ = [
    'auth_bp',
    'student_bp',
    'lecturer_bp',
    'attendance_bp',
    'chatbot_bp',
    'admin_bp',
]
