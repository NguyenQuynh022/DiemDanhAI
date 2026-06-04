"""
run_student.py — Sinh viên
Truy cập: http://localhost:5002
"""
import os
os.environ['PORT'] = '5002'   # config.py đọc PORT để set SESSION_COOKIE_NAME

from app import create_app

app = create_app()

if __name__ == '__main__':
    print("=" * 45)
    print("  EduPortal — SINH VIÊN")
    print("  http://localhost:5002")
    print("  Cookie: eduportal_student")
    print("=" * 45)
    app.run(host='0.0.0.0', port=5002, debug=True, use_reloader=False)
