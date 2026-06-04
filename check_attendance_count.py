#!/usr/bin/env python
from app import create_app
from models.attendance import Attendance

app = create_app()

with app.app_context():
    count = Attendance.query.filter_by(session_id=39060).count()
    records = Attendance.query.filter_by(session_id=39060).all()
    print(f'Attendance records for session 39060: {count}')
    for r in records:
        print(f'  student_id={r.student_id} status={r.status} method={r.method} time={r.checkin_time}')
