from app.models import User

def test_login_successful(client):
    res = client.post('/login', data={
        'username': 'testadmin',
        'password': 'AdminPass123!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'Infrastructure Overview' in res.data or b'Logged in successfully' in res.data

def test_login_invalid_password(client):
    res = client.post('/login', data={
        'username': 'testadmin',
        'password': 'WrongPassword!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'Invalid username or password' in res.data

def test_login_nonexistent_user(client):
    res = client.post('/login', data={
        'username': 'ghost_user',
        'password': 'Password123'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'Invalid username or password' in res.data

def test_logout(auth_client):
    res = auth_client.get('/logout', follow_redirects=True)
    assert res.status_code == 200
    assert b'You have been logged out securely' in res.data

def test_change_password_successful(auth_client, app):
    res = auth_client.post('/change-password', data={
        'current_password': 'AdminPass123!',
        'new_password': 'NewSecurePassword456!',
        'confirm_password': 'NewSecurePassword456!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'Your password has been changed successfully' in res.data

    with app.app_context():
        user = User.query.filter_by(username='testadmin').first()
        assert user.check_password('NewSecurePassword456!')

def test_change_password_wrong_current(auth_client):
    res = auth_client.post('/change-password', data={
        'current_password': 'WrongCurrentPassword',
        'new_password': 'NewSecurePassword456!',
        'confirm_password': 'NewSecurePassword456!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'Current password verification failed' in res.data

def test_cli_create_admin(runner, app):
    result = runner.invoke(args=['create-admin', '--username', 'newadmin', '--password', 'SecretPass789'])
    assert 'created successfully' in result.output
    with app.app_context():
        user = User.query.filter_by(username='newadmin').first()
        assert user is not None
        assert user.check_password('SecretPass789')
