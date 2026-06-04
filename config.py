import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')

    DB_HOST     = os.getenv('DB_HOST',     'localhost')
    DB_PORT     = os.getenv('DB_PORT',     '3306')
    DB_USER     = os.getenv('DB_USER',     'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'Quynh12345')
    DB_NAME     = os.getenv('DB_NAME',     'attendance_system')

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    AI_PROVIDER       = os.getenv('AI_PROVIDER', 'anthropic').strip().lower()
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '').strip()
    GROQ_API_KEY      = os.getenv('GROQ_API_KEY',      '').strip()
    GEMINI_API_KEY    = os.getenv('GEMINI_API_KEY',    '').strip()

    # Session
    SESSION_COOKIE_HTTPONLY  = True
    SESSION_COOKIE_SAMESITE  = 'Lax'
    REMEMBER_COOKIE_DURATION = 86400  # 1 ngày (giây)

    # Tách cookie theo port → GV (:5001) và SV (:5002) không đá session nhau
    # khi dùng chung máy / chung trình duyệt
    _PORT_COOKIE = {
        '5001': 'eduportal_lecturer',
        '5002': 'eduportal_student',
    }
    SESSION_COOKIE_NAME = _PORT_COOKIE.get(
        os.getenv('PORT', '5000'),
        'eduportal_session',   # fallback khi chạy port khác (dev mặc định)
    )