from datetime import timedelta
from app.models import db, Website, Incident, utc_now
from app.services.incident_manager import handle_monitoring_result

def test_incident_created_on_downtime(app):
    with app.app_context():
        site = Website(name='Incident Test Site', url='http://127.0.0.1:8085/health')
        db.session.add(site)
        db.session.commit()

        # Simulate first check failure
        failure_result = {
            'is_available': False,
            'status_code': 503,
            'response_time_ms': 120.0,
            'error_type': 'http_error',
            'error_message': 'HTTP 503 Service Unavailable'
        }
        handle_monitoring_result(site, failure_result)

        incidents = Incident.query.filter_by(website_id=site.id).all()
        assert len(incidents) == 1
        assert incidents[0].is_resolved is False
        assert incidents[0].error_type == 'http_error'
        assert incidents[0].cause == 'HTTP 503 Service Unavailable'

def test_prevent_duplicate_open_incidents(app):
    with app.app_context():
        site = Website(name='Duplicate Test Site', url='http://127.0.0.1:8085/health')
        db.session.add(site)
        db.session.commit()

        failure_result = {
            'is_available': False,
            'status_code': 500,
            'response_time_ms': 50.0,
            'error_type': 'http_error',
            'error_message': 'Internal Server Error'
        }

        # Multiple consecutive failures
        handle_monitoring_result(site, failure_result)
        handle_monitoring_result(site, failure_result)
        handle_monitoring_result(site, failure_result)

        open_incidents = Incident.query.filter_by(website_id=site.id, is_resolved=False).all()
        assert len(open_incidents) == 1

def test_incident_automatic_resolution(app):
    with app.app_context():
        site = Website(name='Recovery Test Site', url='http://127.0.0.1:8085/health')
        db.session.add(site)
        db.session.commit()

        # 1. Start incident with simulated start time 120 seconds ago
        earlier = utc_now() - timedelta(seconds=120)
        incident = Incident(
            website_id=site.id,
            started_at=earlier,
            is_resolved=False,
            error_type='connection_error',
            cause='Connection refused',
            resolved_by='pending'
        )
        db.session.add(incident)
        db.session.commit()

        # 2. Simulate recovery check
        recovery_result = {
            'is_available': True,
            'status_code': 200,
            'response_time_ms': 45.2,
            'error_type': 'none',
            'error_message': None
        }
        handle_monitoring_result(site, recovery_result)

        resolved_incident = db.session.get(Incident, incident.id)
        assert resolved_incident.is_resolved is True
        assert resolved_incident.resolved_at is not None
        assert resolved_incident.resolved_by == 'system_auto_recovery'
        assert resolved_incident.duration_seconds >= 120
