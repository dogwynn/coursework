import random
from pathlib import Path
from typing import List, Sequence
import logging
import mimetypes
import base64
import hashlib
import json

import jinja2
from pkg_resources import resource_filename as _resource_filename
import toolz.curried as _
from toolz.curried import (
    compose, curry, pipe, filter, mapcat, do, map, first,
)

from larc import yaml
import larc.common as __
from larc.common import (
    maybe_first, is_int, is_seq, call, vmap, to_pyrsistent,
    deref, get,
)
from larc.rest import (
    Endpoint,
)

from ..common import (
    markdown, maybe_markdown_from_path, hashed_path, resolve_path,
)
from .. import canvas
from ..canvas.course import Course

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

def generator():
    from ..__init__ import __version__
    return f'coursework-{__version__}'

resource_filename = compose(
    Path,
    curry(_resource_filename)(__name__),
)

def templates_path(path: str = '.'):
    return Path(resource_filename('j2'), path)
j2_path = templates_path

def css_path(path: str = '.'):
    return Path(resource_filename('css'), path)

def js_path(path: str = '.'):
    return Path(resource_filename('js'), path)

@curry
def slide_md(course: Course, course_root: str, path: str):
    path = resolve_path(course_root, path)
    if path.exists():
        return pipe(
            path,
            # render_markdown_path(course, course_root),
        )
    log.error(
        f'No slide markdown at {path}'
    )

@curry
def slide_link(course: Course, course_root: str,
               md_path: str, link_text: str = None, *,
               force_upload: bool = False,
               dry_run: bool = False):
    md_path = resolve_path(course_root, md_path)
    html_path = Path(md_path.parent, md_path.stem + '.html')
    
    

@curry
def image_hash(course_root: str, path: str):
    path = resolve_path(course_root, path)
    if path.exists():
        return pipe(
            path.read_bytes(),
            hashlib.md5,
            call('hexdigest'),
        )
    log.error(
        f'No image at {path}'
    )

@curry
def base64_content(mimetype: str, data: bytes):
    return f'data:{mimetype};base64,{base64.b64encode(data).decode()}'

def image_base64(path: str):
    mimetype, encoding = mimetypes.guess_type(path)
    data = Path(path).expanduser().resolve().read_bytes()
    return base64_content(mimetype, data)

FIG = '''
<div>
  <figure class="figure">
    <img {style} src="{data}" />
    <figcaption class="figure-caption">{caption}</figcaption>
  </figure>
</div>
'''

@curry
def fig(course_root: str, path: str, caption: str = '', *,
        style: dict = None):
    path = resolve_path(course_root, path)
    style = pipe(
        pipe(
            style.items(),
            vmap(lambda k, v: f"{k}: {v}"),
            '; '.join,
        ),
        'style="{}"'.format,
    ) if style else ''
    data = image_base64(path)
    return FIG.format(style=style, data=data, caption=caption)

@curry
def page_link(course: Course, course_root: str,
              path: str, link_text: str = None, ref: str = None, *,
              force_upload: bool = False,
              dry_run: bool = False):
    ref = f'#{ref}' if ref else ''
    path = resolve_path(course_root, path)

    meta = maybe_markdown_from_path(path).meta
    if not meta or 'title' not in meta:
        log.error(f'Cannot read page title from {path}')
        return link_text or path.name

    title = meta['title']
    html_url = pipe(
        canvas.page.pages(course),
        filter(lambda p: p.data['title'] == title),
        maybe_first,
        lambda p: p.data['html_url'],
    )

    link_text = link_text or title
    if html_url:
        return (
            f'<a title="{title}" href="{html_url}{ref}">{link_text}</a>'
        )
    log.error(
        f'Could not retrieve Canvas page with title: {title}'
    )
    return link_text


