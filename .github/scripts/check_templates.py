"""Parse every Jinja template in the plugin to catch syntax errors.

Only syntax is checked: templates are parsed, not rendered, so `extends`/`include` targets
(including Indico's `~`-prefixed originals) and template variables are not resolved.
"""

import sys
from pathlib import Path

from jinja2 import Environment, TemplateSyntaxError


# Extensions Indico enables, so `{% trans %}`, `{% do %}`, `{% break %}` etc. parse
env = Environment(extensions=['jinja2.ext.i18n', 'jinja2.ext.do', 'jinja2.ext.loopcontrols'])

failed = False
for path in sorted(Path('indico_zoom_timetable').rglob('*.html')):
    try:
        env.parse(path.read_text(), filename=str(path))
    except TemplateSyntaxError as exc:
        # GitHub Actions annotation format, so errors show inline on the PR diff
        print(f'::error file={path},line={exc.lineno}::{exc.message}')
        failed = True
    else:
        print(f'ok    {path}')

sys.exit(1 if failed else 0)
