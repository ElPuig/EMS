import base64
from datetime import date

from odoo.tests.common import HttpCase, TransactionCase, tagged

from .common import create_level_study

FAKE_PDF = b'%PDF-1.4 fake public schedule'


def _create_fixtures(cls, prefix):
    cls.level, cls.study = create_level_study(cls, prefix, level={'name': f'Test Level ({prefix})'}, study={
        'code': f'{prefix}001', 'name': f'Test Study ({prefix})', 'date': date.today(),
    })
    cls.subject = cls.env['ems.subject'].create({
        'code': f'{prefix}001', 'acronym': prefix, 'name': f'Test Subject ({prefix})',
        'study_ids': [(6, 0, [cls.study.id])],
    })
    cls.space = cls.env['ems.space'].create({
        'code': f'{prefix}-A', 'name': f'Test Space ({prefix})',
        'space_type_id': cls.env.ref('ems.space_type_classroom').id,
        'work_location_id': cls.env.ref('ems.work_location_main').id,
    })
    cls.group = cls.env['ems.group'].create({
        'course': 1, 'acronym': prefix, 'level_id': cls.level.id, 'study_id': cls.study.id,
        'space_id': cls.space.id, 'shift': 'morning',
    })
    cls.teacher = cls.env['hr.employee'].create({'name': f'Test Teacher ({prefix})', 'employee_type': 'teacher'})
    cls.calendar = cls.env['resource.calendar'].create({'name': f'Test Calendar ({prefix})'})
    cls.teacher.resource_calendar_id = cls.calendar


