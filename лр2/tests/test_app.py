import pytest

from app import (
    COOKIE_NAME,
    COOKIE_VALUE,
    ERROR_INVALID_CHARS,
    ERROR_WRONG_DIGITS,
    app as flask_app,
    format_phone_number,
    validate_phone_number,
)


@pytest.fixture()
def client():
    flask_app.config.update(TESTING=True)
    with flask_app.test_client() as test_client:
        yield test_client


def page_text(response):
    return response.get_data(as_text=True)


def test_url_params_page_shows_all_passed_params(client):
    response = client.get("/url-params?name=Ivan&city=Kazan&tag=one&tag=two")
    html = page_text(response)

    assert response.status_code == 200
    for expected in ("name", "Ivan", "city", "Kazan", "tag", "one", "two"):
        assert expected in html


def test_headers_page_shows_header_names_and_values(client):
    response = client.get(
        "/headers",
        headers={
            "X-Lab-Header": "first value",
            "X-Another-Header": "second value",
        },
    )
    html = page_text(response)

    assert response.status_code == 200
    assert "X-Lab-Header" in html
    assert "first value" in html
    assert "X-Another-Header" in html
    assert "second value" in html


def test_cookie_page_sets_cookie_when_it_is_missing(client):
    response = client.get("/cookies")
    html = page_text(response)
    set_cookie_headers = response.headers.getlist("Set-Cookie")

    assert response.status_code == 200
    assert COOKIE_NAME in html
    assert COOKIE_VALUE in html
    assert any(f"{COOKIE_NAME}={COOKIE_VALUE}" in header for header in set_cookie_headers)


def test_cookie_page_deletes_cookie_when_it_exists(client):
    client.get("/cookies")

    response = client.get("/cookies")
    html = page_text(response)
    set_cookie_headers = response.headers.getlist("Set-Cookie")

    assert response.status_code == 200
    assert "теперь удалена" in html
    assert any(f"{COOKIE_NAME}=" in header for header in set_cookie_headers)
    assert any("Expires=" in header for header in set_cookie_headers)


def test_form_params_page_shows_submitted_form_values(client):
    response = client.post(
        "/form-params",
        data={
            "username": "Анна",
            "course": "Веб-программирование",
        },
    )
    html = page_text(response)

    assert response.status_code == 200
    assert "username" in html
    assert "Анна" in html
    assert "course" in html
    assert "Веб-программирование" in html


@pytest.mark.parametrize(
    ("phone", "formatted"),
    [
        ("+7 (123) 456-75-90", "8-123-456-75-90"),
        ("8(123)4567590", "8-123-456-75-90"),
        ("123.456.75.90", "8-123-456-75-90"),
        ("  +7 123 456 75 90  ", "8-123-456-75-90"),
        ("123 456 75 90", "8-123-456-75-90"),
    ],
)
def test_valid_phone_numbers_are_formatted(phone, formatted):
    is_valid, error = validate_phone_number(phone)

    assert is_valid is True
    assert error is None
    assert format_phone_number(phone) == formatted


@pytest.mark.parametrize(
    "phone",
    [
        "+7 (123) 456-75-9",
        "8(123)456759",
        "123456789",
        "",
        "++--",
    ],
)
def test_phone_validation_rejects_wrong_digit_count(phone):
    is_valid, error = validate_phone_number(phone)

    assert is_valid is False
    assert error == ERROR_WRONG_DIGITS


@pytest.mark.parametrize(
    "phone",
    [
        "123-abc-4567",
        "+7 (123) 456-75-9x",
        "123/456/7890",
        "8(123)4567590!",
    ],
)
def test_phone_validation_rejects_invalid_characters(phone):
    is_valid, error = validate_phone_number(phone)

    assert is_valid is False
    assert error == ERROR_INVALID_CHARS


def test_phone_page_shows_bootstrap_error_for_wrong_digit_count(client):
    response = client.post("/phone", data={"phone": "123456789"})
    html = page_text(response)

    assert response.status_code == 200
    assert ERROR_WRONG_DIGITS in html
    assert "is-invalid" in html
    assert "invalid-feedback" in html


def test_phone_page_shows_bootstrap_error_for_invalid_characters(client):
    response = client.post("/phone", data={"phone": "123/456/7890"})
    html = page_text(response)

    assert response.status_code == 200
    assert ERROR_INVALID_CHARS in html
    assert "is-invalid" in html
    assert "invalid-feedback" in html


def test_phone_page_shows_formatted_number_for_valid_input(client):
    response = client.post("/phone", data={"phone": "+7 (123) 456-75-90"})
    html = page_text(response)

    assert response.status_code == 200
    assert "8-123-456-75-90" in html
    assert "is-invalid" not in html
    assert "invalid-feedback" not in html
