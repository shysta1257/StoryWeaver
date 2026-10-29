import os
from flask import Flask
from pymongo import MongoClient


def create_app(test_config=None):
    app = Flask(__name__)

    # Config
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    app.config["MONGO_URI"] = os.environ.get("MONGO_URI", "mongodb://localhost:27017/storyweaver")
    app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 24 * 30  # 30 days

    if test_config:
        app.config.update(test_config)

    # MongoDB (in-memory mongomock when testing, so tests never touch a real server)
    if app.config.get("TESTING"):
        import mongomock
        client = mongomock.MongoClient()
    else:
        client = MongoClient(app.config["MONGO_URI"])
    uri = app.config["MONGO_URI"]
    db_name = uri.rsplit("/", 1)[-1].split("?")[0] or "storyweaver"
    app.db = client[db_name]
    app.mongo_client = client

    # Security hooks and context processors
    from .security import init_security
    init_security(app)

    # Blueprints
    from .routes.auth import bp as auth_bp
    from .routes.stories import bp as stories_bp
    from .routes.users import bp as users_bp
    from .routes.api import bp as api_bp
    from .routes.insights import bp as insights_bp
    from .routes.admin import bp as admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(stories_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(insights_bp)
    app.register_blueprint(admin_bp)

    # Home route
    from .routes.home import bp as home_bp
    app.register_blueprint(home_bp)

    # Template filters
    from .models import time_ago
    app.add_template_filter(time_ago, "time_ago")
    app.add_template_filter(lambda n: chr(64 + n) if 1 <= n <= 26 else str(n), "upper_alpha")

    # Friendly error pages
    from flask import render_template

    def _error(e):
        return render_template("error.html", error=e), e.code

    for code in (400, 403, 404, 405, 500):
        app.register_error_handler(code, _error)

    return app
