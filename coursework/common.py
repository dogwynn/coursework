import re
import hashlib
from pathlib import Path
import pprint
from typing import Union
import logging
import json

import markdown as _markdown
import toolz.curried as _

from larc import yaml
from larc.rest import Api, Endpoint
from larc import common

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

CONTENT_DIRS = {
    'slide': 'slides',
    'page': 'pages',
    'quiz': 'quizzes',
    'assign': 'assignments',
    'module': 'modules.yml',
}

def content_paths(path: (str, Path)):
    return _.pipe(
        CONTENT_DIRS.items(),
        common.vmap(lambda k, d: (k, Path(path, d).expanduser().resolve())),
        dict,
    )

def find_course_root(path: (str, Path)):
    path = Path(path).expanduser().resolve()
    for parent in _.concatv([path], path.parents):
        paths = content_paths(parent)
        if any(p.exists() for p in paths.values()):
            return parent
    log.error(
        f'Could not find any course root for {path}'
    )

def find_content_paths(path: (str, Path)):
    root = find_course_root(path)
    if root:
        return content_paths(root)
    log.error(
        f'Could not find any content paths for {path}'
    )

def hash_from_content(content: Union[bytes, str]):
    return _.pipe(
        content if type(content) is bytes else content.encode(
            'utf-8', errors='ignore'
        ),
        hashlib.md5,
        lambda h: h.hexdigest(),
    )

def hash_from_dict(content: dict):
    return _.pipe(
        content,
        common.json_dumps(sort_keys=True, default=str),
        common.call('encode', 'utf-8'),
        hashlib.md5,
        common.call('hexdigest'),
    )

def hash_from_path(path: Union[str, Path]):
    return hash_from_content(Path(path).read_bytes())

def hashed_path(path: Union[str, Path]):
    '''Given a path, return its "hashed" version

    Example:

    >>> hashed_path('/a/b/c.txt')
    Path('/a/b/c-<MD5-hash-of-c.txt>.txt')

    '''
    path = Path(path).expanduser().resolve()
    path_hash = hash_from_path(path)
    return Path(
        path.parent,
        f'{path.stem}-{path_hash}{path.suffix}',
    )

def resolve_path(course_root: str, path: str):
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return Path(course_root, path).expanduser().resolve()

def markdown(content: str, **kwargs):
    class HtmlWithMeta(str):
        meta = None

    md = _markdown.Markdown(
        extensions=_.pipe(
            _.concatv(
                [
                    'larc.markdown.meta_yaml',
                    'larc.markdown.yaml_data',
                    'larc.markdown.card',
                    'larc.markdown.table',
                    # 'coursework.markdown.codehilite',
                ],
                [
                    'extra',
                    'codehilite',
                ],
                kwargs.get('extensions', []),
            ),
            set,
            tuple,
        ),
            
        extension_configs=_.merge(
            {
                'extra': {},
                # 'coursework.markdown.codehilite': {
                #     'noclasses': True,
                #     'guess_lang': False,
                #     'linenumstyle': 'inline',
                # },
                'codehilite': {
                    'noclasses': True,
                    'guess_lang': False,
                    # 'linenumstyle': 'inline',
                },
            },
            kwargs.get('extension_configs', {}),
        ),
    )

    output = HtmlWithMeta(md.convert(content))
    output.meta = md.meta or {}
    return output

def maybe_markdown_from_path(path: str, **kwargs):
    try:
        return markdown(Path(path).expanduser().read_text())
    except Exception as error:
        log.error(f'Exception while reading markdown: {error}')
    return common.Null

