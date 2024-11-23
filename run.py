from app import create_app, db
from app.models import Notification, UserPreference
from app.routes import bp

app = create_app()
app.register_blueprint(bp)
db.init_app(app)

@app.before_first_request
def setup():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
