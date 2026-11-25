"""
services/email_service.py — Gửi email thông báo từ Giảng viên đến tất cả Sinh viên trong lớp học phần
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from flask import current_app


def is_smtp_configured() -> bool:
    user = (current_app.config.get('SMTP_USER') or '').strip()
    pw   = (current_app.config.get('SMTP_PASSWORD') or '').strip()
    return bool(user and pw)


def send_class_bulk_email(
    lecturer_name: str,
    lecturer_email: str | None,
    cls_name: str,
    course_name: str,
    subject: str,
    body_text: str,
    recipient_emails: list[str],
) -> tuple[bool, int, str]:
    """
    Gửi email hàng loạt (qua BCC để bảo mật danh sách email cá nhân và gửi nhanh trong 1 kết nối SMTP)
    đến toàn bộ sinh viên có email của lớp học phần.
    Trả về: (smtp_sent_ok, sent_count, detail_message)
    """
    valid_emails = sorted({e.strip() for e in recipient_emails if e and '@' in e})
    if not valid_emails:
        return False, 0, 'Chưa có sinh viên nào trong lớp cập nhật địa chỉ email.'

    if not is_smtp_configured():
        return (
            False,
            0,
            'Chưa cấu hình SMTP_USER / SMTP_PASSWORD trong file .env (đã gửi vào Hộp thư Thông báo học vụ nội bộ cho toàn bộ sinh viên; có thể nhấn "Mở Gmail / Mail Client" để gửi qua ứng dụng mail).',
        )

    smtp_host = current_app.config.get('SMTP_HOST', 'smtp.gmail.com')
    smtp_port = int(current_app.config.get('SMTP_PORT', 587))
    smtp_user = current_app.config.get('SMTP_USER', '').strip()
    smtp_pw   = current_app.config.get('SMTP_PASSWORD', '').strip()
    from_name = f"{lecturer_name} ({cls_name} - EduPortal)"

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"[{cls_name}] {subject}"
    msg['From']    = formataddr((from_name, smtp_user))
    msg['To']      = smtp_user
    if lecturer_email and '@' in lecturer_email:
        msg['Reply-To'] = lecturer_email

    plain_content = (
        f"Kính gửi các bạn sinh viên lớp {cls_name} — {course_name},\n\n"
        f"{body_text}\n\n"
        f"---\n"
        f"Giảng viên phụ trách: {lecturer_name}\n"
        f"{'Email liên hệ: ' + lecturer_email if lecturer_email else ''}\n"
        f"Hệ thống Quản lý Đào tạo EduPortal"
    )

    html_body_escaped = (
        body_text.replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('\n', '<br>')
    )
    html_content = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:640px;margin:0 auto;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden">
      <div style="background:linear-gradient(135deg,#1e1b4b,#4f46e5);color:#ffffff;padding:18px 24px">
        <div style="font-size:12px;opacity:0.85;text-transform:uppercase;letter-spacing:0.06em">Thông báo lớp học phần · EduPortal</div>
        <h2 style="margin:6px 0 0;font-size:18px">{course_name} ({cls_name})</h2>
      </div>
      <div style="padding:22px 24px;color:#0f172a;line-height:1.65;font-size:14.5px">
        <p style="margin-top:0">Chào các bạn sinh viên lớp <strong>{cls_name}</strong>,</p>
        <div style="background:#f8fafc;border-left:4px solid #4f46e5;padding:14px 16px;border-radius:0 8px 8px 0;margin:14px 0">
          {html_body_escaped}
        </div>
        <p style="margin-bottom:0;color:#475569;font-size:13px">
          Trân trọng,<br>
          <strong>{lecturer_name}</strong>
          {f' &middot; <a href="mailto:{lecturer_email}">{lecturer_email}</a>' if lecturer_email else ''}
        </p>
      </div>
    </div>
    """

    msg.attach(MIMEText(plain_content, 'plain', 'utf-8'))
    msg.attach(MIMEText(html_content, 'html', 'utf-8'))

    all_rcpts = list(valid_emails)
    if lecturer_email and '@' in lecturer_email and lecturer_email not in all_rcpts:
        all_rcpts.append(lecturer_email)

    try:
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=20) as server:
                server.login(smtp_user, smtp_pw)
                server.sendmail(smtp_user, all_rcpts, msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
                server.ehlo()
                server.starttls()
                server.login(smtp_user, smtp_pw)
                server.sendmail(smtp_user, all_rcpts, msg.as_string())
        return True, len(valid_emails), f'Đã gửi email SMTP thành công tới {len(valid_emails)} địa chỉ email sinh viên.'
    except Exception as exc:
        return False, 0, f'Không thể gửi qua SMTP ({exc}). Đã chuyển thông báo vào Hộp thư nội bộ của cả lớp.'
