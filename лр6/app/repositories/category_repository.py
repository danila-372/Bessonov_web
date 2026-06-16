from app.models import Category

class CategoryRepository:
    def __init__(self, db):
        self.db = db

    def get_all_categories(self):
        return self.db.session.execute(self.db.select(Category)).scalars()