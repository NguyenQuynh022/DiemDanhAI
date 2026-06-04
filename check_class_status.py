#!/usr/bin/env python
from app import create_app
from models.class_model import Class
from models.session import Session
from datetime import date

app = create_app()

with app.app_context():
    cls = Class.query.filter_by(course_code='PL103', class_name='PL103-06').first()
    if not cls:
        print('Class PL103-06 not found')
        exit(1)
    print(f'Found class {cls.id}: {cls.class_name} {cls.course_name} lecturer_id={cls.lecturer_id}')
    today = date(2026, 6, 4)
    sessions = Session.query.filter_by(class_id=cls.id, session_date=today).all()
    if not sessions:
        print('No session for today 2026-06-04')
    else:
        for s in sessions:
            print(f'  Session {s.id} status={s.status} {s.start_time}-{s.end_time}')
