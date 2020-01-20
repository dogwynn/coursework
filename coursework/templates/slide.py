'''TODO

'''
import re
from pathlib import Path

import toolz.curried as _
from toolz.curried import (
    curry, pipe, map, concatv, mapcat,
)

from larc import common as lcommon
from larc.common import (
    call,
)
from larc.rest import (
    Endpoint,
)

from ..config import (
    get_config,
)
from .common import (
    resolve_path, template_environment, css_path, js_path, j2_path,
)

# ----------------------------------------------------------------------
#
# remark.js
#
# ----------------------------------------------------------------------

@curry
def glob_sources(path_f, globs):
    def resolver(path='.'):
        return pipe(
            globs,
            mapcat(lambda n: path_f(path).glob(n)),
            map(lambda p: p.read_text()),
            tuple,
        )
    return resolver


remark_css_sources = glob_sources(
    css_path, [
        'remark/*.css',
    ]
)

remark_js_sources = glob_sources(
    js_path, [
        'remark/*.js',
    ],
)

@curry
def render_remark_slides(course: Endpoint, course_root: str,
                         path: str, **template_kw):
    '''Render remark.js slides from a single Markdown file

    '''
    path = resolve_path(course_root, path)
    env = template_environment(course, course_root, **template_kw)

    @curry
    def render(path, **kw):
        return pipe(
            path.read_text(),
            env.from_string,
            call('render', **kw),
        )

    config = get_config()
    branding = config.get('branding', {})
    
    sources = {
        'css': pipe(
            concatv(
                remark_css_sources(),
                [render(j2_path('remark-slide.css.j2'),
                        branding=branding)]
            ),
            tuple,
        ),
        'js': remark_js_sources(),
    }

    markdown = render(path)

    html = pipe(
        j2_path('remark-slide-deck.html.j2'),
        render(sources=sources, markdown=markdown),
    )

    return html

def get_slide_title(content):
    match = re.search(r'^#\s(?P<title>\S.*)$', content, re.M)
    if match:
        return match.groupdict()['title'].strip()

@curry
def slide_page(course: Endpoint, course_root: str,
               md_path: (str, Path), html_path: (str, Path),
               file_ep: Endpoint, **template_kw):
    md_path = resolve_path(course_root, md_path)
    html_path = resolve_path(course_root, html_path)
    env = template_environment(course, course_root, **template_kw)

    @curry
    def render(path, **kw):
        return pipe(
            path.read_text(),
            env.from_string,
            call('render', **kw),
        )

    markdown = render(md_path)
    title = get_slide_title(markdown) or md_path
    return _.pipe(
        j2_path('slide-page.md.j2'),
        render(
            url=file_ep.data['url'],
            html_filename=html_path.name,
            title=title,
            markdown=markdown,
        ),
    )

