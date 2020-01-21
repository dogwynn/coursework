import os
import re
import pprint
from pathlib import Path
from typing import Union
import logging

import requests
from toolz.curried import (
    pipe, map,
)
from larc import yaml
from larc import common as lcommon

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

class ConfigurationError(ValueError):
    pass

def default_config_path():
    return Path(
        '~/.config/coursework/config.yml'
    ).expanduser()

def init_config():
    path = default_config_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(CONFIG_TEMPLATE)
    return yaml.read_yaml(path)

def validate_config_path(path: str):
    try:
        config = yaml.read_yaml(path)
    except Exception as error:
        return (False, (
            f'Config path ({path}) is not valid YAML:\n{error}'
        ))
    valid, reasons = validate_config(config)
    if not valid:
        return (False, (
            f'Your config ({path}) is not a valid configuration:\n'
            '{reasons}'
        ))
    return True, ''

_required_keys = {
    'api_token', 'root_dir', 'base_url', 'regexes'
}
def validate_config(config: dict):
    reasons = []

    missing = _required_keys - set(config)
    if missing:
        missing_str = pipe(
            missing, sorted, map(lambda k: f'- {k}'), '\n'.join,
        )
        reasons.append(
            f'The following keys are missing:\n{missing_str}'
        )

    if 'root_dir' in config:
        if not Path(config['root_dir']).expanduser().resolve().exists():
            reasons.append(
                'Root directory ("root_dir") does not'
                f' exist: {config["root_dir"]}'
            )

    if 'base_url' in config:
        bad_url = False
        try:
            requests.get(config['base_url'])
        except Exception as error:
            bad_url = True
            reasons.append(
                f'Problem accessing "base_url":\n{error}'
            )
        if 'api_token' in config and not bad_url:
            from .api import get_api
            api = get_api(config['base_url'], config['api_token'])
            try:
                resp = api('users', 'self').get()
                if resp.status_code == 404:
                    reasons.append(
                        'Your "base_url" does not correctly point at the'
                        ' Canvas REST API for your institution:'
                        f' {config["base_url"]}'
                    )
                elif resp.status_code == 401:
                    reasons.append(
                        'Your "api_token" does not provide you access to'
                        ' the Canvas REST API for your institution:'
                        f' {config["api_token"]}'
                    )
                elif resp.status_code != 200:
                    reasons.append(
                        'There is an issue with either your'
                        ' "api_token" or "base_url" such that'
                        ' the Canvas REST API for your institution returns'
                        ' an unsuccessful status code:\n'
                        f'  return code: {resp.status_code}\n'
                        f'  api token: {config["api_token"]}\n'
                        f'  base URL: {config["base_url"]}'
                    )
            except Exception as error:
                reasons.append(
                    f'Problem accessing API:\n{error}'
                )

    def valid_regex(r):
        reasons = []
        if 'key' not in r and 'keys' not in r:
            reasons.append('''Doesn't have either "key" or "keys"''')
        elif 'key' in r:
            if not lcommon.is_str(r['key']):
                reasons.append(
                    '"key" is not a string.'
                )
        elif 'keys' in r:
            if not lcommon.is_seq(r['keys']):
                reasons.append(
                    '"keys" is not a sequence. If specifying a single key,'
                    ' then "key" should be used.'
                )
        if 'regex' not in r:
            reasons.append('Missing "regex"')
        else:
            try:
                re.compile(r['regex'])
            except re.error as error:
                reasons.append(f'Error compiling regex: {error}')
            except TypeError:
                reasons.append(
                    f'Must provide a regular expression: {r["regex"]}'
                )
        if reasons:
            return False, pipe(reasons, map(lambda s: f'- {s}'), '\n'.join)
        return True, ''

    for regex in config.get('regexes', []):
        valid, reasons_str = valid_regex(regex)
        if not valid:
            reasons.append(
                f'Invalid regex: \n{pprint.pformat(regex)}\n'
                f'Reasons:\n{reasons_str}'
            )

    if reasons:
        return False, '\n\n'.join(reasons)

    return True, ''

def get_config(path: Union[str, Path] = None):
    if path is not None:
        valid, reasons = validate_config_path(path)
        if not valid:
            return False, reasons
        return True, yaml.read_yaml(path)
    return True, init_config()

def get_config_bang(path: Union[str, Path] = None) -> dict:
    success, output = get_config(path)
    if success:
        return output
    log.error(f'Failure to load config:\n{output}')
    raise ConfigurationError(
        'Configuration cannot be loaded. See above for reasons'
    )

