'''TODO

'''
from pathlib import Path
import typing as T
import logging

import requests
import toolz.curried as _
from toolz.curried import (
    pipe, filter, do, map,
)

from larc.common import (
    maybe_first, is_int,
)
from larc.rest import (
    IdResourceEndpoint, get_id_resources,
)
from larc.parallel import thread_map

from ..common import hashed_path

from .course import course_resource_docstring

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

folders = get_id_resources(
    'folders', memo=True,
    help=course_resource_docstring('folders'),
)

def root_folder(course: IdResourceEndpoint):
    '''For a given course enpoint, return its root folder object

    >>> import canvasapi, tokenmanager
    >>> token = tokenmanager.get_tokens().canvas
    >>> api = canvasapi.api.get_api(
    ...     'https://example.instructure.com/api/v1', token
    ... )
    >>> c, *_ = canvasapi.course.all_courses(api())
    >>> root = canvasapi.course.root_folder(c)

    Will return Null object if no root folder is found.
    '''
    return pipe(
        folders(course),
        filter(lambda f: f.data['parent_folder_id'] is None),
        maybe_first,
    )

files = get_id_resources(
    'files', memo=True,
    help=course_resource_docstring('files'),
)

def course_files_matching_path(course: IdResourceEndpoint, path: str):
    path = Path(path).expanduser().resolve()
    return pipe(
        files(course),
        filter(lambda f: f.data['filename'] == path.name),
        tuple,
    )

def upload_course_file(course: IdResourceEndpoint, path: str,
                       parent_dir: str = None, *, hashed=False):
    '''Upload a file to a course
    
    Canvas upload process:

    - Notify Canvas that you are uploading a file with a POST to the
      file creation endpoint. This POST will include the file name and
      file size, along with information about what context the file is
      being created in.
    
    - Upload the file using the information returned in the first POST
      request.
    
    - On successful upload, the API will respond with a redirect. This
      redirect needs to be followed to complete the upload, or the
      file may not appear.

    '''
    path = Path(path).expanduser().resolve()

    post_data = {
        'name': hashed_path(path).name if hashed else path.name,
        'size': path.stat().st_size,
    }

    if parent_dir is None:
        post_data['parent_folder_id'] = root_folder(course).data['id']
    elif is_int(parent_dir):
        post_data['parent_folder_id'] = parent_dir
    else:
        post_data['parent_folder_path'] = str(parent_dir)

    # Notify Canvas API
    init_resp = course('files').post(data=post_data)
    if init_resp.status_code in range(200, 300):
        upload_info = init_resp.json()

        url = upload_info['upload_url']
        params = upload_info['upload_params']

        # Upload file
        with path.open('rb') as rfp:
            upload_resp = requests.post(
                url, data=params,
                files={'file': rfp}
            )

        if upload_resp.status_code in range(200, 300):
            return IdResourceEndpoint(
                course.api('files'),  # Files are in their own URL
                                      # space (i.e. not in course
                                      # tree)
                upload_resp.json(),
                form_key=None, id_key='id',
            )

        # Upload went wrong
        log.error(
            f'There was an error uploading file:\n'
            f'  url: {url}\n'
            f'  params: {params}\n'
            f'  code: {upload_resp.status_code}\n'
            'Response:\n'
            f'{upload_resp.content[:1000]}'
        )
    else:
        # Initialization went wrong
        log.error(
            f'There was an error initiating file upload:\n'
            f'  post data: {post_data}\n'
            f'  code: {init_resp.status_code}\n'
            'Response:\n'
            f'{init_resp.content[:1000]}'
        )

def upload_course_files(course: IdResourceEndpoint, paths: T.Sequence[str],
                        pmap=thread_map, **upload_kw):
    return _.pipe(
        paths,
        pmap(upload_course_file(course, **upload_kw)),
        tuple,
    )
