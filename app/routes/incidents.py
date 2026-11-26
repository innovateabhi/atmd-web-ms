from flask import Blueprint, render_template, request
from flask_login import login_required
from app.models import Incident, Website

incidents_bp = Blueprint('incidents', __name__, url_prefix='/incidents')

@incidents_bp.route('')
@login_required
def index():
    status_filter = request.args.get('status', 'all')
    website_id = request.args.get('website_id', type=int)

    query = Incident.query

    if status_filter == 'active':
        query = query.filter_by(is_resolved=False)
    elif status_filter == 'resolved':
        query = query.filter_by(is_resolved=True)

    if website_id:
        query = query.filter_by(website_id=website_id)

    incidents = query.order_by(Incident.started_at.desc()).all()
    websites = Website.query.order_by(Website.name.asc()).all()

    active_count = Incident.query.filter_by(is_resolved=False).count()
    resolved_count = Incident.query.filter_by(is_resolved=True).count()

    return render_template(
        'incidents/index.html',
        incidents=incidents,
        websites=websites,
        current_status=status_filter,
        current_website_id=website_id,
        active_count=active_count,
        resolved_count=resolved_count
    )

@incidents_bp.route('/<int:incident_id>')
@login_required
def detail(incident_id):
    incident = Incident.query.get_or_404(incident_id)
    notifications = incident.notifications.order_by(Incident.started_at.desc()).all()
    return render_template('incidents/detail.html', incident=incident, notifications=notifications)
