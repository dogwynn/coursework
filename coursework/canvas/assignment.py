'''TODO

'''
from pathlib import Path
from typing import Union
from itertools import zip_longest
import logging
import tempfile
import pprint

import requests
from toolz.curried import (
    compose, filter, pipe, map, curry, merge, first,
)
from toolz.curried import do

from larc.common import (
    update_if_key_exists, maybe_pipe, Null, getitem, vmap,
    replace_key, vdo,
)
from larc import common as lcommon
from larc.rest import (
    get_id_resources, new_id_resource, update_endpoint, IdResourceEndpoint,
)
from larc import yaml
from larc.parallel import thread_map

from .course import (
    course_resource_docstring, create_course_resource_docstring,
)
from .metadata import get_metadata, set_metadata
from ..common import (
    hash_from_content, hash_from_dict, resolve_path,
)
from .. import templates

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

# ----------------------------------------------------------------------
#
# AssignmentGroup functionality
#
# ----------------------------------------------------------------------

assignment_groups = get_id_resources(
    'assignment_groups', memo=True,
)

new_assignment_group = new_id_resource(
    'assignment_groups',
    help=create_course_resource_docstring(
        'assignment_group',
        {'name': 'Assignment Group X',
         'group_weight': 30},
    )
)

@curry
def find_assignment_group(course: IdResourceEndpoint, name: str):
    groups = pipe(
        assignment_groups(course),
        filter(lambda g: g.data['name'].lower().startswith(name)),
        tuple,
    )
    if len(groups):
        if len(groups) == 1:
            return groups[0]
        log.error(
            f'More than one AssignmentGroup matches name={name} --> '
            f'{", ".join(g.data["name"] for g in groups)}'
        )
        return Null
    log.error(f'No groups match name={name}')
    return Null

@curry
def group_data_from_dict(course: IdResourceEndpoint, data: dict):
    kmap = {
        'weight': 'group_weight',
        'w': 'group_weight',
        'n': 'name',
    }
    for k, kf in kmap.items():
        if k in data:
            data = replace_key(k, kf, None, data)

    rules = data.get('rules', {})
    if rules:
        rules_kmap = {
            'high': 'drop_highest',
            'h': 'drop_highest',
            'low': 'drop_lowest',
            'l': 'drop_lowest',
            'never': 'never_drop',
        }
        for k, kf in rules_kmap.items():
            if k in rules:
                rules = replace_key(k, kf, None, rules)
        data['rules'] = rules

    return data
        
@curry
def group_data_from_yaml_content(course: IdResourceEndpoint, yaml_data: str):
    return maybe_pipe(
        yaml_data,
        yaml.load,
        getitem('assignment'),
        enumerate,
        vmap(lambda i, d: merge(d, {'position': i + 1})),
        map(group_data_from_dict(course)),
        tuple,
    )

@curry
def group_data_from_yaml_path(course: IdResourceEndpoint,
                              path: Union[str, Path]):
    return pipe(
        Path(path).expanduser().read_text(),
        group_data_from_yaml_content(course),
    )

@curry
def sync_assignment_groups_from_path(course: IdResourceEndpoint,
                                     path: Union[str, Path]):
    group_data = group_data_from_yaml_path(course, path)
    group_names = [g['name'] for g in group_data]

    @curry
    def do_log(logger, msg):
        return logger(
            '[sync_assignment_groups_from_path] ' + msg
        )
    log_info = do_log(log.info)
    log_error = do_log(log.error)

    group_eps = assignment_groups(course, do_memo=False)
    group_ep_names = [g.data['name'] for g in group_eps]

    # Don't delete already created assignment groups. Report them to
    # be deleted manually.
    unneeded = set(group_ep_names) - set(group_names)
    if unneeded:
        log_error(
            'The following assignment groups need to be removed manually:\n'
            f'{", ".join(sorted(unneeded))}'
        )
        log_error(
            '... setting position(s) to 999'
        )
        pipe(
            group_eps,
            filter(lambda ep: ep.data['name'] in unneeded),
            do(lambda ep: update_endpoint(ep, {'position': 99})),
            tuple,
        )

    missing_names = set(group_names) - set(group_ep_names)
    # Create missing assignment groups
    if missing_names:
        log_info(
            'The following assignment groups will be created:\n'
            f'{", ".join(sorted(missing_names))}'
        )
        new_data = pipe(
            group_data,
            filter(lambda d: d['name'] in missing_names),
            map(do(lambda d: log_info(
                f'... creating group: {d["name"]}'
            ))),
            map(lambda d: (d, hash_from_dict(d),
                           new_assignment_group(course, d))),
            map(vdo(lambda d, h, ep: log_info(
                f'... setting hash: {h}'
            ))),
            map(vdo(lambda d, h, ep: set_metadata(ep, {'hash': h}))),
            tuple,
        )

    group_hashes = pipe(
        group_data,
        map(hash_from_dict),
        tuple,
    )

    name_to_ep = pipe(
        assignment_groups(course, do_memo=False),
        map(lambda ep: (ep, get_metadata(ep).get('hash'))),
        vmap(lambda ep, h: (ep.data['name'], (ep, h))),
        dict,
    )
    for data in group_data:
        ep, h = name_to_ep[data['name']]
        data_hash = hash_from_dict(data)
        if h != data_hash:
            log_info(f'Updating group: {data["name"]}')
            update_endpoint(ep, data)
            set_metadata(ep, {'hash': data_hash})

