from app import create_app, initialize_database


app = create_app()

with app.app_context():
    initialize_database()
    print("База данных инициализирована.")
