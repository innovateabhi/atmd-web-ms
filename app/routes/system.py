from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from app.services.system_info import get_system_metrics

system_bp = Blueprint('system', __name__, url_prefix='/system')

@system_bp.route('')
@login_required
def index():
    metrics = get_system_metrics()
    return render_template('system/index.html', metrics=metrics)

@system_bp.route('/api/metrics')
@login_required
def metrics_api():
    metrics = get_system_metrics()
    return jsonify(metrics)
