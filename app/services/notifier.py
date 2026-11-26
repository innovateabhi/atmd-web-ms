import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.models import db, Setting, NotificationLog, Incident, Website, utc_now

def send_incident_notification(incident: Incident, website: Website, event_type: str = 'down'):
    """
    Dispatches email notifications when website downtime is detected or resolved.
    Logs delivery status and details to the notification_logs table.
    """
    smtp_enabled = Setting.get_value('smtp_enabled', 'false').lower() in ('true', '1', 'yes')
    recipient = Setting.get_value('alert_email_recipient', '')

    if not smtp_enabled or not recipient:
        # Log skipped notification
        log_entry = NotificationLog(
            incident_id=incident.id if incident else None,
            website_id=website.id,
            notification_type='down_alert' if event_type == 'down' else 'recovery_alert',
            recipient=recipient or 'not_configured',
            status='skipped',
            details='SMTP alert delivery is disabled or recipient email is unset.',
            sent_at=utc_now()
        )
        db.session.add(log_entry)
        db.session.commit()
        return False, "SMTP disabled or no recipient configured"

    smtp_server = Setting.get_value('smtp_server', 'localhost')
    smtp_port = int(Setting.get_value('smtp_port', '587'))
    smtp_use_tls = Setting.get_value('smtp_use_tls', 'true').lower() in ('true', '1', 'yes')
    smtp_user = Setting.get_value('smtp_username', '')
    smtp_pass = Setting.get_value('smtp_password', '')
    sender = Setting.get_value('alert_email_sender', 'no-reply@uptime-monitor.local')

    if event_type == 'down':
        subject = f"[ALERT] Website DOWN: {website.name} ({website.url})"
        body = (
            f"Automated Alert Notification\n\n"
            f"Website: {website.name}\n"
            f"URL: {website.url}\n"
            f"Status: UNAVAILABLE / DOWN\n"
            f"Detected At: {incident.started_at.strftime('%Y-%m-%d %H:%M:%S UTC') if incident else utc_now()}\n"
            f"Error Category: {incident.error_type if incident else 'unknown'}\n"
            f"Details: {incident.cause if incident else 'Check failure'}\n\n"
            f"Generated automatically by Linux Automated Uptime Monitoring System."
        )
    else:
        duration_desc = f"{incident.duration_seconds} seconds" if (incident and incident.duration_seconds) else "unknown"
        subject = f"[RESOLVED] Website UP: {website.name} ({website.url})"
        body = (
            f"Recovery Notification\n\n"
            f"Website: {website.name}\n"
            f"URL: {website.url}\n"
            f"Status: OPERATIONAL / RECOVERED\n"
            f"Recovered At: {incident.resolved_at.strftime('%Y-%m-%d %H:%M:%S UTC') if (incident and incident.resolved_at) else utc_now()}\n"
            f"Observed Outage Duration: {duration_desc}\n\n"
            f"Generated automatically by Linux Automated Uptime Monitoring System."
        )

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = recipient
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
        if smtp_use_tls:
            server.starttls()
        if smtp_user and smtp_pass:
            server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()

        log_entry = NotificationLog(
            incident_id=incident.id if incident else None,
            website_id=website.id,
            notification_type='down_alert' if event_type == 'down' else 'recovery_alert',
            recipient=recipient,
            status='sent',
            details=f"Email successfully delivered to {recipient}",
            sent_at=utc_now()
        )
        db.session.add(log_entry)
        db.session.commit()
        return True, "Notification sent successfully."
    except Exception as e:
        log_entry = NotificationLog(
            incident_id=incident.id if incident else None,
            website_id=website.id,
            notification_type='down_alert' if event_type == 'down' else 'recovery_alert',
            recipient=recipient,
            status='failed',
            details=f"SMTP transmission error: {str(e)}"[:500],
            sent_at=utc_now()
        )
        db.session.add(log_entry)
        db.session.commit()
        return False, str(e)
