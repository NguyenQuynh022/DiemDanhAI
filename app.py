from flask import Flask
from config import Config
from extensions import db, login_manager


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    from routes import (
        auth_bp,
        student_bp,
        lecturer_bp,
        attendance_bp,
        chatbot_bp,
        admin_bp,
    )

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(lecturer_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(chatbot_bp)
    app.register_blueprint(admin_bp)

    with app.app_context():
        import models  # noqa: F401
        db.create_all()

    # Inject global template variables (timedelta, current semester, academic week & registration status)
    @app.context_processor
    def inject_globals():
        from datetime import date, timedelta
        from utils.timetable import (
            get_all_semesters,
            get_current_semester_id,
            format_semester_label,
            get_semester_start,
        )
        from models.registration_config import RegistrationConfig

        today = date.today()
        cur_sem_id = get_current_semester_id(today)
        cur_sem_label = format_semester_label(cur_sem_id)
        all_sems = get_all_semesters()

        try:
            s_start = get_semester_start(cur_sem_id)
            cur_week = max(1, ((today - s_start).days // 7) + 1)
        except Exception:
            cur_week = 1

        reg_open = False
        try:
            open_cfgs = RegistrationConfig.query.filter_by(is_open=True).all()
            reg_open = any(c.is_active_now for c in open_cfgs)
        except Exception:
            pass

        return {
            'timedelta': timedelta,
            'global_semesters': all_sems,
            'global_sem_id': cur_sem_id,
            'global_sem_label': cur_sem_label,
            'global_week_num': cur_week,
            'global_reg_open': reg_open,
        }

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
