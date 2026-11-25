from extensions import db
from datetime import datetime


class FaceData(db.Model):
    """
    Bảng lưu vector trung tâm (mean 128D SFace embedding) của sinh viên trong CSDL MySQL.
    """
    __tablename__ = 'face_data'

    id              = db.Column(db.Integer,     primary_key=True)
    student_id      = db.Column(db.Integer,     db.ForeignKey('users.id', ondelete='CASCADE'),
                                 nullable=False, unique=True)
    embedding       = db.Column(db.LargeBinary, nullable=False)
    embedding_model = db.Column(db.String(50),  default='sface_onnx_128d')
    image_count     = db.Column(db.Integer,     default=1)
    confidence      = db.Column(db.Numeric(5,4))
    liveness_score  = db.Column(db.Numeric(5,4))
    is_trained      = db.Column(db.Boolean,     default=False)
    created_at      = db.Column(db.DateTime,    default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow)

    student = db.relationship(
        'User',
        backref=db.backref('face_data', uselist=False, cascade='all, delete-orphan', passive_deletes=True),
    )


class FaceSample(db.Model):
    """
    Bảng lưu từng mẫu góc mặt (chính diện, nghiêng nhẹ trái/phải, nháy mắt...) của sinh viên vào MySQL.
    Dữ liệu này được đồng bộ trực tiếp ra ai_models/datasets/face_embeddings.csv để train Model AI.
    """
    __tablename__ = 'face_samples'

    id            = db.Column(db.Integer,     primary_key=True)
    student_id    = db.Column(db.Integer,     db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    pose_label    = db.Column(db.String(30),  default='frontal')      # frontal, slight_left, slight_right, smile, live_frame
    embedding     = db.Column(db.LargeBinary, nullable=False)         # 128D float32 vector (pickle)
    quality_score = db.Column(db.Numeric(5,4), default=0.95)
    image_path    = db.Column(db.String(255))
    created_at    = db.Column(db.DateTime,    default=datetime.utcnow)

    student = db.relationship(
        'User',
        backref=db.backref('face_samples', cascade='all, delete-orphan', passive_deletes=True),
    )
