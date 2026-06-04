"""
Face Recognition Service
Dùng thư viện face_recognition (dlib) để:
1. Detect khuôn mặt trong ảnh
2. Tạo embedding 128-chiều
3. So sánh khoảng cách giữa hai embedding
"""
import base64
import io
import json
import pickle
import numpy as np
from datetime import datetime

# ── Thử import face_recognition, fallback sang deepface ──────
BACKEND = None

try:
    import face_recognition
    BACKEND = 'face_recognition'
except ImportError:
    pass

if BACKEND is None:
    try:
        from deepface import DeepFace
        BACKEND = 'deepface'
    except ImportError:
        pass

if BACKEND is None:
    try:
        import cv2
        BACKEND = 'opencv'
    except ImportError:
        pass

THRESHOLD = 0.50   # Ngưỡng khoảng cách (face_recognition) — càng nhỏ càng khắt khe
THRESHOLD_DF = 0.60  # Ngưỡng cosine similarity (deepface)


# ── Decode base64 image → numpy array ─────────────────────────
def decode_image(b64_string: str):
    """
    Nhận chuỗi base64 (có hoặc không có prefix data:image/...;base64,)
    Trả về numpy array (H, W, 3) kiểu uint8
    """
    if ',' in b64_string:
        b64_string = b64_string.split(',', 1)[1]
    img_bytes = base64.b64decode(b64_string)
    from PIL import Image
    img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
    return np.array(img)


# ── Tạo embedding từ ảnh ──────────────────────────────────────
def encode_face(image_np):
    """
    Nhận numpy array ảnh.
    Trả về (embedding_bytes, error_message)
    embedding_bytes: pickle.dumps(np.array) hoặc None nếu lỗi
    """
    if BACKEND == 'face_recognition':
        locs = face_recognition.face_locations(image_np, model='hog')
        if not locs:
            return None, 'Không phát hiện khuôn mặt trong ảnh'
        if len(locs) > 1:
            return None, f'Phát hiện {len(locs)} khuôn mặt — chỉ được có 1 khuôn mặt'
        encodings = face_recognition.face_encodings(image_np, known_face_locations=locs)
        if not encodings:
            return None, 'Không thể trích xuất đặc trưng khuôn mặt'
        return pickle.dumps(encodings[0]), None

    elif BACKEND == 'deepface':
        try:
            result = DeepFace.represent(image_np, model_name='Facenet',
                                        enforce_detection=True, detector_backend='opencv')
            if not result:
                return None, 'Không phát hiện khuôn mặt'
            emb = np.array(result[0]['embedding'])
            return pickle.dumps(emb), None
        except Exception as e:
            return None, f'Lỗi DeepFace: {str(e)}'

    elif BACKEND == 'opencv':
        # Fallback: dùng OpenCV Haar cascade (độ chính xác thấp hơn)
        gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = cascade.detectMultiScale(gray, 1.1, 4, minSize=(80, 80))
        if len(faces) == 0:
            return None, 'Không phát hiện khuôn mặt'
        if len(faces) > 1:
            return None, 'Nhiều hơn 1 khuôn mặt trong khung hình'
        x, y, w, h = faces[0]
        face_crop = cv2.resize(image_np[y:y+h, x:x+w], (128, 128))
        emb = face_crop.flatten().astype(np.float32) / 255.0
        return pickle.dumps(emb), None

    else:
        return None, 'Chưa cài thư viện nhận diện khuôn mặt (face_recognition / deepface / opencv)'


# ── So sánh hai embedding ─────────────────────────────────────
def compare_faces(stored_bytes: bytes, new_bytes: bytes):
    """
    Trả về (is_match: bool, score: float, error: str|None)
    score: khoảng cách (0 = giống hệt, 1 = khác hoàn toàn)
    """
    try:
        stored = pickle.loads(stored_bytes)
        new    = pickle.loads(new_bytes)

        if BACKEND == 'face_recognition':
            dist = float(np.linalg.norm(stored - new))
            return dist < THRESHOLD, round(1 - dist, 4), None

        elif BACKEND in ('deepface', 'opencv'):
            # Cosine similarity
            dot = float(np.dot(stored, new))
            norm = (np.linalg.norm(stored) * np.linalg.norm(new))
            similarity = dot / norm if norm > 0 else 0.0
            return similarity >= THRESHOLD_DF, round(similarity, 4), None

        else:
            return False, 0.0, 'Backend chưa được khởi tạo'
    except Exception as e:
        return False, 0.0, f'Lỗi so sánh: {str(e)}'


# ── Thông tin backend đang dùng ───────────────────────────────
def get_backend_info():
    return {
        'backend': BACKEND or 'none',
        'available': BACKEND is not None,
        'threshold': THRESHOLD if BACKEND == 'face_recognition' else THRESHOLD_DF,
    }
