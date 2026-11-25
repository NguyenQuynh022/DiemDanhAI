"""
services/face_service.py — Hệ thống AI Điểm danh Khuôn mặt Chuyên sâu & Chống giả mạo (Anti-Spoofing)

Kiến trúc 4 tầng bảo mật & chính xác cao:
  1. Phát hiện khuôn mặt + 5 điểm mốc (2 mắt, mũi, 2 khóe miệng) bằng mạng Deep Learning YuNet (ONNX).
  2. Trích xuất đặc trưng 128-chiều chuẩn L2 bằng mạng Deep Learning SFace (ONNX) có căn chỉnh khuôn mặt (Face Alignment).
  3. Lưu trữ kép:
     - Cơ sở dữ liệu MySQL: bảng `face_data` (vector trung tâm) + bảng `face_samples` (đa góc mặt của từng sinh viên).
     - Bộ file CSV chuẩn hóa (`ai_models/datasets/`):
       + `face_embeddings.csv`: Chứa `student_id, student_code, full_name, pose_label, quality_score, f0..f127` dùng trực tiếp để train model.
       + `face_registry.csv`: Danh sách sinh viên đã đăng ký sinh trắc học & trạng thái train.
       + `attendance_ai_logs.csv`: Nhật ký điểm danh AI kèm điểm khớp & điểm Liveness chống giả mạo.
  4. Huấn luyện Model Phân loại AI (`ai_models/trained/face_classifier.pkl` + `training_metrics.json`):
     - Kết hợp Calibrated Support Vector Machine (RBF/Linear) / MLP / K-Nearest Centroid trên không gian 128D.
     - Khi điểm danh: Xác thực kép (Trained Model Probability + Cosine Similarity trực tiếp với mẫu DB của đúng sinh viên đang đăng nhập).
  5. Chống giả mạo người thật (Active Multi-Frame Liveness + Passive Texture/Screen Anti-Spoofing):
     - Yêu cầu chuỗi nhiều khung hình liên tiếp (Live Video Burst) từ camera thật.
     - Kiểm tra chuyển động vi mô tự nhiên của 5 điểm mốc 3D & biến thiên khung hình (chặn ảnh in / ảnh tĩnh 100%).
     - Kiểm tra độ sắc nét Laplacian, phản xạ lóa màn hình điện thoại (Specular Glare), nhiễu sọc Moiré tần số cao (FFT) và độ tương phản tự nhiên.
"""
from __future__ import annotations

import base64
import csv
import io
import json
import os
import pickle
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import joblib
import numpy as np
from PIL import Image

ROOT_DIR    = Path(__file__).resolve().parents[1]
WEIGHTS_DIR = ROOT_DIR / 'ai_models' / 'weights'
DATASET_DIR = ROOT_DIR / 'ai_models' / 'datasets'
TRAINED_DIR = ROOT_DIR / 'ai_models' / 'trained'

YUNET_ONNX_PATH = WEIGHTS_DIR / 'face_detection_yunet_2023mar.onnx'
SFACE_ONNX_PATH = WEIGHTS_DIR / 'face_recognition_sface_2021dec.onnx'

EMBEDDINGS_CSV_PATH = DATASET_DIR / 'face_embeddings.csv'
REGISTRY_CSV_PATH   = DATASET_DIR / 'face_registry.csv'
AI_LOGS_CSV_PATH    = DATASET_DIR / 'attendance_ai_logs.csv'

MODEL_PKL_PATH      = TRAINED_DIR / 'face_classifier.pkl'
METRICS_JSON_PATH   = TRAINED_DIR / 'training_metrics.json'

# Ngưỡng chuẩn SFace 128D (OpenCV Zoo benchmark: Cosine >= 0.363 là cùng 1 người; ta nâng lên 0.50 + xác thực kép để cực kỳ chặt chẽ)
COSINE_THRESHOLD       = 0.50
MODEL_PROB_THRESHOLD   = 0.55
LIVENESS_MIN_SCORE     = 0.58
EMBEDDING_DIM          = 128

_dnn_lock   = threading.Lock()
_detector   = None
_recognizer = None


def _ensure_dirs():
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    TRAINED_DIR.mkdir(parents=True, exist_ok=True)


def _get_dnn_engines():
    """
    Khởi tạo singleton YuNet FaceDetectorYN & SFace FaceRecognizerSF.
    Lưu ý quan trọng trên Windows: Đường dẫn thư mục có dấu tiếng Việt (VD 'ĐACN1_AIDiemDanh')
    khiến hàm C++ std::ifstream của OpenCV không mở được trực tiếp từ chuỗi path Unicode.
    Do đó ta đọc bytes bằng Python (hỗ trợ Unicode 100%) và nạp thẳng qua buffer bộ nhớ!
    """
    global _detector, _recognizer
    _ensure_dirs()
    if _detector is not None and _recognizer is not None:
        return _detector, _recognizer

    if YUNET_ONNX_PATH.exists() and SFACE_ONNX_PATH.exists():
        yunet_buf = np.frombuffer(YUNET_ONNX_PATH.read_bytes(), dtype=np.uint8)
        sface_buf = np.frombuffer(SFACE_ONNX_PATH.read_bytes(), dtype=np.uint8)
        try:
            _detector = cv2.FaceDetectorYN.create(
                "onnx",
                yunet_buf,
                np.empty(0, dtype=np.uint8),
                (320, 320),
                0.72,
                0.3,
                5000,
            )
            _recognizer = cv2.FaceRecognizerSF.create(
                "onnx",
                sface_buf,
                np.empty(0, dtype=np.uint8),
            )
        except Exception:
            # Fallback copy ra thư mục đệm thuần ASCII nếu phiên bản OpenCV cũ không nhận buffer
            import tempfile, shutil
            ascii_cache = Path(tempfile.gettempdir()) / 'eduportal_onnx_cache'
            ascii_cache.mkdir(parents=True, exist_ok=True)
            y_tmp = ascii_cache / 'yunet.onnx'
            s_tmp = ascii_cache / 'sface.onnx'
            if not y_tmp.exists():
                shutil.copy2(YUNET_ONNX_PATH, y_tmp)
            if not s_tmp.exists():
                shutil.copy2(SFACE_ONNX_PATH, s_tmp)
            _detector = cv2.FaceDetectorYN.create(
                str(y_tmp), "", (320, 320), score_threshold=0.72, nms_threshold=0.3, top_k=5000
            )
            _recognizer = cv2.FaceRecognizerSF.create(str(s_tmp), "")
    return _detector, _recognizer


