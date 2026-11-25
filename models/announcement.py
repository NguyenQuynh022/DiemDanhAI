from extensions import db
from datetime import datetime


class Announcement(db.Model):
    __tablename__ = 'announcements'

    id           = db.Column(db.Integer, primary_key=True)
    title        = db.Column(db.String(300), nullable=False)
    content      = db.Column(db.Text)
    category     = db.Column(
        db.Enum('academic', 'finance', 'general', 'scholarship', 'exam'),
        nullable=False,
        default='academic',
    )
    is_new       = db.Column(db.Boolean, default=True)
    is_pinned    = db.Column(db.Boolean, default=False)
    is_published = db.Column(db.Boolean, default=True)
    author_id    = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    author = db.relationship('User', foreign_keys=[author_id], backref='announcements_posted')

    CATEGORY_LABELS = {
        'academic':    'Thông báo từ Phòng Đào tạo',
        'finance':     'Thông báo về Kế hoạch Tài chính',
        'exam':        'Lịch thi & Khảo thí',
        'scholarship': 'Công tác Sinh viên & Học bổng',
        'general':     'Thông báo chung',
    }

    @property
    def category_label(self) -> str:
        return self.CATEGORY_LABELS.get(self.category, 'Thông báo từ Phòng Đào tạo')

    def __repr__(self):
        return f'<Announcement {self.id}: {self.title[:35]}>'
