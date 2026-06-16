from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, urlparse

import pytest

from app import create_app


SUCCESS_MESSAGE = "Вы успешно вошли в систему."
ERROR_MESSAGE = "Неверно введены логин или пароль."
AUTH_REQUIRED_MESSAGE = (
    "Для доступа к запрашиваемой странице необходимо пройти процедуру "
    "аутентификации."
)


@pytest.fixture()
def app():
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret-key",
        }
    )


@pytest.fixture()
def client(app):
    return app.test_client()


def html(response):
    return response.get_data(as_text=True)


def login(
    client,
    username="user",
    password="qwerty",
    remember=False,
    next_url="",
    follow_redirects=False,
):
    data = {
        "username": username,
        "password": password,
    }

    if remember:
        data["remember"] = "on"

    if next_url:
        data["next"] = next_url
        return client.post(
            "/login",
            query_string={"next": next_url},
            data=data,
            follow_redirects=follow_redirects,
        )

    return client.post("/login", data=data, follow_redirects=follow_redirects)


def test_visits_counter_increments_for_same_user(client):
    first_response = client.get("/visits")
    second_response = client.get("/visits")

    assert first_response.status_code == 200
    assert "Вы посетили эту страницу 1 раз(а)." in html(first_response)
    assert "Вы посетили эту страницу 2 раз(а)." in html(second_response)


def test_visits_counter_is_separate_for_each_user(app):
    first_client = app.test_client()
    second_client = app.test_client()

    first_client.get("/visits")
    first_second_response = first_client.get("/visits")
    second_first_response = second_client.get("/visits")

    assert "Вы посетили эту страницу 2 раз(а)." in html(first_second_response)
    assert "Вы посетили эту страницу 1 раз(а)." in html(second_first_response)


def test_successful_login_redirects_to_index(client):
    response = login(client)

    assert response.status_code == 302
    assert urlparse(response.headers["Location"]).path == "/"


def test_successful_login_shows_success_message_on_index(client):
    response = login(client, follow_redirects=True)

    assert response.status_code == 200
    assert SUCCESS_MESSAGE in html(response)
    assert "Здравствуйте, user. Вы вошли в приложение." in html(response)


def test_failed_login_stays_on_login_page_and_shows_error(client):
    response = login(client, password="wrong-password")

    assert response.status_code == 200
    assert ERROR_MESSAGE in html(response)
    assert "<h1>Вход</h1>" in html(response)


def test_failed_login_does_not_authenticate_user(client):
    login(client, password="wrong-password")

    response = client.get("/secret")

    assert response.status_code == 302
    assert urlparse(response.headers["Location"]).path == "/login"


def test_authenticated_user_can_open_secret_page(client):
    login(client)

    response = client.get("/secret")

    assert response.status_code == 200
    assert "<h1>Секретная страница</h1>" in html(response)
    assert "Это закрытый раздел" in html(response)


def test_anonymous_user_is_redirected_from_secret_to_login(client):
    response = client.get("/secret")
    location = urlparse(response.headers["Location"])

    assert response.status_code == 302
    assert location.path == "/login"
    assert parse_qs(location.query)["next"] == ["/secret"]


def test_anonymous_user_sees_auth_required_message_after_secret_redirect(client):
    response = client.get("/secret", follow_redirects=True)

    assert response.status_code == 200
    assert "<h1>Вход</h1>" in html(response)
    assert AUTH_REQUIRED_MESSAGE in html(response)


def test_login_after_secret_redirect_returns_user_to_secret_page(client):
    redirect_response = client.get("/secret")
    next_url = parse_qs(urlparse(redirect_response.headers["Location"]).query)["next"][0]

    response = login(client, next_url=next_url, follow_redirects=True)

    assert response.status_code == 200
    assert SUCCESS_MESSAGE in html(response)
    assert "<h1>Секретная страница</h1>" in html(response)


def test_remember_me_sets_remember_token_with_lifetime(client):
    response = login(client, remember=True)
    cookies = response.headers.getlist("Set-Cookie")
    remember_cookie = next(
        cookie for cookie in cookies if cookie.startswith("remember_token=")
    )
    expires_header = next(
        part.strip().removeprefix("Expires=")
        for part in remember_cookie.split(";")
        if part.strip().startswith("Expires=")
    )
    expires_at = parsedate_to_datetime(expires_header)

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    remaining_lifetime = expires_at - datetime.now(timezone.utc)

    assert remember_cookie
    assert timedelta(days=6, hours=23) <= remaining_lifetime <= timedelta(
        days=7, hours=1
    )


def test_login_without_remember_me_does_not_set_remember_token(client):
    response = login(client, remember=False)
    cookies = response.headers.getlist("Set-Cookie")

    assert all(not cookie.startswith("remember_token=") for cookie in cookies)


def test_navbar_for_anonymous_user_hides_secret_link(client):
    response = client.get("/")
    page = html(response)

    assert 'href="/"' in page
    assert 'href="/visits"' in page
    assert 'href="/login"' in page
    assert 'href="/secret"' not in page
    assert 'href="/logout"' not in page


def test_navbar_for_authenticated_user_shows_secret_link(client):
    login(client)
    response = client.get("/")
    page = html(response)

    assert 'href="/"' in page
    assert 'href="/visits"' in page
    assert 'href="/secret"' in page
    assert 'href="/logout"' in page
    assert 'href="/login"' not in page