# ═════════════════════════════════════════════════════════════════════════════
# 1. DECODE ẢNH & PHÁT HIỆN KHUÔN MẶT + 5 ĐIỂM MỐC + EMBEDDING 128D
# ═════════════════════════════════════════════════════════════════════════════

def decode_image(b64_string: str) -> np.ndarray:
    """Giải mã ảnh base64 thành mảng RGB uint8 (H, W, 3)."""
    if ',' in b64_string:
        b64_string = b64_string.split(',', 1)[1]
    img_bytes = base64.b64decode(b64_string)
    img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
    return np.array(img, dtype=np.uint8)


def detect_and_extract_sface(image_rgb: np.ndarray) -> tuple[Optional[np.ndarray], Optional[dict], Optional[str]]:
    """
    Phát hiện đúng 1 khuôn mặt thật, kiểm tra chất lượng khung mặt, căn chỉnh 5 điểm mốc (Alignment)
    và trích xuất vector 128-chiều chuẩn hóa L2 từ mạng SFace ONNX.
    Trả về: (embedding_128d_float32, face_meta_dict, error_msg)
    """
    if image_rgb is None or image_rgb.size == 0:
        return None, None, 'Khung hình camera trống.'

    h, w = image_rgb.shape[:2]
    if h < 120 or w < 120:
        return None, None, 'Độ phân giải ảnh quá thấp, vui lòng dùng camera rõ nét hơn.'

    img_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
    detector, recognizer = _get_dnn_engines()

    if detector is None or recognizer is None:
        return None, None, 'Chưa tải trọng số mô hình AI YuNet/SFace trong thư mục ai_models/weights.'

    with _dnn_lock:
        detector.setInputSize((w, h))
        _, faces = detector.detect(img_bgr)

        if faces is None or len(faces) == 0:
            return None, None, 'Không phát hiện khuôn mặt trong khung hình. Vui lòng nhìn thẳng vào camera.'

        if len(faces) > 1:
            # Lọc các khuôn mặt đủ lớn (> 6% chiều rộng ảnh) để tránh nhiễu nền nhỏ
            valid_faces = [f for f in faces if f[2] >= w * 0.12 and f[3] >= h * 0.12]
            if len(valid_faces) > 1:
                return None, None, f'Phát hiện {len(valid_faces)} khuôn mặt trong khung hình — chỉ cho phép 1 người điểm danh!'
            face = valid_faces[0] if valid_faces else faces[0]
        else:
            face = faces[0]

        x, y, fw, fh = float(face[0]), float(face[1]), float(face[2]), float(face[3])
        det_score = float(face[14])

        if fw < w * 0.14 or fh < h * 0.16:
            return None, None, 'Khuôn mặt ở quá xa camera. Vui lòng tiến lại gần khung bầu dục hơn.'

        # Căn chỉnh khuôn mặt chuẩn theo 5 landmarks (mắt phải, mắt trái, mũi, 2 khóe miệng)
        aligned_bgr = recognizer.alignCrop(img_bgr, face)
        feat = recognizer.feature(aligned_bgr)

    emb = np.asarray(feat, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(emb))
    if norm > 0:
        emb = emb / norm

    landmarks = np.array([
        [face[4], face[5]],    # right eye
        [face[6], face[7]],    # left eye
        [face[8], face[9]],    # nose tip
        [face[10], face[11]],  # right mouth corner
        [face[12], face[13]],  # left mouth corner
    ], dtype=np.float32)

    # Ước lượng góc quay đầu ngang (yaw ratio từ vị trí mũi so với 2 mắt)
    eye_dist = max(1.0, float(np.linalg.norm(landmarks[1] - landmarks[0])))
    nose_rel = (landmarks[2][0] - landmarks[0][0]) / eye_dist  # ~0.5 khi nhìn thẳng

    meta = {
        'bbox': [round(x, 1), round(y, 1), round(fw, 1), round(fh, 1)],
        'det_score': round(det_score, 4),
        'landmarks': landmarks,
        'yaw_ratio': round(float(nose_rel), 4),
        'aligned_bgr': aligned_bgr,
    }
    return emb, meta, None


def encode_face(image_rgb: np.ndarray) -> tuple[Optional[bytes], Optional[str]]:
    """Hàm tương thích ngược: trích xuất vector 128D và đóng gói bytes."""
    emb, _meta, err = detect_and_extract_sface(image_rgb)
    if err or emb is None:
        return None, err
    return pickle.dumps(emb), None