@curry
def assign_link(course: Course, course_root: str,
                path: str, link_text: str = None, *,
                force_upload: bool = False,
                dry_run: bool = False):
    path = resolve_path(course_root, path)

    meta = maybe_markdown_from_path(path).meta
    if not meta or 'name' not in meta:
        log.error(f'Cannot read assignment name from {path}')
        return link_text or path.name

    name = meta['name']
    html_url = pipe(
        canvas.assignment.assignments(course),
        filter(lambda a: a.data['name'] == name),
        maybe_first,
        lambda a: a.data['html_url'],
    )

    link_text = link_text or name
    if html_url:
        return (
            f'<a title="{name}" href="{html_url}">{link_text}</a>'
        )
    log.error(
        f'Could not retrieve Canvas assignment with name: {name}'
    )
    return link_text
               
@curry
def questions(course: Course, course_root: str, path: str):
    return pipe(
        canvas.quiz.quiz_data_from_yaml(course, course_root, path),
        call('get', 'questions', []),
    )
    # name = Path(path).name

    # quiz_path = pipe(
    #     canvas.quiz
    #     resolve_path(course_root, 'quizzes').glob('quiz-*.yml'),
    #     filter(lambda p: p.name == name),
    #     maybe_first,
    # )

    # if quiz_path:
    #     return pipe(
    #         quiz_path.read_text(),
    #         template_environment(
    #             course, course_root
    #         ).from_string,
    #         lambda template: template.render(),
    #         yaml.load,
    #         lambda quiz: quiz.get('questions') or []
    #     )

    # log.error(f'Quiz {name} not found.')

@curry
def code_section(course: Course, course_root: str,
                 path: str, **kw):
    path = resolve_path(course_root, path)

    log.debug(f'Inserting code from {path}')
    kw_str = json.dumps(_.merge({'linenos': 'inline'}, kw))
    return f'```python3 {kw_str}\n{path.read_text()}\n```'
    # if lines:
    #     lines_str = pipe(
    #         lines,
    #         mapcat(lambda v: [v] if is_int(v) else v),
    #         ' '.join,
    #         lambda t: 'hl_lines="{' + t + '}"',
    #     )
    #     return f'```python3 {lines_str}\n{path.read_text()}\n```'

    # else:
    #     return f'```python3\n{path.read_text()}\n```'

# course = '-'.join(
#     map(str, (self.course.id.year,self.course.id.period,
#               self.course.id.section))
# )

@curry
def shuffled(rng: random.Random, values):
    return rng.sample(values, len(values))
shuffle = shuffled

@curry
def take(rng: random.Random, seq: Sequence, start, stop=None, step=None):
    seq = list(seq)
    if start >= 0 and start < 1:
        # Random percentage of seq
        return rng.sample(
            seq, int(len(seq) * start) or 1
        )
    else:
        if not step:
            step = 1
        if not stop:
            stop = start
            start = 0
        return seq[start:stop:step]

def to_yaml(obj):
    if is_seq(obj):
        obj = list(obj)
    return yaml.dump(obj)

def file_url(course: Course, func_name: str,
             path: Path, force_upload: bool, dry_run: bool):
    matching_files = canvas.file.course_files_matching_path(
        course, hashed_path(path)
    )

    if dry_run:
        log.info(
            f'[{func_name}] DRY RUN{" -FORCE-" if force_upload else ""}'
            f' uploading file: {path}'
        )
        url = 'PLACEHOLDER_URL'
    else:
        if not matching_files or force_upload:
            log.info(
                f'[{func_name}]{" -FORCE-" if force_upload else ""}'
                f' uploading file: {path}'
            )
            canvas.file.upload_course_file(course, path, hashed=True)
            file_ep = canvas.file.upload_course_file(course, path)
            if file_ep:
                canvas.file.files.reset_cache(course)
                url = file_ep.data['url']
            else:
                log.error(
                    f'[{func_name}]{" -FORCE-" if force_upload else ""}'
                    f' uploading file... Could not get URL for uploaded'
                    f' file: {path}'
                )
                url = 'BAD_URL_FAILED_UPLOAD'
        else:
            url = pipe(
                canvas.file.course_files_matching_path(course, path),
                first,
                deref('data'),
                get('url'),
            )

    return url

