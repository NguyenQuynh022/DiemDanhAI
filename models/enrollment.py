from extensions import db
from datetime import datetime


class Enrollment(db.Model):
    __tablename__ = 'enrollments'

    id          = db.Column(db.Integer, primary_key=True)
    student_id  = db.Column(db.Integer, db.ForeignKey('users.id',   ondelete='CASCADE'), nullable=False)
    class_id    = db.Column(db.Integer, db.ForeignKey('classes.id', ondelete='CASCADE'), nullable=False)
    enrolled_by = db.Column(db.Integer, db.ForeignKey('users.id',   ondelete='SET NULL'))
    status      = db.Column(db.Enum('enrolled', 'dropped', 'completed'), default='enrolled')
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('student_id', 'class_id', name='uq_enrollment'),
    )

    student = db.relationship('User', foreign_keys=[student_id], backref='enrollments')
