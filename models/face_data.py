from extensions import db
from datetime import datetime


class FaceData(db.Model):
    __tablename__ = 'face_data'

    id              = db.Column(db.Integer,     primary_key=True)
    student_id      = db.Column(db.Integer,     db.ForeignKey('users.id', ondelete='CASCADE'),
                                 nullable=False, unique=True)
    embedding       = db.Column(db.LargeBinary, nullable=False)
    embedding_model = db.Column(db.String(50),  default='face_recognition')
    image_count     = db.Column(db.Integer,     default=1)
    confidence      = db.Column(db.Numeric(5,4))
    created_at      = db.Column(db.DateTime,    default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow)

    student = db.relationship('User', backref=db.backref('face_data', uselist=False))
