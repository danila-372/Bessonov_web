from datetime import datetime

import pytest

from app import create_app
from app.models import Category, Course, Image, User, db


@pytest.fixture()
def app(tmp_path):
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_ECHO': False,
        'UPLOAD_FOLDER': tmp_path,
    })

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def create_user(login, first_name='Test', last_name='User', password='qwerty'):
    user = User(first_name=first_name, last_name=last_name, login=login)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    return user


@pytest.fixture()
def sample_course(app):
    with app.app_context():
        category = Category(name='Programming')
        author = create_user('author', first_name='Course', last_name='Author')
        image = Image(
            id='course-image',
            file_name='course.jpg',
            mime_type='image/jpeg',
            md5_hash='course-image-hash',
        )
        course = Course(
            name='Python Basics',
            short_desc='Short description',
            full_desc='Full description',
            category=category,
            author=author,
            bg_image=image,
            created_at=datetime(2026, 1, 1, 12, 0, 0),
        )
        db.session.add_all([category, author, image, course])
        db.session.commit()
        return course.id


@pytest.fixture()
def student(app):
    with app.app_context():
        user = create_user('student', first_name='Review', last_name='Student')
        db.session.commit()
        return user.id


def login(client, login='student', password='qwerty'):
    return client.post('/auth/login', data={
        'login': login,
        'password': password,
    }, follow_redirects=True)
