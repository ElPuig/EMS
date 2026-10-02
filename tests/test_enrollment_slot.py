from datetime import date

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase

from odoo.addons.ems.models.shared.attendance_mixin import EMS_BYPASS_TEMPLATE_LOCK_KEY

from .common import create_level_study, create_role_employee, create_role_user, next_student_id


def create_enrollment_slot_fixture(cls):
    """Shared by the backend tests and the tour: subject TSLT taught to group C (Monday and
    Tuesday), D (Wednesday and Thursday), E (another study of the same level, Friday) and F
    (another level, Friday), with two students enrolled through C."""
    cls.level, cls.study = create_level_study(cls, 'TSLT')
    # A second study of the SAME level - recovering a subject with another study's group.
    cls.other_study = cls.env['ems.study'].create({
        'code': 'TSLT-02', 'acronym': 'TSLTB', 'name': 'Test TSLT Study B',
        'date': '2026-01-01', 'deprecated': False, 'level_id': cls.level.id,
    })
    cls.other_level, cls.far_study = create_level_study(cls, 'TSLX')
    cls.subject = cls.env['ems.subject'].create({
        'code': 'TSLT001', 'acronym': 'TSLT', 'name': 'TSLT Split Subject',
        'study_ids': [(6, 0, [cls.study.id, cls.other_study.id, cls.far_study.id])],
    })
    Group = cls.env['ems.group']
    cls.group_c = Group.create({'course': 1, 'acronym': 'C', 'level_id': cls.level.id, 'study_id': cls.study.id})
    cls.group_d = Group.create({'course': 1, 'acronym': 'D', 'level_id': cls.level.id, 'study_id': cls.study.id})
    cls.group_other_study = Group.create({'course': 1, 'acronym': 'E', 'level_id': cls.level.id, 'study_id': cls.other_study.id})
    cls.group_other_level = Group.create({'course': 1, 'acronym': 'F', 'level_id': cls.other_level.id, 'study_id': cls.far_study.id})
    space_type = cls.env.ref('ems.space_type_classroom')
    location = cls.env.ref('ems.work_location_main')
    cls.space, cls.space_b = cls.env['ems.space'].create([
        {'code': f'TSLT-{code}', 'name': f'Test Space {code} (Enrollment Slot)',
         'space_type_id': space_type.id, 'work_location_id': location.id}
        for code in ('A', 'B')
    ])
    # One teacher per group, all on different weekdays: no overlap constraint gets in the way.
    cls.line_c_mon, cls.line_c_tue = _create_template(cls, cls.group_c, cls.study, [('0', 9.0, 10.0), ('1', 9.0, 10.0)])
    cls.line_d_wed, cls.line_d_thu = _create_template(cls, cls.group_d, cls.study, [('2', 9.0, 10.0), ('3', 9.0, 10.0)])
    (cls.line_e_fri,) = _create_template(cls, cls.group_other_study, cls.other_study, [('4', 9.0, 10.0)])
    (cls.line_f_fri,) = _create_template(cls, cls.group_other_level, cls.far_study, [('4', 11.0, 12.0)])

    # '0000 ' sorts first in the students list (the tour opens it from there).
    cls.student, cls.classmate = cls.env['res.partner'].create([
        {'name': name, 'contact_type': 'student', 'student_id': next_student_id(), 'main_group_id': cls.group_c.id}
        for name in ('0000 TSLT Split Student', '0000 TSLT Classmate')
    ])
    Enrollment = cls.env['ems.enrollment']
    cls.enrollment = Enrollment.create({'student_id': cls.student.id, 'group_id': cls.group_c.id, 'subject_id': cls.subject.id})
    cls.classmate_enrollment = Enrollment.create({'student_id': cls.classmate.id, 'group_id': cls.group_c.id, 'subject_id': cls.subject.id})


