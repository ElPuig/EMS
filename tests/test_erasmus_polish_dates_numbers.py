from lxml import etree

from odoo.tests.common import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval

# A time that decides something the reader must act on keeps its hour: an interview is an
# appointment, the turn to choose a destination is counted in hours, and an offer can end at any
# time of the day. Everything else in the Erasmus+ screens shows the day alone.
KEEP_TIME = {
    ('ems.erasmus.application', 'interview_date'),
    ('ems.erasmus.interview', 'interview_date'),
    ('ems.erasmus.interview.schedule', 'date_start'),
    ('ems.erasmus.mobility', 'turn_deadline'),
    ('ems.erasmus.offer', 'deadline'),
    ('ems.erasmus.offer.wizard', 'deadline'),
}


@tagged('post_install', '-at_install')
class TestErasmusDatesNumbers(TransactionCase):
    """Issue #778 - dates and numbers in the Erasmus+ screens."""

    def _datetime_nodes(self, node, model):
        """Every datetime <field> under `node`, going down into the embedded lists and forms."""
        for child in node:
            if not isinstance(child.tag, str):
                continue
            field = model._fields.get(child.get('name')) if child.tag == 'field' else None
            if field and field.type == 'datetime':
                yield model._name, field.name, child
            if field and field.relational:
                for sub in child:
                    if isinstance(sub.tag, str):
                        yield from self._datetime_nodes(sub, self.env[field.comodel_name])
            else:
                yield from self._datetime_nodes(child, model)

    def test_datetimes_show_the_day_unless_the_hour_decides(self):
        """Odoo's own show_time option: the stored value is untouched, and an editable input keeps
        its hour (a typed date with no time would close a deadline at midnight)."""
        views = self.env['ir.ui.view'].search([('model', '=like', 'ems.erasmus%'), ('type', '!=', 'qweb')])
        checked = 0
        for view in views:
            for model, name, node in self._datetime_nodes(etree.fromstring(view.arch_db), self.env[view.model]):
                options = safe_eval(node.get('options') or '{}')
                where = f"{view.name}: {model}.{name}"
                if (model, name) in KEEP_TIME:
                    self.assertIs(options.get('show_time', True), True, f"{where} must keep its hour")
                    self.assertIs(options.get('show_seconds'), False, f"{where} shows the seconds")
                else:
                    self.assertIs(options.get('show_time'), False, f"{where} shows the time")
                checked += 1
        self.assertGreater(checked, 50)

    def test_zero_that_means_nothing_is_blank(self):
        """The widget reads the same stored 0: nothing about these values changes."""
        for model, names in (('ems.erasmus.diffusion', ['recipient_count']),
                             ('ems.erasmus.quality.history', ['staff_applicants', 'staff_target']),
                             ('ems.erasmus.support.rate', ['band_to', 'min_days'])):
            for view in self.env['ir.ui.view'].search([('model', '=', model), ('type', 'in', ('list', 'form'))]):
                root = etree.fromstring(view.arch_db)
                for name in names:
                    for node in root.iter('field'):
                        if node.get('name') == name:
                            self.assertEqual(node.get('widget'), 'ems_blank_zero', f"{view.name}: {name}")
