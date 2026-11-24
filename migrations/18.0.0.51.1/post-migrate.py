# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _department_job_from_members(api.Environment(cr, SUPERUSER_ID, {}))


def _department_job_from_members(env):
    """Issue #815: the job position of ASP staff is now declared on their department. An existing
    installation has it on each employee, so a department whose ASP members all share one job takes
    that job (a department without members, or with several different jobs, is left for an
    administrator to set; it is logged). The department's own write() then gives that job to any
    member that had none. Through the ORM so the security groups the job carries stay synced."""
    pairs = env['hr.employee']._read_group(
        [('department_id.job_id', '=', False), ('department_id.is_top_level', '=', False),
         ('employee_type', '=', 'asp'), ('job_id', '!=', False)],
        ['department_id', 'job_id'], ['__count'])
    jobs = {}
    for department, job, _count in pairs:
        jobs[department] = jobs.get(department, env['hr.job']) | job
    for department, department_jobs in jobs.items():
        if len(department_jobs) == 1:
            department.job_id = department_jobs
        else:
            _logger.warning("Department %s has ASP members with several job positions: choose its job position by hand.", department.display_name)
