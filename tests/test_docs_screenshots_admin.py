# -*- coding: utf-8 -*-
"""Regenerates the screenshots used by the Admin user manuals.

Split into one test METHOD per small batch of manuals (see plans/user_manual_screenshots.md
for the batching rationale - quota control, one topical group at a time) rather than one
method for the whole role, unlike test_docs_screenshots_head_of_studies.py's single method -
17 admin manuals is too much fixture/capture work for one method to stay reviewable.

Tagged '-standard' on purpose - see the identical NOTE in test_docs_screenshots.py. Run a
single batch by hand, e.g.:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags='*/ems:TestDocsScreenshotsAdmin.test_capture_batch1_absences_attendance_notice_strike' --stop-after-init -c /etc/odoo/odoo.conf"

Writes PNGs to /tmp/ems_doc_screenshots (override with EMS_SCREENSHOT_DIR); copy them into
docs/assets/admin/ by hand afterwards. See test_docs_screenshots.py's own module docstring for
the full rationale (rolled-back transaction, made-up people, one element per shot).
"""
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.tests.common import HttpCase, tagged

from .common import (
    DocsScreenshotMixin, create_level_study_group, create_role_employee, create_role_user,
    next_student_id,
)


@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshotsAdmin(HttpCase, DocsScreenshotMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Both 'academic_admin' (the EMS Academic-block Administrator role, needed for the
        # normal ems.* config screens) and base.group_system (needed for Odoo's own Settings
        # screen, res.config.settings - see CLAUDE.md-adjacent research this session:
        # ems.group_academic_admin does NOT imply base.group_system on its own, only
        # ems.group_settings_admin does) - one login covers every admin capture in this file,
        # matching how the real centre "Administrator" account actually holds both.
        cls.admin_user = create_role_user(cls, 'academic_admin', 'doc_shot_admin', lang='ca_ES',
                                          name='Administrador EMS', email='admin.ems@example.com')
        cls.admin_user.write({'groups_id': [(4, cls.env.ref('ems.group_settings_admin').id)]})

    @classmethod
    def _student(cls, name, group, age=15, **overrides):
        return cls.env['res.partner'].create({
            'name': name, 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': group.id,
            'birth_date': date.today() - relativedelta(years=age),
            **overrides,
        })

    def test_capture_batch1_absences_attendance_notice_strike(self):
        # --- Notice (Communications > Notices > New) ---
        level, study, group = create_level_study_group(
            self, 'ADM', level={'name': 'Administració'}, study={'name': 'Estudi Notificacions'})
        student = self._student(
            'Marta Prova', group, age=15,
            student_email='marta.prova@example.com', email='marta.prova.personal@example.com')
        family = self.env['res.partner'].create({
            'name': 'Família Prova', 'contact_type': 'family', 'email': 'familia.prova@example.com',
        })
        self.env['res.partner.relation'].create({
            'left_partner_id': family.id,
            'type_id': self.env.ref('ems.relation_type_father').id,
            'right_partner_id': student.id,
        })
        # res.partner.relation.all (what student.relation_all_ids actually reads) is a SQL VIEW
        # model, not a plain table - it does not see the res.partner.relation row just created
        # above within the same transaction unless explicitly flushed first. Without this,
        # _onchange_groups() below silently finds 0 relations and skips the family recipient
        # entirely (found by actually inspecting notice_line_ids - not a hypothetical).
        self.env.flush_all()
        self.env.invalidate_all()
        notice = self.env['ems.notice'].create({
            'subject': 'Reunió de pares i mares', 'message': '<p>Us convidem a la reunió trimestral.</p>',
            'recipient_type': 'both', 'group_ids': [(6, 0, [group.id])],
        })
        # Populates notice_line_ids the same way the form's own onchange does when a real user
        # picks Groups/Send to - see models/communications/notice.py's _onchange_groups(). Calling
        # it directly on a persisted record (not a NewId) is safe: the resulting field assignment
        # is a real write, not a virtual onchange preview.
        notice._onchange_groups()
        self._capture(
            '/odoo/action-ems.action_communication_list/%d' % notice.id,
            '.o_form_sheet', 'admin-notice-create-form.png',
            login='doc_shot_admin', wait_for='.o_form_sheet .o_field_widget[name="notice_line_ids"] .o_data_row',
        )

        # --- Attendance statuses (Attendance > Configuration > Sessions > Statuses) ---
        # No fixture needed: this is EMS's own shipped configuration data (roll-call button
        # catalogue), not personal data, so the real seeded rows are safe to screenshot directly.
        self._capture(
            '/odoo/action-ems.action_attendance_status_list',
            '.o_list_table', 'admin-attendance-status-list.png',
            login='doc_shot_admin', wait_for='.o_list_renderer .o_data_row',
        )

        # --- Strike reasons (Convivencia > Configuration > Strikes > Reasons) ---
        # Same as above - shipped configuration data, not personal, safe to capture directly.
        self._capture(
            '/odoo/action-ems.action_strike_reason_list',
            '.o_list_table', 'admin-strike-reasons-list.png',
            login='doc_shot_admin', wait_for='.o_list_renderer .o_data_row',
        )

        # --- Staff Absence Settings (Settings > EMS Management) ---
        # Odoo's own res.config.settings screen: a single page with one <app> tab per module,
        # each holding several named <block>s. Each <setting id="..."> renders with that same id
        # as a real DOM id (confirmed by reading web's settings_form_compiler.js /
        # form_compiler.js / setting.xml this session) - #ems_full_day_hours is stable to target.
        # Navigate on the default (first) tab, then click the "EMS Management" tab to reveal it.
        self._capture(
            '/odoo/action-base_setup.action_general_configuration',
            # ':has()' (Chrome 150 here, well past the ~105 baseline) selects the specific
            # settings block containing our target id - the <block> itself renders no stable
            # class/id of its own (only title text, not selector-safe), so this is the only way
            # to clip precisely to "Staff Absence Settings" without also grabbing its siblings.
            '.o_settings_container:has(#ems_full_day_hours)',
            'admin-absences-settings.png',
            login='doc_shot_admin', wait_for='a.tab[data-key="ems"]',
            click='a.tab[data-key="ems"]', wait_after='#ems_full_day_hours',
        )
