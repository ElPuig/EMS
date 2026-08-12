from odoo.tests.common import TransactionCase


class TestMinute(TransactionCase):
    """models/documentation/minute.py — EmsMinute. An early-stage feature (see
    the model's own extensive TODO block — future minute types, an
    approval/signature workflow) with real views/menu/security already wired
    up today, just for the "who attended, what was the topic" basics. Zero
    test coverage existed before this pass."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.space = cls.env['ems.space'].create({
            'code': 'TMIN-A', 'name': 'Test Space (Minute)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.department = cls.env['hr.department'].create({'name': 'Test Department (Minute)'})
        cls.workgroup = cls.env['ems.workgroup'].create({'name': 'Test Workgroup (Minute)'})
        cls.assistant = cls.env['res.partner'].create({'name': 'Test Assistant (Minute)'})

    def _minute(self, **vals):
        base = {
            'space_id': self.space.id,
            'assistant_ids': [(6, 0, [self.assistant.id])],
            'abstract': 'Test topic',
        }
        base.update(vals)
        return self.env['ems.minute'].create(base)

    def test_create_requires_abstract(self):
        with self.assertRaises(Exception):
            self.env['ems.minute'].create({
                'space_id': self.space.id,
                'assistant_ids': [(6, 0, [self.assistant.id])],
            })

    def test_assistant_ids_required_is_ui_only_not_orm_enforced(self):
        """assistant_ids is required=True, but Odoo never enforces `required`
        for a One2many/Many2many field at the ORM/create() level — only the
        view blocks saving with none selected. A direct create() with no
        assistants succeeds. Documented here since it's easy to assume
        `required=True` behaves the same for every field type."""
        minute = self.env['ems.minute'].create({
            'space_id': self.space.id,
            'abstract': 'Test topic',
        })
        self.assertFalse(minute.assistant_ids)

    def test_date_default_is_a_callable_not_a_frozen_value(self):
        """Regression test: date's default used to be datetime.today() — called
        immediately at class-definition time, baking in a single fixed
        timestamp shared by every future record, rather than the actual
        creation time. Fixed to fields.Datetime.now (the callable itself, the
        established idiom elsewhere in this codebase, e.g.
        attendance_session.py's own `date` field)."""
        field = self.env['ems.minute']._fields['date']
        self.assertTrue(callable(field.default))

    def test_display_name_department_meeting(self):
        minute = self._minute(type='department', department_id=self.department.id)
        self.assertIn(self.department.name, minute.display_name)

    def test_display_name_workgroup_meeting(self):
        """Regression test: _compute_display_name compared the Python builtin
        `type` (always falsy against the string 'workgroup') instead of
        `minute.type`/`rec.type` — so a workgroup meeting's display_name always
        showed department_id.name (typically blank for a workgroup meeting)
        instead of workgroup_id.name. Fixed in this DTON pass."""
        minute = self._minute(type='workgroup', workgroup_id=self.workgroup.id)
        self.assertIn(self.workgroup.name, minute.display_name)
        self.assertNotIn('False', minute.display_name)

    def test_members_department_meeting(self):
        minute = self._minute(type='department', department_id=self.department.id)
        self.assertEqual(minute.members, "Department: %s" % self.department.name)

    def test_members_workgroup_meeting(self):
        minute = self._minute(type='workgroup', workgroup_id=self.workgroup.id)
        self.assertEqual(minute.members, "Workgroup: %s" % self.workgroup.name)

    def test_members_recomputes_when_workgroup_changes(self):
        """Regression test: _compute_members only depended on 'type', not on
        workgroup_id/department_id themselves — changing the group without
        changing type left 'members' stale. Fixed by adding both to
        @api.depends."""
        other_workgroup = self.env['ems.workgroup'].create({'name': 'Other Workgroup (Minute)'})
        minute = self._minute(type='workgroup', workgroup_id=self.workgroup.id)
        self.assertEqual(minute.members, "Workgroup: %s" % self.workgroup.name)
        minute.workgroup_id = other_workgroup
        self.assertEqual(minute.members, "Workgroup: %s" % other_workgroup.name)
