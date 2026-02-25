# -*- coding: utf-8 -*-

import requests, json, html, re, base64, threading
from odoo import models, fields, api, registry, _
from odoo.exceptions import UserError
from markupsafe import Markup

survey_target_selection = [("students", "Students"), ("teachers", "Teachers"), ("asp", "ASP")]

class ems_limesurvey_header(models.Model):
	_name = "ems.limesurvey_header"
	_description = "LimeSurvey header: contains the survey's header and its content."
	_inherit = ['ems.base']
	
	name = fields.Char(string="Name", required=True)
	title = fields.Char(string="Title", required=True)
	description = fields.Char(string="Description", required=True)
	target = fields.Selection(string="Target", selection=survey_target_selection, required=True)
	level_ids = fields.Many2many(string="Level", comodel_name="ems.level")
	tsv_raw_text = fields.Text(string="Header's content (tab separated)", required=True)
	limesurvey_block_ids = fields.One2many(string="Blocks", comodel_name="ems.limesurvey_block", inverse_name="limesurvey_header_id")
	limesurvey_recipient_ids = fields.One2many(string="Recipients", comodel_name="ems.limesurvey_recipient", inverse_name="limesurvey_header_id")
	
	notes = fields.Text(string="Notes")
	
	@api.depends("name", "target", "level_ids")
	def _compute_display_name(self):			
		for rec in self:				
			target = dict(survey_target_selection).get(rec.target)		
			if not rec.level_ids and not rec.target:
				rec.display_name = "" if not rec.name else rec.name
			elif not rec.level_ids:
				rec.display_name = "%s: %s" % (rec.name, target)
			else:
				levels = []
				for l in rec.level_ids:
					levels.append(l.acronym)
				level_str = str.join(", ", levels)				
				rec.display_name = "%s: %s (%s)" % (rec.name, target, level_str) if rec.target else "%s (%s)" % (rec.name, level_str)

	def action_test(self):
		# TODO: Expected behaviour:
		#		1. Check if exists the main "ems" group:
		#			1.1. If exists, keeps its ID.
		#			1.2. If don't, fires exceptions and requires to create manually the group using the same user (suggest also the description).
		#
		#		2. Every survey will be created into the same group, because the EMS will keep track between every target and its survey.
		#		3. The surveys will be created as "{DisplayName} - {hasCode}". The hashCode will be computed as:
		#		   Sort subject codes.
		#			
		#		4. A new sheet called "Recipients" will contain the relation between recipients (Name, email, survey_target_selection, limesurvey survey name, limsurvey survey link).
		#		5. Buttons (or a kind of wizard with progress like in emails section) in the following order:
		#			5.1. Create the surveys in LimeSurvey (once used, disables the option).
		#			5.2. Enable the surveys in LimeSurvey and send invitations (once used, disables the option).
		#			5.3. Send reminders (disables on closing the survey).
		#			5.4. Close the survey in LimeSurvey (once used, disables the option).
		#			5.5. PHASE 2: Downloads the data from LimeSurvey [and trasnfers it to Metabase <- can we handle it within Odoo?] (once used, disables the option).
		#			5.6. Remove the survey from LimeSurvey, cleans the recipients data. Do not remove already downloaded data! (once used, disables the option BUT enables the first one again).

		# TODO: Metabase import could be in a phase 2. But would be nice to do not use Metabase and keep everything within Odoo. 
		#		In that case, download the data and metabase import can wait, the priority is to create and manage recipients in
		#		order to detect and fix problems quickly. 
		
		ems_grp = self._get_ems_group()
		if not ems_grp:
			#NOTE: The LimeSurvey's API does not allow to create groups.
			raise UserError(_("LimeSurvey's EMS group not found. We're sorry, but the LimeSurvey API v6 does not allow to create survey groups. Please, use the EMS user to crate a survey group called 'EMS' and try again; the EMS will use this group in order to generate all the surveys."))		
			
		if(self.target == "students"): surveys = self._setup_students_surveys()
		elif(self.target == "teachers"): surveys = self._setup_teachers_surveys()
		elif(self.target == "asp"): surveys = self._setup_asp_surveys()
		
		user_id = self.env.uid
		db_name = self.env.cr.dbname

		threaded_sync = threading.Thread(
            target=self._thread_import, 
            args=(surveys, ems_grp, user_id, db_name)
        )
		
		threaded_sync.start()
		return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("LimeSurvey Import"),
                'message': _("Starting process in the background..."),
                'type': 'info', # Can be: 'success', 'warning', 'danger', 'info'
                'sticky': True, # If True, the user should close it manually
            }
        }

		# self._upload_surveys(surveys, ems_grp["gsid"])
		# self._upload_recipients(surveys)
		# self._store_recipients(surveys)

		# return {
		# 	'effect': {
		# 		'fadeout': 'slow',
		# 		'message': f"¡Éxito!",
		# 		'type': 'rainbow_man',
		# 	}
		# }			

		# OPTIM -> 270 - 280 ms
		# NO OP -> 1400 - 1500 ms

		# for key in surveys:
		# 	data = surveys[key]

		# if not ems_grp:
		# 	return {
		# 			'type': 'ir.actions.client',
		# 			'tag': 'display_notification',
		# 			'params': {
		# 				'title': 'No encontrado',
		# 				'message': f"No existe ningún grupo con el nombre '{self.name}'",
		# 				'type': 'warning',
		# 				'sticky': False,
		# 			}
		# 		}
		# else:
		# 	return {
		# 		'effect': {
		# 			'fadeout': 'slow',
		# 			'message': f"¡Éxito! El grupo existe. ID: {ems_grp['gsid']}",
		# 			'type': 'rainbow_man',
		# 		}
		# 	}			

	def _notify(self, cr, message, type, sticky):
		self.env["bus.bus"]._sendone(
			self.env.user.partner_id, "simple_notification", {
				"title": _("LimeSurvey import"), 
				"message": message, 
				"type": type,
				"sticky": sticky
			}
		)
		cr.commit()

	def _thread_import(self, surveys, ems_grp, user_id, db_name):
		# NOTE: important to avoid timeouts, because the main Odoo window becomes blocked till the method finishes...
		db_registry = registry(db_name)
		with db_registry.cursor() as cr:			
			self.env = api.Environment(cr, user_id, {})
			success = True
			try:
				success = success and self._upload_surveys(cr, surveys, ems_grp["gsid"])								
				success = success and self._upload_recipients(cr, surveys)				
				success = success and self._store_recipients(cr, surveys)				
				cr.commit()

			except Exception as e:
				success = False
				self._notify(cr, _(f"Something failed: {e}"), "danger", True)				
				
			if success: self._notify(cr, _("Importation process successfully completed!"), "success", True)
			else: self._notify(cr, _("Importation process completed with some errors."), "warning", True)
			# finally:
			# 	# NOTE: otherwise the notifications ren't sent
			# 	new_cr.commit()

	def _store_recipients(self, cr, surveys):
		# TODO: current items should be deleted (not just unlinked), but this should not happen till a complete refresh...
		try:
			recipients = [[5]]
			for key in surveys:
				for r in surveys[key]["recipients"]:
					recipients.append([0, 0, {
						"name": r["firstname"],
						"email": r["email"],
						"internal_id": key,
						"external_id": surveys[key]["external_id"]
					}])

			self.write({
				"limesurvey_recipient_ids": recipients
			})

			return True
		except Exception as e:
			self._notify(cr, _(f"Something failed when trying to store recipients and survey IDs correlation: {e}"), "danger", True)			
			return False

	def _upload_recipients(self, cr, surveys):			
		success = True
		for key in surveys:
			id = surveys[key]["external_id"]
			recipients = surveys[key]["recipients"]
			resultados = self._run_api_request("add_participants", [id, recipients])
			
			errors = []
			for index, row in enumerate(resultados):
				if isinstance(row, dict) and "error" in row:
					errors.append(f"- '{recipients[index]['firstname']}' with email '{recipients[index]['email']}': {row['error']}")

			if len(errors) == 0:
				self._notify(cr, _(f"Recipients succesfully added to the survey with external ID: {id}"), "info", False)
				
			else:
				success = False
				self._notify(cr, Markup(_(f"Some recipients failed on adding to the survey with external ID: {id}<br>" + "<br>".join(errors))), "danger", True)				
		return success

	def _upload_surveys(self, cr, surveys, gsid):		
		success = True
		for key in surveys:			
			data = base64.b64encode(surveys[key]["raw_tsv"].encode('utf-8')).decode('utf-8')
			id = self._run_api_request("import_survey", [data, "txt"])
			
			if isinstance(id, int) or (isinstance(id, str) and id.isdigit()):				
				# TODO: importing via XML allows to set the GSID, would be nice to reduce the amount of calls to the API (is slow)!
				surveys[key]["external_id"] = id
				self._run_api_request("set_survey_properties", [id, {"gsid": gsid}])	
				self._run_api_request("activate_tokens", [id, [0]])
				self._notify(cr, _(f"Survey succesfully imported with external ID: {id}"), "info", False)
			else:
				success = False
				self._notify(cr, _(f"Unable to import the survey with internal ID: {surveys[key]['internal_id']}"), "danger", True)				
		return success

	def _compute_survey_data(self, student, level, only_key):
		name = f" | {self.name}_{level.acronym}"
		if not only_key:
			content = self.tsv_raw_text
			#content = content.replace("{'SID'}", "str(key)") # it's better to set it automatically and relate it with our hash internally
			#content = content.replace("{'GSID'}", str(gsid)) # ignored by the import engine using TSV... should we change to XML import?
			content = content.replace("{'TITLE'}", self.title)
			content = content.replace("{'DESCRIPTION'}", self.description)

		for block in self.limesurvey_block_ids:
			append = not block.special
			if block.special:
				if block.special_course_filter == 0 or (block.special_course_filter > 0 and block.special_course_filter == student.main_group_id.course):
					# NOTE: special_course can be combined with WPI or Subject.
					if not block.special_subject_enrolled and not block.special_wpi_enrolled: append = True	# Just course filter							
					elif block.special_wpi_enrolled and student.wpi_enrolled: append = True
					elif block.special_subject_enrolled:
						# NOTE: Repeat the block for every enrolled subject.
						for enroll in student.enrollment_ids:
							name += f" | {block.name}_{enroll.subject_id.code}_{enroll.group_id.acronym}"
							if not only_key:
								tmp = block.tsv_raw_text
								tmp = tmp.replace("{'X'}", enroll.subject_id.code)
								tmp = tmp.replace("{'TITLE'}", block.name)
								tmp = tmp.replace("{'LEVEL'}", level.acronym)
								tmp = tmp.replace("{'TOPIC'}", block.name)
								tmp = tmp.replace("{'S_CODE'}", enroll.subject_id.code)
								tmp = tmp.replace("{'S_NAME'}", enroll.subject_id.name)
								tmp = tmp.replace("{'DEGREE'}", student.study_id.acronym)
								tmp = tmp.replace("{'GROUP'}", enroll.group_id.acronym)

								teachings = self.env["ems.teaching"].search([("group_id", "=", enroll.group_id.id), ("subject_id", "=", enroll.subject_id.id)], order="teacher_id asc") or False
								teachers_names = "UNKNOWN" if not teachings else ", ".join(teachings.mapped("teacher_id.name"))
								tmp = tmp.replace("{'TRAINER'}", teachers_names)
								content += tmp
			if append:
				name += f" | {block.name}"	
				if not only_key:
					tmp = block.tsv_raw_text
					tmp = tmp.replace("{'TITLE'}", block.name)
					tmp = tmp.replace("{'LEVEL'}", level.acronym)
					tmp = tmp.replace("{'TOPIC'}", block.name)
					tmp = tmp.replace("{'S_CODE'}", block.name) # NOTE: this is not a mistake, the block name (topic) is used here also.
					tmp = tmp.replace("{'S_NAME'}", block.name) # NOTE: this is not a mistake, the block name (topic) is used here also.
					tmp = tmp.replace("{'DEGREE'}", student.study_id.acronym)
					tmp = tmp.replace("{'GROUP'}", student.main_group_id.acronym)
					tmp = tmp.replace("{'TRAINER'}", "")
					content += tmp
		
		return {
			"key": hash(name), 
			"raw_tsv": None if only_key else content
		}

	def _setup_students_surveys(self):
		surveys = dict()
		for level in self.level_ids:
			# NOTE: Students without main group should be skipped, because they're not already enrolled (or have been resgined).
			students = self.env["res.partner"].search([("level_id", "=", level.id), ("main_group_id", "!=", False)])			
			for student in students:
				# NOTE: Computing just the key and then, if needed, the survey data, boosts the performance in about 81,3% (from an average of 1500ms to 280ms).
				#		The same method is used in order to share the code (in order to compute the key, the same items used to compute the content are used in the same way).
				key = self._compute_survey_data(student, level, True)["key"]
				recipient = {
					# NOTE: those fields are required by LimeSurvey in order to add recipients to the survey. 
					"email": student.student_email,
					"firstname": student.name,
					"lastname": ""
				}
				if key in surveys: surveys[key]["recipients"].append(recipient)
				else: 
					surveys[key] = {
						"recipients": [recipient],
						"raw_tsv": self._compute_survey_data(student, level, False)["raw_tsv"]
					}					
		return surveys	

	def _setup_teachers_surveys(self):
		fake = 0

	def _setup_asp_surveys(self):
		fake = 0

	def _run_api_request(self, method, params=[]):
		self.ensure_one()
				
		headers = {'content-type': 'application/json'}
		session_key = self._get_session_key(headers)

		if not session_key:
			raise UserError(_("Unable to get the LimeSurvey's session key."))
		
		try:
			session = [session_key]
			payload = {
                "method": method,
                "params": [*session, *params], 
                "id": 1
            }
			
			response = requests.post(self.env.company.limesurvey_api, data=json.dumps(payload), headers=headers)
			if response.status_code != 200:
				raise UserError(f"LimeSurvey API call error: {response.reason} \n\n {self._extract_limesurvey_html_error(response.text)}")
			elif response.json().get('error'):
				raise UserError(f"LimeSurvey API call error:  {response.json().get('error')}")
			
			result = response.json().get('result')
			if result is None:
				raise UserError(f"LimeSurvey API call error: unkown (maybe permissions?)")
			return result			

		except UserError as ue:
			raise ue
		except Exception as e:
			raise UserError(f"Unexpected error: {str(e)}")
			
		finally:
			self._release_session_key(session_key, headers)

	def _extract_limesurvey_html_error(self, html_content):		
		match = re.search(r'<h2[^>]*class="error-title"[^>]*>(.*?)</h2>', html_content, re.IGNORECASE | re.DOTALL)
		
		if match:
			raw_text = match.group(1)			
			clean_text = " ".join(raw_text.split())			
			final_text = html.unescape(clean_text)			
			return final_text
			
		return html_content

	def _get_ems_group(self):
		result = self._run_api_request("list_survey_groups", [None])		
		group_found = False if result is None else next((g for g in result if g['name'] == "EMS"), None)
		return None if not group_found else group_found	

	def _get_session_key(self, headers):
		payload = {
			"method": "get_session_key",
			"params": [self.env.company.limesurvey_usr, self.env.company.limesurvey_pwd],
			"id": 1
		}
		response = requests.post(self.env.company.limesurvey_api, data=json.dumps(payload), headers=headers)
		return response.json().get('result')
	
	def _release_session_key(self, session_key, headers):		
		payload = {
			"method": "release_session_key",
			"params": [session_key],
			"id": 1
		}
		requests.post(self.env.company.limesurvey_api, data=json.dumps(payload), headers=headers)
