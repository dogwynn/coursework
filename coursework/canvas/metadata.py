'''Storage of API element metadata using the Canvas User object
custom_data

TODO

'''

import logging

from toolz.curried import pipe, map
from larc.rest import (
    IdResourceEndpoint,
)

from .user import (
    get_data, set_data,
)

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

def md_key(endpoint: IdResourceEndpoint):
    return 'metadata-' + pipe(endpoint.parts, map(str), '-'.join)

def get_metadata(endpoint: IdResourceEndpoint):
    meta = get_data(endpoint.api, md_key(endpoint))
    if not meta:
        set_data(endpoint.api, md_key(endpoint), {})
        return {}
    return meta

def set_metadata(endpoint: IdResourceEndpoint, data: dict):
    return set_data(endpoint.api, md_key(endpoint), data)
