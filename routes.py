from flask import Blueprint, request, jsonify
from .models import Notification, UserPreference, db
from .email_utils import send_email

bp = Blueprint('main', __name__)

@bp.route('/notifications', methods=['POST'])
def create_notification():
    data = request.json
    new_notification = Notification(
        recipient=data['recipient'],
        subject=data['subject'],
        message=data['message'],
    )
    db.session.add(new_notification)
    db.session.commit()
    return jsonify({"status": "Notification created", "id": new_notification.id}), 201

@bp.route('/notifications/<int:id>', methods=['POST'])
def send_notification(id):
    notification = Notification.query.get(id)
    if not notification:
        return jsonify({"error": "Notification not found"}), 404
    from app import create_app
    app = create_app()
    send_email(app, notification)
    db.session.commit()
    return jsonify({"status": "Notification sent", "id": id}), 200

@bp.route('/preferences', methods=['POST'])
def update_preferences():
    data = request.json
    pref = UserPreference.query.filter_by(user_email=data['user_email']).first()
    if not pref:
        pref = UserPreference(user_email=data['user_email'], receive_notifications=data['receive_notifications'])
    else:
        pref.receive_notifications = data['receive_notifications']
    db.session.add(pref)
    db.session.commit()
    return jsonify({"status": "Preferences updated"}), 200