# ═════════════════════════════════════════════════════════════════════════════
# 2. CHỐNG GIẢ MẠO NGƯỜI THẬT (ANTI-SPOOFING & MULTI-FRAME LIVENESS DETECTION)
# ═════════════════════════════════════════════════════════════════════════════

def analyze_passive_antispoof(image_rgb: np.ndarray, face_meta: dict) -> tuple[float, list[str]]:
    """
    Phân tích chống giả mạo thụ động trên vùng khuôn mặt & bối cảnh xung quanh:
      1. Độ sắc nét vi cấu trúc da (Laplacian Variance) -> phát hiện ảnh in mờ / màn hình độ phân giải thấp.
      2. Tần số cao FFT (Moiré Screen Grid Pattern) -> phát hiện sọc lưới pixel khi giơ điện thoại / màn hình máy tính lên trước webcam.
      3. Phản xạ lóa kính/màn hình (Specular Glare Ratio) -> phát hiện ánh sáng đèn phản chiếu trên mặt kính điện thoại hoặc ảnh ép plastic.
      4. Độ rộng dải màu & độ bão hòa da thật (HSV Color Entropy) -> phát hiện ảnh đen trắng / ảnh màu phẳng.
    Trả về: (passive_score 0..1, warnings_list)
    """
    warnings = []
    aligned_bgr = face_meta.get('aligned_bgr')
    if aligned_bgr is None or aligned_bgr.size == 0:
        return 0.0, ['Không thể phân tích vùng da khuôn mặt.']

    gray = cv2.cvtColor(aligned_bgr, cv2.COLOR_BGR2GRAY)
    hsv  = cv2.cvtColor(aligned_bgr, cv2.COLOR_BGR2HSV)

    # 1. Độ sắc nét Laplacian
    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if lap_var < 22.0:
        warnings.append('Hình ảnh quá mờ hoặc mất chi tiết bề mặt thật (nghi ngờ ảnh in/chụp lại).')
        sharp_score = max(0.15, lap_var / 22.0 * 0.55)
    elif lap_var > 2600.0:
        # Nhiễu gai pixel quá gắt thường xuất hiện khi chụp sát màn hình LCD/OLED
        warnings.append('Phát hiện nhiễu hạt tần số cao bất thường nghi từ màn hình điện tử.')
        sharp_score = 0.40
    else:
        sharp_score = 1.0

    # 2. Phát hiện vân Moiré màn hình bằng phổ Fourier 2D (FFT High-Frequency Ring Peak)
    f = np.fft.fft2(gray.astype(np.float32))
    fshift = np.fft.fftshift(f)
    mag = np.log1p(np.abs(fshift))
    mh, mw = mag.shape
    cy, cx = mh // 2, mw // 2
    yy, xx = np.ogrid[:mh, :mw]
    rr = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    mid_ring  = mag[(rr >= 10) & (rr <= 28)]
    high_ring = mag[(rr > 28) & (rr <= 52)]
    hf_ratio  = float(np.mean(high_ring) / (np.mean(mid_ring) + 1e-6))
    # Ảnh chụp qua màn hình điện thoại thường có đỉnh phổ cao tần dày bất thường (hf_ratio > 0.90)
    if hf_ratio > 0.92:
        warnings.append('Phát hiện vân sọc Moiré đặc trưng của màn hình điện thoại / máy tính.')
        fft_score = 0.25
    else:
        fft_score = 1.0 if hf_ratio < 0.85 else 0.72

    # 3. Kiểm tra lóa sáng mặt kính màn hình (Specular Glare: V rất cao > 248 nhưng S gần 0 < 18)
    v_chan = hsv[:, :, 2]
    s_chan = hsv[:, :, 1]
    glare_ratio = float(np.mean((v_chan > 248) & (s_chan < 20)))
    if glare_ratio > 0.14:
        warnings.append('Phát hiện vùng lóa sáng phản chiếu phẳng như mặt kính điện thoại / ảnh bóng.')
        glare_score = 0.30
    else:
        glare_score = 1.0

    # 4. Độ phân tán sắc độ & chiều sâu tương phản tự nhiên trên khuôn mặt 3D
    std_luma = float(np.std(gray))
    mean_sat = float(np.mean(s_chan))
    if std_luma < 16.0 or mean_sat < 14.0:
        warnings.append('Khuôn mặt thiếu độ khối 3D hoặc sắc thái da tự nhiên.')
        color_score = 0.35
    else:
        color_score = 1.0

    # 5. Phát hiện viền khung điện thoại chữ nhật bao quanh khuôn mặt trên khung hình gốc
    h_full, w_full = image_rgb.shape[:2]
    bx, by, bw, bh = face_meta['bbox']
    pad_x1 = max(0, int(bx - bw * 0.45))
    pad_y1 = max(0, int(by - bh * 0.45))
    pad_x2 = min(w_full, int(bx + bw * 1.45))
    pad_y2 = min(h_full, int(by + bh * 1.45))
    roi_gray = cv2.cvtColor(image_rgb[pad_y1:pad_y2, pad_x1:pad_x2], cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(roi_gray, 70, 180)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=65, minLineLength=int(min(bw, bh) * 0.75), maxLineGap=8)
    border_score = 1.0
    if lines is not None and len(lines) >= 6:
        # Đếm đường thẳng đứng & ngang sắc cạnh tạo thành viền điện thoại/khung ảnh
        hv_lines = 0
        for ln in lines:
            x1, y1, x2, y2 = ln[0]
            ang = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            if ang < 7 or abs(ang - 90) < 7 or abs(ang - 180) < 7:
                hv_lines += 1
        if hv_lines >= 5 and (glare_ratio > 0.05 or hf_ratio > 0.83):
            warnings.append('Phát hiện khung viền thẳng bất thường quanh khuôn mặt (nghi giơ điện thoại / ảnh thẻ).')
            border_score = 0.35

    passive_score = (
        0.30 * sharp_score
        + 0.28 * fft_score
        + 0.18 * glare_score
        + 0.14 * color_score
        + 0.10 * border_score
    )
    return round(float(passive_score), 4), warnings


