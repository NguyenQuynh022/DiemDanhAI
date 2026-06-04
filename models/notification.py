from extensions import db
from datetime import datetime


class Notification(db.Model):
    __tablename__ = 'notifications'

    id           = db.Column(db.Integer,     primary_key=True)
    user_id      = db.Column(db.Integer,     db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title        = db.Column(db.String(200), nullable=False)
    content      = db.Column(db.Text)
    is_read      = db.Column(db.Boolean,     default=False)
    related_type = db.Column(db.String(50))   # 'grade', 'enrollment', 'schedule', 'system'
    related_id   = db.Column(db.Integer)
    created_at   = db.Column(db.DateTime,    default=datetime.utcnow)

    user = db.relationship('User', backref='notifications')
