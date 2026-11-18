import importlib.util
import os

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

from .common import create_level_study_group, create_role_employee, create_role_user


class TestScheduleDeclaration(TransactionCase):
    """Issue #723: the Departament's official schedule declaration ("Annexos Dades anuals")."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, _study, cls.group = create_level_study_group(cls, 'TSDE', level={'declaration_code': 'eso'})
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TSDE001', 'acronym': 'TSDE', 'name': 'Test Subject (Schedule Declaration)',
            'study_ids': [(6, 0, _study.ids)],
        })
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Test Teacher (Schedule Declaration)', 'employee_type': 'teacher',
            'identification_id': 'TSDE-NIF-1',
        })
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'Test Calendar (Schedule Declaration)', 'employee_id': cls.teacher.id, 'attendance_ids': [(5, 0, 0)],
        })
        cls.teacher.resource_calendar_id = cls.calendar

    def _student_support_type(self):
        """ATAL is the centre's own type (not EMS data), so it may not exist yet."""
        NonTeaching = self.env['ems.non_teaching_type'].with_context(active_test=False)
        atal = NonTeaching.search([('code', '=', 'ATAL')]) or NonTeaching.create(
            {'code': 'ATAL', 'name': "Atenció a l'alumnat"})
        atal.declaration_code = 'tutoring'
        return atal

    def _apply(self, *blocks):
        """Saves 'blocks' as the teacher's whole schedule (apply_schedule_changes replaces it), one
        after the other from 8:00. A block: a group (a class), a non-teaching type or its xmlid, or a
        (block, dayofweek) pair, or a (block, dayofweek, hours) triple."""
        entries, hour_from = [], 8
        for block in blocks:
            block = block if isinstance(block, tuple) else (block,)
            block, dayofweek, hours = block + ('0', 1)[len(block) - 1:]
            block = self.env.ref(block) if isinstance(block, str) else block
            vals = ({'non_teaching': block.id} if block._name == 'ems.non_teaching_type'
                    else {'subject_id': self.subject.id, 'group_ids': [block.id]})
            entries.append({'dayofweek': dayofweek, 'hour_from': hour_from, 'hour_to': hour_from + hours,
                            'day_period': 'morning', 'name': 'TSDE', **vals})
            hour_from += hours
        self.calendar.apply_schedule_changes(entries)

    def test_class_goes_to_its_level_code(self):
        self._apply((self.group, '0', 2))

        summary = self.calendar.get_schedule_declaration_summary()

        self.assertEqual(summary['lective'], {'eso': 2})
        self.assertEqual(summary['lective_total'], 2)

    def test_group_without_level_takes_its_main_groups_level(self):
        optative = self.env['ems.group'].create({
            'group_type': 'reinforcement', 'name': 'TSDE optative', 'parent_group_ids': [(6, 0, self.group.ids)],
        })
        self._apply(optative)

        self.assertEqual(self.calendar.get_schedule_declaration_summary()['lective'], {'eso': 1})

    def test_level_without_code_goes_to_other(self):
        self.level.declaration_code = False
        self._apply(self.group)

        self.assertEqual(self.calendar.get_schedule_declaration_summary()['lective'], {'other': 1})

    def test_non_teaching_rows_and_columns(self):
        # Guard: fixed. Coordination meeting: fixed on Wednesday only. Management time: lective CD.
        # Break and reduction of working hours: not declared.
        self.env['ems.non_teaching_type']._ems_seed_declaration_codes()
        self._apply('ems.non_teaching_g', ('ems.non_teaching_cm', '2'), ('ems.non_teaching_cm', '1'),
                    'ems.non_teaching_mt', 'ems.non_teaching_br', 'ems.non_teaching_r')

        summary = self.calendar.get_schedule_declaration_summary()

        self.assertEqual(summary['fixed'], {'g': 1, 'rd_rc': 1})
        self.assertEqual(summary['lective'], {'rd_rc': 1, 'cd': 1})
        self.assertEqual((summary['lective_total'], summary['fixed_total']), (2, 2))

    def test_break_guards_are_added_up_before_rounding(self):
        # Developer, 2026-10-29: 25-minute break guards, 1/2/3 -> 1/1/2 h; 20-minute ones (the
        # afternoon), 1/2/3/4 -> 1/1/1/2 h.
        self.env['ems.non_teaching_type']._ems_seed_declaration_codes()
        cases = [(25, 1, 1), (25, 2, 1), (25, 3, 2), (20, 1, 1), (20, 2, 1), (20, 3, 1), (20, 4, 2)]
        for minutes, count, hours in cases:
            with self.subTest(minutes=minutes, count=count):
                self._apply(*[('ems.non_teaching_gb', str(day), minutes / 60) for day in range(count)])

                summary = self.calendar.get_schedule_declaration_summary()

                self.assertEqual(summary['fixed'], {'g': hours})
                self.assertEqual(self.calendar.get_schedule_hours_summary()['fixed']['total'], hours)

    def test_tutoring_goes_to_the_tutored_groups_level(self):
        self.env.ref('ems.non_teaching_tt').declaration_code = 'tutoring'
        self._apply('ems.non_teaching_tt')
        cases = [('eso', 't_eso'), ('bat', 't_bat'), ('pfi', 'pfi'), ('cfgm', 't_fp')]
        for level_code, row in cases:
            with self.subTest(level_code=level_code):
                self.level.declaration_code = level_code
                self.group.tutor_id = self.teacher

                self.assertEqual(self.calendar.get_schedule_declaration_summary()['lective'], {row: 1})

    def test_tutoring_without_tutorship_goes_to_the_level_with_most_classes(self):
        """A teacher who tutors no group (e.g. ATAL hours): the level where they teach the most."""
        self.env.ref('ems.non_teaching_tt').declaration_code = 'tutoring'
        _level, _study, bat_group = create_level_study_group(self, 'TSDB', level={'declaration_code': 'bat'})
        self._apply(self.group, (bat_group, '1', 3), ('ems.non_teaching_tt', '2'))

        self.assertEqual(self.calendar.get_schedule_declaration_summary()['lective'], {'eso': 1, 'bat': 3, 't_bat': 1})

        # No classes at all: T-FP, the default row.
        self._apply('ems.non_teaching_tt')

        self.assertEqual(self.calendar.get_schedule_declaration_summary()['lective'], {'t_fp': 1})

    def test_tutoring_blocks_of_different_levels_split_their_hours(self):
        """Issue #846: a block's own level overrides the teacher rule, so one teacher can have ATAL in
        ESO and in Bachillerato (here BAT has most classes); a block with no level keeps the old rule."""
        self.env.ref('ems.non_teaching_tt').declaration_code = 'tutoring'
        bat_level, _study, bat_group = create_level_study_group(self, 'TSDD', level={'declaration_code': 'bat'})
        self._apply(self.group, (bat_group, '1', 3), ('ems.non_teaching_tt', '2', 2),
                    ('ems.non_teaching_tt', '3', 1), ('ems.non_teaching_tt', '4', 1))
        blocks = self.calendar.attendance_ids.filtered('non_teaching').sorted('dayofweek')
        blocks[0].level_id = self.level
        blocks[1].level_id = bat_level

        self.assertEqual(
            self.calendar.get_schedule_declaration_summary()['lective'],
            {'eso': 1, 'bat': 3, 't_eso': 2, 't_bat': 2})

    def test_tutoring_block_level_without_code_goes_to_the_default_row(self):
        self.env.ref('ems.non_teaching_tt').declaration_code = 'tutoring'
        self.level.declaration_code = False
        self._apply('ems.non_teaching_tt')
        self.calendar.attendance_ids.filtered('non_teaching').level_id = self.level

        self.assertEqual(self.calendar.get_schedule_declaration_summary()['lective'], {'t_fp': 1})

    def test_block_level_is_kept_by_apply_schedule_changes_and_copies(self):
        """The Schedule tab saves the whole week through apply_schedule_changes()."""
        non_teaching = self.env.ref('ems.non_teaching_tt')
        non_teaching.declaration_code = 'tutoring'
        self.calendar.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 8, 'hour_to': 9, 'day_period': 'morning', 'name': 'TSDE',
            'non_teaching': non_teaching.id, 'level_id': self.level.id,
        }])

        block = self.calendar.attendance_ids.filtered('non_teaching')
        self.assertEqual(block.level_id, self.level)
        self.assertEqual(block.copy().level_id, self.level)

    def test_student_support_counts_in_the_row_its_attention_type_says(self):
        """Issue #846: the reported case, 3 h of ESO and 4 of Bachillerato classes plus 8 h of student
        support in ESO: support adds them to ESO's row, and tutoring to T-ESO. No other row appears."""
        atal = self._student_support_type()
        _bat_level, _study, bat_group = create_level_study_group(self, 'TSDS', level={'declaration_code': 'bat'})
        self._apply((self.group, '0', 3), (bat_group, '1', 4), (atal, '2', 8))
        block = self.calendar.attendance_ids.filtered('non_teaching')
        block.level_id = self.level

        self.assertEqual(block.attention_type, 'support')
        self.assertEqual(self.calendar.get_schedule_declaration_summary()['lective'], {'eso': 11, 'bat': 4})

        block.attention_type = 'tutoring'
        self.assertEqual(
            self.calendar.get_schedule_declaration_summary()['lective'], {'eso': 3, 'bat': 4, 't_eso': 8})

    def test_student_support_without_level_uses_the_deduced_level(self):
        atal = self._student_support_type()
        self._apply((self.group, '0', 2), (atal, '1', 1))

        self.assertEqual(self.calendar.get_schedule_declaration_summary()['lective'], {'eso': 3})

    def test_student_support_without_any_level_goes_to_others(self):
        self._apply(self._student_support_type())

        self.assertEqual(self.calendar.get_schedule_declaration_summary()['lective'], {'other': 1})

    def test_student_support_hours_do_not_decide_the_deduced_level(self):
        """Support hours given to ESO don't make ESO the level with most classes."""
        atal = self._student_support_type()
        _bat_level, _study, bat_group = create_level_study_group(self, 'TSDH', level={'declaration_code': 'bat'})
        self._apply((self.group, '0', 1), (bat_group, '1', 2), (atal, '2', 5), (atal, '3', 1))
        blocks = self.calendar.attendance_ids.filtered('non_teaching').sorted('dayofweek')
        blocks[0].level_id = self.level

        self.assertEqual(self.calendar.get_schedule_declaration_summary()['lective'], {'eso': 6, 'bat': 3})

    def test_tutorship_time_always_counts_as_tutoring(self):
        """The attention type only applies to student support: TT keeps its tutoring row."""
        self.env.ref('ems.non_teaching_tt').declaration_code = 'tutoring'
        self._apply('ems.non_teaching_tt')
        block = self.calendar.attendance_ids.filtered('non_teaching')
        block.write({'level_id': self.level.id, 'attention_type': 'support'})

        self.assertFalse(block.non_teaching.is_student_support)
        self.assertEqual(self.calendar.get_schedule_declaration_summary()['lective'], {'t_eso': 1})

    def test_student_support_recoded_by_the_centre_follows_its_code(self):
        """ATAL given another declaration code stops being a support/tutoring choice."""
        atal = self._student_support_type()
        atal.declaration_code = 'cc'
        self._apply(atal)

        self.assertFalse(atal.is_student_support)
        self.assertEqual(self.calendar.get_schedule_declaration_summary()['lective'], {'cc': 1})

    def test_attention_type_is_kept_by_apply_schedule_changes_and_copies(self):
        atal = self._student_support_type()
        self.calendar.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 8, 'hour_to': 9, 'day_period': 'morning', 'name': 'TSDE',
            'non_teaching': atal.id, 'attention_type': 'tutoring',
        }])

        block = self.calendar.attendance_ids.filtered('non_teaching')
        self.assertEqual(block.attention_type, 'tutoring')
        self.assertEqual(block.copy().attention_type, 'tutoring')

    def test_tutorship_subject_goes_to_its_groups_tutoring_row(self):
        self.subject.is_tutorship = True
        self._apply(self.group)

        self.assertEqual(self.calendar.get_schedule_declaration_summary()['lective'], {'t_eso': 1})

    def test_reductions_are_only_their_hours_and_count_in_the_total(self):
        reductions = self.env['ems.teaching_reduction_type'].create([
            {'code': 'TSDE-R1', 'name': 'Test reduction 1', 'reduction_hours': 2},
            {'code': 'TSDE-R2', 'name': 'Test reduction 2', 'reduction_hours': 1},
        ])
        self.teacher.teaching_reduction_ids = reductions
        self._apply(self.group)

        summary = self.calendar.get_schedule_declaration_summary()

        self.assertEqual(summary['reduction'], 3)
        self.assertEqual(summary['lective'], {'eso': 1})
        self.assertEqual(summary['lective_total'], 4)

    def test_seed_sets_the_official_codes(self):
        # ATAL is the centre's own type (not EMS data): seeded by its code when it exists.
        NonTeaching = self.env['ems.non_teaching_type'].with_context(active_test=False)
        atal = NonTeaching.search([('code', '=', 'ATAL')]) or NonTeaching.create({'code': 'ATAL', 'name': "Atenció a l'alumnat"})
        self.env['ems.non_teaching_type']._ems_seed_declaration_codes()

        self.assertEqual(self.env.ref('ems.non_teaching_wic').declaration_code, 'cc')
        self.assertEqual(self.env.ref('ems.non_teaching_tt').declaration_code, 'tutoring')
        self.assertEqual(atal.declaration_code, 'tutoring')
        self.assertFalse(self.env.ref('ems.non_teaching_br').declaration_code)
        self.assertFalse(self.env.ref('ems.non_teaching_r').declaration_code)
        self.assertTrue(self.env.ref('ems.non_teaching_gb').adds_up_periods)
        self.assertFalse(self.env.ref('ems.non_teaching_g').adds_up_periods)

    def test_report_is_in_catalan_with_the_summary(self):
        self._apply((self.group, '0', 2))

        content, _content_type = self.env['ir.actions.report'].with_context(lang='en_US')._render_qweb_pdf(
            'ems.report_schedule_declaration', self.teacher.ids)

        self.assertIn('QUADRE RESUM D’HORES'.encode(), content)
        self.assertIn(b'Dilluns', content)
        self.assertIn(b'TSDE-NIF-1', content)
        # The Departament's logo, as on the official form.
        self.assertIn(b'/ems/static/src/img/departament_educacio_fp.png', content)

    def test_head_of_studies_prints_it_with_the_nif(self):
        user = create_role_user(self, 'head_of_studies', 'tsde_hos')
        self._apply(self.group)

        action = self.teacher.with_user(user).action_print_schedule_declaration()
        content, _content_type = self.env['ir.actions.report'].with_user(user)._render_qweb_pdf(
            action['report_name'], self.teacher.ids)

        # From the form's Actions dropdown: this teacher only.
        self.assertEqual(action['report_name'], 'ems.report_schedule_declaration')
        self.assertEqual(action['context']['active_ids'], self.teacher.ids)
        self.assertIn(b'TSDE-NIF-1', content)

    def test_administrator_prints_it_with_the_nif(self):
        # The administrator is above Direction, though outside the hr hierarchy (CLAUDE.md).
        user = create_role_user(self, 'settings_admin', 'tsde_admin')
        self._apply(self.group)

        content, _content_type = self.env['ir.actions.report'].with_user(user)._render_qweb_pdf(
            'ems.report_schedule_declaration', self.teacher.ids)

        self.assertIn(b'TSDE-NIF-1', content)

    def test_teacher_cannot_render_it_from_the_report_url(self):
        # /report/pdf/... renders without checking the report's groups.
        user = create_role_user(self, 'teacher', 'tsde_teacher_url')

        with self.assertRaises(AccessError):
            self.env['ir.actions.report'].with_user(user)._render_qweb_pdf(
                'ems.report_schedule_declaration', self.teacher.ids)

    def test_teacher_cannot_print_it(self):
        user = create_role_user(self, 'teacher', 'tsde_teacher')
        create_role_employee(self, user)

        with self.assertRaises(AccessError):
            self.teacher.with_user(user).action_print_schedule_declaration()
        # The list's Print menu: what _get_bindings offers this user.
        printable = self.env['ir.actions.actions'].with_user(user).get_bindings('hr.employee').get('report', [])
        self.assertNotIn(self.env.ref('ems.action_report_schedule_declaration').id, [report['id'] for report in printable])

    def test_break_periods_are_flagged_for_the_grid(self):
        self._apply(self.group, 'ems.non_teaching_br')

        lines = self.calendar.get_schedule_report_lines()

        self.assertEqual([line['is_break'] for line in lines], [False, True])

    def test_same_period_with_float_noise_is_one_grid_row(self):
        # 10:00-10:25 stored as ...666 on one day and ...668 on another (issue #723).
        self.calendar.apply_schedule_changes([
            {'dayofweek': '0', 'hour_from': 10, 'hour_to': 10.416666666666666, 'day_period': 'morning',
             'non_teaching': self.env.ref('ems.non_teaching_gb').id, 'name': 'GB'},
            {'dayofweek': '1', 'hour_from': 10, 'hour_to': 10.416666666666668, 'day_period': 'morning',
             'non_teaching': self.env.ref('ems.non_teaching_br').id, 'name': 'BR'},
        ])

        lines = self.calendar.get_schedule_report_lines()

        self.assertEqual([line['time_label'] for line in lines], ['10:00-10:25'])
        self.assertTrue(lines[0]['cells'][0]['entry'] and lines[0]['cells'][1]['entry'])

    def test_class_label_is_composed_in_one_format(self):
        self._apply(self.group)
        block = self.calendar.attendance_ids.filtered('subject_id')
        block.name = 'TSDE: an old free-form name'

        self.assertEqual(block.get_report_label(), f"{self.subject.display_name} ({self.group.name})")

    def test_migration_rewrites_old_block_names(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'migrations', '18.0.0.43.0', 'post-migrate.py')
        spec = importlib.util.spec_from_file_location('ems_migration_18_0_0_43_0', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        self._apply(self.group)
        block = self.calendar.attendance_ids.filtered('subject_id')
        block.name = f"{self.subject.display_name}: {self.group.name}"
        block.flush_recordset()

        migration._unify_class_block_names(self.env)

        self.assertEqual(block.name, f"{self.subject.display_name} ({self.group.name})")

    def test_grid_has_no_rooms(self):
        space = self.env['ems.space'].create({
            'code': 'TSDE-ROOM', 'name': 'Test Room (Schedule Declaration)',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        self.group.space_id = space
        self._apply(self.group)

        declaration, _content_type = self.env['ir.actions.report']._render_qweb_pdf('ems.report_schedule_declaration', self.teacher.ids)
        working_schedule, _content_type = self.env['ir.actions.report']._render_qweb_pdf('ems.report_working_schedule', self.teacher.ids)

        self.assertNotIn(b'Test Room (Schedule Declaration)', declaration)
        self.assertIn(b'Test Room (Schedule Declaration)', working_schedule)
