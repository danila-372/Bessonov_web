from app.models import User

class UserRepository:
    def __init__(self, db):
        self.db = db

    def get_all_users(self):
        return self.db.session.execute(self.db.select(User)).scalars()
    
    def get_user_by_id(self, user_id):
        return self.db.session.execute(self.db.select(User).filter_by(id=user_id)).scalar()

    def get_user_by_login(self, login):
        return self.db.session.execute(self.db.select(User).filter_by(login=login)).scalar()