@curry
def file_link(course: Course, course_root: str,
              path: str, link_text: str = None, *,
              force_upload: bool = False,
              dry_run: bool = False):
    path = resolve_path(course_root, path)

    url = file_url(course, 'file_link', path, force_upload, dry_run)

    link_text = link_text or path.name

    return (
        f'<a class="instructure_file_link" title="{path.name}"'
        f' href="{url}&amp;wrap=1" download="{path.name}">{link_text}</a>'
    )
    

def get_caption(caption):
    return f'<figcaption>{caption}</figcaption>' if caption else ''

def get_style(d: dict):
    return 'style="{}"'.format(
        ' '.join(f'{k}: {v};' for k, v in sorted(d.items()))
    ) if d else ''

@curry
def image_link(course: Course, course_root: str,
               path: str, alt_text: str = None,
               style: str = None, caption: str = None, *,
               force_upload: bool = False,
               dry_run: bool = False):
    path = resolve_path(course_root, path)

    url = file_url(course, 'image_link', path, force_upload, dry_run)

    alt_text = alt_text or path.name

    return (f'<figure style="margin: 10px"><img src="{url}"'
            f' alt="{alt_text}" {get_style(style)} />'
            f'{get_caption(caption)}</figure>')

@curry
def image_anchor(course: Course, course_root: str,
                 path: str, url: str, alt_text: str = None, *,
                 force_upload: bool = False,
                 dry_run: bool = False):
    path = resolve_path(course_root, path)

    img_url = file_url(course, 'image_anchor', path, force_upload, dry_run)
        
    alt_text = alt_text or path.name

    return (
        f'<a target="{alt_text}" href="{url}"><img src="{img_url}"'
        f' alt="{alt_text}" /></a>'
    )

@curry
def template_environment(course: Course, course_root: str, *,
                         force_upload: bool = False,
                         dry_run: bool = False):
    course_root = Path(course_root).expanduser().resolve()
    if not course_root.exists():
        log.error(f'Course root directory does not exist: {course_root}')

    env = jinja2.Environment()

    env.globals['image_base64'] = image_base64
    env.globals['slide_link'] = slide_link(
        course, course_root,
        force_upload=force_upload, dry_run=dry_run,
    )
    env.globals['page_link'] = page_link(
        course, course_root,
        force_upload=force_upload, dry_run=dry_run,
    )
    env.globals['assign_link'] = assign_link(
        course, course_root,
        force_upload=force_upload, dry_run=dry_run,
    )
    env.globals['slide_md'] = slide_md(
        course, course_root,
    )
    env.globals['file_link'] = file_link(
        course, course_root,
        force_upload=force_upload, dry_run=dry_run,
    )
    env.globals['fig'] = fig(course_root)
    env.globals['image_link'] = image_link(
        course, course_root,
        force_upload=force_upload, dry_run=dry_run,
    )
    env.globals['image_anchor'] = image_anchor(
        course, course_root,
        force_upload=force_upload, dry_run=dry_run,
    )
    env.globals['questions'] = questions(
        course, course_root,
    )
    env.globals['code_section'] = code_section(
        course, course_root,
    )

    rng = _.pipe(
        ['year', 'period', 'code', 'section'],
        _.map(course.data.get('metadata', {}).get),
        _.filter(None),
        _.map(str),
        '###'.join,
        lambda v: v.encode('utf-8', errors='ignore'),
        hashlib.md5,
        lambda h: h.hexdigest(),
        random.Random,
    )

    env.globals['shuffled'] = shuffled(rng)
    env.filters['shuffle'] = shuffle(rng)
    env.filters['take'] = take(rng)
    env.filters['to_yaml'] = to_yaml
    
    return env

def render_content(course: Course, course_root: str,
                   content: str, **template_env_kw):
    env = template_environment(course, course_root, **template_env_kw)
    return env.from_string(content).render()
    
render_markdown_content = compose(markdown, render_content)
render_yaml_content = compose(yaml.load, render_content)

def render_path(course: Course, course_root: str,
                path: (str, Path), **template_env_kw):
    path = resolve_path(course_root, path)
    return render_content(course, course_root, path.read_text())

render_markdown_path = compose(markdown, render_path)
render_yaml_path = compose(yaml.load, render_path)

