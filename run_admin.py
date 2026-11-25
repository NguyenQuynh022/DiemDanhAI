"""
run_admin.py — Quản trị viên (Phòng Đào tạo)
Truy cập: http://localhost:5000
"""
import os
os.environ['PORT'] = '5000'   # config.py đọc PORT để set SESSION_COOKIE_NAME

from app import create_app

app = create_app()

if __name__ == '__main__':
    print("=" * 48)
    print("  EduPortal — QUẢN TRỊ VIÊN (ADMIN)")
    print("  http://localhost:5000")
    print("  Cookie: eduportal_admin")
    print("=" * 48)
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=True)