class TestGroupPublicSchedule(TransactionCase):
    """Issue #453 - public, persistent PDF link per group, re-rendered only when the printed
    schedule changes (see docs/en/developers/contacts/group_schedule.md's "Public schedule link")."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _create_fixtures(cls, 'TGPS')
        cls.cron = cls.env.ref('ems.ir_cron_group_public_schedule')

    def _add_block(self, group=None, **extra):
        vals = {
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [(group or self.group).id], 'name': 'TGPS: TGPS',
        }
        vals.update(extra)
        self.calendar.apply_schedule_changes([vals])
        return self.calendar.attendance_ids.filtered(lambda attendance: attendance.subject_id == self.subject)[-1:]

    def _clean(self, groups=None):
        (groups or self.group).write({'public_schedule_dirty': False})

    def _triggers(self):
        return self.env['ir.cron.trigger'].search([('cron_id', '=', self.cron.id)])

    def _clear_triggers(self):
        # A whole test class shares one transaction (hence one cr.now()), so the trigger that
        # setUpClass's own group create() already queued would otherwise dedupe every test's marks.
        self._triggers().unlink()

    # --- Link ---

    def test_slug_and_url_derived_from_name(self):
        slug = self.env['ir.http']._slugify(self.group.name)
        self.assertEqual(self.group.public_schedule_slug, slug)
        self.assertTrue(self.group.public_schedule_url.endswith(f'/ems/schedule/{slug}.pdf'))

    def test_slug_strips_accents_and_spaces(self):
        group = self.env['ems.group'].create({'group_type': 'reinforcement', 'name': 'Reforç Prova TGPS'})
        self.assertEqual(group.public_schedule_slug, 'reforc-prova-tgps')

    def test_slug_follows_rename(self):
        group = self.env['ems.group'].create({'group_type': 'reinforcement', 'name': 'TGPS Old'})
        group.name = 'TGPS New'
        self.assertEqual(group.public_schedule_slug, 'tgps-new')

    # --- Generation ---

    def test_new_group_is_pending_generation(self):
        self.assertTrue(self.group.public_schedule_dirty)
        self.assertFalse(self.group.public_schedule_pdf)

    def test_generate_renders_catalan_pdf_and_clears_flag(self):
        self._add_block()
        self.group._generate_public_schedule()
        self.assertFalse(self.group.public_schedule_dirty)
        content = base64.b64decode(self.group.public_schedule_pdf)
        self.assertIn(self.group.name.encode(), content)
        self.assertIn('Dilluns'.encode(), content)

    def test_cron_only_renders_dirty_groups(self):
        other = self.env['ems.group'].create({'group_type': 'reinforcement', 'name': 'TGPS Clean'})
        self.env['ems.group'].search([('id', '!=', self.group.id)]).write({'public_schedule_dirty': False})
        self.env['ems.group']._cron_generate_public_schedules()
        self.assertTrue(self.group.public_schedule_pdf)
        self.assertFalse(self.group.public_schedule_dirty)
        self.assertFalse(other.public_schedule_pdf)

    def test_cron_reports_remaining_groups_to_the_cron_framework(self):
        other = self.env['ems.group'].create({'group_type': 'reinforcement', 'name': 'TGPS Second'})
        self.env['ems.group'].search([('id', 'not in', (self.group | other).ids)]).write({'public_schedule_dirty': False})
        progress = self.env['ir.cron.progress'].create({'cron_id': self.cron.id})
        self.env['ems.group'].with_context(ir_cron_progress_id=progress.id)._cron_generate_public_schedules(batch_size=1)
        self.assertEqual((progress.done, progress.remaining), (1, 1))
        self.assertEqual(len((self.group | other).filtered('public_schedule_dirty')), 1)

    def test_several_changes_in_one_transaction_trigger_cron_once(self):
        tutor = self.env['hr.employee'].create({'name': 'Test Tutor Once (TGPS)', 'employee_type': 'teacher'})
        self._clear_triggers()
        block = self._add_block()
        block.topic = 'Català'
        # ems.group.write() runs inside its own savepoint, which flushes the cursor's precommit
        # callbacks - the dedupe must survive that.
        self.group.tutor_id = tutor
        self.assertEqual(len(self._triggers()), 1)

    def test_trigger_undone_by_rolled_back_savepoint_is_created_again(self):
        self._clear_triggers()
        with self.assertRaises(ZeroDivisionError), self.env.cr.savepoint():
            self.group._mark_public_schedule_dirty()
            self.assertEqual(len(self._triggers()), 1)
            1 / 0  # pylint: disable=pointless-statement
        self.assertFalse(self._triggers())
        self.group._mark_public_schedule_dirty()
        self.assertEqual(len(self._triggers()), 1)

    def test_mark_does_not_render_inline_but_triggers_cron(self):
        self.group._generate_public_schedule()
        rendered = self.group.public_schedule_pdf
        self._clear_triggers()
        self._add_block()
        self.assertTrue(self.group.public_schedule_dirty)
        self.assertEqual(self.group.public_schedule_pdf, rendered)
        self.assertEqual(len(self._triggers()), 1)

    # --- Triggers ---

    def test_block_create_marks_group(self):
        self._clean()
        self._add_block()
        self.assertTrue(self.group.public_schedule_dirty)

    def test_block_topic_change_marks_group(self):
        block = self._add_block()
        self._clean()
        block.topic = 'Castellà'
        self.assertTrue(self.group.public_schedule_dirty)

    def test_block_moved_to_another_group_marks_both(self):
        other = self.env['ems.group'].create({'group_type': 'reinforcement', 'name': 'TGPS Target', 'shift': 'morning'})
        block = self._add_block()
        self._clean(self.group | other)
        block.group_ids = [(6, 0, [other.id])]
        self.assertTrue(self.group.public_schedule_dirty)
        self.assertTrue(other.public_schedule_dirty)

    def test_block_unlink_marks_group(self):
        block = self._add_block()
        self._clean()
        block.unlink()
        self.assertTrue(self.group.public_schedule_dirty)

    def test_teacher_calendar_archive_marks_group(self):
        self._add_block()
        self._clean()
        self.calendar.action_archive()
        self.assertTrue(self.group.public_schedule_dirty)

    def test_framework_break_change_marks_level_groups(self):
        framework = self.env['resource.calendar'].create({
            'name': 'Test Framework (TGPS)', 'is_framework': True, 'level_id': self.level.id,
            'full_time_required_hours': 24,
        })
        self._clean()
        self.env['resource.calendar.attendance'].create({
            'calendar_id': framework.id, 'name': 'BR: Break', 'dayofweek': '0', 'hour_from': 11,
            'hour_to': 11.5, 'day_period': 'morning', 'non_teaching': self.env.ref('ems.non_teaching_br').id,
        })
        self.assertTrue(self.group.public_schedule_dirty)

    def test_group_header_change_marks_group(self):
        tutor = self.env['hr.employee'].create({'name': 'Test Tutor (TGPS)', 'employee_type': 'teacher'})
        self._clean()
        self.group.tutor_id = tutor
        self.assertTrue(self.group.public_schedule_dirty)

    def test_unprinted_group_field_does_not_mark_group(self):
        self._clean()
        self.group.notes = 'Not printed on the schedule'
        self.assertFalse(self.group.public_schedule_dirty)

    def test_group_reactivation_marks_group(self):
        group = self.env['ems.group'].create({'group_type': 'reinforcement', 'name': 'TGPS Archived'})
        group.active = False
        self._clean(group)
        group.active = True
        self.assertTrue(group.public_schedule_dirty)

    def test_subject_rename_marks_group(self):
        self._add_block()
        self._clean()
        self.subject.name = 'Test Subject Renamed (TGPS)'
        self.assertTrue(self.group.public_schedule_dirty)

    def test_space_rename_marks_group(self):
        self._clean()
        self.space.name = 'Test Space Renamed (TGPS)'
        self.assertTrue(self.group.public_schedule_dirty)

    def test_teacher_rename_marks_group(self):
        self._add_block()
        self._clean()
        self.teacher.name = 'Test Teacher Renamed (TGPS)'
        self.assertTrue(self.group.public_schedule_dirty)

    def test_current_course_change_marks_every_group(self):
        company = self.env.company
        self._clean()
        company.current_course_id = company.current_course_id
        self.assertTrue(self.group.public_schedule_dirty)


@tagged('post_install', '-at_install')
class TestGroupPublicScheduleRoute(HttpCase):
    """The public route only ever streams the stored PDF - no login, never renders."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _create_fixtures(cls, 'TGPR')
        cls.group.write({'public_schedule_pdf': base64.b64encode(FAKE_PDF), 'public_schedule_dirty': False})

    def _url(self, group):
        return f'/ems/schedule/{group.public_schedule_slug}.pdf'

    def test_serves_stored_pdf_without_login(self):
        response = self.url_open(self._url(self.group))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers['Content-Type'].startswith('application/pdf'))
        self.assertEqual(response.content, FAKE_PDF)

    def test_serves_previous_pdf_while_regeneration_is_pending(self):
        self.group.public_schedule_dirty = True
        response = self.url_open(self._url(self.group))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, FAKE_PDF)

    def test_group_without_pdf_is_not_found_and_not_rendered(self):
        group = self.env['ems.group'].create({'group_type': 'reinforcement', 'name': 'TGPR Not Yet'})
        response = self.url_open(self._url(group))
        self.assertEqual(response.status_code, 404)
        self.assertFalse(group.public_schedule_pdf)

    def test_archived_group_is_not_found(self):
        group = self.env['ems.group'].create({'group_type': 'reinforcement', 'name': 'TGPR Archived'})
        group.write({'public_schedule_pdf': base64.b64encode(FAKE_PDF), 'public_schedule_dirty': False})
        group.active = False
        self.assertEqual(self.url_open(self._url(group)).status_code, 404)

    def test_unknown_slug_is_not_found(self):
        self.assertEqual(self.url_open('/ems/schedule/tgpr-does-not-exist.pdf').status_code, 404)
