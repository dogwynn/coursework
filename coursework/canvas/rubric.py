'''TODO

'''
import logging

from larc.rest import (
    IdResourceEndpoint, get_id_resources, new_id_resource,
)

from .course import (
    course_resource_docstring, create_course_resource_docstring,
)


log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

rubrics = get_id_resources(
    'rubrics', form_key='rubric', memo=True,
    help=course_resource_docstring('rubrics'),
)

new_rubric = new_id_resource(
    'rubrics', form_key='rubric',
    post_unpack_f=lambda d: d['rubric'],
    help=create_course_resource_docstring(
        'rubric', {'name': 'Module Name', 'position': 1}
    ),
)
