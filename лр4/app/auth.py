from functools import wraps

from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db
from .validation import validate_password


bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")

    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute(
            """
            SELECT users.*, roles.name AS role_name
            FROM users
            LEFT JOIN roles ON users.role_id = roles.id
            WHERE users.id = ?
            """,
            (user_id,),
        ).fetchone()


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.path))

        return view(**kwargs)

    return wrapped_view


@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        login_value = request.form.get("login", "").strip()
        password = request.form.get("password", "")
        error = None

        user = get_db().execute(
            "SELECT * FROM users WHERE login = ?", (login_value,)
        ).fetchone()

        if user is None:
            error = "Пользователь с таким логином не найден"
        elif not check_password_hash(user["password_hash"], password):
            error = "Неверный пароль"

        if error is None:
            session.clear()
            session["user_id"] = user["id"]
            flash("Вы успешно вошли в систему", "success")
            return redirect(request.args.get("next") or url_for("users.index"))

        flash(error, "danger")

    return render_template("auth/login.html")


@bp.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли из системы", "success")
    return redirect(url_for("users.index"))


@bp.route("/change-password", methods=("GET", "POST"))
@login_required
def change_password():
    errors = {}

    if request.method == "POST":
        old_password = request.form.get("old_password", "")
        new_password = request.form.get("new_password", "")
        repeat_password = request.form.get("repeat_password", "")

        if not check_password_hash(g.user["password_hash"], old_password):
            errors["old_password"] = ["Старый пароль указан неверно"]

        new_password_errors = validate_password(new_password)
        if new_password_errors:
            errors["new_password"] = new_password_errors

        if new_password != repeat_password:
            errors["repeat_password"] = ["Пароли не совпадают"]

        if not errors:
            get_db().execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (generate_password_hash(new_password), g.user["id"]),
            )
            get_db().commit()
            flash("Пароль успешно изменен", "success")
            return redirect(url_for("users.index"))

        flash("Исправьте ошибки в форме", "danger")

    return render_template("auth/change_password.html", errors=errors)
