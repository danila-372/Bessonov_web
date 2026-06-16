import re


LOGIN_RE = re.compile(r"^[A-Za-z0-9]+$")
LATIN_CYRILLIC_LETTERS = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
    "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
)
ARABIC_DIGITS = "0123456789"
ALLOWED_SPECIALS = set(r"""~!?@#$%^&*_-+()[]{}></\|"'.,:;""")
ALLOWED_PASSWORD_CHARS = set(LATIN_CYRILLIC_LETTERS + ARABIC_DIGITS) | ALLOWED_SPECIALS


def validate_login(login):
    errors = []
    login = login or ""

    if not login:
        errors.append("Поле не может быть пустым")
        return errors

    if len(login) < 5:
        errors.append("Логин должен содержать не менее 5 символов")

    if not LOGIN_RE.fullmatch(login):
        errors.append("Логин должен состоять только из латинских букв и цифр")

    return errors


def validate_password(password):
    errors = []
    password = password or ""

    if not password:
        errors.append("Поле не может быть пустым")
        return errors

    if len(password) < 8:
        errors.append("Пароль должен содержать не менее 8 символов")

    if len(password) > 128:
        errors.append("Пароль должен содержать не более 128 символов")

    if any(char.isspace() for char in password):
        errors.append("Пароль не должен содержать пробелы")

    if any(char not in ALLOWED_PASSWORD_CHARS for char in password):
        errors.append(
            "Пароль может содержать только латинские или кириллические буквы, "
            "арабские цифры и допустимые специальные символы"
        )

    if not any(char in LATIN_CYRILLIC_LETTERS and char.isupper() for char in password):
        errors.append("Пароль должен содержать как минимум одну заглавную букву")

    if not any(char in LATIN_CYRILLIC_LETTERS and char.islower() for char in password):
        errors.append("Пароль должен содержать как минимум одну строчную букву")

    if not any(char in ARABIC_DIGITS for char in password):
        errors.append("Пароль должен содержать как минимум одну цифру")

    return errors


def validate_required(value):
    if not (value or "").strip():
        return ["Поле не может быть пустым"]
    return []


def normalize_optional(value):
    value = (value or "").strip()
    return value if value else None


def parse_role_id(value):
    value = (value or "").strip()
    if not value:
        return None

    try:
        return int(value)
    except ValueError:
        return None


def validate_user_form(form, include_credentials):
    errors = {}

    if include_credentials:
        login_errors = validate_login(form.get("login", "").strip())
        if login_errors:
            errors["login"] = login_errors

        password_errors = validate_password(form.get("password", ""))
        if password_errors:
            errors["password"] = password_errors

    last_name_errors = validate_required(form.get("last_name", ""))
    if last_name_errors:
        errors["last_name"] = last_name_errors

    first_name_errors = validate_required(form.get("first_name", ""))
    if first_name_errors:
        errors["first_name"] = first_name_errors

    return errors
