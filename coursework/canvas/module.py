'''TODO

'''
import re
import pprint
from pathlib import Path
from collections import OrderedDict
from typing import Union
import logging

from toolz.curried import (
    curry, pipe, map, filter, merge, first, drop, dissoc,
)

from larc.common import (
    maybe_first, vcall,
)
from larc.rest import (
    Endpoint, update_endpoint, get_id_resources, new_id_resource,
    total_cache_reset,
)

from .course import (
    course_resource_docstring, create_course_resource_docstring,
)
from . import (
    page, assignment, quiz, file,
)


log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

modules = get_id_resources(
    'modules', form_key='module', memo=True,
    help=course_resource_docstring('modules'),
)

new_module = new_id_resource(
    'modules', form_key='module',
    help=create_course_resource_docstring(
        'module', {'name': 'Module Name', 'position': 1}
    ),
)

ITEM_TYPES = [
    "File",
    "Page",
    "Discussion",
    "Assignment",
    "Quiz",
    "SubHeader",
    "ExternalUrl",
    "ExternalTool",
]

RESOURCE_F = {
    'File': file.files,
    'Page': page.pages,
    'Assignment': assignment.assignments,
    'Quiz': quiz.quizzes,
}

def get_item_type(test: str):
    for t in ITEM_TYPES:
        if re.search(test, t, re.I):
            return t

items = get_id_resources(
    'items', form_key='module_item', memo=True,
    data={'include[]': ['content_details']},
    help='''For a given module endpoint, return a tuple of its module item
    object endpoints

    Example:

    >>> course, *_ = canvasapi.course.all_courses(api())
    >>> module, *_ = canvasapi.module.modules(course)
    >>> module_items = canvasapi.module.items(module)
    ''',
)

new_item = new_id_resource(
    'items', form_key='module_item', memo=True,
    help='''For a given module endpoint, create a new module item

    Example:

    >>> module, *_ = canvasapi.module.modules(course)
    >>> new = canvasapi.module.new_item(
    ...     module, {'type': 'Page', 'page-url': 'some-page-url'},
    ... )
    >>>
    ''',
)

@curry
def search_items(resource_iter_f, search_key: str, output_key: str,
                 course: Endpoint, search: str):
    regex = re.compile(re.escape(search))
    found = pipe(
        resource_iter_f(course),
        filter(lambda e: regex.search(e.data[search_key])),
        maybe_first,
    )
    if found:
        return (output_key, found.data[search_key], found.data[found.id_key])
    return (output_key, None, None)

TITLE_KEY = {
    'Page': 'title',
    'Quiz': 'title',
    'Assignment': 'name',
}

SEARCH = {
    'Page': search_items(page.pages, 'title', 'page_url'),
    'Quiz': search_items(quiz.quizzes, 'title', 'content_id'),
    'Assignment': search_items(assignment.assignments, 'name', 'content_id'),
    'File': search_items(file.files, 'filename', 'content_id'),
}

@curry
def item_from_dict(course: Endpoint, item: OrderedDict):
    itype, search = pipe(
        item.items(),
        first,
        vcall(lambda itype, search: (get_item_type(itype), search))
    )

    if itype is not None and itype in SEARCH:
        key, title, value = SEARCH[itype](course, search)
        # Remove the first key, value pair
        base_item = pipe(
            item.items(),
            drop(1),
            dict
        )
        return merge(
            base_item,
            {'type': itype,
             'title': title,
             key: value},
        )

    return item
            
@curry
def module_from_dict(course: Endpoint, module_dict: OrderedDict):
    return {
        'name': module_dict['name'],
        'items': pipe(
            module_dict['items'],
            map(item_from_dict(course)),
            tuple,
        ),
    }

@curry
def find_module(course: Endpoint, module_dict: OrderedDict):
    for m in modules(course):
        if m.data['name'] == module_dict['name']:
            return m

@curry
def find_item(course: Endpoint, item_dict: OrderedDict):
    for m in modules(course):
        for i in items(m):
            if i.data["title"] == item_dict['title']:
                return i

_test_module_data = '''
- name: Learn Python the Hard Way
  items:
    - page: Intro and Setup
    - assign: HW 00
    - assign: HW 01
    - assign: HW 02
    - assign: HW 03
    - assign: HW 04
    - assign: HW 05
    - assign: HW 06
    - assign: HW 07
    - assign: HW 08
    - assign: HW 09
    - assign: HW 10

- name: Final Project
  items:
    - assign: HW 11
'''
def test_module_data(course: Endpoint):
    return module_data_from_yaml_content(course, _test_module_data)

@curry
def module_data_from_yaml_content(course: Endpoint, yaml_data: str):
    from larc import yaml
    return pipe(
        yaml_data,
        yaml.load,
        map(module_from_dict(course)),
        tuple,
    )

@curry
def module_data_from_yaml_path(course: Endpoint, path: (str, Path)):
    return module_data_from_yaml_content(course, Path(path).read_text())

