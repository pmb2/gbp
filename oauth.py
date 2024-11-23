from flask_dance.contrib.google import make_google_blueprint

def setup_google_blueprint():
    return make_google_blueprint(
        client_id="your_google_client_id",
        client_secret="your_google_client_secret",
        scope=[
            "openid",
            "https://www.googleapis.com/auth/business.manage",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile"
        ]
    )