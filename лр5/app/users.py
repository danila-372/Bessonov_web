from datetime import datetime, timezone

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from sqlite3 import IntegrityError
from werkzeug.security import generate_password_hash

from .auth import ADMIN_ROLE, check_rights, login_required
from .db import get_db
from .validation import normalize_optional, parse_role_id, validate_user_form


bp = Blueprint("users", __name__)


def get_roles():
    return get_db().execute("SELECT * FROM roles ORDER BY name").fetchall()


def get_user(user_id):
    user = get_db().execute(
        """
        SELECT users.*, roles.name AS role_name
        FROM users
        LEFT JOIN roles ON users.role_id = roles.id
        WHERE users.id = ?
        """,
        (user_id,),
    ).fetchone()

    if user is None:
        flash("Пользователь не найден", "danger")

    return user


def full_name(user):
    parts = [user["last_name"], user["first_name"], user["middle_name"]]
    return " ".join(part for part in parts if part) or user["login"]


def form_to_user_data(form, include_credentials, include_role=True, current_role_id=None):
    data = {
        "last_name": form.get("last_name", "").strip(),
        "first_name": form.get("first_name", "").strip(),
        "middle_name": normalize_optional(form.get("middle_name")),
        "role_id": parse_role_id(form.get("role_id")) if include_role else current_role_id,
    }

    if include_credentials:
        data["login"] = form.get("login", "").strip()
        data["password"] = form.get("password", "")

    return data


@bp.app_template_filter("full_name")
def full_name_filter(user):
    return full_name(user)


@bp.route("/")
def index():
    users = get_db().execute(
        """
        SELECT users.*, roles.name AS role_name
        FROM users
        LEFT JOIN roles ON users.role_id = roles.id
        ORDER BY users.id
        """
    ).fetchall()
    return render_template("users/index.html", users=users)


@bp.route("/users/<int:user_id>")
@login_required
@check_rights("view_user")
def view_user(user_id):
    user = get_user(user_id)
    if user is None:
        return redirect(url_for("users.index"))

    return render_template("users/view.html", user=user)


@bp.route("/users/create", methods=("GET", "POST"))
@login_required
@check_rights("create_user")
def create_user():
    errors = {}
    form_data = request.form if request.method == "POST" else {}

    if request.method == "POST":
        errors = validate_user_form(request.form, include_credentials=True)

        if not errors:
            data = form_to_user_data(request.form, include_credentials=True)

            try:
                get_db().execute(
                    """
                    INSERT INTO users
                        (login, password_hash, last_name, first_name, middle_name, role_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        data["login"],
                        generate_password_hash(data["password"]),
                        data["last_name"],
                        data["first_name"],
                        data["middle_name"],
                        data["role_id"],
                        datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    ),
                )
                get_db().commit()
            except IntegrityError as error:
                errors["login"] = ["Пользователь с таким логином уже существует"]
                flash(f"Не удалось создать пользователя: {error}", "danger")
            else:
                flash("Пользователь успешно создан", "success")
                return redirect(url_for("users.index"))

        if errors:
            flash("Исправьте ошибки в форме", "danger")

    return render_template(
        "users/create.html",
        roles=get_roles(),
        form_data=form_data,
        errors=errors,
    )


@bp.route("/users/<int:user_id>/edit", methods=("GET", "POST"))
@login_required
@check_rights("edit_user")
def edit_user(user_id):
    user = get_user(user_id)
    if user is None:
        return redirect(url_for("users.index"))

    can_edit_role = g.user["role_name"] == ADMIN_ROLE
    errors = {}
    form_data = {
        "last_name": user["last_name"] or "",
        "first_name": user["first_name"] or "",
        "middle_name": user["middle_name"] or "",
        "role_id": str(user["role_id"] or ""),
    }

    if request.method == "POST":
        form_data = request.form
        errors = validate_user_form(request.form, include_credentials=False)

        if not errors:
            data = form_to_user_data(
                request.form,
                include_credentials=False,
                include_role=can_edit_role,
                current_role_id=user["role_id"],
            )

            try:
                get_db().execute(
                    """
                    UPDATE users
                    SET last_name = ?, first_name = ?, middle_name = ?, role_id = ?
                    WHERE id = ?
                    """,
                    (
                        data["last_name"],
                        data["first_name"],
                        data["middle_name"],
                        data["role_id"],
                        user_id,
                    ),
                )
                get_db().commit()
            except IntegrityError as error:
                flash(f"Не удалось обновить пользователя: {error}", "danger")
            else:
                flash("Пользователь успешно обновлен", "success")
                return redirect(url_for("users.index"))

        if errors:
            flash("Исправьте ошибки в форме", "danger")

    return render_template(
        "users/edit.html",
        user=user,
        roles=get_roles(),
        form_data=form_data,
        errors=errors,
        role_disabled=not can_edit_role,
    )


@bp.route("/users/<int:user_id>/delete", methods=("POST",))
@login_required
@check_rights("delete_user")
def delete_user(user_id):
    user = get_user(user_id)
    if user is None:
        return redirect(url_for("users.index"))

    try:
        get_db().execute("DELETE FROM users WHERE id = ?", (user_id,))
        get_db().commit()
    except IntegrityError as error:
        flash(f"Не удалось удалить пользователя: {error}", "danger")
    else:
        if session.get("user_id") == user_id:
            session.clear()
        flash(f"Пользователь {full_name(user)} успешно удален", "success")

    return redirect(url_for("users.index"))
