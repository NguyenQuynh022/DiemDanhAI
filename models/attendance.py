from extensions import db
from datetime import datetime


class Attendance(db.Model):
    __tablename__ = 'attendance'

    id           = db.Column(db.Integer,    primary_key=True)
    student_id   = db.Column(db.Integer,    db.ForeignKey('users.id',    ondelete='CASCADE'), nullable=False)
    class_id     = db.Column(db.Integer,    db.ForeignKey('classes.id',  ondelete='CASCADE'), nullable=False)
    session_id   = db.Column(db.Integer,    db.ForeignKey('sessions.id', ondelete='SET NULL'))
    session_date = db.Column(db.Date,       nullable=False)
    status       = db.Column(db.Enum('present', 'absent', 'late', 'excused', 'error'), default='present')
    checkin_time = db.Column(db.DateTime)
    method       = db.Column(db.Enum('face', 'manual', 'qr'), default='face')
    face_score   = db.Column(db.Numeric(5, 4))
    note         = db.Column(db.Text)
    created_at   = db.Column(db.DateTime,   default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('student_id', 'class_id', 'session_date', name='uq_attendance'),
    )

    student   = db.relationship('User',  foreign_keys=[student_id], backref='attendance_records')
    class_ref = db.relationship('Class', foreign_keys=[class_id],   backref='attendance_records')
