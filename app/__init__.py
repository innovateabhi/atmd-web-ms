import os
import click
from flask import Flask, render_template
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event
from sqlalchemy.engine import Engine
from dotenv import load_dotenv

from app.models import db, User, Setting

login_manager = LoginManager()
csrf = CSRFProtect()

@event.listens_for(Engine, "connect")
def configure_sqlite_connection(dbapi_connection, connection_record):
    """Enforce SQLite WAL mode, foreign keys, and busy timeout for high reliability."""
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.close()
    except Exception:
        # Pass non-sqlite engines silently
        pass

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def create_app(test_config=None):
    """Application factory for Flask web application."""
    load_dotenv()

    app = Flask(__name__, instance_relative_config=True)

    # Base configuration
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    instance_dir = os.path.join(base_dir, 'instance')
    os.makedirs(instance_dir, exist_ok=True)

    default_db_path = os.path.join(instance_dir, 'uptime_monitor.sqlite3')
    db_path = os.environ.get('DATABASE_PATH', default_db_path)
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(os.path.join(base_dir, db_path))

    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'insecure-dev-secret-key-change-in-production'),
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{db_path}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={
            'pool_pre_ping': True
        },
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        ALLOW_LOCALHOST_MONITORING=os.environ.get('ALLOW_LOCALHOST_MONITORING', 'false').lower() in ('true', '1', 'yes')
    )

    if test_config:
        app.config.update(test_config)

    # Initialize extensions
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.websites import websites_bp
    from app.routes.incidents import incidents_bp
    from app.routes.reports import reports_bp
    from app.routes.system import system_bp
    from app.routes.settings import settings_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(websites_bp)
    app.register_blueprint(incidents_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(settings_bp)

    # Register CLI commands
    register_commands(app)

    # Custom error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500

    @app.errorhandler(403)
    def forbidden_error(e):
        return render_template('errors/403.html'), 403

    return app

def register_commands(app):
    """Register custom flask CLI management commands."""
    @app.cli.command('init-db')
    def init_db_command():
        """Initialize database tables and default configuration settings."""
        db.create_all()

        defaults = {
            'default_interval': '60',
            'default_timeout': '10',
            'smtp_enabled': 'false',
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': '587',
            'smtp_use_tls': 'true',
            'smtp_username': '',
            'smtp_password': '',
            'alert_email_recipient': '',
            'alert_email_sender': 'no-reply@uptime-monitor.local'
        }

        for key, val in defaults.items():
            if not Setting.query.filter_by(key=key).first():
                setting = Setting(key=key, value=val, description=f'Default setting for {key}')
                db.session.add(setting)

        db.session.commit()
        click.echo('Database schema initialized and default settings configured.')

    @app.cli.command('create-admin')
    @click.option('--username', prompt='Administrator username', help='Username for administrator')
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Password for administrator')
    def create_admin_command(username, password):
        """Create or update an administrative user."""
        user = User.query.filter_by(username=username).first()
        if user:
            user.set_password(password)
            db.session.commit()
            click.echo(f'Admin user "{username}" updated successfully.')
        else:
            new_user = User(username=username)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            click.echo(f'Admin user "{username}" created successfully.')

    @app.cli.command('check-now')
    def check_now_command():
        """Run a single check across all active websites from CLI."""
        from app.services.checker import run_all_checks
        click.echo('Starting one-pass health check across all active monitors...')
        run_all_checks()
        click.echo('One-pass health check completed.')
