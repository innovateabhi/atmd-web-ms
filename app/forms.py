from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, IntegerField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo, NumberRange, Optional

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long.')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('new_password', message='Passwords must match.')
    ])
    submit = SubmitField('Update Password')

class WebsiteForm(FlaskForm):
    name = StringField('Monitor Name', validators=[
        DataRequired(),
        Length(min=2, max=128, message='Name must be between 2 and 128 characters.')
    ])
    url = StringField('Target URL', validators=[
        DataRequired(),
        Length(min=7, max=512)
    ])
    check_interval_seconds = IntegerField('Check Interval (seconds)', validators=[
        DataRequired(),
        NumberRange(min=10, max=86400, message='Interval must be between 10 and 86400 seconds.')
    ], default=60)
    timeout_seconds = IntegerField('Request Timeout (seconds)', validators=[
        DataRequired(),
        NumberRange(min=1, max=60, message='Timeout must be between 1 and 60 seconds.')
    ], default=10)
    expected_status_code = StringField('Expected Status Codes', validators=[
        DataRequired(),
        Length(max=64)
    ], default='200')
    is_active = BooleanField('Monitoring Active', default=True)
    submit = SubmitField('Save Monitor')

class SettingsForm(FlaskForm):
    default_interval = IntegerField('Default Interval (seconds)', validators=[
        DataRequired(),
        NumberRange(min=10, max=86400)
    ], default=60)
    default_timeout = IntegerField('Default Request Timeout (seconds)', validators=[
        DataRequired(),
        NumberRange(min=1, max=60)
    ], default=10)
    smtp_enabled = BooleanField('Enable SMTP Email Alerts', default=False)
    smtp_server = StringField('SMTP Hostname', validators=[Optional(), Length(max=128)])
    smtp_port = IntegerField('SMTP Port', validators=[Optional(), NumberRange(min=1, max=65535)], default=587)
    smtp_use_tls = BooleanField('Enable TLS Encryption', default=True)
    smtp_username = StringField('SMTP Username / Email', validators=[Optional(), Length(max=128)])
    smtp_password = PasswordField('SMTP Password / App Password', validators=[Optional()])
    alert_email_sender = StringField('Sender Address', validators=[Optional(), Length(max=128)], default='no-reply@uptime-monitor.local')
    alert_email_recipient = StringField('Alert Recipient Email', validators=[Optional(), Length(max=128)])
    submit = SubmitField('Save Settings')