# def get_config(path: str = None) -> dict:
#     '''Return the configuration dictionary
#     '''
#     path = Path(path).expanduser() if path else default_config_path()
#     if path.exists():
#         return yaml.read_yaml(path)

def get_root_dir(path: str = None):
    config = get_config_bang(path)
    if 'COURSEWORK_ROOT_DIR' in os.environ:
        return os.environ['COURSEWORK_ROOT_DIR']
    elif config and 'root_dir' in config:
        return config['root_dir']

    log.error(
        'Could not find root directory for courses. Must be defined in'
        ' either the COURSEWORK_ROOT_DIR environment variable or in'
        ' the config.yml file.'
    )
    
def get_base_url(path: str = None):
    config = get_config_bang(path)
    if 'COURSEWORK_BASE_URL' in os.environ:
        return os.environ['COURSEWORK_BASE_URL']
    elif config and 'base_url' in config:
        return config['base_url']

    log.error(
        'Could not find base URL for the institution. Must be defined in'
        ' either the COURSEWORK_BASE_URL environment variable or in'
        ' the config.yml file.'
    )

def get_token(path: str = None):
    config = get_config_bang(path)
    if 'COURSEWORK_TOKEN' in os.environ:
        return os.environ['COURSEWORK_TOKEN']
    elif config and 'api_token' in config:
        return config['api_token']

    log.error(
        'Could not find Canvas API token. Must be defined in either'
        ' the COURSEWORK_TOKEN environment variable or in the'
        ' config.yml file.'
    )

CONFIG_TEMPLATE = r'''
#----------------------------------------------------------------------
# Canvas API configuration file
#----------------------------------------------------------------------

# You must generate an API token and place it here.
#
# https://canvas.instructure.com/doc/api/file.oauth.html#manual-token-generation
#
api_token: >-
  PUT YOUR API TOKEN HERE

# This is the root directory for your course data. It must exist prior
# to use of the coursework tools.
#
root_dir: >-
  ~/courses

# This is the base URL of your institution's canvas API. Replace
# <yourinstitution> with the correct portion of the URL for your
# institution.
#
base_url: >-
  https://<yourinstitution>.instructure.com/api/v1/


# Regexes are how we pull out the institution-specific metadata for a
# course. Each one is specified as a YAML dictionary. The regular
# expression (specified with "regex") is run on particular values in
# the retrieved Canvas API course object. These course object values
# are retrived via the "key" (or "keys" as seen below).
#
regexes:
  #
  # The following metadata values are necessary:
  #
  # - code: the catalog code of a course (e.g. CSC101 or MAT205)
  # - section: the section designation of a course (e.g. 01 or 01TU1)
  # - year: year the course is offered (e.g. 2019)
  # - period: seasonal period of course (e.g. Fall, Spring, Summer)
  #
  # The following metadata values are optional:
  #
  # - name: the name of the course (e.g. Intro to CS or CS I)
  #
  # The regex dictionaries are specified in order of primacy. If an
  # earlier regex for a particular key matches, then the rest are
  # ignored.
  #
  # In the case of Belhaven University, the code, name and section are
  # specified in both the "name" course attribute and the
  # "course_code" course attribute. However, the quality of the data
  # in the "name" attribute is better than "course_code" (i.e. the
  # "course_code" value truncates the name), so the regex for "name"
  # is before the "course_code" regex, even though they are the
  # same. That way, in case one of them is missing, at least some of
  # the metadata is caught.
  
  - key: name
    regex: >-
      ^(?P<code>\S+) (?P<name>.*?) (?P<section>\S+)$
  - key: course_code
    regex: >-
      ^(?P<code>\S+) (?P<name>.*?) (?P<section>\S+)$

  # As a fallback if there just isn't any parsable data
  - key: name
    regex: >-
      ^(?P<name>.*)$
  - key: course_code
    regex: >-
      ^(?P<name>.*)$

  # At Belhaven, the year and period of the course is stored in the
  # name value nested inside the term object for the course. So to
  # retrieve nested data, we have to use "keys" rather than
  # "key". This is the equivalent of course['term']['name']
  
  - keys:
      - term
      - name
    regex: >-
      ^(?P<year>\d+)\s+(?P<period>.*)$

  # In previous years, the period came before the year
  - keys:
      - term
      - name
    regex: >-
      ^(?P<period>\D*?)\s+(?P<year>\d+)$

  - keys:
      - term
      - created_at
    regex: >-
      ^(?P<year>\d{4})-.*$
'''