class ems_limesurvey_block(models.Model):
	_name = "ems.limesurvey_block"
	_description = "LimeSurvey block: contains the main data about a LimeSurvey's session block."
	_order = 'sort, id'
	_inherit = ['ems.base']
	
	name = fields.Char(string="Name", required=True)
	tsv_raw_text = fields.Text(string="Block's content (tab separated)", required=True)
	limesurvey_header_id = fields.Many2one(string="Survey", comodel_name="ems.limesurvey_header")
	sort = fields.Integer(string="Sort", default=1)
	special = fields.Boolean(string="Special behaviour", default=False)
	special_course_filter = fields.Integer(string="Course", default=0)
	special_wpi_enrolled = fields.Boolean(string="WorkPlace Intership (if enrolled)", default=False)
	special_subject_enrolled = fields.Boolean(string="Subject (all enrolled)", default=False)
	notes = fields.Text(string="Notes")	

	@api.onchange("special_wpi_enrolled", "special_subject_enrolled")
	def _onchange_special(self):	
		for rec in self:	
			# TODO: mutually excluded, check if it's more appropiate to use radios instead of checkboxes.
			if rec.special_wpi_enrolled: rec.special_subject_enrolled = False
			elif rec.special_subject_enrolled: rec.special_wpi_enrolled = False
class ems_limesurvey_recipient(models.Model):
	_name = "ems.limesurvey_recipient"
	_description = "LimeSurvey recipient: contains the relation between a recipient and its survey."
	_inherit = ['ems.base']
	
	limesurvey_header_id = fields.Many2one(string="Survey", comodel_name="ems.limesurvey_header")
	name = fields.Char(string="Name", required=True)
	email = fields.Char(string="Email", required=True)
	external_id = fields.Char(string="External ID (LimeSurvey)", required=True)
	internal_id = fields.Char(string="Internal ID (EMS)", required=True)
	
	