import pytest
from pathlib import Path

from coursework import canvas

HERE = Path(__file__).resolve().parent

@pytest.fixture
def api():
    return canvas.api.get_api_from_config()

@pytest.fixture
def courses(api, vts):
    return canvas.course.courses(api(), do_memo=False)

@pytest.yield_fixture(scope='session')
def course_root():
    return Path(HERE, 'course_root').resolve()

@pytest.fixture
def course(api, vts):
    #canvas.course.find_course(courses, year=2018, code='csc122')
    return canvas.course.course_by_id(api(), 15882)

@pytest.fixture
def pages(course, vts):
    return canvas.page.pages(course, do_memo=False)

@pytest.fixture
def page(course, vts):
    return canvas.page.find_page(course, "Page For Unit Testing")

@pytest.fixture
def quizzes(course, vts):
    return canvas.quiz.quizzes(course, do_memo=False)
