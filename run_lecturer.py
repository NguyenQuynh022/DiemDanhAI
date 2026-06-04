"""
run_lecturer.py — Giảng viên
Truy cập: http://localhost:5001
"""
import os
os.environ['PORT'] = '5001'   # config.py đọc PORT để set SESSION_COOKIE_NAME

from app import create_app

app = create_app()

if __name__ == '__main__':
    print("=" * 45)
    print("  EduPortal — GIẢNG VIÊN")
    print("  http://localhost:5001")
    print("  Cookie: eduportal_lecturer")
    print("=" * 45)
    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)
