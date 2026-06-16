from werkzeug.security import check_password_hash, generate_password_hash


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


def test_index_is_public_and_hides_private_actions(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "Список пользователей".encode() in response.data
    assert "Просмотр".encode() not in response.data
    assert "Создание пользователя".encode() not in response.data
    assert "Редактирование".encode() not in response.data
    assert "Удаление".encode() not in response.data


def test_authenticated_index_shows_crud_actions(client, auth):
    auth.login()
    response = client.get("/")

    assert "Создание пользователя".encode() in response.data
    assert "Редактирование".encode() in response.data
    assert "Удаление".encode() in response.data


def test_view_user_requires_authentication(client):
    response = client.get("/users/1")

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_admin_can_view_user(client, auth):
    auth.login()
    response = client.get("/users/1")

    assert response.status_code == 200
    assert "Системный".encode() in response.data
    assert "Администратор".encode() in response.data


def test_regular_user_sees_only_own_actions(client, auth, db):
    user = create_regular_user(db)
    auth.login("user1", "User123!")

    response = client.get("/")

    assert f"/users/{user['id']}".encode() in response.data
    assert f"/users/{user['id']}/edit".encode() in response.data
    assert b"/users/1/edit" not in response.data
    assert "Создание пользователя".encode() not in response.data
    assert "Удаление".encode() not in response.data


def test_regular_user_cannot_view_other_profile(client, auth, db):
    create_regular_user(db)
    auth.login("user1", "User123!")

    response = client.get("/users/1", follow_redirects=True)

    assert response.status_code == 200
    assert "У вас недостаточно прав для доступа к данной странице.".encode() in response.data


def test_regular_user_can_view_own_profile(client, auth, db):
    user = create_regular_user(db)
    auth.login("user1", "User123!")

    response = client.get(f"/users/{user['id']}")

    assert response.status_code == 200
    assert "Обычный".encode() in response.data
    assert "Пользователь".encode() in response.data


def test_create_requires_authentication(client):
    response = client.get("/users/create")

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_create_user_success(client, auth, db):
    auth.login()
    response = client.post(
        "/users/create",
        data={
            "login": "ivanov1",
            "password": "Password1!",
            "last_name": "Иванов",
            "first_name": "Иван",
            "middle_name": "Иванович",
            "role_id": "",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Пользователь успешно создан".encode() in response.data

    user = db.execute("SELECT * FROM users WHERE login = ?", ("ivanov1",)).fetchone()
    assert user is not None
    assert user["password_hash"] != "Password1!"
    assert check_password_hash(user["password_hash"], "Password1!")
    assert user["created_at"]
    assert user["role_id"] is None


def test_create_user_validation_keeps_form_values(client, auth):
    auth.login()
    response = client.post(
        "/users/create",
        data={
            "login": "иван",
            "password": "short",
            "last_name": "",
            "first_name": "",
            "middle_name": "Петрович",
            "role_id": "",
        },
    )

    assert response.status_code == 200
    assert "Исправьте ошибки в форме".encode() in response.data
    assert "Логин должен содержать не менее 5 символов".encode() in response.data
    assert "Логин должен состоять только из латинских букв и цифр".encode() in response.data
    assert "Пароль должен содержать не менее 8 символов".encode() in response.data
    assert "Поле не может быть пустым".encode() in response.data
    assert "Петрович".encode() in response.data
    assert b"is-invalid" in response.data


def test_create_user_duplicate_login_shows_error(client, auth):
    auth.login()
    response = client.post(
        "/users/create",
        data={
            "login": "admin",
            "password": "Password1!",
            "last_name": "Иванов",
            "first_name": "Иван",
            "middle_name": "",
            "role_id": "",
        },
    )

    assert response.status_code == 200
    assert "Пользователь с таким логином уже существует".encode() in response.data


def test_edit_requires_authentication(client):
    response = client.get("/users/1/edit")

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_edit_user_success(client, auth, db):
    auth.login()
    role = db.execute("SELECT id FROM roles WHERE name = ?", ("Пользователь",)).fetchone()
    response = client.post(
        "/users/1/edit",
        data={
            "last_name": "Петров",
            "first_name": "Петр",
            "middle_name": "",
            "role_id": str(role["id"]),
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Пользователь успешно обновлен".encode() in response.data

    user = db.execute("SELECT * FROM users WHERE id = 1").fetchone()
    assert user["last_name"] == "Петров"
    assert user["first_name"] == "Петр"
    assert user["middle_name"] is None
    assert user["role_id"] == role["id"]


def test_edit_user_validation(client, auth):
    auth.login()
    response = client.post(
        "/users/1/edit",
        data={"last_name": "", "first_name": "", "middle_name": "", "role_id": ""},
    )

    assert response.status_code == 200
    assert "Поле не может быть пустым".encode() in response.data
    assert b"is-invalid" in response.data
    assert 'name="login"'.encode() not in response.data
    assert 'name="password"'.encode() not in response.data


def test_regular_user_cannot_change_own_role(client, auth, db):
    user = create_regular_user(db)
    admin_role = db.execute("SELECT id FROM roles WHERE name = ?", ("Администратор",)).fetchone()
    auth.login("user1", "User123!")

    response = client.get(f"/users/{user['id']}/edit")

    assert response.status_code == 200
    assert b'<select id="role_id" name="role_id" disabled>' in response.data

    response = client.post(
        f"/users/{user['id']}/edit",
        data={
            "last_name": "Новая",
            "first_name": "Фамилия",
            "middle_name": "",
            "role_id": str(admin_role["id"]),
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    updated_user = db.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    assert updated_user["last_name"] == "Новая"
    assert updated_user["role_id"] == user["role_id"]


def test_regular_user_cannot_create_or_delete_users(client, auth, db):
    user = create_regular_user(db)
    auth.login("user1", "User123!")

    create_response = client.get("/users/create", follow_redirects=True)
    delete_response = client.post(f"/users/{user['id']}/delete", follow_redirects=True)

    assert "У вас недостаточно прав для доступа к данной странице.".encode() in create_response.data
    assert "У вас недостаточно прав для доступа к данной странице.".encode() in delete_response.data
    assert db.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone() is not None


def test_delete_requires_authentication(client):
    response = client.post("/users/1/delete")

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_delete_user_success(client, auth, db):
    auth.login()
    client.post(
        "/users/create",
        data={
            "login": "delete1",
            "password": "Password1!",
            "last_name": "Удаляемый",
            "first_name": "Пользователь",
            "middle_name": "",
            "role_id": "",
        },
    )
    user = db.execute("SELECT id FROM users WHERE login = ?", ("delete1",)).fetchone()

    response = client.post(f"/users/{user['id']}/delete", follow_redirects=True)

    assert response.status_code == 200
    assert "успешно удален".encode() in response.data
    assert db.execute("SELECT * FROM users WHERE login = ?", ("delete1",)).fetchone() is None


def test_change_password_requires_authentication(client):
    response = client.get("/auth/change-password")

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_change_password_validation(client, auth):
    auth.login()
    response = client.post(
        "/auth/change-password",
        data={
            "old_password": "wrong",
            "new_password": "short",
            "repeat_password": "other",
        },
    )

    assert response.status_code == 200
    assert "Старый пароль указан неверно".encode() in response.data
    assert "Пароль должен содержать не менее 8 символов".encode() in response.data
    assert "Пароли не совпадают".encode() in response.data


def test_change_password_success(client, auth):
    auth.login()
    response = client.post(
        "/auth/change-password",
        data={
            "old_password": "Admin123!",
            "new_password": "NewPassword1!",
            "repeat_password": "NewPassword1!",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Пароль успешно изменен".encode() in response.data

    auth.logout()
    login_response = auth.login(password="NewPassword1!")
    assert "Вы успешно вошли в систему".encode() in login_response.data
