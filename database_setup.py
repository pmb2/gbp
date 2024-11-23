from app import create_app, db
from models import Notification, UserPreference

def create_database():
    app = create_app()
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://username:password@localhost:5432/yourdatabase'
    with app.app_context():
        db.create_all()

if __name__ == '__main__':
    create_database()
