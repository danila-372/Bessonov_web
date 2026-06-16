from app.models import Review


class ReviewRepository:
    SORTS = {'new', 'positive', 'negative'}

    def __init__(self, db):
        self.db = db

    def _course_reviews_query(self, course_id, sort='new'):
        query = self.db.select(Review).filter(Review.course_id == course_id)

        if sort == 'positive':
            return query.order_by(Review.rating.desc(), Review.created_at.desc(), Review.id.desc())

        if sort == 'negative':
            return query.order_by(Review.rating.asc(), Review.created_at.desc(), Review.id.desc())

        return query.order_by(Review.created_at.desc(), Review.id.desc())

    def get_recent_reviews(self, course_id, limit=5):
        query = self._course_reviews_query(course_id).limit(limit)
        return self.db.session.execute(query).scalars().all()

    def get_pagination_info(self, course_id, sort='new'):
        query = self._course_reviews_query(course_id, sort)
        return self.db.paginate(query)

    def get_all_reviews(self, pagination=None, course_id=None, sort='new'):
        if pagination is not None:
            return pagination.items

        query = self._course_reviews_query(course_id, sort)
        return self.db.session.execute(query).scalars().all()

    def get_user_review(self, course_id, user_id):
        return self.db.session.execute(
            self.db.select(Review).filter(
                Review.course_id == course_id,
                Review.user_id == user_id,
            )
        ).scalar()

    def add_review(self, course, user_id, rating, text):
        rating = int(rating)
        text = text.strip()

        if rating < 0 or rating > 5:
            raise ValueError('rating must be from 0 to 5')

        if not text:
            raise ValueError('review text must not be empty')

        if self.get_user_review(course.id, user_id) is not None:
            raise ValueError('user already reviewed this course')

        review = Review(
            course_id=course.id,
            user_id=user_id,
            rating=rating,
            text=text,
        )
        course.rating_sum = (course.rating_sum or 0) + rating
        course.rating_num = (course.rating_num or 0) + 1

        try:
            self.db.session.add(review)
            self.db.session.commit()
        except Exception as e:
            self.db.session.rollback()
            raise e

        return review
