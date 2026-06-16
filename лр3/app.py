from datetime import timedelta
from urllib.parse import urljoin, urlsplit

from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)


USERS = {
    "user": {
        "password": "qwerty",
    }
}


class User(UserMixin):
    def __init__(self, user_id):
        self.id = user_id


login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = (
    "Для доступа к запрашиваемой странице необходимо пройти процедуру "
    "аутентификации."
)
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id):
    if user_id in USERS:
        return User(user_id)
    return None


def is_safe_next_url(target):
    if not target:
        return False

    host_url = urlsplit(request.host_url)
    redirect_url = urlsplit(urljoin(request.host_url, target))
    return (
        redirect_url.scheme in ("http", "https")
        and redirect_url.netloc == host_url.netloc
    )


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY="dev-secret-key",
        REMEMBER_COOKIE_DURATION=timedelta(days=7),
        REMEMBER_COOKIE_HTTPONLY=True,
    )

    if test_config:
        app.config.update(test_config)

    login_manager.init_app(app)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/visits")
    def visits():
        session["visits_count"] = session.get("visits_count", 0) + 1
        return render_template("visits.html", visits=session["visits_count"])

    @app.route("/login", methods=["GET", "POST"])
    def login():
        next_url = request.form.get("next") or request.args.get("next") or ""

        if current_user.is_authenticated:
            if is_safe_next_url(next_url):
                return redirect(next_url)
            return redirect(url_for("index"))

        username = ""
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            remember = request.form.get("remember") == "on"

            if username in USERS and USERS[username]["password"] == password:
                login_user(User(username), remember=remember)
                flash("Вы успешно вошли в систему.", "success")

                if is_safe_next_url(next_url):
                    return redirect(next_url)
                return redirect(url_for("index"))

            flash("Неверно введены логин или пароль.", "danger")

        return render_template("login.html", next_url=next_url, username=username)

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("Вы вышли из системы.", "info")
        return redirect(url_for("index"))

    @app.route("/secret")
    @login_required
    def secret():
        return render_template("secret.html")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