def create_modules_from_data(course: Endpoint, module_data: list,
                             dry_run: bool = False):
    reset_cache = False
    # Create modules if they don't exist
    for mod_dict in module_data:
        mod = find_module(course, mod_dict)
        if not mod:
            # Need to create
            without_items = dissoc(mod_dict, 'items')
            log.info(f'Creating new module: {without_items}')
            if not dry_run:
                new_module(course, without_items)
            else:
                log.info(f'... DRY RUN')
            reset_cache = True
    if reset_cache:
        # Reset the module cache for this course
        modules.reset_cache(course)
    else:
        log.info('No changes to module structure')

def order_modules_from_data(course: Endpoint, module_data: list,
                            dry_run: bool = False):
    reset_cache = False
    # Make sure modules are in correct order
    for mod_i, mod_dict in enumerate(module_data, 1):
        mod = find_module(course, mod_dict)
        if mod.data['position'] != mod_i:
            log.info(
                f'Moving position of module {mod_dict["name"]} to {mod_i}'
            )
            if not dry_run:
                update_endpoint(mod, {'position': mod_i})
            else:
                log.info(f'... DRY RUN')
                
            reset_cache = True
    if reset_cache:
        # Reset the module cache for this course
        modules.reset_cache(course)
    else:
        log.info('No changes to module order')

def create_module_items_from_data(course: Endpoint, module_data: list,
                                  dry_run: bool = False):
    new_item_created = False
    # Create new items if they don't exist
    for mod_dict in module_data:
        reset_cache = False
        module = find_module(course, mod_dict)
        for item_dict in mod_dict['items']:
            item = find_item(course, item_dict)
            if not item:
                log.info(f'Creating new item: {item_dict}')
                # Need to create
                if not dry_run:
                    new_item(module, item_dict)
                else:
                    log.info(f'... DRY RUN')
                    
                reset_cache = True
                new_item_created = True
        if reset_cache:
            # Reset items cache for this module
            items.reset_cache(module)
    if not new_item_created:
        log.info('No new items created')

def move_module_items_from_data(course: Endpoint, module_data: list,
                                dry_run: bool = False):
    item_moved = False
    # Move module items that are in the wrong module
    for mod_dict in module_data:
        module = find_module(course, mod_dict)
        item_ids = pipe(
            items(module),
            map(lambda i: (i.data[i.id_key], i)),
            dict,
        )
        reset_cache = False
        for item_dict in mod_dict['items']:
            item = find_item(course, item_dict)
            if item and item.data[item.id_key] not in item_ids:
                # Need to move this item to its correct parent
                parent_id = module.data[module.id_key]
                log.info(
                    f'Moving item "{item_dict["title"]}" to'
                    f' module "{mod_dict["name"]}"'
                )
                log.debug(
                    f'Module:\n{pprint.pformat(module.data)}\n'
                    f'Item:\n{pprint.pformat(item.data)}\n'
                )
                if not dry_run:
                    update_endpoint(
                        item, {'module_id': parent_id},
                        do_refresh=False,  # This item is no longer in the
                                           # same parent module. So a
                                           # refresh of the same endpoint
                                           # would 404
                    )
                else:
                    log.info(f'... DRY RUN')
                reset_cache = True
                item_moved = True
        if reset_cache:
            # Reset items cache for this module (to reflect item
            # movement)
            items.reset_cache(module)
    if not item_moved:
        log.info('No items needed moving')

def order_module_items_from_data(course: Endpoint, module_data: list,
                                 dry_run: bool = False):
    item_reordered = False
    # Make sure module items are in correct order
    for mod_dict in module_data:
        module = find_module(course, mod_dict)
        reset_cache = False
        for item_i, item_dict in enumerate(mod_dict['items'], 1):
            item = find_item(course, item_dict)
            if item and item.data['position'] != item_i:
                log.info(
                    f'Moving item "{item_dict["title"]}" position'
                    f' to {item_i}'
                )
                log.debug(
                    f'\nmodule:\n{pprint.pformat(module.data)}\n'
                    f'\nitem_dict:\n{pprint.pformat(item_dict)}\n'
                    f'item.data:\n{pprint.pformat(item.data)}'
                )
                if not dry_run:
                    update_endpoint(
                        item, {'position': item_i},
                        do_refresh=False,  # XXX FIX XXX not sure why this
                                           # is necessary. The item hasn't
                                           # changed parents. /sad_shrug
                    )
                else:
                    log.info(f'... DRY RUN')
                    
                reset_cache = True
                item_reordered = True
        if reset_cache:
            # Reset entire cache to reflect movement among modules
            total_cache_reset()

    if not item_reordered:
        log.info('No items needed reordering')

@curry
def sync_modules(course: Endpoint, module_data: list, dry_run: bool = False):
    create_modules_from_data(course, module_data, dry_run=dry_run)
    order_modules_from_data(course, module_data, dry_run=dry_run)
    create_module_items_from_data(course, module_data, dry_run=dry_run)
    move_module_items_from_data(course, module_data, dry_run=dry_run)
    order_module_items_from_data(course, module_data, dry_run=dry_run)
    return True

def sync_modules_from_yaml_path(course: Endpoint, path: Union[str, Path],
                                dry_run: bool = False):
    return pipe(
        path,
        module_data_from_yaml_path(course),
        sync_modules(course, dry_run=dry_run),
    )
