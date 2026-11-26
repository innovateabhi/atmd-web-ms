from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required
from app.models import db, Setting
from app.forms import SettingsForm
from app.services.notifier import send_incident_notification

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

@settings_bp.route('', methods=['GET', 'POST'])
@login_required
def index():
    form = SettingsForm()

    if request.method == 'GET':
        form.default_interval.data = int(Setting.get_value('default_interval', '60'))
        form.default_timeout.data = int(Setting.get_value('default_timeout', '10'))
        form.smtp_enabled.data = Setting.get_value('smtp_enabled', 'false').lower() in ('true', '1', 'yes')
        form.smtp_server.data = Setting.get_value('smtp_server', '')
        form.smtp_port.data = int(Setting.get_value('smtp_port', '587'))
        form.smtp_use_tls.data = Setting.get_value('smtp_use_tls', 'true').lower() in ('true', '1', 'yes')
        form.smtp_username.data = Setting.get_value('smtp_username', '')
        # Do not re-populate password field for security
        form.alert_email_sender.data = Setting.get_value('alert_email_sender', 'no-reply@uptime-monitor.local')
        form.alert_email_recipient.data = Setting.get_value('alert_email_recipient', '')

    if form.validate_on_submit():
        Setting.set_value('default_interval', str(form.default_interval.data), 'Default check interval')
        Setting.set_value('default_timeout', str(form.default_timeout.data), 'Default request timeout')
        Setting.set_value('smtp_enabled', 'true' if form.smtp_enabled.data else 'false', 'Enable SMTP')
        Setting.set_value('smtp_server', form.smtp_server.data.strip() if form.smtp_server.data else '', 'SMTP Host')
        Setting.set_value('smtp_port', str(form.smtp_port.data or 587), 'SMTP Port')
        Setting.set_value('smtp_use_tls', 'true' if form.smtp_use_tls.data else 'false', 'SMTP TLS')
        Setting.set_value('smtp_username', form.smtp_username.data.strip() if form.smtp_username.data else '', 'SMTP User')

        if form.smtp_password.data:
            Setting.set_value('smtp_password', form.smtp_password.data, 'SMTP Password')

        Setting.set_value('alert_email_sender', form.alert_email_sender.data.strip() if form.alert_email_sender.data else '', 'Sender Email')
        Setting.set_value('alert_email_recipient', form.alert_email_recipient.data.strip() if form.alert_email_recipient.data else '', 'Recipient Email')

        flash('System configuration updated successfully.', 'success')
        return redirect(url_for('settings.index'))

    return render_template('settings/index.html', form=form)

@settings_bp.route('/test-email', methods=['POST'])
@login_required
def test_email():
    """Trigger a diagnostic email delivery to test SMTP credentials."""
    from app.models import NotificationLog, utc_now
    import smtplib
    from email.mime.text import MIMEText

    recipient = Setting.get_value('alert_email_recipient')
    if not recipient:
        flash('Cannot send test email: Alert Recipient Email is not configured.', 'warning')
        return redirect(url_for('settings.index'))

    server_host = Setting.get_value('smtp_server')
    port = int(Setting.get_value('smtp_port', '587'))
    use_tls = Setting.get_value('smtp_use_tls', 'true').lower() in ('true', '1', 'yes')
    user = Setting.get_value('smtp_username', '')
    pwd = Setting.get_value('smtp_password', '')
    sender = Setting.get_value('alert_email_sender', 'no-reply@uptime-monitor.local')

    msg = MIMEText('This is a test notification from the Linux Automated Website Uptime Monitoring System.')
    msg['Subject'] = '[TEST] Monitoring Alert System Diagnostic'
    msg['From'] = sender
    msg['To'] = recipient

    try:
        s = smtplib.SMTP(server_host, port, timeout=10)
        if use_tls:
            s.starttls()
        if user and pwd:
            s.login(user, pwd)
        s.send_message(msg)
        s.quit()
        flash(f'Diagnostic test email successfully dispatched to {recipient}.', 'success')
    except Exception as e:
        flash(f'Failed to deliver test email: {str(e)}', 'danger')

    return redirect(url_for('settings.index'))
