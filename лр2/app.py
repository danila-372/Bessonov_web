import re

from flask import Flask, make_response, render_template, request


app = Flask(__name__)

COOKIE_NAME = "lab2_cookie"
COOKIE_VALUE = "flask-lab-2"
ALLOWED_PHONE_RE = re.compile(r"^[\d\s().+\-]*$")

ERROR_WRONG_DIGITS = "Недопустимый ввод. Неверное количество цифр."
ERROR_INVALID_CHARS = (
    "Недопустимый ввод. В номере телефона встречаются недопустимые символы."
)


def validate_phone_number(phone: str) -> tuple[bool, str | None]:
    """Validate phone input according to the lab rules."""
    if not ALLOWED_PHONE_RE.fullmatch(phone):
        return False, ERROR_INVALID_CHARS

    stripped_phone = phone.strip()
    digits = re.sub(r"\D", "", phone)
    expected_digits = (
        11 if stripped_phone.startswith("+7") or stripped_phone.startswith("8") else 10
    )

    if len(digits) != expected_digits:
        return False, ERROR_WRONG_DIGITS

    return True, None


def format_phone_number(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    local_digits = digits[1:] if len(digits) == 11 else digits

    return (
        f"8-{local_digits[0:3]}-{local_digits[3:6]}-"
        f"{local_digits[6:8]}-{local_digits[8:10]}"
    )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/url-params")
def url_params():
    return render_template(
        "url_params.html",
        params=list(request.args.items(multi=True)),
    )


@app.route("/headers")
def headers():
    return render_template("headers.html", headers=list(request.headers.items()))


@app.route("/cookies")
def cookies():
    cookie_value = request.cookies.get(COOKIE_NAME)

    if cookie_value is None:
        response = make_response(
            render_template(
                "cookies.html",
                action="set",
                cookie_name=COOKIE_NAME,
                cookie_value=COOKIE_VALUE,
            )
        )
        response.set_cookie(COOKIE_NAME, COOKIE_VALUE)
        return response

    response = make_response(
        render_template(
            "cookies.html",
            action="delete",
            cookie_name=COOKIE_NAME,
            cookie_value=cookie_value,
        )
    )
    response.delete_cookie(COOKIE_NAME)
    return response


@app.route("/form-params", methods=["GET", "POST"])
def form_params():
    form_values = list(request.form.items(multi=True)) if request.method == "POST" else []
    return render_template("form_params.html", form_values=form_values)


@app.route("/phone", methods=["GET", "POST"])
def phone():
    phone_value = ""
    error = None
    formatted_phone = None

    if request.method == "POST":
        phone_value = request.form.get("phone", "")
        is_valid, error = validate_phone_number(phone_value)

        if is_valid:
            formatted_phone = format_phone_number(phone_value)

    return render_template(
        "phone.html",
        phone_value=phone_value,
        error=error,
        formatted_phone=formatted_phone,
    )


if __name__ == "__main__":
    app.run(debug=True)
