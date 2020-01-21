'''TODO

'''
import re
import pprint
import logging
from pathlib import Path
from typing import Tuple, Iterable

import toolz.curried as _
from larc import common as lcommon
from larc import yaml
from larc import rest

from .. import config

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

Course = rest.IdResourceEndpoint

@_.curry
def parse_course_metadata(regexes: list, course_dict: dict):
    r'''
    Examples:
    
    >>> regexes = [
    ...    {'key': 'name',
    ...    'regex: r'^(?P<code>\S+) (?P<name>.*?) (?P<section>\S+)$'},
    ...    {'key': 'course_code',
    ...     'regex': r'^(?P<code>\S+) (?P<name>.*?) (?P<section>\S+)$'}
    ... ]
    >>> course_dict = {
    ...   'name': 'CS102 CompSci II S01',
    ... }
    >>> parse_course_metadata(regexes, course_dict) == {
    ...   'code': 'CS102', 'name': 'CompSci II', 'section': 'S01',
    ... }
    True
    '''
    def get_course_value(regex_dict):
        if 'key' in regex_dict:
            if regex_dict['key'] in course_dict:
                return course_dict[regex_dict['key']]
        elif 'keys' in regex_dict:
            return _.get_in(regex_dict['keys'], course_dict)

    def transform_year(d):
        if 'year' in d:
            return _.assoc(d, 'year', int(d['year']))
        return d
            
    return _.pipe(
        regexes,
        _.map(lambda d: (get_course_value(d), re.compile(d['regex']))),
        _.filter(_.first),
        lcommon.vmap(lambda value, regex: regex.search(value)),
        _.filter(None),
        _.map(lambda m: m.groupdict()),
        _.map(transform_year),
        tuple,
        reversed,
        tuple,
        lambda dicts: _.merge(*(dicts or [{}])),
    )

default_course_meta_f = parse_course_metadata(
    config.get_config_bang()['regexes']
)

course_by_id = rest.get_id_resource(
    'courses',
    form_key='course',
    data={'include[]': [
        'term', 'total_students',
        'syllabus_body',
    ]},
    meta_f=default_course_meta_f,
)

courses = rest.get_id_resources(
    'courses', form_key='course', memo=True,
    data={'include[]': [
        'term', 'total_students',
        'syllabus_body',
        # 'needs_grading_count', 'public_description',
        # 'total_scores', 'current_grading_period_scores',
        # 'course_progress', 'sections', 'storage_quota_used_mb',
        # 'passback_status', 'favorites', 'teachers', 'observed_users',
    ]},
    meta_f=default_course_meta_f,
)
get_courses = courses

def course_metadata(course: Course):
    return course.data['metadata']

def course_id_tuple(course: Course):
    id_keys = ['year', 'period', 'name', 'code', 'section']
    return _.pipe(
        id_keys,
        _.map(course_metadata(course).get),
        _.filter(None),
        tuple,
    )

publish = rest.update_endpoint(
    update={'event': 'offer'},
    get_kw={'data': {'include[]': [
        'term', 'total_students',
    ]}},
)

def settings(course: Course):
    return course('settings').get().json()

def update_settings(course: Course, update: dict):
    course('settings').put(data=update)
    return settings(course)

def course_resource_docstring(name: str):
    return f'''For a given course endpoint, return a tuple of all its {name}
    endpoints

    Args:

      course (Endpoint): course endpoint from which to retrieve {name}

    Example:

    >>> api = coursework.canvas.api.get_api_from_config()
    >>> c, *_ = coursework.canvas.course.courses(api())
    >>> {name} = coursework.canvas.course.{name}(c)
    '''
    
def create_course_resource_docstring(name: str, example: dict):
    return f'''Create new {name} object for a given course endpoint

    Args:

      course (Endpoint): course endpoint
    
      data (dict): requisite data for creating the {name}

    Example:

    >>> api = coursework.canvas.api.get_api_from_config()
    >>> course, *_ = coursework.canvas.course.courses(api())
    >>> new_{name} = coursework.canvas.{name}.new_{name}(
    ...   course, {example}
    ... )
    >>>

    Returns:
      New {name} Endpoint or None if error
    '''

