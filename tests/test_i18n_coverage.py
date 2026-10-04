import ast
import glob
import os
import re

from odoo.tests.common import TransactionCase, tagged

MODULE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LANGUAGES = ('ca_ES', 'es_ES')
# Folders whose _() strings never reach a user: tests, migrations and helper scripts.
PYTHON_SKIPPED_FOLDERS = ('tests', 'migrations', 'scripts')
# Magic fields every model has; Odoo itself translates their labels.
MAGIC_FIELDS = {'id', 'display_name', 'create_uid', 'create_date', 'write_uid', 'write_date'}


def _unescape(text):
    return re.sub(r'\\(.)', lambda match: {'n': '\n', 't': '\t'}.get(match.group(1), match.group(1)), text)


def _po_blocks(lang):
    """{msgid: comment lines of its block} for i18n/<lang>.po."""
    with open(os.path.join(MODULE_ROOT, 'i18n', f'{lang}.po'), encoding='utf-8') as handle:
        content = handle.read()
    blocks = {}
    for block in content.split('\n\n'):
        match = re.search(r'^msgid ((?:".*"\n?)+)', block, re.M)
        if match:
            msgid = _unescape(''.join(re.findall(r'"((?:[^"\\]|\\.)*)"', match.group(1))))
            blocks[msgid] = '\n'.join(line for line in block.splitlines() if line.startswith('#'))
    return blocks


def _python_strings():
    """(path, line, text) of every _("literal") in the module's own Python code."""
    for path in sorted(glob.glob(os.path.join(MODULE_ROOT, '**', '*.py'), recursive=True)):
        relative = os.path.relpath(path, MODULE_ROOT)
        if relative.split(os.sep)[0] in PYTHON_SKIPPED_FOLDERS:
            continue
        with open(path, encoding='utf-8') as handle:
            tree = ast.parse(handle.read())
        for node in ast.walk(tree):
            function = getattr(node, 'func', None)
            name = getattr(function, 'id', None) or getattr(function, 'attr', None)
            if (isinstance(node, ast.Call) and name == '_' and node.args
                    and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                yield relative, node.lineno, node.args[0].value


def _javascript_strings():
    """(path, line, text) of every _t("literal") with a single string literal in static/src."""
    pattern = re.compile(r'''_t\(\s*(["'])((?:(?!\1)[^\\\n]|\\.)*)\1\s*[,)]''')
    for path in sorted(glob.glob(os.path.join(MODULE_ROOT, 'static', 'src', '**', '*.js'), recursive=True)):
        with open(path, encoding='utf-8') as handle:
            content = handle.read()
        for match in pattern.finditer(content):
            yield (os.path.relpath(path, MODULE_ROOT), content.count('\n', 0, match.start()) + 1,
                   _unescape(match.group(2)))


@tagged('post_install', '-at_install')
class TestI18nCoverage(TransactionCase):
    """Every user-facing text EMS adds must be translated to Catalan and Spanish (see CLAUDE.md's
    "All literals must be translatable"). Wrapping a string in _() or _t() only makes it
    translatable; without its .po entry it shows in English to everyone (issue #557)."""

    def _assert_strings_translated(self, strings, marker):
        for lang in LANGUAGES:
            blocks = _po_blocks(lang)
            missing = sorted({
                f'{path}:{line}: {text!r}' for path, line, text in strings
                if marker not in blocks.get(text, '')
            })
            with self.subTest(lang=lang):
                self.assertFalse(missing, f"Not translated in i18n/{lang}.po (or its block lacks "
                                          f"'#. {marker}'):\n" + '\n'.join(missing))

    def test_python_messages_are_translated(self):
        # A Python string only loads at runtime if its block carries '#. odoo-python'
        # (odoo/tools/translate.py, PYTHON_TRANSLATION_COMMENT).
        self._assert_strings_translated(list(_python_strings()), 'odoo-python')

    def test_python_message_translates_at_runtime(self):
        # The test above only checks the .po files; this proves Odoo actually loads one of the
        # messages fixed in issue #557 for a Catalan/Spanish user.
        message = 'Guard mode requires teacher access.'
        self.assertEqual(self.env(context={'lang': 'ca_ES'})._(message), 'El mode guàrdia requereix accés de docent.')
        self.assertEqual(self.env(context={'lang': 'es_ES'})._(message), 'El modo guardia requiere acceso de docente.')

    def test_javascript_messages_are_translated(self):
        self._assert_strings_translated(list(_javascript_strings()), 'odoo-javascript')

    def test_ems_field_labels_are_translated(self):
        # Read from the database, which is what users see: a native field EMS only retouches
        # keeps the translation its own module ships, and inherited fields (the chatter's) are
        # not EMS's to translate - only fields EMS itself defines are checked.
        installed = [lang for lang in LANGUAGES if self.env['res.lang']._lang_get(lang)]
        self.assertTrue(installed, "Neither Catalan nor Spanish is installed - nothing was checked.")
        self.env.cr.execute("""
            SELECT f.model, f.name, f.field_description
              FROM ir_model_fields f
              JOIN ir_model_data d ON d.model = 'ir.model.fields' AND d.res_id = f.id AND d.module = 'ems'
        """)
        missing = []
        for model, name, labels in self.env.cr.fetchall():
            field = self.env[model]._fields.get(name) if model in self.env else None
            if not field or field._module != 'ems' or name in MAGIC_FIELDS:
                continue
            missing += [f'{model}.{name} ({lang}): {labels.get("en_US")!r}'
                        for lang in installed if not labels.get(lang)]
        self.assertFalse(missing, "Field labels with no translation:\n" + '\n'.join(sorted(missing)))
