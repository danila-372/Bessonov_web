from flask import Flask
from flask_migrate import Migrate
from sqlalchemy.exc import SQLAlchemyError

from app.models import db
from app.auth import bp as auth_bp, init_login_manager
from app.courses import bp as courses_bp
from app.routes import bp as main_bp

def handle_sqlalchemy_error(err):
    error_msg = ('Возникла ошибка при подключении к базе данных. '
                 'Повторите попытку позже.')
    return f'{error_msg} (Подробнее: {err})', 500

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_pyfile('config.py')

    if test_config:
        app.config.from_mapping(test_config)

    db.init_app(app)
    migrate = Migrate(app, db)

    init_login_manager(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(courses_bp)
    app.register_blueprint(main_bp)
    app.errorhandler(SQLAlchemyError)(handle_sqlalchemy_error)

    return app