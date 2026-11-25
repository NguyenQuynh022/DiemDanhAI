from extensions import db
from datetime import datetime


class RegistrationConfig(db.Model):
    """
    Cấu hình đợt mở Đăng ký tín chỉ do Admin (Phòng Đào tạo) quản lý.
    Chỉ cho phép Sinh viên đăng ký khi Admin bật mở (is_open=True) và nằm trong thời gian đăng ký (nếu có đặt lịch).
    """
    __tablename__ = 'registration_configs'

    id          = db.Column(db.Integer, primary_key=True)
    semester    = db.Column(db.String(20), nullable=False, unique=True)
    is_open     = db.Column(db.Boolean, nullable=False, default=False)
    open_from   = db.Column(db.DateTime, nullable=True)
    open_until  = db.Column(db.DateTime, nullable=True)
    min_courses = db.Column(db.Integer, nullable=False, default=3)
    max_courses = db.Column(db.Integer, nullable=False, default=7)
    note        = db.Column(db.String(300))
    updated_by  = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def is_active_now(self) -> bool:
        """Kiểm tra cổng đăng ký thực sự đang mở theo nút bật của Admin VÀ nằm trong khung thời gian đăng ký."""
        if not self.is_open:
            return False
        now = datetime.now()
        if self.open_from and now < self.open_from:
            return False
        if self.open_until and now > self.open_until:
            return False
        return True

    @property
    def status_reason(self) -> str:
        """Lý do trạng thái hiện tại để hiển thị rõ ràng cho Admin & Sinh viên."""
        if not self.is_open:
            return 'Phòng Đào tạo (Admin) hiện đang đóng cổng đăng ký tín chỉ.'
        now = datetime.now()
        if self.open_from and now < self.open_from:
            return f'Chưa đến thời gian mở đăng ký (Bắt đầu từ {self.open_from.strftime("%H:%M ngày %d/%m/%Y")}).'
        if self.open_until and now > self.open_until:
            return f'Đã hết thời hạn đăng ký tín chỉ (Kết thúc lúc {self.open_until.strftime("%H:%M ngày %d/%m/%Y")}).'
        if self.open_from and self.open_until:
            return f'Thời gian mở: {self.open_from.strftime("%H:%M %d/%m/%Y")} → {self.open_until.strftime("%H:%M %d/%m/%Y")}'
        if self.open_until:
            return f'Mở đăng ký đến {self.open_until.strftime("%H:%M ngày %d/%m/%Y")}'
        return 'Đang mở đăng ký theo quyết định của Phòng Đào tạo (Admin)'

    def __repr__(self):
        return f'<RegistrationConfig {self.semester} open={self.is_open}>'
