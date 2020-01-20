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
    'slide_path', type=click.Path(exists=True, dir_okay=False),
)
@click.option(
    '-t', '--slide-type', type=click.Choice(['remark']),
    default='remark',
)
@cli.common.metadata_options
@cli.common.config_options
@click.option(
    '--loglevel', default='info',
)
def render_slide_html(slide_path, slide_type,
                      year, section, period, code, name,
                      root_dir, config_path, loglevel):
    '''Render HTML version of slide Markdown

    SLIDE_PATH: Path to file with slide Markdown. Will search given directory
    recursively for course.yml file. If provided with a directory with
    multiple course.yml files, will error out.

    '''
    setup_logging(loglevel)
    render_func = {
        'remark': templates.slide.render_remark_slides,
    }.get(slide_type)

    config = cli.common.get_config_maybe_die(config_path)
    
    course = cli.common.find_course_maybe_die(
        canvas.api.get_api_from_config(config),
        year=year, section=section, period=period, code=code, name=name,
    )


@click.command()
@click.argument(
    'course-dir', type=click.Path(exists=True), required=True,
)
@click.option(
    '--loglevel', default='info',
)
def sync_slides(course_dir, loglevel):
    '''Sync course slides from directory containing slide markdown files

    COURSE-DIR: Path of section-specific course directory
    (e.g. "~/courses/cs101/section-01") . Will search given directory
    recursively for some number of course.yml files.

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
    slides_path = content_paths['slide']
    log.info(f'Found slides path: {slides_path}')
    slide_md_paths = _.pipe(
        slides_path.glob('slide-*.md'),
        sorted,
    )
    if not slide_md_paths:
        exit_with_msg(
            f'Could not find any slides in {slides_path}'
        )

    _.pipe(
        slide_md_paths,
        _.map(str),
        sorted,
        yaml.dump,
        lambda s: 'Slides found:\n' + s,
        log.info,
    )

    renderers = _.pipe(
        courses,
        _.map(lambda c: templates.slide.render_remark_slides(c, course_root)),
        tuple,
    )

    def render_path(course, md_path):
        for renderer in renderers:
            html_path = Path(md_path.parent, f'{md_path.stem}.html')
            html_content = renderer(md_path)
            log.info(
                f'Writing {len(html_content)} bytes to {html_path}'
            )
            html_path.write_text(html_content)
            log.info(
                f'Uploading {html_path} to course {course.data["name"]}:'
            )
            file_ep = canvas.file.upload_course_file(course, html_path)
            log.info(
                f'  ...done {html_path} -> {course.data["name"]}'
            )
            return (course, md_path, html_path, file_ep)

    all_content = _.pipe(
        itertools.product(courses, slide_md_paths),
        parallel.thread_map(lcommon.vcall(render_path), max_workers=10),
        tuple,
    )

    pages = _.pipe(
        courses,
        _.mapcat(canvas.page.pages),
    )

    for course, md_path, html_path, file_ep in all_content:
        page_content = templates.slide.slide_page(
            course, course_root, md_path, html_path, file_ep,
        )
        page_path = Path(
            content_paths['page'],
            f'page-{md_path.name}',
        )
        log.info(f'Writing page for {md_path}  -->  {page_path}')
        page_path.write_text(page_content)
    