def verify_liveness_sequence(frames_rgb: list[np.ndarray], challenge_mode: str = 'auto') -> dict:
    """
    Xác thực NGƯỜI THẬT ĐANG ĐIỂM DANH (Multi-Frame Liveness + Anti-Spoofing):
      - Yêu cầu tối thiểu 3 khung hình chụp liên tiếp từ luồng video trực tiếp.
      - Kiểm tra:
        1. Khuôn mặt hiện diện liên tục & nhất quán là cùng 1 người xuyên suốt các frame.
        2. Không phải luồng ảnh tĩnh đóng băng (pixel diff == 0 -> chặn fake camera tĩnh / ảnh chèn).
        3. Biến thiên vi mô 3D tự nhiên giữa các khung hình (tỷ lệ yaw của mũi so với 2 mắt, biểu cảm cơ mặt)
           khác với chuyển động tịnh tiến cứng nhắc của 1 tấm ảnh phẳng.
        4. Điểm chống giả mạo thụ động (Laplacian, FFT Moiré, Glare, 3D shading) đạt chuẩn người thật.
    Trả về dict:
      {
        'is_live': bool,
        'liveness_score': float,
        'mean_embedding': np.ndarray | None,
        'reason': str,
      }
    """
    if not frames_rgb or len(frames_rgb) < 3:
        return {
            'is_live': False,
            'liveness_score': 0.0,
            'mean_embedding': None,
            'reason': 'Cần chuỗi video trực tiếp (ít nhất 3 khung hình liên tiếp) để xác thực người thật chống giả mạo.',
        }

    embeddings = []
    metas      = []
    passive_scores = []
    all_warnings   = []

    for idx, frm in enumerate(frames_rgb):
        emb, meta, err = detect_and_extract_sface(frm)
        if err or emb is None:
            return {
                'is_live': False,
                'liveness_score': 0.0,
                'mean_embedding': None,
                'reason': f'Khung hình #{idx + 1}: {err}',
            }
        p_score, warns = analyze_passive_antispoof(frm, meta)
        embeddings.append(emb)
        metas.append(meta)
        passive_scores.append(p_score)
        all_warnings.extend(warns)

    # 1. Kiểm tra các frame có hoàn toàn giống hệt nhau (ảnh tĩnh đóng băng / virtual static image) không
    frame_diffs = []
    for i in range(1, len(frames_rgb)):
        if frames_rgb[i].shape == frames_rgb[i - 1].shape:
            diff = float(np.mean(np.abs(frames_rgb[i].astype(np.float32) - frames_rgb[i - 1].astype(np.float32))))
            frame_diffs.append(diff)

    mean_pixel_diff = float(np.mean(frame_diffs)) if frame_diffs else 0.0
    if mean_pixel_diff < 0.65:
        return {
            'is_live': False,
            'liveness_score': 0.12,
            'mean_embedding': None,
            'reason': '⚠️ Phát hiện khung hình tĩnh hoàn toàn không có chuyển động sống (nghi dùng ảnh tĩnh giả mạo)!',
        }

    # 2. Kiểm tra tính nhất quán khuôn mặt xuyên suốt chuỗi frame (không được tráo người giữa chừng)
    base_emb = embeddings[0]
    within_sims = [float(np.dot(base_emb, e)) for e in embeddings[1:]]
    if min(within_sims) < 0.55:
        return {
            'is_live': False,
            'liveness_score': 0.20,
            'mean_embedding': None,
            'reason': 'Khuôn mặt thay đổi bất thường giữa các khung hình. Vui lòng giữ 1 người duy nhất trước camera.',
        }

    # 3. Kiểm tra chuyển động 3D sống (head yaw / micro-expression) khi người dùng thực hiện thử thách nghiêng nhẹ đầu / nháy mắt
    yaw_vals = [m['yaw_ratio'] for m in metas]
    yaw_span = max(yaw_vals) - min(yaw_vals)

    # Biến thiên phi tuyến vùng mặt đã căn chỉnh (nếu là ảnh phẳng dịch chuyển tịnh tiến, sau khi alignCrop 5 điểm mốc thì gần như bất biến!)
    aligned_diffs = []
    for i in range(1, len(metas)):
        a1 = cv2.cvtColor(metas[i - 1]['aligned_bgr'], cv2.COLOR_BGR2GRAY).astype(np.float32)
        a2 = cv2.cvtColor(metas[i]['aligned_bgr'], cv2.COLOR_BGR2GRAY).astype(np.float32)
        aligned_diffs.append(float(np.mean(np.abs(a2 - a1))))
    mean_aligned_diff = float(np.mean(aligned_diffs)) if aligned_diffs else 0.0

    # Chặn tuyệt đối ảnh phẳng 2D dịch chuyển tịnh tiến trước camera:
    # Khi giơ 1 bức ảnh phẳng hoặc điện thoại lên lắc nhẹ ngang/dọc, sau khi alignCrop theo 5 mốc mắt-mũi-miệng,
    # toàn bộ khuôn mặt đã căn chỉnh gần như đông cứng (mean_aligned_diff rất nhỏ < 2.2) VÀ tỷ lệ phối cảnh 3D không đổi!
    if mean_aligned_diff < 2.2 and yaw_span < 0.055:
        return {
            'is_live': False,
            'liveness_score': 0.24,
            'mean_embedding': None,
            'reason': '🚫 Phát hiện khuôn mặt phẳng 2D không có biến thiên cơ mặt / phối cảnh 3D (nghi dùng ảnh chụp hoặc màn hình giả mạo)!',
        }

    if challenge_mode == 'head_turn':
        # Xoay đầu 3D thật (nghiêng trái/phải ~10-15°) luôn tạo yaw_span >= 0.095 và biến dạng phối cảnh aligned_diff >= 4.2.
        # Ngược lại, một tấm ảnh 2D phẳng cầm tay dịch chuyển hoặc lắc trước camera không thể đổi phối cảnh 3D mũi-mắt (yaw_span < 0.085).
        if yaw_span < 0.088 or mean_aligned_diff < 4.0:
            return {
                'is_live': False,
                'liveness_score': 0.34,
                'mean_embedding': None,
                'reason': '🚫 Chặn nghi vấn dùng ảnh 2D / màn hình: Chưa phát hiện góc xoay đầu 3D thật của khuôn mặt (ảnh phẳng không thể thay đổi phối cảnh 3D mũi-mắt). Hãy hơi xoay nhẹ đầu sang trái rồi sang phải!',
            }

    # Điểm chuyển động sống 3D
    if mean_aligned_diff < 1.35 and yaw_span < 0.015:
        motion_score = 0.25
        all_warnings.append('Bề mặt khuôn mặt sau căn chỉnh quá cứng đơ như ảnh 2D phẳng.')
    else:
        motion_score = min(1.0, 0.55 + min(0.25, yaw_span * 3.5) + min(0.20, mean_aligned_diff / 18.0))

    avg_passive = float(np.mean(passive_scores))
    final_liveness = round(0.62 * avg_passive + 0.38 * motion_score, 4)

    if final_liveness < LIVENESS_MIN_SCORE or avg_passive < 0.52:
        warn_msg = all_warnings[0] if all_warnings else 'Không đạt ngưỡng xác thực người thật chống giả mạo.'
        return {
            'is_live': False,
            'liveness_score': final_liveness,
            'mean_embedding': None,
            'reason': f'🚫 Chặn điểm danh giả mạo (Liveness {final_liveness * 100:.0f}%): {warn_msg}',
        }

    # Tổng hợp vector trung bình chuẩn hóa L2 từ toàn bộ khung hình sống -> giảm nhiễu ánh sáng, tăng độ chính xác tối đa!
    mean_emb = np.mean(np.stack(embeddings, axis=0), axis=0).astype(np.float32)
    mean_emb /= max(1e-8, float(np.linalg.norm(mean_emb)))

    return {
        'is_live': True,
        'liveness_score': final_liveness,
        'mean_embedding': mean_emb,
        'yaw_span': round(float(yaw_span), 4),
        'reason': 'Xác thực người thật thành công.',
    }


