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
    # Secretariat prints the attendance PDFs too, from the 'Reports' screen they see (issue #633).
    'ems.attendance_report_wizard': {'teacher': 'rwc', 'secretary': 'rwc'},
    'ems.attendance_status': {'teacher': 'r'},
    'ems.content': {'teacher': 'r', 'secretary': 'r'},
    'ems.convalidation.info_reason': {'teacher': '', 'secretary': 'r', 'head_of_studies': 'r', 'academic_admin': 'rwcu'},
    'ems.convalidation.rejection_reason': {'teacher': '', 'secretary': 'r', 'head_of_studies': 'r', 'academic_admin': 'rwcu'},
    'ems.course': {'teacher': 'r', 'secretary': 'r', 'erasmus': 'r'},
    'ems.criteria': {'teacher': 'r', 'secretary': 'r'},
    # Issue #683: the applications have record rules and a write() guard, tested in test_erasmus.py.
    # Issue #697: the Secretary reads the calls and projects of the grant payments it makes.
    'ems.erasmus.call': {'teacher': '', 'secretary': 'r', 'head_of_studies': 'r', 'erasmus': 'rwcu'},
    'ems.erasmus.call.document': {'teacher': '', 'head_of_studies': 'r', 'erasmus': 'rwcu'},
    # Issue #684: the modules frozen for the record average, written only by the call's closing.
    'ems.erasmus.application.grade': {'teacher': '', 'secretary': '', 'head_of_studies': 'r', 'erasmus': 'r'},
    'ems.erasmus.call.modality': {'teacher': '', 'head_of_studies': 'r', 'erasmus': 'rwcu'},
    # Issue #685: frozen lines and offers are written only by the resolutions' and offers' actions.
    'ems.erasmus.resolution': {'teacher': '', 'secretary': '', 'head_of_studies': 'r', 'erasmus': 'rwcu'},
    'ems.erasmus.resolution.line': {'teacher': '', 'secretary': '', 'head_of_studies': 'r', 'erasmus': 'r'},
    'ems.erasmus.offer': {'teacher': '', 'secretary': '', 'head_of_studies': 'r', 'erasmus': 'r'},
    'ems.erasmus.claim': {'teacher': '', 'secretary': '', 'head_of_studies': 'r', 'erasmus': 'rwcu'},
    # Issue #686: plan ratings have record rules (own ratings for panel members), tested in test_erasmus_staff.py.
    'ems.erasmus.call.panel': {'teacher': '', 'secretary': '', 'head_of_studies': 'r', 'erasmus': 'rwcu'},
    'ems.erasmus.plan_rating': {'teacher': '', 'secretary': '', 'head_of_studies': '', 'erasmus': 'rwcu'},
    'ems.erasmus.application.merit': {'teacher': '', 'secretary': '', 'head_of_studies': 'r', 'erasmus': 'rwcu'},
    # Issue #687: the Director writes only the decision on a staff proposal (write() guard, test_erasmus_mobility.py).
    'ems.erasmus.destination': {'teacher': '', 'secretary': '', 'head_of_studies': 'r', 'erasmus': 'rwcu'},
    'ems.erasmus.call.question': {'teacher': '', 'secretary': '', 'head_of_studies': 'r', 'erasmus': 'rwcu'},
    'ems.erasmus.call.task': {'teacher': '', 'secretary': '', 'head_of_studies': 'r', 'erasmus': 'rwcu'},
    'ems.erasmus.mobility': {'teacher': '', 'secretary': '', 'head_of_studies': 'rw', 'erasmus': 'rwcu'},
    'ems.erasmus.project': {'teacher': '', 'secretary': 'r', 'head_of_studies': 'r', 'erasmus': 'rwcu'},
    # Issue #701: a plain teacher reaches nothing; the leader and accompanying teachers (a hidden
    # group EMS manages) only their own mobilities, through record rules tested in
    # test_erasmus_group_mobility.py.
    'ems.erasmus.group.mobility': {'teacher': '', 'secretary': '', 'head_of_studies': 'r', 'erasmus': 'rwcu'},
    'ems.erasmus.group.registration': {'teacher': '', 'secretary': '', 'head_of_studies': 'r', 'erasmus': 'rwcu'},
    'ems.erasmus.group.participant': {'teacher': '', 'secretary': '', 'head_of_studies': 'r', 'erasmus': 'rwcu'},
    'ems.erasmus.group.draw': {'teacher': '', 'secretary': '', 'head_of_studies': 'r', 'erasmus': 'r'},
    'ems.erasmus.group.draw.line': {'teacher': '', 'secretary': '', 'head_of_studies': 'r', 'erasmus': 'r'},
    'ems.erasmus.group.log': {'teacher': '', 'secretary': '', 'head_of_studies': 'r', 'erasmus': 'rwcu'},
    # Issue #697: payments are marked paid by the Secretary through a button (write() guard, test_erasmus_grant.py).
    'ems.erasmus.provision': {'teacher': '', 'secretary': 'r', 'head_of_studies': '', 'erasmus': 'rwcu'},
    'ems.erasmus.invoice': {'teacher': '', 'secretary': 'r', 'head_of_studies': '', 'erasmus': 'rwcu'},
    'ems.erasmus.payment': {'teacher': '', 'secretary': 'r', 'head_of_studies': '', 'erasmus': 'rwcu'},
    'ems.erasmus.project.document': {'teacher': '', 'secretary': 'rwc', 'head_of_studies': 'r', 'erasmus': 'rwcu'},
    # Exports are a log: created (as oneself) and read, never changed nor deleted (test_erasmus_records.py).
    'ems.erasmus.export': {'teacher': '', 'secretary': 'rc', 'head_of_studies': '', 'erasmus': 'rc'},
    'ems.erasmus.mobility.task': {'teacher': '', 'secretary': '', 'head_of_studies': 'r', 'erasmus': 'rwcu'},
    'ems.erasmus.self_assessment': {'teacher': '', 'secretary': '', 'head_of_studies': 'r', 'erasmus': 'rwcu'},
    'ems.erasmus.self_assessment.answer': {'teacher': '', 'secretary': '', 'head_of_studies': 'r', 'erasmus': 'rwcu'},
    'ems.group': {'teacher': 'r', 'secretary': 'r', 'department_chief': 'rwcu', 'head_of_studies': 'rwcu'},
    'ems.level': {'teacher': 'r', 'secretary': 'r', 'erasmus': 'r'},
    'ems.non_teaching_type': {'teacher': 'r', 'department_chief': 'rwcu'},
    'ems.outcome': {'teacher': 'r', 'secretary': 'r'},
    'ems.space': {'teacher': 'r', 'secretary': 'r'},
    'ems.space_type': {'teacher': 'r', 'secretary': 'r'},
    'ems.study': {'teacher': 'r', 'secretary': 'r'},
    'ems.subject': {'teacher': 'r', 'secretary': 'r'},
    'ems.teaching': {'teacher': 'r', 'secretary': 'r', 'head_of_studies': 'rwc'},
    'ems.teaching_reduction_type': {'teacher': 'r', 'department_chief': 'rwcu'},
    'ems.tracking': {'teacher': 'r', 'secretary': 'r'},
    # Issue #635: the roles that may edit the academic history.
    'ems.title_import_wizard': {'teacher': '', 'head_of_studies': '', 'secretary': 'rwcu', 'academic_admin': 'rwcu'},
    'ems.title_register_wizard': {'teacher': '', 'head_of_studies': '', 'secretary': 'rwcu', 'academic_admin': 'rwcu'},
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
