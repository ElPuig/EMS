# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date, datetime

class EmsCourse(models.Model):
	_name = "ems.course"
	_description = "Course: defines a range of time when a course is running (for example: 2024-2025)."
	_order = "start desc"
	_sql_constraints = [
		('unique_course_name', 'unique (name)', 'duplicated course!')
    ]

	name = fields.Char(string="Name", compute="_compute_name", store=True)
	start = fields.Integer(string="Start", default=lambda self: datetime.now().year, required=True)
	end = fields.Integer(string="End", default=lambda self: datetime.now().year+1, required=True)	

	# 1. Operational Course: For day-to-day operations (Attendance, Grades, Incidents)
	is_current = fields.Boolean(
		string="Current (Operational)", 
		help="Check this box if this course is currently active for daily academic management."
	)

	# 2. Enrollment default Course: For enrollments and new registrations
	is_enrollment_default = fields.Boolean(
		string="Enrollment Default", 
		help="Check this box if this is the default course for new enrollments (usually the upcoming academic year)."
	)

	@api.depends("start", "end")
	def _compute_name(self):
		for course in self:
			course.name = "%s-%s" % (course.start, course.end)

	def date_range(self):
		"""The course's calendar window, as (first day, last day): 1 September of 'start' to
		31 August of 'end'. The model only stores the two years, but anything counting per-course
		(the staff health absence allowance, for one) needs real dates to filter on. Returns False
		for an empty recordset, so callers can test it directly."""
		if not self:
			return False
		self.ensure_one()
		return date(self.start, 9, 1), date(self.end, 8, 31)

	@api.model
	def _ems_seed_enrollment_default(self):
		"""Mark an enrollment default when no course carries one, and only then.

		'is_enrollment_default' is live application state, not configuration: the centre
		moves it when it opens the following year's campaign. That is why it is NOT a
		column of data/custom/ems.course.csv - a synced column would silently revert that
		move on the next upgrade, and new enrollments would start landing on the wrong
		course (see CLAUDE.md, "fields that are live application state").

		Leaving it out of the file means something has to set the initial value instead:
		this method, called from post_init_hook (fresh installs) and from the 18.0.0.22.0
		post-migrate (installations created before the column left the file).

		The guard is what makes it safe to re-run: an instance that already flagged a
		course - whichever one, and however it got there - is left untouched. It only
		acts on the "nobody is flagged" state, which is the one that breaks every
		"which course do new enrollments belong to" lookup at once.

		The course chosen is the one after the operational course, since enrollments are
		taken for the year ahead; with no operational course to count from, the earliest
		course is as good a guess as any and the admin can move it from the course form.
		"""
		companies = self.env['res.company'].search([('enrollment_course_id', '=', False)])
		flagged = self.search([('is_enrollment_default', '=', True)], limit=1)
		if flagged:
			# Already decided: only backfill the companies whose selector never got the
			# value (installations that carried the flag before the setting existed).
			companies.enrollment_course_id = flagged
			return self.browse()
		current = self.search([('is_current', '=', True)], limit=1)
		course = self.search([('start', '>', current.start)], order='start asc', limit=1) \
			if current else self.browse()
		course = course or self.search([], order='start asc', limit=1)
		if course:
			# Through the company selector, so the flag and the setting are written by the
			# one method that owns that pairing (_sync_enrollment_course_flag).
			companies.enrollment_course_id = course
			if not course.is_enrollment_default:
				course.is_enrollment_default = True
		return course

	@api.constrains('is_current')
	def _check_unique_current(self):
		for course in self:
			if course.is_current:
				others = self.search([
					('is_current', '=', True),
					('id', '!=', course.id)
				])
				if others:
					raise ValidationError(_("Configuration Error! There can be only one Course marked as 'Current (Operational)' at a time."))

	@api.constrains('is_enrollment_default')
	def _check_unique_enrollment_default(self):
		for course in self:
			if course.is_enrollment_default:
				others = self.search([
					('is_enrollment_default', '=', True),
					('id', '!=', course.id)
				])
				if others:
					raise ValidationError(_("Configuration Error! There can be only one Course marked as 'Enrollment Default' at a time."))
