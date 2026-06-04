from extensions import db
from datetime import datetime


class Session(db.Model):
    __tablename__ = 'sessions'

    id           = db.Column(db.Integer,    primary_key=True)
    class_id     = db.Column(db.Integer,    db.ForeignKey('classes.id', ondelete='CASCADE'), nullable=False)
    session_date = db.Column(db.Date,       nullable=False)
    start_time   = db.Column(db.Time,       nullable=False)
    end_time     = db.Column(db.Time,       nullable=False)
    topic        = db.Column(db.String(200))
    room         = db.Column(db.String(50))
    status       = db.Column(db.Enum('scheduled', 'ongoing', 'completed', 'cancelled'), default='scheduled')
    created_at   = db.Column(db.DateTime,   default=datetime.utcnow)

    attendance_records = db.relationship('Attendance', backref='session_ref', lazy='dynamic')
