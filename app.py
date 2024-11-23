from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail

db = SQLAlchemy()
mail = Mail()

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://username:password@localhost:5432/yourdatabase'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = 'your-email@gmail.com'
    app.config['MAIL_PASSWORD'] = 'your-app-password'

    db.init_app(app)
    mail.init_app(app)
    return app
