from datetime import datetime, timezone
from app.models import db, Incident, Website, utc_now

def handle_monitoring_result(website: Website, check_result: dict):
    """
    State machine for website health monitoring:
    - Creates a new Incident when downtime is first detected (preventing duplicates).
    - Automatically resolves any existing open Incident when the website recovers.
    - Accurately tracks downtime start, recovery timestamp, and observed duration.
    """
    from app.services.notifier import send_incident_notification

    now = utc_now()

    if not check_result['is_available']:
        # Check if an open incident already exists for this website
        existing_incident = Incident.query.filter_by(
            website_id=website.id,
            is_resolved=False
        ).order_by(Incident.started_at.desc()).first()

        if not existing_incident:
            # Create new incident
            incident = Incident(
                website_id=website.id,
                started_at=now,
                is_resolved=False,
                error_type=check_result.get('error_type', 'unknown'),
                cause=check_result.get('error_message', 'Health check failed'),
                resolved_by='pending'
            )
            db.session.add(incident)
            db.session.commit()

            # Trigger downtime alert
            send_incident_notification(incident, website, event_type='down')
    else:
        # Website is healthy. Look for unresolved incidents to resolve
        open_incidents = Incident.query.filter_by(
            website_id=website.id,
            is_resolved=False
        ).all()

        for incident in open_incidents:
            incident.resolved_at = now
            incident.is_resolved = True
            incident.resolved_by = 'system_auto_recovery'

            # Calculate total duration in seconds
            if incident.started_at:
                # Ensure tz-awareness compatibility
                started = incident.started_at
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                duration = int((now - started).total_seconds())
                incident.duration_seconds = max(0, duration)
            else:
                incident.duration_seconds = 0

            db.session.commit()

            # Trigger recovery alert
            send_incident_notification(incident, website, event_type='recovery')
