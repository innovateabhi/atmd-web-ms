from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

def utc_now():
    """Return current UTC timestamp without timezone offset issues."""
    return datetime.now(timezone.utc)

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)

    def __init__(
        self,
        username: str = None,
        password_hash: str = None,
        created_at: datetime = None,
        last_login: datetime = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        if username is not None:
            self.username = username
        if password_hash is not None:
            self.password_hash = password_hash
        if created_at is not None:
            self.created_at = created_at
        if last_login is not None:
            self.last_login = last_login
        for k, v in kwargs.items():
            setattr(self, k, v)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


class Website(db.Model):
    __tablename__ = 'websites'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    url = db.Column(db.String(512), nullable=False, index=True)
    check_interval_seconds = db.Column(db.Integer, default=60, nullable=False)
    timeout_seconds = db.Column(db.Integer, default=10, nullable=False)
    expected_status_code = db.Column(db.String(64), default='200', nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    current_status = db.Column(db.String(32), default='pending', nullable=False, index=True)
    last_checked_at = db.Column(db.DateTime, nullable=True, index=True)
    last_response_time_ms = db.Column(db.Float, nullable=True)
    last_status_code = db.Column(db.Integer, nullable=True)
    last_error_message = db.Column(db.String(512), nullable=True)
    consecutive_failures = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    logs = db.relationship('MonitoringLog', backref='website', lazy='dynamic', cascade='all, delete-orphan')
    incidents = db.relationship('Incident', backref='website', lazy='dynamic', cascade='all, delete-orphan')
    notifications = db.relationship('NotificationLog', backref='website', lazy='dynamic', cascade='all, delete-orphan')

    def __init__(
        self,
        name: str = None,
        url: str = None,
        check_interval_seconds: int = 60,
        timeout_seconds: int = 10,
        expected_status_code: str = '200',
        is_active: bool = True,
        current_status: str = 'pending',
        last_checked_at: datetime = None,
        last_response_time_ms: float = None,
        last_status_code: int = None,
        last_error_message: str = None,
        consecutive_failures: int = 0,
        created_at: datetime = None,
        updated_at: datetime = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        if name is not None:
            self.name = name
        if url is not None:
            self.url = url
        self.check_interval_seconds = check_interval_seconds
        self.timeout_seconds = timeout_seconds
        self.expected_status_code = expected_status_code
        self.is_active = is_active
        self.current_status = current_status
        if last_checked_at is not None:
            self.last_checked_at = last_checked_at
        if last_response_time_ms is not None:
            self.last_response_time_ms = last_response_time_ms
        if last_status_code is not None:
            self.last_status_code = last_status_code
        if last_error_message is not None:
            self.last_error_message = last_error_message
        self.consecutive_failures = consecutive_failures
        if created_at is not None:
            self.created_at = created_at
        if updated_at is not None:
            self.updated_at = updated_at
        for k, v in kwargs.items():
            setattr(self, k, v)

    @property
    def expected_status_list(self):
        """Parse comma or space separated status codes into integer list."""
        codes = []
        for part in str(self.expected_status_code).replace(',', ' ').split():
            try:
                codes.append(int(part.strip()))
            except ValueError:
                continue
        return codes or [200]

    def __repr__(self):
        return f'<Website {self.name} - {self.url}>'


class MonitoringLog(db.Model):
    __tablename__ = 'monitoring_logs'

    id = db.Column(db.Integer, primary_key=True)
    website_id = db.Column(db.Integer, db.ForeignKey('websites.id', ondelete='CASCADE'), nullable=False, index=True)
    checked_at = db.Column(db.DateTime, default=utc_now, nullable=False, index=True)
    is_available = db.Column(db.Boolean, nullable=False, index=True)
    status_code = db.Column(db.Integer, nullable=True)
    response_time_ms = db.Column(db.Float, nullable=True)
    error_type = db.Column(db.String(64), nullable=True)  # dns_error, connection_error, timeout, ssl_error, http_error, none
    error_message = db.Column(db.String(512), nullable=True)

    def __init__(
        self,
        website_id: int = None,
        checked_at: datetime = None,
        is_available: bool = True,
        status_code: int = None,
        response_time_ms: float = None,
        error_type: str = None,
        error_message: str = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        if website_id is not None:
            self.website_id = website_id
        if checked_at is not None:
            self.checked_at = checked_at
        self.is_available = is_available
        if status_code is not None:
            self.status_code = status_code
        if response_time_ms is not None:
            self.response_time_ms = response_time_ms
        if error_type is not None:
            self.error_type = error_type
        if error_message is not None:
            self.error_message = error_message
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __repr__(self):
        return f'<MonitoringLog website_id={self.website_id} ok={self.is_available} time={self.checked_at}>'


class Incident(db.Model):
    __tablename__ = 'incidents'

    id = db.Column(db.Integer, primary_key=True)
    website_id = db.Column(db.Integer, db.ForeignKey('websites.id', ondelete='CASCADE'), nullable=False, index=True)
    started_at = db.Column(db.DateTime, default=utc_now, nullable=False, index=True)
    resolved_at = db.Column(db.DateTime, nullable=True, index=True)
    is_resolved = db.Column(db.Boolean, default=False, nullable=False, index=True)
    duration_seconds = db.Column(db.Integer, nullable=True)
    error_type = db.Column(db.String(64), nullable=True)
    cause = db.Column(db.String(512), nullable=True)
    resolved_by = db.Column(db.String(64), default='system_auto_recovery', nullable=False)

    notifications = db.relationship('NotificationLog', backref='incident', lazy='dynamic')

    def __init__(
        self,
        website_id: int = None,
        started_at: datetime = None,
        resolved_at: datetime = None,
        is_resolved: bool = False,
        duration_seconds: int = None,
        error_type: str = None,
        cause: str = None,
        resolved_by: str = 'system_auto_recovery',
        **kwargs
    ):
        super().__init__(**kwargs)
        if website_id is not None:
            self.website_id = website_id
        if started_at is not None:
            self.started_at = started_at
        if resolved_at is not None:
            self.resolved_at = resolved_at
        self.is_resolved = is_resolved
        if duration_seconds is not None:
            self.duration_seconds = duration_seconds
        if error_type is not None:
            self.error_type = error_type
        if cause is not None:
            self.cause = cause
        self.resolved_by = resolved_by
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __repr__(self):
        return f'<Incident id={self.id} website_id={self.website_id} resolved={self.is_resolved}>'


class NotificationLog(db.Model):
    __tablename__ = 'notification_logs'

    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(db.Integer, db.ForeignKey('incidents.id', ondelete='SET NULL'), nullable=True, index=True)
    website_id = db.Column(db.Integer, db.ForeignKey('websites.id', ondelete='CASCADE'), nullable=False, index=True)
    notification_type = db.Column(db.String(32), nullable=False)  # down_alert, recovery_alert, test_email
    recipient = db.Column(db.String(256), nullable=False)
    status = db.Column(db.String(32), nullable=False)  # sent, failed, skipped
    details = db.Column(db.String(512), nullable=True)
    sent_at = db.Column(db.DateTime, default=utc_now, nullable=False, index=True)

    def __init__(
        self,
        incident_id: int = None,
        website_id: int = None,
        notification_type: str = None,
        recipient: str = None,
        status: str = None,
        details: str = None,
        sent_at: datetime = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        if incident_id is not None:
            self.incident_id = incident_id
        if website_id is not None:
            self.website_id = website_id
        if notification_type is not None:
            self.notification_type = notification_type
        if recipient is not None:
            self.recipient = recipient
        if status is not None:
            self.status = status
        if details is not None:
            self.details = details
        if sent_at is not None:
            self.sent_at = sent_at
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __repr__(self):
        return f'<NotificationLog id={self.id} type={self.notification_type} status={self.status}>'


class Setting(db.Model):
    __tablename__ = 'settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(256), nullable=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    def __init__(
        self,
        key: str = None,
        value: str = None,
        description: str = None,
        updated_at: datetime = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        if key is not None:
            self.key = key
        if value is not None:
            self.value = value
        if description is not None:
            self.description = description
        if updated_at is not None:
            self.updated_at = updated_at
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def get_value(cls, key: str, default=None):
        row = cls.query.filter_by(key=key).first()
        if row:
            return row.value
        return default

    @classmethod
    def set_value(cls, key: str, value: str, description: str = None):
        row = cls.query.filter_by(key=key).first()
        if row:
            row.value = str(value)
            if description:
                row.description = description
            row.updated_at = utc_now()
        else:
            row = cls(key=key, value=str(value), description=description, updated_at=utc_now())
            db.session.add(row)
        db.session.commit()
        return row

    def __repr__(self):
        return f'<Setting {self.key}={self.value}>'
