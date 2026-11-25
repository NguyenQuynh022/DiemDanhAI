"""
scripts/ai/train_face_model.py — Script CLI xuất dữ liệu khuôn mặt từ MySQL ra CSV và huấn luyện Model AI
Chạy trực tiếp: python scripts/ai/train_face_model.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app import create_app
from services.face_service import train_face_recognition_model

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        print("=" * 60)
        print("  EDUPORTAL AI — ĐỒNG BỘ CSV & HUẤN LUYỆN MODEL KHUÔN MẶT")
        print("=" * 60)
        res = train_face_recognition_model()
        for k, v in res.items():
            print(f"  • {k}: {v}")
        print("=" * 60)
