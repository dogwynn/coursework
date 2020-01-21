import pprint
import logging

from toolz.curried import pipe, map, merge
from larc.rest import (
    Api, IdResourceEndpoint, get_id_resources, ResourceEndpoint,
)

from .course import course_resource_docstring

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

students = get_id_resources(
    'users', form_key='user',
    data={'enrollment_type[]': 'student'},
    help=course_resource_docstring('students'),
    memo=True,
)

users = get_id_resources(
    'users', form_key='user',
    # data={'enrollment_type[]': 'student'},
    help=course_resource_docstring('users'),
    memo=True,
)

teachers = get_id_resources(
    'users', form_key='user',
    data={'enrollment_type[]': 'teacher'},
    help=course_resource_docstring('teachers'),
    memo=True,
)

def get_self(api: Api):
    ep = api('users', 'self')
    return ResourceEndpoint(ep, ep.get().json(), 'user')

def get_data(api: Api, key: str, *, default=None,
             ns='com.lowlandresearch.coursework'):
    self = get_self(api)

    resp = self('custom_data', key).get(json={'ns': ns})
    if resp.status_code in range(200, 300):
        return resp.json()['data']
    else:
        return default

def set_data(api: Api, key, data: dict, *,
             ns='com.lowlandresearch.coursework'):
    self = get_self(api)

    resp = self('custom_data', key).put(
        json={'ns': ns, 'data': data},
    )
    if resp.status_code in range(200, 300):
        return resp.json()['data']
    else:
        log.error(f'Could not set key {key} to value:'
                  f' {pprint.pformat(data)[:1000]}')

_STUDENT_DB_KEY = 'student-db'
def _get_student_db(api: Api):
    student_db = get_data(api, _STUDENT_DB_KEY)
    if student_db is None:
        student_db = {}
        _set_student_db(api, student_db)
    return student_db

def _set_student_db(api: Api, student_db: dict):
    set_data(api, _STUDENT_DB_KEY, student_db)

def course_student_db(course: IdResourceEndpoint):
    all_db = _get_student_db(course.api)

    return pipe(
        students(course),
        map(lambda s: all_db.get(str(s.data['id']), {'id': s.data['id']})),
        tuple,
    )

def sync_students(api: Api, students: tuple):
    all_db = _get_student_db(api)
    return _set_student_db(
        api,
        merge(
            all_db,
            {s['id']: s for s in students},
        )
    )
