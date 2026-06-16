from app.validation import validate_login, validate_password


def test_validate_login_rules():
    assert "Поле не может быть пустым" in validate_login("")
    assert "Логин должен содержать не менее 5 символов" in validate_login("abc")
    assert "Логин должен состоять только из латинских букв и цифр" in validate_login("логин1")
    assert validate_login("login1") == []


def test_validate_password_rules():
    errors = validate_password("short")

    assert "Пароль должен содержать не менее 8 символов" in errors
    assert "Пароль должен содержать как минимум одну заглавную букву" in errors
    assert "Пароль должен содержать как минимум одну цифру" in errors

    assert "Пароль не должен содержать пробелы" in validate_password("Password 1")
    assert any("допустимые специальные символы" in error for error in validate_password("Password1="))
    assert validate_password("ПарольTest1!") == []
