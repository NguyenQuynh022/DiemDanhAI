from flask import Flask
from config import Config
from extensions import db, login_manager


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    from routes.auth_routes       import auth_bp
    from routes.student_routes    import student_bp
    from routes.lecturer_routes   import lecturer_bp
    from routes.attendance_routes import attendance_bp
    from routes.chatbot_routes    import chatbot_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(lecturer_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(chatbot_bp)

    with app.app_context():
        from models.user         import User
        from models.class_model  import Class
        from models.enrollment   import Enrollment
        from models.session      import Session
        from models.grade        import Grade
        from models.attendance   import Attendance
        from models.notification import Notification
        from models.audit_log    import AuditLog
        from models.face_data    import FaceData
        db.create_all()

    # Inject global template variables
    @app.context_processor
    def inject_globals():
        from datetime import timedelta
        return {'timedelta': timedelta}

    # Inject unread notification count into all student templates
    @app.context_processor
    def inject_unread():
        from flask_login import current_user
        if current_user.is_authenticated and current_user.role == 'student':
            from models.notification import Notification
            try:
                cnt = Notification.query.filter_by(
                    user_id=current_user.id, is_read=False).count()
                return {'unread_count': cnt}
            except Exception:
                pass
        return {'unread_count': 0}

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
