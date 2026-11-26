import os
import pytest
from app import create_app
from app.models import db, User, Website, Setting

@pytest.fixture
def app():
    """Create and configure a clean testing application context."""
    test_config = {
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
        'ALLOW_LOCALHOST_MONITORING': True,
        'SECRET_KEY': 'test-secret-key-academic'
    }

    app = create_app(test_config=test_config)

    with app.app_context():
        db.create_all()

        # Seed initial admin
        admin = User(username='testadmin')
        admin.set_password('AdminPass123!')
        db.session.add(admin)

        # Seed settings
        Setting.set_value('default_interval', '60')
        Setting.set_value('default_timeout', '10')
        Setting.set_value('smtp_enabled', 'false')

        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """A test client for dispatching requests."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """A test CLI runner for invoking flask click commands."""
    return app.test_cli_runner()

@pytest.fixture
def auth_client(client):
    """A test client logged in as testadmin."""
    client.post('/login', data={
        'username': 'testadmin',
        'password': 'AdminPass123!'
    }, follow_redirects=True)
    return client
