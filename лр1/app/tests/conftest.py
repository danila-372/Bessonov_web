from datetime import datetime
import pytest
from flask import template_rendered
from contextlib import contextmanager
from app import app as application

@pytest.fixture
def app():
    return application

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
@contextmanager
def captured_templates(app):
    recorded = []
    def record(sender, template, context, **extra):
        recorded.append((template, context))
    template_rendered.connect(record, app)
    try:
        yield recorded
    finally:
        template_rendered.disconnect(record, app)

@pytest.fixture
def posts_list():
    return [
        {
            'title': 'Первый тестовый пост',
            'text': 'Подробный текст первого тестового поста.',
            'author': 'Иванов Иван Иванович',
            'date': datetime(2025, 3, 10, 12, 30),
            'image_id': 'first.jpg',
            'comments': [
                {
                    'author': 'Петров Петр Петрович',
                    'text': 'Текст первого комментария.',
                    'replies': [
                        {
                            'author': 'Сидоров Сидор Сидорович',
                            'text': 'Текст ответа на комментарий.',
                            'replies': []
                        }
                    ]
                }
            ]
        },
        {
            'title': 'Второй тестовый пост',
            'text': 'Подробный текст второго тестового поста.',
            'author': 'Смирнова Анна Сергеевна',
            'date': datetime(2024, 12, 5, 9, 15),
            'image_id': 'second.jpg',
            'comments': []
        }
    ]
