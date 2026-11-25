#!/usr/bin/env python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app import create_app
from models.class_model import Class
from models.user import User
import json

app = create_app()

with app.app_context():
    classes = Class.query.all()
    result = []
    for cls in classes:
        info = cls.schedule_info
        if info is None:
            continue
        # if JSON stored as string, parse
        if isinstance(info, str):
            try:
                info = json.loads(info)
            except Exception:
                continue
        entries = []
        if isinstance(info, dict):
            entries = [info]
        elif isinstance(info, list):
            entries = info
        else:
            continue
        for item in entries:
            if not isinstance(item, dict):
                continue
            day = item.get('day')
            if day == 3:
                lecturer = User.query.get(cls.lecturer_id)
                result.append((cls.id, cls.class_name, cls.course_name, cls.course_code, lecturer.full_name if lecturer else None, lecturer.email if lecturer else None, item))
                break
    if not result:
        print('No Thursday classes found')
    else:
        print('Thursday classes:')
        for cls_id, class_name, course_name, code, lecturer_name, email, item in result:
            print(f'{cls_id}: {class_name} ({course_name}, {code}) — Lecturer: {lecturer_name} [{email}] — schedule {item}')