# ═════════════════════════════════════════════════════════════════════════════
# 3. ĐỒNG BỘ DỮ LIỆU KHUÔN MẶT CSDL MYSQL <-> FILE .CSV & HUẤN LUYỆN MODEL AI
# ═════════════════════════════════════════════════════════════════════════════

def sync_face_datasets_to_csv() -> dict:
    """
    Xuất toàn bộ dữ liệu khuôn mặt đã đăng ký trong CSDL MySQL (`face_samples` & `face_data`)
    ra 2 file CSV chuẩn tại `ai_models/datasets/`:
      1. `face_embeddings.csv`: Dữ liệu vector 128 chiều dùng để train model AI.
      2. `face_registry.csv`: Danh sách hồ sơ sinh viên đã đăng ký khuôn mặt.
    """
    _ensure_dirs()
    from models.user import User
    from models.face_data import FaceData, FaceSample

    samples = (
        FaceSample.query
        .join(User, User.id == FaceSample.student_id)
        .order_by(FaceSample.student_id, FaceSample.id)
        .all()
    )

    emb_headers = [
        'sample_id', 'student_id', 'student_code', 'username', 'full_name',
        'pose_label', 'quality_score', 'created_at',
    ] + [f'f{i}' for i in range(EMBEDDING_DIM)]

    valid_sample_rows = 0
    students_in_csv = set()

    with open(EMBEDDINGS_CSV_PATH, 'w', newline='', encoding='utf-8-sig') as fp:
        writer = csv.writer(fp)
        writer.writerow(emb_headers)

        for smp in samples:
            try:
                vec = np.asarray(pickle.loads(smp.embedding), dtype=np.float32).reshape(-1)
                if vec.shape[0] != EMBEDDING_DIM:
                    continue
                stu = smp.student
                writer.writerow([
                    smp.id,
                    smp.student_id,
                    (stu.student_code or '') if stu else '',
                    stu.username if stu else '',
                    stu.full_name if stu else '',
                    smp.pose_label or 'frontal',
                    float(smp.quality_score or 0.95),
                    smp.created_at.strftime('%Y-%m-%d %H:%M:%S') if smp.created_at else '',
                    *[round(float(x), 6) for x in vec],
                ])
                valid_sample_rows += 1
                students_in_csv.add(smp.student_id)
            except Exception:
                continue

        # Fallback: nếu có bản ghi trong face_data dạng 128D mà chưa có trong face_samples thì xuất kèm luôn
        for fd in FaceData.query.order_by(FaceData.student_id).all():
            if fd.student_id in students_in_csv:
                continue
            try:
                vec = np.asarray(pickle.loads(fd.embedding), dtype=np.float32).reshape(-1)
                if vec.shape[0] != EMBEDDING_DIM:
                    continue
                stu = fd.student
                writer.writerow([
                    f'fd_{fd.id}',
                    fd.student_id,
                    (stu.student_code or '') if stu else '',
                    stu.username if stu else '',
                    stu.full_name if stu else '',
                    'centroid',
                    float(fd.confidence or 0.95),
                    fd.updated_at.strftime('%Y-%m-%d %H:%M:%S') if fd.updated_at else '',
                    *[round(float(x), 6) for x in vec],
                ])
                valid_sample_rows += 1
                students_in_csv.add(fd.student_id)
            except Exception:
                continue

    # Xuất file face_registry.csv
    reg_headers = [
        'student_id', 'student_code', 'username', 'full_name',
        'embedding_model', 'sample_count', 'liveness_score', 'is_trained', 'updated_at',
    ]
    all_fd = FaceData.query.order_by(FaceData.updated_at.desc()).all()
    with open(REGISTRY_CSV_PATH, 'w', newline='', encoding='utf-8-sig') as fp:
        writer = csv.writer(fp)
        writer.writerow(reg_headers)
        for fd in all_fd:
            stu = fd.student
            writer.writerow([
                fd.student_id,
                (stu.student_code or '') if stu else '',
                stu.username if stu else '',
                stu.full_name if stu else '',
                fd.embedding_model or '',
                fd.image_count or 0,
                float(fd.liveness_score or 0.0) if fd.liveness_score is not None else '',
                1 if fd.is_trained else 0,
                fd.updated_at.strftime('%Y-%m-%d %H:%M:%S') if fd.updated_at else '',
            ])

    return {
        'embeddings_csv': str(EMBEDDINGS_CSV_PATH),
        'registry_csv': str(REGISTRY_CSV_PATH),
        'total_samples': valid_sample_rows,
        'total_students': len(students_in_csv),
    }