def _create_template(cls, group, study, slots):
    teacher = cls.env['hr.employee'].create({'name': f'Test Teacher {group.acronym} (Enrollment Slot)', 'employee_type': 'teacher'})
    template = cls.env['ems.attendance_template'].create({
        'teacher_ids': [(6, 0, teacher.ids)],
        'study_ids': [(6, 0, study.ids)],
        'subject_id': cls.subject.id,
        'group_ids': [(6, 0, group.ids)],
        'start_date': date(2026, 1, 1),
        'end_date': date(2026, 12, 31),
    })
    return tuple(cls.env['ems.attendance_schedule'].create({
        'attendance_template_id': template.id, 'weekday': weekday,
        'start_time': start, 'end_time': end, 'space_id': cls.space.id,
    }) for weekday, start, end in slots)


class EnrollmentSlotCase(TransactionCase):
    """Issue #534: a student attending one subject split across several groups (custom schedule).
    See docs/en/developers/contacts/enrollment_slot.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_enrollment_slot_fixture(cls)

    def _slot(self, line, group, enrollment=None):
        return self.env['ems.enrollment.slot'].create({
            'enrollment_id': (enrollment or self.enrollment).id,
            'group_id': group.id,
            'attendance_schedule_id': line.id,
        })

    def _split_c_mon_d_wed(self):
        """2 h + 2 h in the issue, 1 h + 1 h here: Monday with C, Wednesday with D."""
        self.enrollment.action_customize_slots()
        self.enrollment.slot_ids.filtered(lambda slot: slot.weekday == '1').unlink()
        self._slot(self.line_d_wed, self.group_d)

    def _lines_of(self, student):
        return self.env['ems.attendance_schedule'].search([('student_ids', 'in', student.id)])


class TestEnrollmentSlot(EnrollmentSlotCase):

    # -- following the group (unchanged behavior) --

    def test_enrollment_without_slots_follows_its_group(self):
        self.assertFalse(self.enrollment.is_custom_schedule)
        self.assertEqual(self._lines_of(self.student), self.line_c_mon | self.line_c_tue)

    def test_customize_stores_current_slots_and_keeps_rosters(self):
        self.enrollment.action_customize_slots()

        self.assertTrue(self.enrollment.is_custom_schedule)
        self.assertEqual(len(self.enrollment.slot_ids), 2)
        self.assertEqual(set(self.enrollment.slot_ids.mapped('state')), {'ok'})
        self.assertEqual(self._lines_of(self.student), self.line_c_mon | self.line_c_tue)

    # -- custom schedule --

    def test_split_between_two_groups(self):
        self._split_c_mon_d_wed()

        self.assertEqual(self._lines_of(self.student), self.line_c_mon | self.line_d_wed)
        self.assertEqual(self._lines_of(self.classmate), self.line_c_mon | self.line_c_tue)

    def test_slot_with_a_group_of_another_study_of_the_same_level(self):
        self.enrollment.action_customize_slots()
        self._slot(self.line_e_fri, self.group_other_study)

        self.assertIn(self.line_e_fri, self._lines_of(self.student))

    def test_group_picker_offers_only_groups_teaching_the_subject(self):
        # group_no_class: same level, but no class of the subject at all.
        group_no_class = self.env['ems.group'].create({'course': 1, 'acronym': 'G', 'level_id': self.level.id, 'study_id': self.study.id})
        self.enrollment.action_customize_slots()

        offered = self.enrollment.slot_ids[:1].allowed_group_ids

        self.assertEqual(offered, self.group_c | self.group_d | self.group_other_study)
        self.assertNotIn(group_no_class, offered)
        self.assertNotIn(self.group_other_level, offered)

    def test_session_picker_offers_only_the_chosen_group_sessions(self):
        self.enrollment.action_customize_slots()
        Slot = self.env['ems.enrollment.slot']

        with_group = Slot.new({'enrollment_id': self.enrollment.id, 'group_id': self.group_d.id})
        without_group = Slot.new({'enrollment_id': self.enrollment.id})

        self.assertEqual(with_group.allowed_schedule_ids._origin, self.line_d_wed | self.line_d_thu)
        self.assertEqual(without_group.allowed_schedule_ids._origin,
                         self.line_c_mon | self.line_c_tue | self.line_d_wed | self.line_d_thu | self.line_e_fri)

    def test_picking_a_session_sets_its_group(self):
        """Group C left over from an earlier choice, then a group D session picked: the row must
        follow the session, never end up as a class that doesn't exist."""
        self.enrollment.action_customize_slots()
        draft = self.env['ems.enrollment.slot'].new({
            'enrollment_id': self.enrollment.id, 'group_id': self.group_c.id,
            'attendance_schedule_id': self.line_d_wed.id,
        })
        draft._onchange_attendance_schedule_id()
        self.assertEqual(draft.group_id, self.group_d)

        slot = self.env['ems.enrollment.slot'].create({
            'enrollment_id': self.enrollment.id, 'group_id': self.group_c.id,
            'attendance_schedule_id': self.line_d_thu.id,
        })
        self.assertEqual(slot.group_id, self.group_d)
        self.assertEqual(slot.state, 'ok')

    def test_session_names_follow_the_reader_language(self):
        """The session picker shows ems.attendance_schedule's display_name: its weekday must be in
        the reader's language, and searchable as typed in it, while the stored 'name' (the sort
        key) stays English."""
        Schedule = self.env['ems.attendance_schedule'].with_context(lang='ca_ES')
        line = Schedule.browse(self.line_c_mon.id)

        self.assertIn('Dilluns', line.display_name)
        self.assertIn('Monday', line.name)
        found = Schedule.name_search('Dilluns', [('id', 'in', (self.line_c_mon | self.line_c_tue).ids)])
        self.assertEqual([record_id for record_id, _name in found], [self.line_c_mon.id])

    def test_sessions_are_ordered_by_weekday_number(self):
        """Alphabetically, Friday would come before Monday (and Dijous before Dilluns)."""
        friday = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': self.line_c_mon.attendance_template_id.id,
            'weekday': '4', 'start_time': 9.0, 'end_time': 10.0, 'space_id': self.space_b.id,
        })
        found = self.env['ems.attendance_schedule'].search([
            ('attendance_template_id', '=', self.line_c_mon.attendance_template_id.id),
        ])
        self.assertEqual(found.ids, [self.line_c_mon.id, self.line_c_tue.id, friday.id])

    def test_slot_with_a_group_of_another_level_is_rejected(self):
        self.enrollment.action_customize_slots()
        with self.assertRaises(ValidationError):
            self._slot(self.line_f_fri, self.group_other_level)

    def test_rejection_messages_are_translated(self):
        # The .po entries must actually apply at runtime, not merely exist (CLAUDE.md's i18n rule).
        self.enrollment.action_customize_slots()
        Slot = self.env['ems.enrollment.slot'].with_context(lang='ca_ES')
        with self.assertRaises(ValidationError) as level_error:
            Slot.create({'enrollment_id': self.enrollment.id, 'group_id': self.group_other_level.id,
                         'attendance_schedule_id': self.line_f_fri.id})
        self.assertIn('només s\'hi poden fer servir els grups del mateix nivell', str(level_error.exception))
        with self.assertRaises(ValidationError) as time_error:
            Slot.create({'enrollment_id': self.enrollment.id, 'group_id': self.group_d.id,
                         'weekday': '0', 'start_time': 9.0, 'end_time': 10.0})
        self.assertIn('no té cap classe', str(time_error.exception))

    def test_slot_at_a_time_the_group_has_no_class_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.env['ems.enrollment.slot'].create({
                'enrollment_id': self.enrollment.id, 'group_id': self.group_d.id,
                'weekday': '0', 'start_time': 9.0, 'end_time': 10.0,
            })

    def test_reloading_rosters_keeps_the_custom_schedule(self):
        self._split_c_mon_d_wed()

        (self.line_c_mon | self.line_c_tue | self.line_d_wed | self.line_d_thu).reload_students()

        self.assertEqual(self._lines_of(self.student), self.line_c_mon | self.line_d_wed)
        self.assertIn(self.classmate, self.line_c_tue.student_ids)

    def test_new_class_reaches_students_following_the_group_only(self):
        self._split_c_mon_d_wed()
        new_line = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': self.line_c_mon.attendance_template_id.id,
            'weekday': '0', 'start_time': 10.0, 'end_time': 11.0, 'space_id': self.space.id,
        })
        # The calendar sync fills every new line the same way.
        new_line.fill_students()

        self.assertIn(self.classmate, new_line.student_ids)
        self.assertNotIn(self.student, new_line.student_ids)

    def test_class_moved_to_another_time_breaks_the_slot(self):
        self._split_c_mon_d_wed()
        # A teacher's schedule change: the Wednesday class moves to Wednesday 11:00. The sync
        # pipeline archives the old line and creates (and fills) a new one.
        self.line_d_wed.with_context(**{EMS_BYPASS_TEMPLATE_LOCK_KEY: True}).action_archive()
        moved = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': self.line_d_wed.attendance_template_id.id,
            'weekday': '2', 'start_time': 11.0, 'end_time': 12.0, 'space_id': self.space.id,
        })
        moved.fill_students()

        slot_d = self.enrollment.slot_ids.filtered(lambda slot: slot.group_id == self.group_d)
        self.assertEqual(slot_d.state, 'broken')
        self.assertEqual(self.student.enrollment_slot_broken_count, 1)
        self.assertNotIn(self.student, moved.student_ids)

    def test_room_change_keeps_the_slot(self):
        self._split_c_mon_d_wed()
        self.line_d_wed.with_context(**{EMS_BYPASS_TEMPLATE_LOCK_KEY: True}).space_id = self.space_b

        self.assertEqual(set(self.enrollment.slot_ids.mapped('state')), {'ok'})
        self.assertEqual(self.student.enrollment_slot_broken_count, 0)

    def test_follow_group_again(self):
        self._split_c_mon_d_wed()

        self.enrollment.action_follow_group()

        self.assertFalse(self.enrollment.slot_ids)
        self.assertEqual(self._lines_of(self.student), self.line_c_mon | self.line_c_tue)

    def test_dropping_the_custom_schedule_deletes_every_slot(self):
        self.student.custom_schedule = True
        self._split_c_mon_d_wed()

        self.student.action_drop_custom_schedule()

        self.assertFalse(self.student.custom_schedule)
        self.assertFalse(self.student.enrollment_slot_ids)
        self.assertEqual(self._lines_of(self.student), self.line_c_mon | self.line_c_tue)

    def test_deleting_the_enrollment_clears_every_custom_line(self):
        self._split_c_mon_d_wed()

        self.enrollment.unlink()

        self.assertFalse(self._lines_of(self.student))
        self.assertFalse(self.env['ems.enrollment.slot'].search([('student_id', '=', self.student.id)]))

    def test_main_group_change_keeps_the_custom_schedule(self):
        self._split_c_mon_d_wed()

        self.env['ems.enrollment']._ems_move_group(self.student, self.group_c, self.group_d)

        enrollment = self.student.enrollment_ids
        self.assertEqual(enrollment.group_id, self.group_d)
        self.assertEqual(len(enrollment.slot_ids), 2)
        self.assertEqual(self._lines_of(self.student), self.line_c_mon | self.line_d_wed)

    def test_main_group_change_of_a_group_follower(self):
        self.env['ems.enrollment']._ems_move_group(self.student, self.group_c, self.group_d)

        self.assertEqual(self._lines_of(self.student), self.line_d_wed | self.line_d_thu)

    def test_changing_the_enrollment_group_moves_a_group_follower(self):
        self.enrollment.group_id = self.group_d

        self.assertEqual(self._lines_of(self.student), self.line_d_wed | self.line_d_thu)

    # -- consumers --

    def test_continuation_session_only_carries_this_slot_roster(self):
        """Two consecutive hours of the same template: the second roll-call copies the first one's
        statuses, but only for the students of its own roster."""
        second_hour = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': self.line_c_mon.attendance_template_id.id,
            'weekday': '0', 'start_time': 10.0, 'end_time': 11.0, 'space_id': self.space.id,
        })
        second_hour.fill_students()
        self.enrollment.action_customize_slots()
        self.enrollment.slot_ids.filtered(
            lambda slot: slot.weekday == '0' and slot.start_time == 10.0).unlink()
        monday = date(2026, 3, 2)
        Session = self.env['ems.attendance_session_header']

        teacher = self.line_c_mon.attendance_template_id.teacher_ids
        first = Session.create({'attendance_schedule_id': self.line_c_mon.id, 'date': monday, 'mode': 'scheduled', 'session_teacher_id': teacher.id})
        second = Session.create({'attendance_schedule_id': second_hour.id, 'date': monday, 'mode': 'scheduled', 'session_teacher_id': teacher.id})

        self.assertIn(self.student, first.attendance_session_line_ids.student_id)
        self.assertNotIn(self.student, second.attendance_session_line_ids.student_id)
        self.assertIn(self.classmate, second.attendance_session_line_ids.student_id)

    def test_grading_stays_with_the_enrollment_group(self):
        teacher = self.line_d_wed.attendance_template_id.teacher_ids
        session_d = self.env['ems.grade_session'].create({
            'group_id': self.group_d.id, 'subject_id': self.subject.id, 'round': '1', 'teacher_id': teacher.id,
        })

        self._split_c_mon_d_wed()

        self.assertNotIn(self.student, session_d.grade_subject_line_ids.student_id)


