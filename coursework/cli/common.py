import logging

import click

from toolz.curried import (
    pipe, curry, compose, valfilter,
)
from larc import yaml
from larc.common import (
    help_text, not_null, vmap, maybe_first,
)

from .. import config
from .. import canvas

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

@curry
def exit_with_msg(logger, msg):
    ctx = click.get_current_context()
    click.echo(ctx.get_help())
    logger.error(msg)
    raise click.Abort()

_exit_with_msg = exit_with_msg(log)

metadata_options = compose(
    click.option(
        '-y', '--year', type=int,
        help=help_text('''

        Year of course (e.g. 2019)

        ''')
    ),
    click.option(
        '-s', '--section',
        help=help_text('''

        Section of course (e.g. 01TU1 or 01)

        ''')
    ),
    click.option(
        '-p', '--period',
        # type=click.Choice(
        #     ['fall', 'winter', 'spring', 'may', 'summer', 'online']
        # ),
        help=help_text('''

        Seasonal period of course (e.g. fall, spring, etc.)

        ''')
    ),
    click.option(
        '-c', '--code',
        help=help_text('''

        Catalog code of course (e.g. csc111 or CS101)

        ''')
    ),
    click.option(
        '-n', '--name',
        help=help_text('''

        Name of course (e.g. "Programming Fundamentals")
        
        ''')
    )
)

config_options = compose(
    click.option(
        '-r', '--root-dir',
        type=click.Path(),
        help=help_text('''

        Root path for all courses in which to place this particular course
        directory. If not provided, will pull from OS environment variable
        first (COURSEWORK_ROOT_DIR), then it will try to pull it from the
        YAML config (~/.config/coursework/config.yml). Otherwise, will
        error out.

        '''),
    ),
    click.option(
        '--config-path', type=click.Path(exists=True, dir_okay=False),
        help=help_text('''

        Path to a YAML-encoded configuration file. If not given, then will
        load configuration from the default location
        (~/.config/coursework/config.yml)

        ''')
    )
)

def get_config_maybe_die(config_path):
    if config_path is not None:
        valid, reasons = config.validate_config_path(config_path)
        if not valid:
            _exit_with_msg(reasons)
        return yaml.read_yaml(config_path)
    return config.init_config()

def nonempty_search_kw(search_kw):
    return pipe(
        search_kw.items(),
        valfilter(not_null),
    )

def nonempty_search_kw_maybe_die(search_kw):
    search_kw = nonempty_search_kw(search_kw)
    if not search_kw:
        _exit_with_msg(
            'No metadata search conditions given (e.g. year,'
            ' period, code, etc.)'
        )
    
def kw_str(search_kw):
    return pipe(
        search_kw.items(),
        sorted,
        vmap(lambda k, v: '{k}={v}'),
        ', '.join,
    )
    
def find_courses(api, **search_kw):
    return canvas.course.filter_courses_via_api(
        api, **nonempty_search_kw(search_kw)
    )

def find_course(api, **search_kw):
    return pipe(
        find_courses(api, **search_kw),
        maybe_first,
    )

def find_courses_maybe_die(api, **search_kw):
    courses = find_courses(api, **search_kw)
    if not courses:
        _exit_with_msg(
            f'No courses found with search criteria: {kw_str(search_kw)}'
        )
    return courses

def find_course_maybe_die(api, **search_kw):
    search_kw = nonempty_search_kw_maybe_die(search_kw)
    courses = canvas.course.find_courses_via_api(
        api, **search_kw
    )
    if not courses:
        _exit_with_msg(
            f'No courses found with search criteria: {kw_str(search_kw)}'
        )
    if len(courses) > 1:
        courses_str = pipe(
            courses,
            map(lambda c: f"- {c.data['name']}"),
            '\n'.join
        )
        _exit_with_msg(
            f'Search criteria returned more than one Course:'
            f' {kw_str(search_kw)}\n'
            f'{courses_str}'
        )
    return courses[0]

