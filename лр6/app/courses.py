from flask import Blueprint, render_template, request, flash, redirect, url_for, abort
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.models import db
from app.repositories import CourseRepository, UserRepository, CategoryRepository, ImageRepository, ReviewRepository

user_repository = UserRepository(db)
course_repository = CourseRepository(db)
category_repository = CategoryRepository(db)
image_repository = ImageRepository(db)
review_repository = ReviewRepository(db)

bp = Blueprint('courses', __name__, url_prefix='/courses')

COURSE_PARAMS = [
    'author_id', 'name', 'category_id', 'short_desc', 'full_desc'
]

REVIEW_SORTS = {
    'new': 'По новизне',
    'positive': 'Сначала положительные',
    'negative': 'Сначала отрицательные',
}

def params():
    return { p: request.form.get(p) or None for p in COURSE_PARAMS }

def search_params():
    return {
        'name': request.args.get('name'),
        'category_ids': [x for x in request.args.getlist('category_ids') if x],
    }

def review_params():
    return {
        'rating': request.form.get('rating') or 5,
        'text': request.form.get('text') or '',
    }

def safe_next_url(default_url):
    next_url = request.form.get('next')
    if next_url and next_url.startswith('/') and not next_url.startswith('//'):
        return next_url
    return default_url

@bp.route('/')
def index():
    pagination = course_repository.get_pagination_info(**search_params())
    courses = course_repository.get_all_courses(pagination=pagination)
    categories = category_repository.get_all_categories()
    return render_template('courses/index.html',
                           courses=courses,
                           categories=categories,
                           pagination=pagination,
                           search_params=search_params())

@bp.route('/new')
@login_required
def new():
    course = course_repository.new_course()
    categories = category_repository.get_all_categories()
    users = user_repository.get_all_users()
    return render_template('courses/new.html',
                           categories=categories,
                           users=users,
                           course=course)

@bp.route('/create', methods=['POST'])
@login_required
def create():
    f = request.files.get('background_img')
    img = None
    course = None 

    try:
        if f and f.filename:
            img = image_repository.add_image(f)

        image_id = img.id if img else None
        course = course_repository.add_course(**params(), background_image_id=image_id)
    except IntegrityError as err:
        flash(f'Возникла ошибка при записи данных в БД. Проверьте корректность введённых данных. ({err})', 'danger')
        categories = category_repository.get_all_categories()
        users = user_repository.get_all_users()
        return render_template('courses/new.html',
                            categories=categories,
                            users=users,
                            course=course)

    flash(f'Курс {course.name} был успешно добавлен!', 'success')

    return redirect(url_for('courses.index'))

@bp.route('/<int:course_id>')
def show(course_id):
    course = course_repository.get_course_by_id(course_id)
    if course is None:
        abort(404)
    current_user_review = None
    if current_user.is_authenticated:
        current_user_review = review_repository.get_user_review(course.id, current_user.id)
    recent_reviews = review_repository.get_recent_reviews(course.id)
    return render_template('courses/show.html',
                           course=course,
                           recent_reviews=recent_reviews,
                           current_user_review=current_user_review,
                           review_sorts=REVIEW_SORTS)

@bp.route('/<int:course_id>/reviews')
def reviews(course_id):
    course = course_repository.get_course_by_id(course_id)
    if course is None:
        abort(404)
    sort = request.args.get('sort', 'new')
    if sort not in REVIEW_SORTS:
        sort = 'new'
    pagination = review_repository.get_pagination_info(course.id, sort=sort)
    current_user_review = None
    if current_user.is_authenticated:
        current_user_review = review_repository.get_user_review(course.id, current_user.id)
    return render_template('courses/reviews.html',
                           course=course,
                           reviews=review_repository.get_all_reviews(pagination=pagination),
                           pagination=pagination,
                           sort=sort,
                           review_sorts=REVIEW_SORTS,
                           current_user_review=current_user_review)

@bp.route('/<int:course_id>/reviews', methods=['POST'])
@login_required
def create_review(course_id):
    course = course_repository.get_course_by_id(course_id)
    if course is None:
        abort(404)
    try:
        review_repository.add_review(course=course, user_id=current_user.id, **review_params())
        flash('Отзыв успешно добавлен.', 'success')
    except ValueError:
        flash('Не удалось сохранить отзыв. Проверьте оценку и текст отзыва.', 'danger')
    except IntegrityError as err:
        db.session.rollback()
        flash(f'Возникла ошибка при записи данных в БД. ({err})', 'danger')

    return redirect(safe_next_url(url_for('courses.show', course_id=course.id)))
