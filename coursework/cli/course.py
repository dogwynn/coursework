import re
from pathlib import Path
import textwrap
import logging

import click
from toolz.curried import (
    map, pipe, filter, merge,
)

from larc.common import (
    help_text
)
from larc import yaml
from larc.logging import setup_logging

from ..canvas.api import get_api
from ..canvas import course
from .. import config
# from ..config import (
#     init_config, validate_config_path, get_base_url, get_token,
#     get_root_dir,
# )
# from ..common import (
#     parse_course_metadata,
# )
from . import common

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

exit_with_msg = common.exit_with_msg(log)

@click.command()
@common.metadata_options
@common.config_options
@click.option(
    '--loglevel', default='info',
)
def init_course(year, section, period, code, name, root_dir, config_path,
                loglevel):
    '''Initialize Canvas course on the file system. Will save course
    metadata in course.yml file to be used by other tools.

    '''
    setup_logging(loglevel)

    conf = config.get_config(config_path)
    
    root_dir = root_dir or config.get_root_dir(config_path)
    if not root_dir:
        return

    root_dir = Path(root_dir).expanduser().resolve()

    api = get_api(
        config.get_base_url(config_path), config.get_token(config_path)
    )

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

    courses = pipe(
        course.courses(api()),
        filter(valid_course),
        filter(filter_course),
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
        
    course_dirs = pipe(
        courses,
        map(course_dir),
        tuple,
    )

    for (c, d) in zip(courses, course_dirs):
        if not d.exists():
            log.info(f'Creating course directory {d}')
            d.mkdir(parents=True)
        yaml.write_yaml(Path(d, 'course.yml'), c.data)
