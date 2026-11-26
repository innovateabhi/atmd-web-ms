from app.models import Website, db
from app.services.checker import validate_target_url

def test_add_website_form_validation(auth_client, app):
    res = auth_client.post('/websites/add', data={
        'name': 'Test Academic Portal',
        'url': 'http://127.0.0.1:8085/health',
        'check_interval_seconds': 30,
        'timeout_seconds': 5,
        'expected_status_code': '200',
        'is_active': True
    }, follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        site = Website.query.filter_by(name='Test Academic Portal').first()
        assert site is not None
        assert site.url == 'http://127.0.0.1:8085/health'
        assert site.check_interval_seconds == 30
        assert site.timeout_seconds == 5
        assert site.expected_status_code == '200'

def test_ssrf_blocking_private_ip():
    # When allow_localhost=False, private/loopback destinations are blocked
    is_valid, msg, err_type = validate_target_url('http://127.0.0.1:8085/secret', allow_localhost=False)
    assert not is_valid
    assert err_type == 'ssrf_blocked'

    is_valid, msg, err_type = validate_target_url('http://192.168.1.1/admin', allow_localhost=False)
    assert not is_valid
    assert err_type == 'ssrf_blocked'

def test_allow_localhost_when_enabled():
    # When allow_localhost=True, loopback destination is allowed for test demonstrations
    is_valid, ip, err_type = validate_target_url('http://127.0.0.1:8085/health', allow_localhost=True)
    assert is_valid
    assert ip == '127.0.0.1'

def test_invalid_scheme():
    is_valid, msg, err_type = validate_target_url('ftp://example.com/file')
    assert not is_valid
    assert err_type == 'invalid_scheme'

def test_toggle_pause_resume(auth_client, app):
    with app.app_context():
        site = Website(name='Toggle Test', url='http://127.0.0.1:8085/health', is_active=True)
        db.session.add(site)
        db.session.commit()
        site_id = site.id

    # Pause
    res = auth_client.post(f'/websites/{site_id}/toggle', follow_redirects=True)
    assert res.status_code == 200
    with app.app_context():
        site = db.session.get(Website, site_id)
        assert site.is_active is False

    # Resume
    res = auth_client.post(f'/websites/{site_id}/toggle', follow_redirects=True)
    assert res.status_code == 200
    with app.app_context():
        site = db.session.get(Website, site_id)
        assert site.is_active is True

def test_delete_website(auth_client, app):
    with app.app_context():
        site = Website(name='Delete Me', url='http://127.0.0.1:8085/health', is_active=True)
        db.session.add(site)
        db.session.commit()
        site_id = site.id

    res = auth_client.post(f'/websites/{site_id}/delete', follow_redirects=True)
    assert res.status_code == 200
    with app.app_context():
        site = db.session.get(Website, site_id)
        assert site is None
