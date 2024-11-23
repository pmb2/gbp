import os
from flask_dance.contrib.google import make_google_blueprint
from dotenv import load_dotenv

load_dotenv()

def setup_google_blueprint():
    return make_google_blueprint(
        client_id=os.getenv("CLIENT_ID"),
        client_secret=os.getenv("CLIENT_SECRET"),
        scope=[
            "openid",
            "https://www.googleapis.com/auth/business.manage",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile"
        ],
        redirect_to="auth/callback"
    )
