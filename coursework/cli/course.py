import re
from pathlib import Path
import logging

import click
import toolz.curried as _

import larc.common as __
from larc import yaml
from larc import rest
from larc.logging import setup_logging

from .. import common
from .. import canvas
from .. import config
# from ..config import (
#     init_config, validate_config_path, get_base_url, get_token,
#     get_root_dir,
# )
# from ..common import (
#     parse_course_metadata,
# )
from .. import cli

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

exit_with_msg = cli.common.exit_with_msg(log)

@click.command()
@cli.common.metadata_options
@cli.common.config_options
@click.option(
    '--loglevel', default='info',
)
def init_course(year, section, period, code, name, root_dir, config_path,
                loglevel):
    '''Initialize Canvas course on the file system. Will save course
    metadata in course.yml file to be used by other tools.

    '''
    setup_logging(loglevel)

    conf = cli.common.get_config_maybe_die(config_path)
    
    root_dir = root_dir or config.get_root_dir(config_path)
    if not root_dir:
        return

    root_dir = Path(root_dir).expanduser().resolve()

    # api = get_api(
    #     config.get_base_url(config_path), config.get_token(config_path)
    # )
    api = canvas.api.get_api_from_config()

    def meta(c, k):
        return c.data['metadata'].get(k)

    def valid_course(c):
        return all(
            meta(c, k) for k in ['code', 'year', 'period', 'section']
        )
    
    def filter_course(c):
        if year and not meta(c, 'year') == year:
            return False
        if section and not re.search(meta(c, 'section'), section, re.I):
            return False
        if period and not re.search(meta(c, 'period'), period, re.I):
            return False
        if code and not re.search(meta(c, 'code'), code, re.I):
            return False
        return True

    courses = _.pipe(
        canvas.course.courses(api()),
        _.filter(valid_course),
        _.filter(filter_course),
        tuple,
    )
    log.info(courses)

    def course_dir(c):
        code, year, period, section = (
            meta(c, 'code'), meta(c, 'year'),
            meta(c, 'period'), meta(c, 'section')
        )
        return Path(
            root_dir,
            code.replace('-', '').lower(),
            f'{year}-{period.lower()}',
            section.lower()
        )
        
    course_dirs = _.pipe(
        courses,
        _.map(course_dir),
        tuple,
    )

    for (c, d) in zip(courses, course_dirs):
        if not d.exists():
            log.info(f'Creating course directory {d}')
            d.mkdir(parents=True)
        yaml.write_yaml(Path(d, 'course.yml'), c.data)

@click.command()
@click.argument(
    'course_dir', type=click.Path(exists=True), required=True,
)
@click.option(
    '--loglevel', default='info',
)
def sync_syllabus(course_dir, loglevel):
    '''Sync course syllabus from COURSE_DIR/<sections>/syllabus.md

    COURSE_DIR: Path of course directory. Will search given directory
    recursively for course.yml file. If provided with a directory with
    multiple course.yml files, will sync syllabus across all courses
    corresponding to found course.yml files.

    '''
    setup_logging(loglevel)

    api = canvas.api.get_api_from_config()
    course_lut = _.pipe(
        canvas.course.find_course_paths(course_dir),
        canvas.course.courses_from_yaml_paths(api),
        dict
    )

    if not course_lut:
        exit_with_msg('Could not find course information.')

    log.info(f'{len(course_lut)} courses found.')
    _.pipe(
        course_lut.items(),
        __.vmap(lambda p, c: c.data['name']),
        sorted,
        yaml.dump,
        lambda s: '\n' + s,
        log.info
    )

    # course_root = common.find_course_root(course_dir)
    # if not course_root:
    #     exit_with_msg('Could not find course root given course'
    #                   f' dir: {course_dir}')
    
    for course_path, course in course_lut.items():
        syl_path = Path(course_path.parent, 'syllabus.md')
        if syl_path.exists():
            log.info(f'Found syllabus: {syl_path}')
            rest.update_endpoint(
                course, {
                    'syllabus_body': _.pipe(
                        syl_path.read_text(),
                        common.markdown,
                    ),
                },
            )
        

@click.command()
@click.argument(
    'course_dir', type=click.Path(exists=True), required=True,
)
@click.option(
    '--loglevel', default='info',
)
def print_students(course_dir, loglevel):
    '''Print students in course

    COURSE_DIR: Path of course directory. Will search given directory
    recursively for course.yml file. If provided with a directory with
    multiple course.yml files, will sync syllabus across all courses
    corresponding to found course.yml files.

    '''
    setup_logging(loglevel)

    api = canvas.api.get_api_from_config()
    course_lut = _.pipe(
        canvas.course.find_course_paths(course_dir),
        canvas.course.courses_from_yaml_paths(api),
        dict
    )

    if not course_lut:
        exit_with_msg('Could not find course information.')

    log.info(f'{len(course_lut)} courses found.')
    _.pipe(
        course_lut.items(),
        __.vmap(lambda p, c: c.data['name']),
        sorted,
        yaml.dump,
        lambda s: '\n' + s,
        log.info
    )

    # course_root = common.find_course_root(course_dir)
    # if not course_root:
    #     exit_with_msg('Could not find course root given course'
    #                   f' dir: {course_dir}')
    keys = ['sortable_name', 'short_name', 'email']
    students = _.pipe(
        course_lut.items(),
        __.vmapcat(lambda path, course: canvas.user.students(course)),
        _.map(lambda ep: _.pipe(keys, _.map(lambda k: ep.data[k]), tuple)),
        sorted,
        _.map(lambda t: '\t'.join(t)),
        '\n'.join,
        print
    )
    
    # for course_path, course in course_lut.items():
    #     students = canvas.user.students(course)
    #     syl_path = Path(course_path.parent, 'syllabus.md')
    #     if syl_path.exists():
    #         log.info(f'Found syllabus: {syl_path}')
    #         rest.update_endpoint(
    #             course, {
    #                 'syllabus_body': _.pipe(
    #                     syl_path.read_text(),
    #                     common.markdown,
    #                 ),
    #             },
    #         )
        