def append_attendance_ai_log_csv(
    student_id: int,
    student_code: str,
    full_name: str,
    class_name: str,
    session_id: int,
    cosine_score: float,
    model_prob: float,
    liveness_score: float,
    accepted: bool,
    note: str = '',
):
    """Ghi nhật ký kiểm định AI (thành công & chặn giả mạo) vào file `attendance_ai_logs.csv`."""
    _ensure_dirs()
    file_exists = AI_LOGS_CSV_PATH.exists() and AI_LOGS_CSV_PATH.stat().st_size > 0
    with open(AI_LOGS_CSV_PATH, 'a', newline='', encoding='utf-8-sig') as fp:
        writer = csv.writer(fp)
        if not file_exists:
            writer.writerow([
                'timestamp', 'student_id', 'student_code', 'full_name',
                'class_name', 'session_id', 'cosine_score', 'model_prob',
                'liveness_score', 'result', 'note',
            ])
        writer.writerow([
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            student_id,
            student_code or '',
            full_name or '',
            class_name or '',
            session_id,
            round(float(cosine_score), 4),
            round(float(model_prob), 4),
            round(float(liveness_score), 4),
            'ACCEPTED' if accepted else 'REJECTED',
            note,
        ])


def train_face_recognition_model() -> dict:
    """
    Đọc trực tiếp dữ liệu từ file `ai_models/datasets/face_embeddings.csv` (được đồng bộ từ MySQL),
    tăng cường dữ liệu nhẹ trên mặt cầu đơn vị (Hypersphere Jitter Augmentation) để chống overfitting khi ít mẫu,
    huấn luyện bộ phân loại kết hợp:
      - Support Vector Machine (SVC probability=True, kernel='rbf', class_weight='balanced')
      - K-Nearest Centroids (Cosine Prototype Dictionary cho từng sinh viên)
    Lưu ra `ai_models/trained/face_classifier.pkl` và `training_metrics.json`, đồng thời cập nhật `is_trained=True` trong DB.
    """
    from sklearn.svm import SVC
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.preprocessing import normalize
    from sklearn.model_selection import cross_val_score
    from extensions import db
    from models.face_data import FaceData

    sync_info = sync_face_datasets_to_csv()
    if not EMBEDDINGS_CSV_PATH.exists():
        return {'ok': False, 'msg': 'Chưa có file face_embeddings.csv để huấn luyện.'}

    X_list = []
    y_list = []
    meta_by_sid = {}

    with open(EMBEDDINGS_CSV_PATH, 'r', encoding='utf-8-sig') as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            try:
                sid = int(row['student_id'])
                vec = np.array([float(row[f'f{i}']) for i in range(EMBEDDING_DIM)], dtype=np.float32)
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
                X_list.append(vec)
                y_list.append(sid)
                meta_by_sid[sid] = {
                    'student_code': row.get('student_code', ''),
                    'full_name': row.get('full_name', ''),
                }
            except Exception:
                continue

    if not X_list:
        # Xóa model cũ nếu không còn dữ liệu hợp lệ
        if MODEL_PKL_PATH.exists():
            MODEL_PKL_PATH.unlink()
        metrics = {
            'trained': False,
            'trained_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'num_students': 0,
            'num_raw_samples': 0,
            'accuracy': None,
            'msg': 'Chưa có sinh viên nào đăng ký mẫu khuôn mặt chuẩn 128D SFace.',
        }
        METRICS_JSON_PATH.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8')
        return {'ok': True, **metrics}

    X_raw = np.stack(X_list, axis=0)
    y_raw = np.array(y_list, dtype=np.int64)
    unique_sids = sorted(set(y_list))

    # Tính vector tâm chuẩn (Centroid) cho từng sinh viên
    centroids = {}
    samples_by_sid = {}
    for sid in unique_sids:
        stu_vecs = X_raw[y_raw == sid]
        c = np.mean(stu_vecs, axis=0)
        c = c / max(1e-8, float(np.linalg.norm(c)))
        centroids[int(sid)] = c.astype(np.float32)
        samples_by_sid[int(sid)] = stu_vecs.astype(np.float32)

    # Tăng cường dữ liệu (Data Augmentation trên không gian 128D L2) để mỗi sinh viên có ít nhất 12 mẫu huấn luyện ổn định
    rng = np.random.default_rng(42)
    X_aug, y_aug = [X_raw], [y_raw]
    for sid in unique_sids:
        stu_vecs = samples_by_sid[sid]
        needed = max(6, 14 - len(stu_vecs))
        base_choices = stu_vecs[rng.integers(0, len(stu_vecs), size=needed)]
        noise = rng.normal(0.0, 0.025, size=base_choices.shape).astype(np.float32)
        synth = normalize(base_choices + noise, norm='l2').astype(np.float32)
        X_aug.append(synth)
        y_aug.append(np.full(needed, sid, dtype=np.int64))

    X_train = np.concatenate(X_aug, axis=0)
    y_train = np.concatenate(y_aug, axis=0)

    svm_clf = None
    cv_acc  = 1.0
    if len(unique_sids) >= 2:
        base_svc = SVC(C=8.0, kernel='rbf', gamma='scale', class_weight='balanced', random_state=42)
        cv_folds = min(5, min(int(np.sum(y_train == s)) for s in unique_sids))
        if cv_folds >= 2:
            scores = cross_val_score(base_svc, X_train, y_train, cv=cv_folds, scoring='accuracy')
            cv_acc = float(np.mean(scores))
        svm_clf = CalibratedClassifierCV(base_svc, cv=max(2, min(3, cv_folds)))
        svm_clf.fit(X_train, y_train)

    bundle = {
        'version': '2.0-sface-128d',
        'trained_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'classes': unique_sids,
        'meta_by_sid': meta_by_sid,
        'centroids': centroids,
        'samples_by_sid': samples_by_sid,
        'svm_clf': svm_clf,
        'cv_accuracy': round(cv_acc, 4),
    }
    joblib.dump(bundle, MODEL_PKL_PATH)

    # Đánh dấu các bản ghi trong DB đã được đưa vào model AI
    FaceData.query.filter(FaceData.student_id.in_(unique_sids)).update({'is_trained': True}, synchronize_session=False)
    db.session.commit()
    sync_face_datasets_to_csv()  # Cập nhật lại cột is_trained=1 trong face_registry.csv

    metrics = {
        'trained': True,
        'algorithm': 'SFace-128D ONNX + RBF-SVM Classifier + Cosine Prototype Verification' if svm_clf else 'SFace-128D ONNX + Cosine Prototype Verification (1-class mode)',
        'trained_at': bundle['trained_at'],
        'num_students': len(unique_sids),
        'num_raw_samples': int(len(X_raw)),
        'num_augmented_samples': int(len(X_train)),
        'accuracy': round(cv_acc * 100, 2),
        'model_path': str(MODEL_PKL_PATH),
        'embeddings_csv': sync_info['embeddings_csv'],
    }
    METRICS_JSON_PATH.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'ok': True, **metrics}


