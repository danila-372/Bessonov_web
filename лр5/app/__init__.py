from pathlib import Path

from flask import Flask

from . import auth, db, users, visit_logs


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="dev",
        DATABASE=str(Path(app.instance_path) / "users.sqlite"),
    )

    if test_config is not None:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)

    with app.app_context():
        db.init_db()

    app.register_blueprint(auth.bp)
    app.register_blueprint(users.bp)
    app.register_blueprint(visit_logs.bp)

    return app