class TestEnrollmentSlotAccess(EnrollmentSlotCase):
    """Same reach as ems.enrollment: secretary edits any student's slots, a plain teacher only
    reads them."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.secretary = create_role_user(cls, 'secretary', 'test_secretary_enrollment_slot')
        cls.teacher_user = create_role_user(cls, 'teacher', 'test_teacher_enrollment_slot')
        create_role_employee(cls, cls.teacher_user)

    def test_secretary_can_customize(self):
        self.enrollment.with_user(self.secretary).action_customize_slots()
        self.env['ems.enrollment.slot'].with_user(self.secretary).create({
            'enrollment_id': self.enrollment.id, 'group_id': self.group_d.id,
            'attendance_schedule_id': self.line_d_wed.id,
        })

        self.assertIn(self.student, self.line_d_wed.student_ids)

    def test_plain_teacher_cannot_create_slots(self):
        self.enrollment.action_customize_slots()
        with self.assertRaises(AccessError):
            self.env['ems.enrollment.slot'].with_user(self.teacher_user).create({
                'enrollment_id': self.enrollment.id, 'group_id': self.group_d.id,
                'attendance_schedule_id': self.line_d_wed.id,
            })
        self.assertTrue(self.enrollment.slot_ids.with_user(self.teacher_user).read(['weekday']))


class TestEnrollmentSlotCalendar(TransactionCase):
    """The same rule through the real pipeline: teachers' calendars ('apply_schedule_changes')
    drive the templates, the rosters and the student's schedule tab."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(cls, 'TSLC')
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TSLC001', 'acronym': 'TSLC', 'name': 'Test Subject (Enrollment Slot Calendar)',
            'study_ids': [(6, 0, cls.study.ids)],
        })
        space_type = cls.env.ref('ems.space_type_classroom')
        location = cls.env.ref('ems.work_location_main')
        cls.space_c, cls.space_d = cls.env['ems.space'].create([
            {'code': f'TSLC-{code}', 'name': f'Test Space {code} (Enrollment Slot Calendar)',
             'space_type_id': space_type.id, 'work_location_id': location.id}
            for code in ('C', 'D')
        ])
        cls.group_c, cls.group_d = cls.env['ems.group'].create([
            {'course': 1, 'acronym': acronym, 'level_id': cls.level.id, 'study_id': cls.study.id,
             'space_id': space.id, 'shift': 'morning'}
            for acronym, space in (('C', cls.space_c), ('D', cls.space_d))
        ])
        cls.teacher_c, cls.teacher_d = cls.env['hr.employee'].create([
            {'name': f'Test Teacher {acronym} (Enrollment Slot Calendar)', 'employee_type': 'teacher',
             'resource_calendar_id': cls.env['resource.calendar'].create({'name': f'Test Calendar {acronym} (Enrollment Slot)'}).id}
            for acronym in ('C', 'D')
        ])
        cls._schedule(cls.teacher_c, cls.group_c, [('0', 9, 10), ('1', 9, 10)])
        cls._schedule(cls.teacher_d, cls.group_d, [('2', 9, 10), ('3', 9, 10)])

        cls.student = cls.env['res.partner'].create({
            'name': 'Test Student (Enrollment Slot Calendar)', 'contact_type': 'student',
            'student_id': next_student_id(), 'main_group_id': cls.group_c.id,
        })
        cls.student_d = cls.env['res.partner'].create({
            'name': 'Test Student D (Enrollment Slot Calendar)', 'contact_type': 'student',
            'student_id': next_student_id(), 'main_group_id': cls.group_d.id,
        })
        cls.enrollment = cls.env['ems.enrollment'].create({'student_id': cls.student.id, 'group_id': cls.group_c.id, 'subject_id': cls.subject.id})
        cls.env['ems.enrollment'].create({'student_id': cls.student_d.id, 'group_id': cls.group_d.id, 'subject_id': cls.subject.id})

        # Tuesday with C swapped for Wednesday with D.
        cls.enrollment.action_customize_slots()
        cls.enrollment.slot_ids.filtered(lambda slot: slot.weekday == '1').unlink()
        cls.env['ems.enrollment.slot'].create({
            'enrollment_id': cls.enrollment.id, 'group_id': cls.group_d.id,
            'weekday': '2', 'start_time': 9.0, 'end_time': 10.0,
        })

    @classmethod
    def _schedule(cls, teacher, group, slots):
        teacher.resource_calendar_id.apply_schedule_changes([
            {'dayofweek': weekday, 'hour_from': start, 'hour_to': end, 'day_period': 'morning',
             'subject_id': cls.subject.id, 'group_ids': [group.id], 'name': f'{group.acronym}: TSLC'}
            for weekday, start, end in slots
        ])

    def _line(self, group, weekday, start):
        return self.env['ems.attendance_schedule'].search([
            ('attendance_template_id.subject_id', '=', self.subject.id),
            ('attendance_template_id.group_ids', 'in', group.id),
            ('weekday', '=', weekday), ('start_time', '=', start),
        ])

    def test_student_schedule_shows_only_the_custom_slots(self):
        blocks = self.student.schedule_attendance_ids.filtered('subject_id')

        self.assertEqual(
            sorted((block.dayofweek, block.employee_id) for block in blocks),
            [('0', self.teacher_c), ('2', self.teacher_d)])

    def test_rosters_follow_the_custom_slots(self):
        self.assertIn(self.student, self._line(self.group_c, '0', 9.0).student_ids)
        self.assertNotIn(self.student, self._line(self.group_c, '1', 9.0).student_ids)
        self.assertIn(self.student, self._line(self.group_d, '2', 9.0).student_ids)
        self.assertNotIn(self.student, self._line(self.group_d, '3', 9.0).student_ids)

    def test_teacher_moving_the_class_breaks_the_slot(self):
        self._schedule(self.teacher_d, self.group_d, [('2', 11, 12), ('3', 9, 10)])

        moved = self._line(self.group_d, '2', 11.0)
        self.assertTrue(moved)
        self.assertIn(self.student_d, moved.student_ids)
        self.assertNotIn(self.student, moved.student_ids)
        self.assertEqual(self.student.enrollment_slot_broken_count, 1)

    def test_teacher_adding_a_class_skips_the_custom_student(self):
        self._schedule(self.teacher_c, self.group_c, [('0', 9, 10), ('1', 9, 10), ('4', 9, 10)])

        self.assertNotIn(self.student, self._line(self.group_c, '4', 9.0).student_ids)
