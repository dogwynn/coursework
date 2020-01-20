'''TODO

'''
from pathlib import Path
from typing import Union
import logging

from toolz.curried import (
    curry, compose, pipe, map, do,
)

from larc.rest import (
    IdResourceEndpoint, get_id_resources, new_id_resource, update_endpoint,
)
from larc.parallel import thread_map as pmap

from .course import (
    course_resource_docstring, create_course_resource_docstring,
)
from .metadata import get_metadata, set_metadata
from ..common import (
    hash_from_content, resolve_path,
)
from .. import templates

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

pages = get_id_resources(
    'pages', form_key='wiki_page', id_key='url', memo=True,
    help=course_resource_docstring('pages'),
)

new_page = new_id_resource(
    'pages', form_key='wiki_page', id_key='url',
    help=create_course_resource_docstring(
        'page', {'title': 'A New Page', 'body': '<p>Some HTML content.</p>'}
    ),
)

@curry
def find_page(course: IdResourceEndpoint, title: str):
    for p in pages(course):
        if p.data['title'] == title:
            return p.refresh()

@curry
def sync_page_from_path(course: IdResourceEndpoint, course_root: str,
                        path: Union[str, Path]):
    html = templates.common.render_markdown_path(course, course_root, path)
    title = html.meta.get('title')

    if not title:
        log.error(
            f'The Canvas page ({path}) does not have a title specified.'
        )
        return False

    page = find_page(course, title)
    if not page:
        # Need to create new
        log.info(
            f'[sync_page_from_path] Creating new page:\n'
            f'-  title: "{title}"\n'
            f'-   path: {path}\n'
            f'- course: {course.data["name"]}'
        )
        page = new_page(course, {'title': title, 'body': html})

    meta = get_metadata(page)

    path = resolve_path(course_root, path)
    content_hash = hash_from_content(path.read_text())
    extant_hash = meta.get('hash')

    if not content_hash == extant_hash:
        log.info(
            f'[sync_page_from_path] Updating page:\n'
            f'-  title: "{title}"\n'
            f'-   path: {path}\n'
            f'- course: {course.data["name"]}'
        )
        meta['hash'] = content_hash
        set_metadata(page, meta)
        return update_endpoint(page, {'body': html})
    return page

@curry
def sync_pages_from_path(course: IdResourceEndpoint, course_root: str,
                         pages_root: str):
    return pipe(
        Path(pages_root).expanduser().glob('page-*.md'),
        pmap(sync_page_from_path(course, course_root), max_workers=5),
        tuple,
    )
