import logging

import requests
from toolz.curried import (
    curry,
)

from larc.rest import (
    Api, TokenAuth,
)

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

@curry
def get_api(base_url, token, *, session: requests.Session = None):
    return Api(base_url, TokenAuth(token), session or requests.Session())

def get_api_from_config(config: dict = None):
    from ..config import get_base_url, get_token
    return get_api(get_base_url(config), get_token(config))
