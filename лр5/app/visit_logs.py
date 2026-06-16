import csv
from datetime import datetime
from io import StringIO
from math import ceil

from flask import Blueprint, Response, g, render_template, request

from .auth import ADMIN_ROLE, check_rights, login_required
from .db import get_db
from .users import full_name


bp = Blueprint("visit_logs", __name__, url_prefix="/visit-logs")
PER_PAGE = 10
GUEST_NAME = "Неаутентифицированный пользователь"


@bp.before_app_request
def log_visit():
    if request.endpoint == "static":
        return

    user = getattr(g, "user", None)
    user_id = user["id"] if user is not None else None
    get_db().execute(
        "INSERT INTO visit_logs (path, user_id) VALUES (?, ?)",
        (request.path[:100], user_id),
    )
    get_db().commit()


def is_admin():
    user = getattr(g, "user", None)
    return user is not None and user["role_name"] == ADMIN_ROLE


def user_name(row):
    if row["user_id"] is None or row["login"] is None:
        return GUEST_NAME

    return full_name(row)


@bp.app_template_filter("format_visit_datetime")
def format_visit_datetime(value):
    if not value:
        return ""

    try:
        return datetime.fromisoformat(value).strftime("%d.%m.%Y %H:%M:%S")
    except ValueError:
        return value


def get_page_number():
    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        return 1

    return max(page, 1)


def get_visit_rows(page):
    params = []
    where = ""
    if not is_admin():
        where = "WHERE visit_logs.user_id = ?"
        params.append(g.user["id"])

    total = get_db().execute(
        f"SELECT COUNT(*) FROM visit_logs {where}",
        params,
    ).fetchone()[0]
    total_pages = max(ceil(total / PER_PAGE), 1)
    page = min(page, total_pages)
    offset = (page - 1) * PER_PAGE

    rows = get_db().execute(
        f"""
        SELECT
            visit_logs.*,
            users.login,
            users.last_name,
            users.first_name,
            users.middle_name
        FROM visit_logs
        LEFT JOIN users ON visit_logs.user_id = users.id
        {where}
        ORDER BY datetime(visit_logs.created_at) DESC, visit_logs.id DESC
        LIMIT ? OFFSET ?
        """,
        [*params, PER_PAGE, offset],
    ).fetchall()

    return rows, total, total_pages, page, offset


def get_page_report_rows():
    return get_db().execute(
        """
        SELECT path, COUNT(*) AS visits_count
        FROM visit_logs
        GROUP BY path
        ORDER BY visits_count DESC, path
        """
    ).fetchall()


def get_user_report_rows():
    return get_db().execute(
        """
        SELECT
            visit_logs.user_id,
            users.login,
            users.last_name,
            users.first_name,
            users.middle_name,
            COUNT(*) AS visits_count
        FROM visit_logs
        LEFT JOIN users ON visit_logs.user_id = users.id
        GROUP BY visit_logs.user_id, users.login, users.last_name, users.first_name, users.middle_name
        ORDER BY visits_count DESC, users.last_name, users.first_name, users.login
        """
    ).fetchall()


def export_csv(filename, headers, rows):
    csv_file = StringIO()
    writer = csv.writer(csv_file)
    writer.writerow(headers)
    writer.writerows(rows)

    return Response(
        csv_file.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bp.route("")
@login_required
@check_rights("view_visit_logs")
def index():
    rows, total, total_pages, page, offset = get_visit_rows(get_page_number())

    return render_template(
        "visit_logs/index.html",
        rows=rows,
        total=total,
        total_pages=total_pages,
        page=page,
        offset=offset,
        user_name=user_name,
    )


@bp.route("/pages")
@login_required
@check_rights("view_page_report")
def pages_report():
    return render_template("visit_logs/pages.html", rows=get_page_report_rows())


@bp.route("/pages.csv")
@login_required
@check_rights("export_page_report")
def export_pages_report():
    rows = [
        (index, row["path"], row["visits_count"])
        for index, row in enumerate(get_page_report_rows(), start=1)
    ]
    return export_csv("visits_by_pages.csv", ["№", "Страница", "Количество посещений"], rows)


@bp.route("/users")
@login_required
@check_rights("view_user_report")
def users_report():
    return render_template("visit_logs/users.html", rows=get_user_report_rows(), user_name=user_name)


@bp.route("/users.csv")
@login_required
@check_rights("export_user_report")
def export_users_report():
    rows = [
        (index, user_name(row), row["visits_count"])
        for index, row in enumerate(get_user_report_rows(), start=1)
    ]
    return export_csv("visits_by_users.csv", ["№", "Пользователь", "Количество посещений"], rows)