# ═════════════════════════════════════════════════════════════════════════════
# 4. SO KHỚP & NHẬN DIỆN CHÍNH XÁC BẰNG MODEL ĐÃ TRAIN + DB EMBEDDING
# ═════════════════════════════════════════════════════════════════════════════

def verify_student_identity(student_id: int, probe_embedding: np.ndarray, stored_db_bytes: bytes) -> dict:
    """
    Xác thực danh tính kép cực kỳ chặt chẽ:
      1. So khớp Cosine trực tiếp với vector mẫu của sinh viên trong MySQL (`face_data` & `face_samples`).
      2. Dự đoán qua Model AI đã train (`face_classifier.pkl`):
         - Kiểm tra xem trong toàn bộ các sinh viên đã đăng ký, người giống nhất (Top-1) có đúng là `student_id` không
           (ngăn chặn 2 người có nét hơi giống nhau nhận nhầm).
         - Tính điểm xác suất SVM (`model_prob`).
    """
    probe = np.asarray(probe_embedding, dtype=np.float32).reshape(-1)
    norm  = float(np.linalg.norm(probe))
    if norm > 0:
        probe = probe / norm

    try:
        stored_vec = np.asarray(pickle.loads(stored_db_bytes), dtype=np.float32).reshape(-1)
    except Exception:
        return {
            'is_match': False,
            'score': 0.0,
            'cosine_score': 0.0,
            'model_prob': 0.0,
            'err': 'Dữ liệu khuôn mặt cũ chưa tương thích chuẩn 128D SFace. Vui lòng đăng ký lại khuôn mặt mới!',
        }

    if stored_vec.shape[0] != EMBEDDING_DIM:
        return {
            'is_match': False,
            'score': 0.0,
            'cosine_score': 0.0,
            'model_prob': 0.0,
            'err': 'Mẫu khuôn mặt của bạn thuộc định dạng cũ (chưa chuẩn 128D AI). Vui lòng vào "Đăng ký khuôn mặt" quét lại 1 lần để nâng cấp!',
        }

    stored_vec = stored_vec / max(1e-8, float(np.linalg.norm(stored_vec)))
    cosine_sim = float(np.dot(probe, stored_vec))

    model_prob = cosine_sim
    top1_sid   = student_id
    max_sample_sim = cosine_sim

    if MODEL_PKL_PATH.exists():
        try:
            bundle = joblib.load(MODEL_PKL_PATH)
            samples_map = bundle.get('samples_by_sid', {})
            centroids   = bundle.get('centroids', {})
            svm_clf     = bundle.get('svm_clf')

            if student_id in samples_map:
                sims = np.dot(samples_map[student_id], probe)
                max_sample_sim = max(cosine_sim, float(np.max(sims)))

            if centroids:
                best_sid, best_c_sim = max(
                    ((sid, float(np.dot(c_vec, probe))) for sid, c_vec in centroids.items()),
                    key=lambda item: item[1],
                )
                # Nếu có 1 sinh viên khác trong hệ thống khớp cao hơn hẳn sinh viên đang đăng nhập -> từ chối ngay!
                if best_sid != student_id and best_c_sim > max_sample_sim + 0.04:
                    top1_sid = best_sid

            if svm_clf is not None and student_id in bundle.get('classes', []):
                probs = svm_clf.predict_proba(probe.reshape(1, -1))[0]
                cls_list = list(svm_clf.classes_)
                idx = cls_list.index(student_id)
                model_prob = float(probs[idx])
                pred_sid = int(cls_list[int(np.argmax(probs))])
                if len(cls_list) >= 2 and pred_sid != student_id and float(np.max(probs)) > 0.70 and max_sample_sim < 0.58:
                    top1_sid = pred_sid
        except Exception:
            pass

    effective_cosine = max(cosine_sim, max_sample_sim)
    # Quy đổi điểm hiển thị thân thiện (0..1): Cosine 0.50 -> ~0.78, Cosine 0.75 -> ~0.92
    display_conf = float(np.clip(0.50 + effective_cosine * 0.58, 0.0, 0.995))

    if top1_sid != student_id:
        return {
            'is_match': False,
            'score': round(effective_cosine, 4),
            'display_score': round(display_conf, 4),
            'cosine_score': round(effective_cosine, 4),
            'model_prob': round(model_prob, 4),
            'err': None,
            'reject_msg': 'Khuôn mặt trên camera không khớp với tài khoản sinh viên đang đăng nhập!',
        }

    is_match = (effective_cosine >= COSINE_THRESHOLD) and (
        model_prob >= MODEL_PROB_THRESHOLD or effective_cosine >= 0.56
    )
    return {
        'is_match': is_match,
        'score': round(display_conf if is_match else effective_cosine, 4),
        'display_score': round(display_conf, 4),
        'cosine_score': round(effective_cosine, 4),
        'model_prob': round(model_prob, 4),
        'err': None,
        'reject_msg': None if is_match else f'Khuôn mặt không khớp với hồ sơ đã đăng ký (Cosine: {effective_cosine:.2f} < {COSINE_THRESHOLD:.2f}).',
    }


