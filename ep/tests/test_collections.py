from pathlib import Path

import pytest
from sqlalchemy import select

from app import Book, Collection, Cover, Genre, create_app, db, initialize_database


PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
)


@pytest.fixture()
def app(tmp_path):
    database_path = tmp_path / "test.db"
    upload_path = tmp_path / "uploads"
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path.as_posix()}",
            "UPLOAD_FOLDER": str(upload_path),
        }
    )
    with application.app_context():
        initialize_database()
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


def csrf(client):
    with client.session_transaction() as flask_session:
        flask_session["_csrf_token"] = "test-csrf-token"
    return "test-csrf-token"


def post(client, url, data=None, **kwargs):
    form_data = {"csrf_token": csrf(client)}
    form_data.update(data or {})
    return client.post(url, data=form_data, **kwargs)


def login(client, login_name, password=None):
    return post(
        client,
        "/login",
        {"login": login_name, "password": password or login_name},
        follow_redirects=True,
    )


def create_book_record(app, title="Книга для подборки", year=2024):
    with app.app_context():
        genre = db.session.scalar(select(Genre).limit(1))
        book = Book(
            title=title,
            description="Описание",
            year=year,
            publisher="Тестовое издательство",
            author="Тестовый автор",
            pages=120,
            genres=[genre],
        )
        db.session.add(book)
        db.session.flush()
        filename = f"collection-{book.id}.png"
        cover = Cover(
            filename=filename,
            mime_type="image/png",
            md5_hash=f"collection-{book.id:021d}",
            book=book,
        )
        db.session.add(cover)
        Path(app.config["UPLOAD_FOLDER"], filename).write_bytes(PNG_BYTES)
        db.session.commit()
        return book.id


def test_user_collections_flow(app, client):
    book_id = create_book_record(app)

    response = client.get("/collections", follow_redirects=True)
    assert response.status_code == 200
    assert response.request.path == "/login"

    login(client, "admin")
    response = client.get("/collections", follow_redirects=True)
    assert response.request.path == "/"

    login(client, "user")
    response = client.get("/")
    assert "Мои подборки".encode() in response.data

    response = post(
        client,
        "/collections",
        {"title": "Любимое"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Подборка успешно добавлена".encode() in response.data

    with app.app_context():
        collection = db.session.scalar(
            select(Collection).where(Collection.title == "Любимое")
        )
        assert collection is not None
        collection_id = collection.id

    response = client.get(f"/books/{book_id}")
    assert "Добавить в подборку".encode() in response.data
    assert "Любимое".encode() in response.data

    response = post(
        client,
        f"/books/{book_id}/collections",
        {"collection_id": str(collection_id)},
        follow_redirects=True,
    )
    assert "Книга успешно добавлена в подборку".encode() in response.data

    response = client.get(f"/collections/{collection_id}")
    assert "Книга для подборки".encode() in response.data
    with app.app_context():
        collection = db.session.get(Collection, collection_id)
        assert len(collection.books) == 1
        assert collection.books[0].id == book_id

    post(
        client,
        f"/books/{book_id}/collections",
        {"collection_id": str(collection_id)},
        follow_redirects=True,
    )
    with app.app_context():
        collection = db.session.get(Collection, collection_id)
        assert len(collection.books) == 1
