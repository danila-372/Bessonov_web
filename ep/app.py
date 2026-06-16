from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from urllib.parse import urljoin, urlparse

import bleach
import markdown
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from markupsafe import Markup
from sqlalchemy import CheckConstraint, event, func, or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import selectinload
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


db = SQLAlchemy()

AUTH_REQUIRED_MESSAGE = (
    "Для выполнения данного действия необходимо пройти процедуру аутентификации"
)
ACCESS_DENIED_MESSAGE = "У вас недостаточно прав для выполнения данного действия"

ROLE_ADMIN = "admin"
ROLE_MODERATOR = "moderator"
ROLE_USER = "user"
BOOK_EDITOR_ROLES = {ROLE_ADMIN, ROLE_MODERATOR}
REVIEWER_ROLES = {ROLE_ADMIN, ROLE_MODERATOR, ROLE_USER}

ALLOWED_MARKDOWN_TAGS = {
    "a",
    "blockquote",
    "br",
    "code",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "ul",
}
ALLOWED_MARKDOWN_ATTRIBUTES = {"a": ["href", "title"]}


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


book_genres = db.Table(
    "book_genres",
    db.Column(
        "book_id",
        db.Integer,
        db.ForeignKey("books.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "genre_id",
        db.Integer,
        db.ForeignKey("genres.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

collection_books = db.Table(
    "collection_books",
    db.Column(
        "collection_id",
        db.Integer,
        db.ForeignKey("collections.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "book_id",
        db.Integer,
        db.ForeignKey("books.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=False)

    users = db.relationship("User", back_populates="role")


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(64), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    middle_name = db.Column(db.String(100))
    role_id = db.Column(
        db.Integer, db.ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False
    )

    role = db.relationship("Role", back_populates="users")
    reviews = db.relationship(
        "Review", back_populates="user", cascade="all, delete-orphan"
    )
    collections = db.relationship(
        "Collection",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def full_name(self):
        return " ".join(
            part for part in (self.last_name, self.first_name, self.middle_name) if part
        )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Genre(db.Model):
    __tablename__ = "genres"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)


class Book(db.Model):
    __tablename__ = "books"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    publisher = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255), nullable=False)
    pages = db.Column(db.Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("year BETWEEN 1 AND 9999", name="valid_book_year"),
        CheckConstraint("pages > 0", name="positive_book_pages"),
    )

    genres = db.relationship(
        "Genre", secondary=book_genres, backref=db.backref("books", lazy="selectin")
    )
    cover = db.relationship(
        "Cover",
        back_populates="book",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    reviews = db.relationship(
        "Review",
        back_populates="book",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Review.created_at.desc()",
    )
    collections = db.relationship(
        "Collection",
        secondary=collection_books,
        back_populates="books",
    )

    @property
    def average_rating(self):
        if not self.reviews:
            return None
        return sum(review.rating for review in self.reviews) / len(self.reviews)


class Cover(db.Model):
    __tablename__ = "covers"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    md5_hash = db.Column(db.String(32), nullable=False, index=True)
    book_id = db.Column(
        db.Integer,
        db.ForeignKey("books.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    book = db.relationship("Book", back_populates="cover")


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(
        db.Integer, db.ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rating = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        CheckConstraint("rating BETWEEN 0 AND 5", name="valid_review_rating"),
        db.UniqueConstraint("book_id", "user_id", name="one_review_per_book_and_user"),
    )

    book = db.relationship("Book", back_populates="reviews")
    user = db.relationship("User", back_populates="reviews")


class Collection(db.Model):
    __tablename__ = "collections"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint("title", "user_id", name="unique_collection_title_per_user"),
    )

    user = db.relationship("User", back_populates="collections")
    books = db.relationship(
        "Book",
        secondary=collection_books,
        back_populates="collections",
        order_by=lambda: (Book.year.desc(), Book.id.desc()),
    )


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-change-me"),
        SQLALCHEMY_DATABASE_URI="sqlite:///" + str(Path(app.instance_path) / "library.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER=str(Path(app.instance_path) / "uploads"),
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
        AUTHOR_SIGNATURE=os.environ.get(
            "AUTHOR_SIGNATURE", "Группа: укажите группу | ФИО: укажите ФИО"
        ),
    )
    if test_config:
        app.config.update(test_config)
    if not test_config or "AUTHOR_SIGNATURE" not in test_config:
        app.config["AUTHOR_SIGNATURE"] = os.environ.get(
            "AUTHOR_SIGNATURE", "Группа: 241-372 | ФИО: Бессонов Данила Алексеевич"
        )

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    db.init_app(app)

    register_template_helpers(app)
    register_routes(app)

    @app.cli.command("init-db")
    def init_db_command():
        initialize_database()
        print("База данных инициализирована.")

    return app


def register_template_helpers(app):
    @app.context_processor
    def inject_globals():
        return {
            "current_user": get_current_user(),
            "csrf_token": get_csrf_token,
            "ROLE_ADMIN": ROLE_ADMIN,
            "ROLE_MODERATOR": ROLE_MODERATOR,
            "ROLE_USER": ROLE_USER,
            "BOOK_EDITOR_ROLES": BOOK_EDITOR_ROLES,
        }

    @app.template_filter("markdown")
    def markdown_filter(value):
        return render_markdown(value)


def register_routes(app):
    @app.get("/")
    def index():
        page = request.args.get("page", 1, type=int)
        search = request.args.get("q", "").strip()
        statement = (
            select(Book)
            .options(
                selectinload(Book.genres),
                selectinload(Book.reviews),
                selectinload(Book.cover),
            )
            .order_by(Book.year.desc(), Book.id.desc())
        )
        if search:
            pattern = f"%{search}%"
            statement = (
                statement.join(Book.genres, isouter=True)
                .where(
                    or_(
                        Book.title.ilike(pattern),
                        Book.author.ilike(pattern),
                        Book.publisher.ilike(pattern),
                        Genre.name.ilike(pattern),
                    )
                )
                .distinct()
            )
        books = db.paginate(statement, page=page, per_page=10, error_out=False)
        return render_template("index.html", books=books, search=search)

    @app.get("/collections")
    @roles_required(ROLE_USER)
    def collections():
        user = get_current_user()
        user_collections = db.session.scalars(
            select(Collection)
            .options(selectinload(Collection.books))
            .where(Collection.user_id == user.id)
            .order_by(Collection.title)
        ).all()
        return render_template("collections.html", collections=user_collections)

    @app.post("/collections")
    @roles_required(ROLE_USER)
    def create_collection():
        require_valid_csrf()
        user = get_current_user()
        title = request.form.get("title", "").strip()
        if not title:
            flash("Введите название подборки.", "danger")
            return redirect(url_for("collections"))
        collection = Collection(title=title, user=user)
        try:
            db.session.add(collection)
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("Не удалось добавить подборку. Проверьте корректность данных.", "danger")
        else:
            flash("Подборка успешно добавлена.", "success")
        return redirect(url_for("collections"))

    @app.get("/collections/<int:collection_id>")
    @roles_required(ROLE_USER)
    def collection_detail(collection_id):
        collection = get_user_collection_or_404(collection_id)
        return render_template("collection_detail.html", collection=collection)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            require_valid_csrf()
            user = db.session.scalar(
                select(User).where(User.login == request.form.get("login", "").strip())
            )
            password = request.form.get("password", "")
            if user is None or not user.check_password(password):
                flash(
                    "Невозможно аутентифицироваться с указанными логином и паролем",
                    "danger",
                )
                return render_template("login.html")
            session.clear()
            session["user_id"] = user.id
            session.permanent = request.form.get("remember") == "on"
            flash("Вы успешно вошли в систему.", "success")
            next_page = request.args.get("next")
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for("index"))
        return render_template("login.html")

    @app.post("/logout")
    @login_required
    def logout():
        require_valid_csrf()
        session.clear()
        flash("Вы вышли из системы.", "success")
        next_page = request.form.get("next")
        if next_page and is_safe_url(next_page):
            return redirect(next_page)
        return redirect(url_for("index"))

    @app.get("/uploads/<path:filename>")
    def uploaded_file(filename):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    @app.get("/books/<int:book_id>")
    def book_detail(book_id):
        book = get_book_or_404(book_id)
        user = get_current_user()
        own_review = None
        user_collections = []
        if user:
            own_review = db.session.scalar(
                select(Review).where(
                    Review.book_id == book.id, Review.user_id == user.id
                )
            )
            if user.role.name == ROLE_USER:
                user_collections = db.session.scalars(
                    select(Collection)
                    .where(Collection.user_id == user.id)
                    .order_by(Collection.title)
                ).all()
        return render_template(
            "book_detail.html",
            book=book,
            own_review=own_review,
            user_collections=user_collections,
        )

    @app.post("/books/<int:book_id>/collections")
    @roles_required(ROLE_USER)
    def add_book_to_collection(book_id):
        require_valid_csrf()
        book = get_book_or_404(book_id)
        collection_id = parse_int(request.form.get("collection_id"))
        if collection_id is None:
            flash("Выберите подборку.", "danger")
            return redirect(url_for("book_detail", book_id=book.id))
        collection = get_user_collection_or_404(collection_id)
        if book not in collection.books:
            collection.books.append(book)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                flash("Не удалось добавить книгу в подборку.", "danger")
                return redirect(url_for("book_detail", book_id=book.id))
        flash("Книга успешно добавлена в подборку.", "success")
        return redirect(url_for("book_detail", book_id=book.id))

    @app.route("/books/new", methods=["GET", "POST"])
    @roles_required(ROLE_ADMIN)
    def create_book():
        genres = get_all_genres()
        if request.method == "POST":
            require_valid_csrf()
            book = Book()
            selected_genre_ids = request.form.getlist("genres")
            errors = apply_book_form(book, genres, selected_genre_ids)
            cover_file = request.files.get("cover")
            if not cover_file or not cover_file.filename:
                errors.append("Выберите файл обложки.")
            elif not cover_file.mimetype.startswith("image/"):
                errors.append("Обложка должна быть изображением.")
            if errors:
                flash_form_errors(errors)
                return render_template(
                    "book_form.html",
                    book=book,
                    genres=genres,
                    selected_genre_ids=selected_genre_ids,
                    mode="create",
                )

            created_filename = None
            try:
                cover_data = cover_file.read()
                if not cover_data:
                    raise ValueError("Файл обложки пуст.")
                digest = hashlib.md5(cover_data).hexdigest()
                db.session.add(book)
                db.session.flush()
                existing_cover = db.session.scalar(
                    select(Cover).where(Cover.md5_hash == digest)
                )
                if existing_cover:
                    cover = Cover(
                        filename=existing_cover.filename,
                        mime_type=existing_cover.mime_type,
                        md5_hash=digest,
                        book=book,
                    )
                else:
                    cover = Cover(
                        filename="pending",
                        mime_type=cover_file.mimetype,
                        md5_hash=digest,
                        book=book,
                    )
                    db.session.add(cover)
                    db.session.flush()
                    extension = get_image_extension(cover_file.filename)
                    cover.filename = f"{cover.id}{extension}"
                    created_filename = cover.filename
                    save_upload(created_filename, cover_data)
                db.session.add(cover)
                db.session.commit()
            except Exception:
                db.session.rollback()
                remove_unused_file(created_filename)
                flash(
                    "При сохранении данных возникла ошибка. "
                    "Проверьте корректность введённых данных.",
                    "danger",
                )
                return render_template(
                    "book_form.html",
                    book=book,
                    genres=genres,
                    selected_genre_ids=selected_genre_ids,
                    mode="create",
                )
            flash("Книга успешно добавлена.", "success")
            return redirect(url_for("book_detail", book_id=book.id))
        return render_template(
            "book_form.html",
            book=None,
            genres=genres,
            selected_genre_ids=[],
            mode="create",
        )

    @app.route("/books/<int:book_id>/edit", methods=["GET", "POST"])
    @roles_required(ROLE_ADMIN, ROLE_MODERATOR)
    def edit_book(book_id):
        book = get_book_or_404(book_id)
        genres = get_all_genres()
        if request.method == "POST":
            require_valid_csrf()
            selected_genre_ids = request.form.getlist("genres")
            errors = apply_book_form(book, genres, selected_genre_ids)
            if errors:
                flash_form_errors(errors)
                return render_template(
                    "book_form.html",
                    book=book,
                    genres=genres,
                    selected_genre_ids=selected_genre_ids,
                    mode="edit",
                )
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                flash(
                    "При сохранении данных возникла ошибка. "
                    "Проверьте корректность введённых данных.",
                    "danger",
                )
                return render_template(
                    "book_form.html",
                    book=book,
                    genres=genres,
                    selected_genre_ids=selected_genre_ids,
                    mode="edit",
                )
            flash("Данные книги успешно обновлены.", "success")
            return redirect(url_for("book_detail", book_id=book.id))
        return render_template(
            "book_form.html",
            book=book,
            genres=genres,
            selected_genre_ids=[str(genre.id) for genre in book.genres],
            mode="edit",
        )

    @app.post("/books/<int:book_id>/delete")
    @roles_required(ROLE_ADMIN)
    def delete_book(book_id):
        require_valid_csrf()
        book = get_book_or_404(book_id)
        cover_filename = book.cover.filename if book.cover else None
        title = book.title
        try:
            db.session.delete(book)
            db.session.commit()
            remove_unused_file(cover_filename)
        except Exception:
            db.session.rollback()
            flash("При удалении книги возникла ошибка.", "danger")
            return redirect(url_for("index"))
        flash(f"Книга «{title}» успешно удалена.", "success")
        return redirect(url_for("index"))

    @app.route("/books/<int:book_id>/reviews/new", methods=["GET", "POST"])
    @roles_required(ROLE_ADMIN, ROLE_MODERATOR, ROLE_USER)
    def create_review(book_id):
        book = get_book_or_404(book_id)
        user = get_current_user()
        own_review = db.session.scalar(
            select(Review).where(
                Review.book_id == book.id, Review.user_id == user.id
            )
        )
        if own_review:
            flash("Вы уже оставили рецензию на эту книгу.", "warning")
            return redirect(url_for("book_detail", book_id=book.id))
        if request.method == "POST":
            require_valid_csrf()
            rating = request.form.get("rating", "5")
            text = sanitize_markdown(request.form.get("text", ""))
            errors = []
            if rating not in {"0", "1", "2", "3", "4", "5"}:
                errors.append("Выберите оценку от 0 до 5.")
            if not text.strip():
                errors.append("Введите текст рецензии.")
            if errors:
                flash_form_errors(errors, prefix="Не удалось сохранить рецензию.")
                return render_template(
                    "review_form.html", book=book, rating=rating, text=text
                )
            review = Review(book=book, user=user, rating=int(rating), text=text)
            try:
                db.session.add(review)
                db.session.commit()
            except Exception:
                db.session.rollback()
                flash("Не удалось сохранить рецензию.", "danger")
                return render_template(
                    "review_form.html", book=book, rating=rating, text=text
                )
            flash("Рецензия успешно добавлена.", "success")
            return redirect(url_for("book_detail", book_id=book.id))
        return render_template("review_form.html", book=book, rating="5", text="")

    @app.post("/reviews/<int:review_id>/delete")
    @roles_required(ROLE_ADMIN, ROLE_MODERATOR)
    def delete_review(review_id):
        require_valid_csrf()
        review = db.session.get(Review, review_id)
        if review is None:
            abort(404)
        book_id = review.book_id
        try:
            db.session.delete(review)
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("При удалении рецензии возникла ошибка.", "danger")
        else:
            flash("Рецензия удалена.", "success")
        return redirect(url_for("book_detail", book_id=book_id))


def initialize_database():
    db.create_all()
    if db.session.scalar(select(func.count(Role.id))) == 0:
        db.session.add_all(
            [
                Role(
                    name=ROLE_ADMIN,
                    description="Администратор: полный доступ к системе.",
                ),
                Role(
                    name=ROLE_MODERATOR,
                    description="Модератор: редактирование книг и рецензий.",
                ),
                Role(
                    name=ROLE_USER,
                    description="Пользователь: просмотр книг и создание рецензий.",
                ),
            ]
        )
        db.session.flush()

    if db.session.scalar(select(func.count(Genre.id))) == 0:
        db.session.add_all(
            [
                Genre(name="Антиутопия"),
                Genre(name="Детектив"),
                Genre(name="Классика"),
                Genre(name="Научная фантастика"),
                Genre(name="Приключения"),
                Genre(name="Роман"),
                Genre(name="Фэнтези"),
            ]
        )

    if db.session.scalar(select(func.count(User.id))) == 0:
        role_by_name = {
            role.name: role for role in db.session.scalars(select(Role)).all()
        }
        users = [
            User(
                login="admin",
                last_name="Иванов",
                first_name="Иван",
                middle_name="Иванович",
                role=role_by_name[ROLE_ADMIN],
            ),
            User(
                login="moderator",
                last_name="Петрова",
                first_name="Мария",
                middle_name="Сергеевна",
                role=role_by_name[ROLE_MODERATOR],
            ),
            User(
                login="user",
                last_name="Сидоров",
                first_name="Алексей",
                middle_name=None,
                role=role_by_name[ROLE_USER],
            ),
        ]
        for user in users:
            user.set_password(user.login)
        db.session.add_all(users)
    db.session.commit()


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if get_current_user() is None:
            flash(AUTH_REQUIRED_MESSAGE, "warning")
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)

    return wrapped_view


def roles_required(*allowed_roles):
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            user = get_current_user()
            if user is None:
                flash(AUTH_REQUIRED_MESSAGE, "warning")
                return redirect(url_for("login", next=request.full_path.rstrip("?")))
            if user.role.name not in allowed_roles:
                flash(ACCESS_DENIED_MESSAGE, "danger")
                return redirect(url_for("index"))
            return view(*args, **kwargs)

        return wrapped_view

    return decorator


def get_csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_hex(24)
        session["_csrf_token"] = token
    return token


def require_valid_csrf():
    expected = session.get("_csrf_token")
    actual = request.form.get("csrf_token")
    if not expected or not actual or not secrets.compare_digest(expected, actual):
        abort(400)


def is_safe_url(target):
    reference_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in {"http", "https"} and reference_url.netloc == test_url.netloc


def sanitize_markdown(value):
    return bleach.clean(value.strip(), tags=set(), attributes={}, strip=True)


def render_markdown(value):
    rendered = markdown.markdown(value or "", extensions=["extra", "sane_lists"])
    clean_html = bleach.clean(
        rendered,
        tags=ALLOWED_MARKDOWN_TAGS,
        attributes=ALLOWED_MARKDOWN_ATTRIBUTES,
        protocols={"http", "https", "mailto"},
        strip=True,
    )
    return Markup(clean_html)


def get_book_or_404(book_id):
    book = db.session.scalar(
        select(Book)
        .options(
            selectinload(Book.genres),
            selectinload(Book.cover),
            selectinload(Book.reviews).selectinload(Review.user),
        )
        .where(Book.id == book_id)
    )
    if book is None:
        abort(404)
    return book


def get_user_collection_or_404(collection_id):
    user = get_current_user()
    collection = db.session.scalar(
        select(Collection)
        .options(
            selectinload(Collection.books).selectinload(Book.genres),
            selectinload(Collection.books).selectinload(Book.reviews),
            selectinload(Collection.books).selectinload(Book.cover),
        )
        .where(Collection.id == collection_id, Collection.user_id == user.id)
    )
    if collection is None:
        abort(404)
    return collection


def get_all_genres():
    return db.session.scalars(select(Genre).order_by(Genre.name)).all()


def apply_book_form(book, genres, selected_genre_ids):
    errors = []
    title = request.form.get("title", "").strip()
    description = sanitize_markdown(request.form.get("description", ""))
    publisher = request.form.get("publisher", "").strip()
    author = request.form.get("author", "").strip()
    year = parse_int(request.form.get("year"))
    pages = parse_int(request.form.get("pages"))

    if not title:
        errors.append("Введите название книги.")
    if not description:
        errors.append("Введите описание книги.")
    if year is None or not 1 <= year <= 9999:
        errors.append("Укажите корректный год.")
    if not publisher:
        errors.append("Введите название издательства.")
    if not author:
        errors.append("Введите автора.")
    if pages is None or pages <= 0:
        errors.append("Количество страниц должно быть положительным числом.")

    selected_ids = {parse_int(item) for item in selected_genre_ids}
    selected_ids.discard(None)
    genre_by_id = {genre.id: genre for genre in genres}
    if not selected_ids or not selected_ids.issubset(genre_by_id):
        errors.append("Выберите хотя бы один жанр.")

    book.title = title
    book.description = description
    book.year = year
    book.publisher = publisher
    book.author = author
    book.pages = pages
    book.genres = [genre_by_id[genre_id] for genre_id in selected_ids if genre_id in genre_by_id]
    return errors


def parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def flash_form_errors(errors, prefix=None):
    message = "При сохранении данных возникла ошибка. Проверьте корректность введённых данных."
    if prefix:
        message = prefix
    flash(message, "danger")
    for error in errors:
        flash(error, "danger")


def get_image_extension(original_filename):
    extension = Path(secure_filename(original_filename)).suffix.lower()
    if not extension or len(extension) > 10:
        return ".img"
    return extension


def save_upload(filename, data):
    upload_path = Path(current_app_config("UPLOAD_FOLDER")) / filename
    upload_path.write_bytes(data)


def remove_unused_file(filename):
    if not filename:
        return
    has_references = db.session.scalar(
        select(func.count(Cover.id)).where(Cover.filename == filename)
    )
    if has_references:
        return
    upload_path = Path(current_app_config("UPLOAD_FOLDER")) / filename
    if upload_path.exists():
        upload_path.unlink()


def current_app_config(key):
    from flask import current_app

    return current_app.config[key]


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