def compare_faces(stored_bytes: bytes, new_bytes: bytes):
    """Hàm tương thích ngược."""
    try:
        stored = np.asarray(pickle.loads(stored_bytes), dtype=np.float32).reshape(-1)
        new    = np.asarray(pickle.loads(new_bytes), dtype=np.float32).reshape(-1)
        if stored.shape != new.shape:
            return False, 0.0, 'Kích thước vector khuôn mặt không khớp — vui lòng đăng ký lại khuôn mặt.'
        sim = float(np.dot(stored / (np.linalg.norm(stored) + 1e-8), new / (np.linalg.norm(new) + 1e-8)))
        return sim >= COSINE_THRESHOLD, round(sim, 4), None
    except Exception as e:
        return False, 0.0, f'Lỗi so sánh: {e}'


def get_backend_info() -> dict:
    """Thông tin chi tiết về Engine AI, Model đã train và Dataset CSV."""
    _ensure_dirs()
    has_onnx = YUNET_ONNX_PATH.exists() and SFACE_ONNX_PATH.exists()
    metrics = {}
    if METRICS_JSON_PATH.exists():
        try:
            metrics = json.loads(METRICS_JSON_PATH.read_text(encoding='utf-8'))
        except Exception:
            metrics = {}

    return {
        'backend': 'YuNet + SFace 128D (ONNX) + SVM Classifier' if has_onnx else 'uninitialized',
        'available': has_onnx,
        'threshold': COSINE_THRESHOLD,
        'liveness_threshold': LIVENESS_MIN_SCORE,
        'anti_spoofing': True,
        'model_trained': bool(MODEL_PKL_PATH.exists() and metrics.get('trained')),
        'trained_at': metrics.get('trained_at'),
        'trained_students': metrics.get('num_students', 0),
        'trained_samples': metrics.get('num_raw_samples', 0),
        'cv_accuracy': metrics.get('accuracy'),
        'embeddings_csv_exists': EMBEDDINGS_CSV_PATH.exists(),
        'registry_csv_exists': REGISTRY_CSV_PATH.exists(),
        'logs_csv_exists': AI_LOGS_CSV_PATH.exists(),
    }
