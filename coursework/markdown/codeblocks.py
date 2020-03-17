import re
import logging
from typing import Union, Sequence

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from pygments import highlight
from pygments import lexers
from pygments import formatters

import toolz.curried as _
import larc.common as __
from larc import yaml

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

lang_regexes = _.pipe(
    [
        re.compile(
            r'''(?:(?:^::+)|(?P<shebang>^[#]!)) # Shebang or 2 or more colons
            (?P<path>(?:/\w+)*[/ ])?            # Zero or 1 path
            (?P<lang>[\w#.+-]*)                 # The language
            ''', re.VERBOSE
        ),
        r'''\s+hl_lines=(?P<quot>"|')(?P<hl_lines>.*?)(?P=quot)''',
        r'''\s+linenums=(?P<quot>"|')(?P<linenums>.*?)(?P=quot)''',
    ],
    _.map(re.compile),
    tuple,
)

get_lang = _.compose(
    _.merge,
    _.map(lambda m: m.groupdict()),
    _.filter(None),
    lambda first_line: [r.search(first_line) for r in lang_regexes],
)

range_re = re.compile(r'(?P<start>\d+)\.\.(?P<stop>\d+)')
def parse_range(r_value: str):
    match = range_re.search(r_value)
    if match:
        start, stop = _.pipe(
            [match.group('start'), match.group('stop')],
            _.map(int),
        )
        return range(start, stop + 1)

def int_or_range(value: Union[int, str]):
    if __.is_int(value):
        return [value]
    if __.is_str(value):
        return parse_range(value)

def parse_hl_lines(options: dict):
    return _.pipe(
        options.get('hl_lines') or [],
        _.mapcat(int_or_range),
        _.filter(None),
        tuple,
        _.assoc(options, 'hl_lines'),
    )

'''
```python3 {lines: [1, 2, 3, 5..6]}

def myfunction(a, b):
    pass

```
'''

block_re = re.compile(
    r'''
(?P<fence>^(?:`{3,}))[ ]*         # Opening ```
((?P<lang>[\w#.+-]*))?        # Optional lang
([ ]*(?P<options>.*?)\n)?
(?P<code>.*?)(?<=\n)
(?P=fence)[ ]*$
''',
    re.MULTILINE | re.DOTALL | re.VERBOSE
)

def escape(txt):
    """ basic html escaping """
    return (
        txt
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )

def code_wrap(lang: str, code: str, **_):
    lang_class = f' class="{lang}"' if lang else ""
    return f'<pre><code{lang_class}>{code}</code></pre>'

def code_highlight(lang: str, code: str, **pygments_kw):
    pass

def get_lexer(guess: bool, lang: str, code: str):
    try:
        lexer = lexers.get_lexer_by_name(lang)
    except ValueError:
        try:
            if guess:
                lexer = lexers.guess_lexer(code)
            else:
                lexer = lexers.get_lexer_by_name('text')
        except ValueError:
            lexer = lexers.get_lexer_by_name('text')
    return lexer

def parse_guess(guess_lang: bool, options: dict):
    guess_keys = {'no_guess', 'guess'}
    
    if 'no_guess' in options:
        return False, _.dissoc(options, *guess_keys)

    if 'guess' in options:
        return options.get('guess'), _.dissoc(options, *guess_keys)

    return guess_lang, _.dissoc(options, *guess_keys)

def _get_code_blocks(text, *, guess_lang: bool = True, **pygments_kw):
    # text = "\n".join(lines)
    for match in block_re.finditer(text):
        start, end = match.start(), match.end()
        mdict = match.groupdict()
        lang = mdict['lang'] or ''
        code = mdict['code'] or ''
        options = _.pipe(
            mdict.get('options') or '{}',
            yaml.load
        )

        guess, options = parse_guess(guess_lang, options)
        lexer = get_lexer(guess, lang, code)

        options = parse_hl_lines(options)

        kwargs = _.merge(pygments_kw, options)
        formatter = formatters.get_formatter_by_name(
            'html', **kwargs,
        )
        yield start, end, lang, highlight(code, lexer, formatter)

@_.curry
def get_code_blocks(text, **kw):
    return _.pipe(
        _get_code_blocks(text, **kw),
        tuple,
        reversed,
    )

def replace_code_blocks(lines: Sequence[str], **kw):
    text = '\n'.join(lines)
    for start, end, lang, html in get_code_blocks(text, **kw):
        text = text[:start] + html + text[end:]
    return text.split('\n')
        
    
class CodeblockPreprocessor(Preprocessor):
    def run(self, lines):
        """ Match and store Fenced Code Blocks in the HtmlStash. """
        return replace_code_blocks(lines, **self.config)


class CodeblocksExtension(Extension):
    def __init__(self, **kwargs):
        # define default configs
        self.config = {
            'linenos': [
                'table',
                "Use lines numbers. 'table' or 'inline"
            ],
            'guess_lang': [True,
                           "Automatic language detection - Default: True"],
            'css_class': ["codehilite",
                          "Set class name for wrapper <div> - "
                          "Default: codehilite"],
            'style': ['default',
                      'Pygments HTML Formatter Style '
                      '(Colorscheme) - Default: default'],
            'noclasses': [False,
                          'Use inline styles instead of CSS classes - '
                          'Default false'],
        }

        super(CodeblocksExtension, self).__init__(**kwargs)

    def extendMarkdown(self, md):
        """ Add CodeblockPreprocessor to the Markdown instance. """
        md.registerExtension(self)

        preproc = CodeblockPreprocessor(md)
        preproc.config = self.getConfigs()
        md.preprocessors.register(preproc, 'codeblock', 25)


def makeExtension(**kwargs):  # pragma: no cover
    return CodeblocksExtension(**kwargs)
