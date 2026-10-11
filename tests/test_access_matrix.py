# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase, tagged

from .common import create_role_user

# Model-level access rights (ir.model.access) per role: the operations each role may perform,
# as letters - r(ead), w(rite), c(reate), u(nlink). Every operation NOT listed must be refused.
# Only models whose access depends on the ACL alone belong here (no ir.rule for these roles):
# record-level rules ("a tutor only edits their own students") need a real record and stay in
# each model's own test file. Replaces the per-model test_<role>_can/cannot_<op> methods that
# used to repeat this check file by file (issue #567).
ACCESS_MATRIX = {
    # Every write goes through the guard duty board's own methods, which check the hierarchy and
    # write with sudo() (see models/attendance/absence_coverage.py).
    'ems.absence_cover': {'teacher': 'r', 'department_chief': 'r', 'head_of_studies': 'r'},
    'ems.attendance_status': {'teacher': 'r'},
    'ems.content': {'teacher': 'r', 'secretary': 'r'},
    'ems.convalidation.info_reason': {'teacher': '', 'secretary': 'r', 'head_of_studies': 'r', 'academic_admin': 'rwcu'},
    'ems.convalidation.rejection_reason': {'teacher': '', 'secretary': 'r', 'head_of_studies': 'r', 'academic_admin': 'rwcu'},
    'ems.course': {'teacher': 'r', 'secretary': 'r'},
    'ems.criteria': {'teacher': 'r', 'secretary': 'r'},
    'ems.group': {'teacher': 'r', 'secretary': 'r', 'department_chief': 'rwcu', 'head_of_studies': 'rwcu'},
    'ems.level': {'teacher': 'r', 'secretary': 'r'},
    'ems.non_teaching_type': {'teacher': 'r', 'department_chief': 'rwcu'},
    'ems.outcome': {'teacher': 'r', 'secretary': 'r'},
    'ems.space': {'teacher': 'r', 'secretary': 'r'},
    'ems.space_type': {'teacher': 'r', 'secretary': 'r'},
    'ems.study': {'teacher': 'r', 'secretary': 'r'},
    'ems.subject': {'teacher': 'r', 'secretary': 'r'},
    'ems.teaching': {'teacher': 'r', 'secretary': 'r', 'head_of_studies': 'rwc'},
    'ems.teaching_reduction_type': {'teacher': 'r', 'department_chief': 'rwcu'},
    'ems.tracking': {'teacher': 'r', 'secretary': 'r'},
    'ems.workgroup': {'teacher': 'r', 'secretary': 'r'},
    'resource.calendar': {'teacher': 'r'},
    'resource.calendar.attendance': {'teacher': 'r'},
}

OPERATIONS = {'r': 'read', 'w': 'write', 'c': 'create', 'u': 'unlink'}


@tagged('post_install', '-at_install')
class TestAccessMatrix(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        roles = {role for rights in ACCESS_MATRIX.values() for role in rights}
        cls.users = {role: create_role_user(cls, role, f'test_access_matrix_{role}') for role in roles}

    def test_model_access_per_role(self):
        for model, rights in ACCESS_MATRIX.items():
            for role, allowed in rights.items():
                records = self.env[model].with_user(self.users[role])
                for letter, operation in OPERATIONS.items():
                    with self.subTest(model=model, role=role, operation=operation):
                        self.assertEqual(records.has_access(operation), letter in allowed)
