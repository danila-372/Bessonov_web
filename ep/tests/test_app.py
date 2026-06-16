import io
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app import Book, Collection, Cover, Genre, Review, User, create_app, db, initialize_database


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


def create_book_record(app, title="Тестовая книга", year=2024):
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
        filename = f"manual-{book.id}.png"
        cover = Cover(
            filename=filename,
            mime_type="image/png",
            md5_hash=f"{book.id:032d}",
            book=book,
        )
        db.session.add(cover)
        Path(app.config["UPLOAD_FOLDER"], filename).write_bytes(PNG_BYTES)
        db.session.commit()
        return book.id, filename


def create_book_with_form(client, title, genre_id, cover_bytes=PNG_BYTES):
    return post(
        client,
        "/books/new",
        {
            "title": title,
            "description": "# Описание\n<script>alert('xss')</script>",
            "year": "2025",
            "publisher": "Учебное издательство",
            "author": "Автор Пример",
            "pages": "256",
            "genres": str(genre_id),
            "cover": (io.BytesIO(cover_bytes), "cover.png"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )


def test_public_pages_and_protected_redirect(app, client):
    book_id, _ = create_book_record(app)

    response = client.get("/")
    assert response.status_code == 200
    assert "Тестовая книга".encode() in response.data

    response = client.get(f"/books/{book_id}")
    assert response.status_code == 200
    assert "Описание".encode() in response.data

    response = client.get("/books/new", follow_redirects=True)
    assert "Для выполнения данного действия необходимо пройти процедуру аутентификации".encode() in response.data


def test_roles_and_cascade_delete_remove_cover_file(app, client):
    book_id, filename = create_book_record(app)
    upload_path = Path(app.config["UPLOAD_FOLDER"], filename)
    with app.app_context():
        user = db.session.scalar(select(User).where(User.login == "user"))
        db.session.add(Review(book_id=book_id, user_id=user.id, rating=5, text="Отзыв"))
        db.session.commit()

    login(client, "moderator")
    assert client.get(f"/books/{book_id}/edit").status_code == 200
    response = post(client, f"/books/{book_id}/delete", follow_redirects=True)
    assert "У вас недостаточно прав для выполнения данного действия".encode() in response.data

    login(client, "admin")
    response = post(client, f"/books/{book_id}/delete", follow_redirects=True)
    assert "успешно удалена".encode() in response.data
    assert not upload_path.exists()
    with app.app_context():
        assert db.session.get(Book, book_id) is None
        assert db.session.scalar(select(func.count(Review.id))) == 0


def test_cover_deduplication_markdown_sanitizing_and_single_review(app, client):
    login(client, "admin")
    with app.app_context():
        genre_id = db.session.scalar(select(Genre.id).limit(1))

    first_response = create_book_with_form(client, "Первая", genre_id)
    second_response = create_book_with_form(client, "Вторая", genre_id)
    assert first_response.status_code == 200
    assert second_response.status_code == 200

    with app.app_context():
        books = db.session.scalars(select(Book).order_by(Book.id)).all()
        covers = db.session.scalars(select(Cover).order_by(Cover.id)).all()
        assert len(books) == 2
        assert len(covers) == 2
        assert covers[0].filename == covers[1].filename
        assert len(list(Path(app.config["UPLOAD_FOLDER"]).iterdir())) == 1
        assert "<script>" not in books[0].description
        book_id = books[0].id

    login(client, "user")
    response = post(
        client,
        f"/books/{book_id}/reviews/new",
        {"rating": "4", "text": "**Хорошо** <script>alert('xss')</script>"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"<strong>" in response.data
    assert b"<script>alert" not in response.data

    response = client.get(f"/books/{book_id}/reviews/new", follow_redirects=True)
    assert "Вы уже оставили рецензию".encode() in response.data
    with app.app_context():
        assert db.session.scalar(select(func.count(Review.id))) == 1


def test_pagination_and_search(app, client):
    for number in range(12):
        create_book_record(app, title=f"Книга {number:02d}", year=2000 + number)

    first_page = client.get("/")
    assert "Книга 11".encode() in first_page.data
    assert "Книга 02".encode() in first_page.data
    assert "Книга 01".encode() not in first_page.data

    second_page = client.get("/?page=2")
    assert "Книга 01".encode() in second_page.data
    assert "Книга 00".encode() in second_page.data

    search_response = client.get("/?q=Книга+07")
    assert "Книга 07".encode() in search_response.data
    assert "Книга 08".encode() not in search_response.data
