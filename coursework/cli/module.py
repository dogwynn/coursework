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
    'course_dir', type=click.Path(exists=True), required=True,
)
@click.option(
    '--dry-run', is_flag=True, help=lcommon.help_text('''

    Don't modify content on Canvas
    
    ''')
)
@click.option(
    '--loglevel', default='info',
)
def sync_modules(course_dir, dry_run, loglevel):
    '''Sync course modules from a modules.yml file.

    COURSE_DIR: Path of course directory. Will search given directory
    recursively for course.yml file. If provided with a directory with
    multiple course.yml files, will sync modules across all courses
    corresponding to found course.yml files.

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

    modules_path = content_paths['module']
    log.info(f'Found modules path: {modules_path}')

    _.pipe(
        itertools.product(courses, [modules_path]),
        parallel.thread_map(lcommon.vcall(
            lambda course, modules_path: (
                canvas.module.sync_modules_from_yaml_path(
                    course, modules_path
                )
            )
        ), max_workers=10),
        tuple,
    )

    # page_md_paths = _.pipe(
    #     pages_path.glob('page-*.md'),
    #     sorted,
    # )
    # if not page_md_paths:
    #     exit_with_msg(
    #         f'Could not find any pages in {pages_path}'
    #     )

    # _.pipe(
    #     itertools.product(courses, [course_root], page_md_paths),
    #     parallel.thread_map(lcommon.vcall(
    #         lambda course, root, page_path: (
    #             canvas.page.sync_page_from_path(course, root, page_path)
    #         )
    #     ), max_workers=10),
    #     tuple,
    # )

    # setup_logging(loglevel)

    # api = get_api_from_config()
    # course = find_course(api, course_dir)

    # if not course:
    #     exit_with_msg('Could not find course information. Aborting...')

    # modules_path = modules_path or course_dir

    # test_path = Path(modules_path)
    # if test_path.is_dir():
    #     # Search for "modules.yml" file
    #     paths = pipe(
    #         walk(test_path),
    #         filter(lambda p: p.name == 'modules.yml'),
    #         tuple,
    #     )

    #     # If none here, abort
    #     if not paths:
    #         exit_with_msg(
    #             f'Could not find modules.yml file in root directory'
    #             f' {test_path}. Aborting...'
    #         )

    #     # If too many, abort
    #     if len(paths) > 1:
    #         exit_with_msg(
    #             f'Multiple ({len(paths)}) modules.yml files in root'
    #             f' directory: {test_path}. Aborting...'
    #         )

    #     modules_path = paths[0]
            
    # elif test_path.is_file():
    #     # Load directly from this file
    #     if test_path.suffix not in {'.yml', '.yaml'}:
    #         # Sanity check for yaml
    #         log.warning(
    #             f"Modules file '{test_path}' does not have a YAML "
    #             "extension (i.e. '.yml' or '.yaml')."
    #         )
    #     modules_path = test_path

    # if not modules_path:
    #     exit_with_msg(
    #         f'No modules.yml file found in root dir:'
    #         f' {test_path}. Aborting...'
    #     )

    # log.info(f'modules.yml found: {modules_path}')
    # sync_modules_from_yaml_path(course, modules_path, dry_run=dry_run)
