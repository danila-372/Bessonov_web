from app.models import Course

class CourseRepository:
    def __init__(self, db):
        self.db = db

    def _all_query(self, name, category_ids):
        query = self.db.select(Course)

        if name:
            query = query.filter(Course.name.ilike(f'%{name}%'))

        if category_ids:
            query = query.filter(Course.category_id.in_(category_ids))

        return query

    def get_pagination_info(self, name=None, category_ids=None):
        query = self._all_query(name, category_ids)
        return self.db.paginate(query)

    def get_all_courses(self, name=None, category_ids=None, pagination=None):
        if pagination is not None:
            return pagination.items 
        
        return self.db.session.execute(self._all_query(name, category_ids)).scalars()

    def get_course_by_id(self, course_id):
        return self.db.session.get(Course, course_id)
    
    def new_course(self):
        return Course()

    def add_course(self, author_id, name, category_id, short_desc, full_desc, background_image_id):
        course = Course(
            author_id=author_id,
            name=name,
            category_id=category_id,
            short_desc=short_desc,
            full_desc=full_desc,
            background_image_id=background_image_id
        )
        try:
            self.db.session.add(course)
            self.db.session.commit()
        except Exception as e:
            self.db.session.rollback()
            raise e  # Пробрасываем любое другое исключение
        
        return course
