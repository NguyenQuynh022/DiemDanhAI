from extensions import db
from datetime import datetime


class Class(db.Model):
    __tablename__ = 'classes'

    id            = db.Column(db.Integer,      primary_key=True)
    class_name    = db.Column(db.String(100),  nullable=False)
    course_name   = db.Column(db.String(100),  nullable=False)
    course_code   = db.Column(db.String(20))
    lecturer_id   = db.Column(db.Integer,      db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    semester      = db.Column(db.String(20),   nullable=False)
    room          = db.Column(db.String(50))
    schedule_info  = db.Column(db.JSON)
    formula_config = db.Column(db.JSON, default=lambda: {'attendance':0.10,'assignment':0.10,'midterm':0.30,'final':0.50})
    max_students  = db.Column(db.Integer,      default=60)
    status        = db.Column(db.Enum('active', 'closed', 'cancelled'), default='active')
    created_at    = db.Column(db.DateTime,     default=datetime.utcnow)
    updated_at    = db.Column(db.DateTime,     default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    lecturer    = db.relationship('User', foreign_keys=[lecturer_id], backref='classes_teaching')
    enrollments = db.relationship('Enrollment', backref='class_ref', lazy='dynamic', cascade='all, delete-orphan')
    sessions    = db.relationship('Session', backref='class_ref', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Class {self.class_name}>'
