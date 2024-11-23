from flask import Flask, redirect, url_for, render_template, session
from flask_dance.contrib.google import make_google_blueprint, google
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required
from oauth import setup_google_blueprint
from db import db
from models import User, Company, Post, Review, Question, Setting, Notification, UserAction, Analytics

app = Flask(__name__)
app.secret_key = "your_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://your_username:your_password@localhost/gbp-flask"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize extensions
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "google.login"

# Setup Google OAuth
google_bp = setup_google_blueprint()
app.register_blueprint(google_bp, url_prefix="/login")


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route("/")
def home():
    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():
    user_data = session.get("google_user", {})
    return render_template("overview.html", user=user_data)


@app.route("/logout")
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("home"))


@app.route("/login/google")
def login_google():
    if not google.authorized:
        return redirect(url_for("google.login"))
    response = google.get("/oauth2/v1/userinfo")
    if response.ok:
        user_info = response.json()
        session["google_user"] = user_info
        user = User.query.filter_by(email=user_info["email"]).first()
        if not user:
            user = User(email=user_info["email"], name=user_info["name"])
            db.session.add(user)
            db.session.commit()
        login_user(user)
        return redirect(url_for("dashboard"))
    return redirect(url_for("home"))


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