# ----------------------------------------------------------------------
# Course search functionality
# ----------------------------------------------------------------------

def has_metadata(course: Course, **search_kw):
    meta = course_metadata(course)

    def has(k, v):
        if k not in meta and k not in course.data:
            log.error(
                f'Searching for key ({k}) in metadata '
                f'with keys: {", ".join(meta.keys())} and key is also not'
                ' in Canvas data'
            )
        if callable(v):
            return v(meta.get(k)) or v(course.data.get(k))
        if lcommon.is_str(v):
            return re.search(
                v, meta.get(k, '') or course.data.get(k, ''), re.I
            )
        return meta.get(k) == v or course.data.get(k) == v

    return all(has(k, v) for k, v in search_kw.items())

@_.curry
def filter_courses(course_iter: Iterable[Course],
                   **search_kw) -> Tuple[Course]:
    return _.pipe(
        course_iter,
        _.filter(lambda c: has_metadata(c, **search_kw)),
        tuple,
    )

@_.curry
def filter_for_course(course_iter: Iterable[Course],
                      **search_kw) -> Course:
    '''Search an iterable of Course endpoints for particular metadata
    attributes

    Metadata attributes (given as keyword arguments):

      year (int): Year of course
      period (str): Seasonal period of course (e.g. "Fall", "Spring")
      name (str): Name of course
      code (str): Course code (e.g. 'csc111' or 'bus222')
      section (str): Course section (e.g. '01TU1')

    You can also search via other Canvas-Endpoint-specific attributes

    '''
    return _.pipe(
        course_iter,
        filter_courses(**search_kw),
        lcommon.maybe_first
    )

@_.curry
def filter_courses_via_api(api: rest.Api, **search_kw):
    return _.pipe(
        get_courses(api()),
        filter_for_course(**search_kw),
    )

find_course_paths = _.compose(
    tuple, _.filter(lambda p: p.name == 'course.yml'), lcommon.walk,
)

def courses_from_path(api: rest.Api,
                      path: (str, Path)) -> Tuple[rest.Endpoint]:
    # courses = get_courses(api())
    return _.pipe(
        find_course_paths(path),
        _.map(yaml.maybe_read_yaml),
        _.map(lambda d: d.get('id')),
        _.filter(None),
        set,
        _.map(course_by_id(api())),
        tuple,
    )

def find_one_course_path(path) -> Path:
    '''Walk the path to find one course.yml file

    If none are found, log error. If more than one is found, log
    error. Otherwise, return path.

    '''
    paths = find_course_paths(path)
    if not paths:
        log.error(
            f'Could not find any course.yml file in the given path: {path}'
        )
        return None
    if len(paths) > 1:
        paths_str = _.pipe(paths, _.map(lambda p: f'- {p}'), '\n'.join)
        log.error(
            f'Multiple course.yml paths found at path: {path}\n'
            f'{paths_str}'
        )
        return None
    return paths[0]

@_.curry
def course_from_path(api: rest.Api, path: (str, Path)) -> rest.Endpoint:
    '''Given a path, recursively search for a course.yml file, get the
    Canvas ID from it and find the course endpoint with that ID

    If more than either more than one or no course.yml files are
    found, will log error and return None.

    '''
    course_path = find_one_course_path(path)
    if course_path:
        course_data = yaml.read_yaml(course_path)
        if 'id' not in course_data:
            log.error(
                'Could not find course ID in course.yml file'
            )
            return None

        course_ep = _.pipe(
            get_courses(api()),
            _.filter(lambda c: c.data['id'] == course_data['id']),
            lcommon.maybe_first,
        )

        if not course_ep:
            log.error(
                'Could not find course in Canvas for course data:\n'
                f'{pprint.pformat(_.dissoc(course_data, "students"))}'
            )
            return None

        return course_ep

