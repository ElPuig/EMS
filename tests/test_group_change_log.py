from odoo.tests.common import TransactionCase

LOGGER = 'odoo.addons.ems.models.employees.user'


class TestGroupChangeLog(TransactionCase):
    """Every grant or revocation of a security group leaves a line in the server log with who
    did it and from which code (issue #535: a hand-granted group kept disappearing untraced)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref('base.user_admin')
        cls.user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Group Log User',
            'login': 'test_group_log_user',
        })
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Test Group Log Employee',
            'employee_type': 'teacher',
            'user_id': cls.user.id,
        })
        cls.group_secretary = cls.env.ref('ems.group_secretary')
        cls.group_coexistence = cls.env.ref('ems.group_coexistence')
        cls.role_coexistence = cls.env.ref('ems.role_coexistence')

    def _log_lines(self, logs):
        return [line for line in logs.output if 'test_group_log_user' in line]

    def test_hand_grant_is_logged_with_its_author(self):
        with self.assertLogs(LOGGER, level='INFO') as logs:
            self.user.with_user(self.admin).write({'groups_id': [(4, self.group_secretary.id)]})
        [line] = self._log_lines(logs)
        self.assertIn(f"changed by {self.admin.login} (uid {self.admin.id})", line)
        # The nearest EMS caller is this test itself; from Settings > Users there is none, and
        # the line then says "no EMS code".
        self.assertIn("via test_hand_grant_is_logged_with_its_author (tests/test_group_change_log.py:", line)
        self.assertIn(self.group_secretary.full_name, line.split('added [')[1].split(']')[0])

    def test_revocation_by_role_sync_names_the_code(self):
        self.employee.write({'role_ids': [(4, self.role_coexistence.id)]})
        with self.assertLogs(LOGGER, level='INFO') as logs:
            self.employee.write({'role_ids': [(3, self.role_coexistence.id)]})
        [line] = [line for line in self._log_lines(logs) if self.group_coexistence.full_name in line]
        self.assertIn("_sync_security_groups (models/employees/employee.py:", line)
        self.assertIn(self.group_coexistence.full_name, line.split('removed [')[1])

    def test_adding_a_user_from_the_group_side_is_logged(self):
        with self.assertLogs(LOGGER, level='INFO') as logs:
            self.group_secretary.write({'users': [(4, self.user.id)]})
        [line] = self._log_lines(logs)
        self.assertIn(self.group_secretary.full_name, line.split('added [')[1].split(']')[0])

    def test_unrelated_user_write_logs_nothing(self):
        with self.assertNoLogs(LOGGER, level='INFO'):
            self.user.write({'name': 'Test Group Log User (renamed)'})