# ----------------------------------------------------------------------
#
# Assignment functionality
#
# ----------------------------------------------------------------------

assignments = compose(
    tuple,
    filter(lambda a: not a.data['is_quiz_assignment']),
    get_id_resources(
        'assignments', form_key='assignment', memo=True,
    )
)
assignments.__class__.__doc__ = course_resource_docstring('assignments')

def transform_assignment_params(params: dict):
    st_trans = {
        'text': 'online_text_entry',
        'url': 'online_url',
        'upload': 'online_upload',
    }
    return pipe(
        params,
        update_if_key_exists(
            'submission_types', lambda d: [
                st_trans.get(t, t) for t in d['submission_types']
            ]
        ),
    )

new_assignment = new_id_resource(
    'assignments', form_key='assignment',
    help=create_course_resource_docstring(
        'assignment', {'name': 'A New Assignment',
                       'submission_types': ['text', 'url', 'upload'],
                       'description': '<p>Some HTML content.</p>'}
    ), body_transform=transform_assignment_params,
)

update_assignment = update_endpoint(
    body_transform=transform_assignment_params,
)

@curry
def find_assignment(course: IdResourceEndpoint, name: str):
    for a in assignments(course):
        if a.data['name'] == name:
            return a.refresh()

@curry
def sync_assignment_from_path(course: IdResourceEndpoint, course_root: str,
                              path: Union[str, Path]):
    @curry
    def do_log(logger, msg):
        return logger(
            '[sync_assignment_from_path] ' + msg
        )
    log_info = do_log(log.info)
    log_error = do_log(log.error)

    html = templates.common.render_markdown_path(course, course_root, path)

    assign_data = html.meta.copy()
    name = assign_data.get('name')

    if not name:
        log_error(
            f'The Canvas assignment at {path} does not have a '
            '"name:" specified.'
        )
        return False

    group_ep = maybe_pipe(
        assign_data.pop('assignment_group', None),
        find_assignment_group(course),
    )
    # rubric = assign_data.pop('rubric', None)
    # if rubric:
    #     if 'use_rubric_for_grading' not in assign_data:
    #         assign_data['use_rubric_for_grading'] = True

    assignment = find_assignment(course, name)
    if not assignment:
        # Need to create new
        log_info(
            f'Creating new assignment: "{name}" from {path}'
        )
        assignment = new_assignment(
            course, merge(assign_data, {'description': str(html)}),
        )

    assign_md = get_metadata(assignment)

    path = resolve_path(course_root, path)
    content_hash = hash_from_content(path.read_text())
    extant_hash = assign_md.get('hash')

    if not content_hash == extant_hash:
        if group_ep:
            log_info(
                f"Found assignment group for {name}: {group_ep.data['name']}"
            )
            assign_data['assignment_group_id'] = group_ep.data['id']

        # log_info(f'Hashes different:'
        #          f' {content_hash} {extant_hash}')
        log_info(
            f'Updating assignment "{name}" at {path}:\n'
            f'{pprint.pformat(assign_data)}'
        )
        assign_md['hash'] = content_hash
        set_metadata(assignment, assign_md)
        
        return update_assignment(
            assignment, merge(assign_data, {'description': str(html)}),
            # do_refresh=False,
        )
    return assignment

@curry
def sync_assignments_from_path(course: IdResourceEndpoint, course_root: str,
                               assignments_root: str, *,
                               map_func=thread_map(max_workers=5)):
    return pipe(
        Path(assignments_root).expanduser().glob('assign-*.md'),
        map_func(sync_assignment_from_path(course, course_root)),
        tuple,
    )

# ----------------------------------------------------------------------
#
# Submission functionality
#
# ----------------------------------------------------------------------

submissions = get_id_resources(
    'submissions', memo=True,
    data={'include[]': ['user', 'rubric_assessment',
                        'submission_comments']},
)

def save_attachments(submission: IdResourceEndpoint,
                     output_dir: Union[str, Path],
                     map_func=thread_map(max_workers=5)):
    '''

    '''
    output_dir_path = Path(output_dir).expanduser()
    if not output_dir_path.exists():
        output_dir_path.mkdir(parents=True, exist_ok=True)
    return maybe_pipe(
        submission.data.get('attachments'),
        map(lcommon.get_many_t(['filename', 'url'])),
        filter(all),
        map_func(lcommon.vcall(lambda f, u: (
            Path(output_dir, f).expanduser(), requests.get(u)
        ))),
        lcommon.vfilter(lambda p, r: r.status_code in range(200, 300)),
        lcommon.vmap(lambda p, r: (
            p, p.write_bytes(r.content)
        )),
        map(first),
        tuple,
    )
        
