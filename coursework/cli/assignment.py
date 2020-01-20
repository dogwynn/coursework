from pathlib import Path
import logging
import itertools

import click
import toolz.curried as _

from larc import yaml
from larc import common as lcommon
from larc.logging import setup_logging
from larc import parallel

from .. import common
from .. import canvas
from .. import templates
from .. import cli

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

exit_with_msg = cli.common.exit_with_msg(log)

@click.command()
@click.argument(
    'course-dir', type=click.Path(exists=True), required=True,
)
@click.option(
    '--loglevel', default='info',
)
def sync_assignments(course_dir, loglevel):
    '''
    '''
    setup_logging(loglevel)

    api = canvas.api.get_api_from_config()
    courses = canvas.course.courses_from_path(api, course_dir)

    if not courses:
        exit_with_msg('Could not find course information.')

    log.info(f'{len(courses)} courses found.')
    _.pipe(
        courses,
        _.map(lambda c: c.data['name']),
        tuple,
        yaml.dump,
        lambda s: '\n' + s,
        log.info
    )

    course_root = common.find_course_root(course_dir)
    if not course_root:
        exit_with_msg('Could not find course root given course'
                      f' dir: {course_dir}')

    log.info(f'Found course root: {course_root}')
    content_paths = common.find_content_paths(course_root)

    assignments_path = content_paths['assign']
    log.info(f'Found assignments path: {assignments_path}')

    assignment_md_paths = _.pipe(
        assignments_path.glob('assign-*.md'),
        sorted,
    )
    if not assignment_md_paths:
        exit_with_msg(
            f'Could not find any assignments in {assignments_path}'
        )

    _.pipe(
        itertools.product(courses, [course_root], assignment_md_paths),
        parallel.thread_map(lcommon.vcall(
            lambda course, root, assignment_path: (
                canvas.assignment.sync_assignment_from_path(
                    course, root, assignment_path
                )
            )
        ), max_workers=10),
        tuple,
    )
