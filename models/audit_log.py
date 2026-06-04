from extensions import db
from datetime import datetime


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id          = db.Column(db.BigInteger,  primary_key=True)
    actor_id    = db.Column(db.Integer,     db.ForeignKey('users.id', ondelete='SET NULL'))
    action_type = db.Column(db.String(50),  nullable=False)
    target_type = db.Column(db.String(50),  nullable=False)
    target_id   = db.Column(db.Integer)
    old_value   = db.Column(db.JSON)
    new_value   = db.Column(db.JSON)
    ip_address  = db.Column(db.String(45))
    created_at  = db.Column(db.DateTime,    default=datetime.utcnow)

    actor = db.relationship('User', foreign_keys=[actor_id])
