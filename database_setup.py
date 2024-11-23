from app import create_app, db
from models import Notification, UserPreference

def create_database():
    app = create_app()
    with app.app_context():
        db.create_all()

if __name__ == '__main__':
    create_database()
