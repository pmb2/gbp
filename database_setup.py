from app import db
from models import Notification, UserPreference

def create_database():
    db.create_all()

if __name__ == '__main__':
    create_database()
