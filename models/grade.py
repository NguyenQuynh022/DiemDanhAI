from extensions import db
from datetime import datetime


class Grade(db.Model):
    __tablename__ = 'grades'

    id               = db.Column(db.Integer,      primary_key=True)
    student_id       = db.Column(db.Integer,      db.ForeignKey('users.id',   ondelete='CASCADE'), nullable=False)
    class_id         = db.Column(db.Integer,      db.ForeignKey('classes.id', ondelete='CASCADE'), nullable=False)
    attendance_score = db.Column(db.Numeric(4,2), nullable=True)
    midterm          = db.Column(db.Numeric(4,2))
    final            = db.Column(db.Numeric(4,2))
    assignment       = db.Column(db.Numeric(4,2))
    total            = db.Column(db.Numeric(4,2))
    grade_letter     = db.Column(db.String(5))
    updated_by       = db.Column(db.Integer,      db.ForeignKey('users.id', ondelete='SET NULL'))
    created_at       = db.Column(db.DateTime,     default=datetime.utcnow)
    updated_at       = db.Column(db.DateTime,     default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('student_id', 'class_id', name='uq_grade'),)

    student   = db.relationship(
        'User',
        foreign_keys=[student_id],
        backref=db.backref('grades', cascade='all, delete-orphan', passive_deletes=True),
    )
    class_ref = db.relationship(
        'Class',
        foreign_keys=[class_id],
        backref=db.backref('grades', cascade='all, delete-orphan', passive_deletes=True),
    )

    def calc_total(self, formula=None):
        """Tính tổng kết theo công thức của lớp, hoặc mặc định 20/30/50"""
        if formula is None:
            formula = {'attendance': 0.10, 'assignment': 0.10, 'midterm': 0.30, 'final': 0.50}
        if self.final is None:
            return

        total = 0.0
        w_att = float(formula.get('attendance', 0))
        w_asg = float(formula.get('assignment', 0))
        w_mid = float(formula.get('midterm',    0))
        w_fin = float(formula.get('final',      0.50))

        if w_att > 0 and self.attendance_score is not None:
            total += float(self.attendance_score) * w_att
        elif w_att > 0:
            # nếu chưa có điểm CC thì phân phối trọng số sang cuối kỳ
            w_fin += w_att

        if w_asg > 0 and self.assignment is not None:
            total += float(self.assignment) * w_asg
        elif w_asg > 0:
            w_fin += w_asg

        if w_mid > 0 and self.midterm is not None:
            total += float(self.midterm) * w_mid
        elif w_mid > 0:
            w_fin += w_mid

        total += float(self.final) * w_fin
        self.total = round(total, 2)

        if   self.total >= 9.0: self.grade_letter = 'A+'
        elif self.total >= 8.5: self.grade_letter = 'A'
        elif self.total >= 8.0: self.grade_letter = 'B+'
        elif self.total >= 7.0: self.grade_letter = 'B'
        elif self.total >= 6.5: self.grade_letter = 'C+'
        elif self.total >= 5.5: self.grade_letter = 'C'
        elif self.total >= 5.0: self.grade_letter = 'D+'
        elif self.total >= 4.0: self.grade_letter = 'D'
        else:                   self.grade_letter = 'F'
