from werkzeug.security import generate_password_hash


def create_regular_user(db, login="user1", password="User123!"):
    role = db.execute("SELECT id FROM roles WHERE name = ?", ("Пользователь",)).fetchone()
    db.execute(
        """
        INSERT INTO users
            (login, password_hash, last_name, first_name, middle_name, role_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            login,
            generate_password_hash(password),
            "Обычный",
            "Пользователь",
            "",
            role["id"],
            "2026-05-17T00:00:00+00:00",
        ),
    )
    db.commit()
    return db.execute("SELECT * FROM users WHERE login = ?", (login,)).fetchone()


def test_visit_log_records_requests(client, db):
    client.get("/")

    log = db.execute("SELECT * FROM visit_logs WHERE path = ?", ("/",)).fetchone()

    assert log is not None
    assert log["user_id"] is None
    assert log["created_at"]


def test_admin_sees_all_visit_logs_and_report_links(client, auth, db):
    db.execute(
        "INSERT INTO visit_logs (path, user_id, created_at) VALUES (?, ?, ?)",
        ("/sample", None, "2001-01-01 01:01:01"),
    )
    db.commit()
    auth.login()

    response = client.get("/visit-logs")

    assert response.status_code == 200
    assert "Журнал посещений".encode() in response.data
    assert "Неаутентифицированный пользователь".encode() in response.data
    assert "/sample".encode() in response.data
    assert "01.01.2001 01:01:01".encode() in response.data
    assert "Отчет по страницам".encode() in response.data
    assert "Отчет по пользователям".encode() in response.data
    assert "Страница 1 из".encode() in response.data


def test_regular_user_sees_only_own_visit_logs(client, auth, db):
    user = create_regular_user(db)
    db.execute(
        "INSERT INTO visit_logs (path, user_id, created_at) VALUES (?, ?, ?)",
        ("/guest", None, "2026-05-17 10:00:00"),
    )
    db.execute(
        "INSERT INTO visit_logs (path, user_id, created_at) VALUES (?, ?, ?)",
        ("/own", user["id"], "2026-05-17 11:00:00"),
    )
    db.commit()
    auth.login("user1", "User123!")

    response = client.get("/visit-logs")

    assert response.status_code == 200
    assert "/own".encode() in response.data
    assert "/guest".encode() not in response.data
    assert "Отчет по страницам".encode() not in response.data
    assert "Отчет по пользователям".encode() not in response.data


def test_regular_user_cannot_open_reports(client, auth, db):
    create_regular_user(db)
    auth.login("user1", "User123!")

    response = client.get("/visit-logs/pages", follow_redirects=True)

    assert response.status_code == 200
    assert "У вас недостаточно прав для доступа к данной странице.".encode() in response.data


def test_pages_report_and_csv_export(client, auth, db):
    db.executemany(
        "INSERT INTO visit_logs (path, user_id, created_at) VALUES (?, ?, ?)",
        [
            ("/alpha", None, "2026-05-17 10:00:00"),
            ("/alpha", None, "2026-05-17 10:01:00"),
            ("/beta", None, "2026-05-17 10:02:00"),
        ],
    )
    db.commit()
    auth.login()

    report_response = client.get("/visit-logs/pages")
    export_response = client.get("/visit-logs/pages.csv")

    assert report_response.status_code == 200
    assert "Экспорт в CVS".encode() in report_response.data
    assert "/alpha".encode() in report_response.data
    assert export_response.status_code == 200
    assert export_response.mimetype == "text/csv"
    assert "attachment; filename=visits_by_pages.csv" in export_response.headers["Content-Disposition"]
    assert "Страница".encode() in export_response.data
    assert "/alpha".encode() in export_response.data


def test_users_report_and_csv_export(client, auth, db):
    user = create_regular_user(db)
    db.executemany(
        "INSERT INTO visit_logs (path, user_id, created_at) VALUES (?, ?, ?)",
        [
            ("/guest", None, "2026-05-17 10:00:00"),
            ("/profile", user["id"], "2026-05-17 10:01:00"),
        ],
    )
    db.commit()
    auth.login()

    report_response = client.get("/visit-logs/users")
    export_response = client.get("/visit-logs/users.csv")

    assert report_response.status_code == 200
    assert "Обычный Пользователь".encode() in report_response.data
    assert "Неаутентифицированный пользователь".encode() in report_response.data
    assert export_response.status_code == 200
    assert "Пользователь".encode() in export_response.data
    assert "Обычный Пользователь".encode() in export_response.data
