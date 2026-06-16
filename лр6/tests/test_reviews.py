from datetime import datetime, timedelta

import sqlalchemy as sa

from app.models import Course, Review, db
from conftest import create_user, login


def add_review(course_id, login_name, rating, text, created_at):
    user = create_user(login_name, first_name=login_name, last_name='Reviewer')
    review = Review(
        course_id=course_id,
        user_id=user.id,
        rating=rating,
        text=text,
        created_at=created_at,
    )
    db.session.add(review)
    db.session.flush()
    return review


def test_authenticated_user_can_create_review_and_course_rating_is_recalculated(app, client, sample_course, student):
    login(client)

    response = client.post(
        f'/courses/{sample_course}/reviews',
        data={
            'rating': '4',
            'text': 'Solid course with useful practice.',
            'next': f'/courses/{sample_course}',
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert 'Solid course with useful practice.' in response.get_data(as_text=True)

    with app.app_context():
        course = db.session.get(Course, sample_course)
        review = db.session.execute(
            db.select(Review).filter_by(course_id=sample_course, user_id=student)
        ).scalar_one()

        assert review.rating == 4
        assert course.rating_sum == 4
        assert course.rating_num == 1
        assert course.rating == 4


def test_course_page_shows_five_latest_reviews(app, client, sample_course):
    base_time = datetime(2026, 1, 1, 12, 0, 0)
    with app.app_context():
        for index in range(6):
            add_review(
                sample_course,
                f'reviewer-{index}',
                5,
                f'review-text-{index}',
                base_time + timedelta(minutes=index),
            )
        db.session.commit()

    response = client.get(f'/courses/{sample_course}')
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'review-text-5' in body
    assert 'review-text-1' in body
    assert 'review-text-0' not in body


def test_reviews_page_sorts_by_positive_rating_and_preserves_sort_in_pagination(app, client, sample_course):
    base_time = datetime(2026, 1, 1, 12, 0, 0)
    with app.app_context():
        for rating in [1, 5, 2, 4, 0, 3]:
            add_review(
                sample_course,
                f'user-rating-{rating}',
                rating,
                f'rating-text-{rating}',
                base_time + timedelta(minutes=rating),
            )
        db.session.commit()

    response = client.get(f'/courses/{sample_course}/reviews?sort=positive&per_page=2')
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert body.index('rating-text-5') < body.index('rating-text-4')
    assert 'rating-text-3' not in body
    assert 'sort=positive' in body


def test_reviews_page_shows_existing_user_review_instead_of_form(app, client, sample_course, student):
    with app.app_context():
        db.session.add(Review(
            course_id=sample_course,
            user_id=student,
            rating=5,
            text='My existing review.',
            created_at=datetime(2026, 1, 1, 12, 0, 0),
        ))
        db.session.commit()

    login(client)
    response = client.get(f'/courses/{sample_course}/reviews')
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'My existing review.' in body
    assert '<textarea' not in body


def test_duplicate_review_is_rejected_without_changing_course_rating(app, client, sample_course, student):
    with app.app_context():
        db.session.add(Review(
            course_id=sample_course,
            user_id=student,
            rating=5,
            text='First review.',
            created_at=datetime(2026, 1, 1, 12, 0, 0),
        ))
        course = db.session.get(Course, sample_course)
        course.rating_sum = 5
        course.rating_num = 1
        db.session.commit()

    login(client)
    response = client.post(
        f'/courses/{sample_course}/reviews',
        data={'rating': '1', 'text': 'Second review.', 'next': f'/courses/{sample_course}'},
        follow_redirects=True,
    )

    assert response.status_code == 200
    with app.app_context():
        course = db.session.get(Course, sample_course)
        reviews_count = db.session.execute(
            db.select(sa.func.count(Review.id)).where(
                Review.course_id == sample_course,
                Review.user_id == student,
            )
        ).scalar_one()

        assert reviews_count == 1
        assert course.rating_sum == 5
        assert course.rating_num == 1
