from app import app
from db import db
from models import User, Company, Post, Review, Question, Setting, Notification, UserAction, Analytics
from sqlalchemy import inspect

def sync_database():
    with app.app_context():
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()

        # List of models to check
        models = [User, Company, Post, Review, Question, Setting, Notification, UserAction, Analytics]

        for model in models:
            table_name = model.__tablename__
            if table_name not in existing_tables:
                print(f"Creating table {table_name}")
                model.__table__.create(db.engine)
            else:
                print(f"Table {table_name} already exists")

if __name__ == "__main__":
    sync_database()
