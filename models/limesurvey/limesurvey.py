# -*- coding: utf-8 -*-

import requests, json, html, re, base64, threading, psycopg2, time
from odoo import models, fields, api, registry, _
from odoo.exceptions import UserError

survey_target_selection = [("students", "Students"), ("teachers", "Teachers"), ("asp", "ASP")]

# NOTE: this class contains the method to call the LimeSurvey's API. Is used by "header" and "recipients" models. 
class limesurvey_api():
	def import_survey(self, raw_tsv):		
		data = base64.b64encode(raw_tsv.encode('utf-8')).decode('utf-8')
		result  = self._run_api_request("import_survey", [data, "txt"])
		
		if isinstance(result, int) or (isinstance(result, str) and result.isdigit()): return result
		else: raise Exception(_("Unable to upload the survey.") + result)

	def set_survey_properties(self, survey_id, gsid):
		# TODO: check result for errors		
		return self._run_api_request("set_survey_properties", [survey_id, {"gsid": gsid}])

	def activate_tokens(self, survey_id):
		# TODO: check result for errors		
		return self._run_api_request("activate_tokens", [survey_id, [0]])

	def add_participants(self, survey_id, recipients):
		#errors = False		
		participants = list(map(lambda x: {k: x[k] for k in ['email', 'firstname', 'lastname']}, recipients))		
		return self._run_api_request("add_participants", [survey_id, participants])

		# TODO: could we return directly "result"?	
		
		# for index, row in enumerate(result):
		# 	if "error" in row:
		# 		recipients[index]["error"] = row["error"]
		# 		errors = True
		# 	else:
		# 		recipients[index]["token"] = row["token"]
		# 		recipients[index]["tid"] = row["tid"]
		
		# if errors:
		# 	raise Exception(_("Unable to upload some participants to the survey."))

	def delete_participants(self, survey_id, participant_ids):		
		error = _("Unable to delete some participants")
		result = self._run_api_request("delete_participants", [survey_id, participant_ids])
		if "2" in result: raise Exception(f"{error}: " + result["2"] )
		elif "1" in result and result["1"] != "Deleted": raise Exception(f"{error}: " + result['1'] )
		elif not "1" in result: raise Exception(f"{error}: " + "UNKWOWN ERROR!")

	def set_participant_properties(self, survey_id, participant_id, participant_data):			
		error = _("Unable to update some participants")
		result = self._run_api_request("set_participant_properties", [survey_id, participant_id, participant_data])

		if "error" in result: raise Exception(f"{error}: " + result["error"])
		elif not "emailstatus" in result: raise Exception(f"{error}: " + result["status"])
		elif result["emailstatus"] != "OK": raise Exception(f"{error}: " + result["emailstatus"])

	def list_participants(self, survey_id):			
		error = _("Unable to count the recipients")
		result = self._run_api_request("list_participants", [survey_id])
		if "status" in result:
			if result["status"] == "No permission":	raise Exception(f"{error}: " + result["status"])				
			elif result["status"] == "No survey participants found.": return 0
			else: return len(result["status"])
		else:
			raise Exception(f"{error}: UNKWONW ERROR!")
		
	def delete_survey(self, survey_id):
		error = _("Unable to delete the survey")
		result = self._run_api_request("delete_survey", [survey_id])
		if "status" in result:
			if result["status"] == "No permission":			
				# Deleted ones appears as "no permissions", checking if exists or not...
				result = self._run_api_request("get_survey_properties", [survey_id])
				if not "status" in result: raise Exception(f"{error}: No permission.")
			elif result["status"] != "OK":
				raise Exception(f"{error}: {result["status"]}")
		else:
			raise Exception(f"{error}: UNKWONW ERROR!")
		
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
class ems_limesurvey_header(models.Model):
	_name = "ems.limesurvey_header"
	_description = "LimeSurvey header: contains the survey's header and its content."
	_inherit = ['ems.base', 'mail.thread', 'mail.activity.mixin']
	
	# NOTE: this field is used to track the wizard progress.
	state = fields.Selection(string='Status', selection=[
        ('draft', 'Draft'),
		('uploading', 'Uploading surveys'),
        ('uploaded', 'Surveys uploaded'),
        ('open', 'Surveys open'),
        ('closed', 'Surveys closed'),
		('downloaded', 'Data downloaded')
    ], default='draft')

	name = fields.Char(string="Name", required=True)
	title = fields.Char(string="Title", required=True)
	description = fields.Char(string="Description", required=True)
	target = fields.Selection(string="Target", selection=survey_target_selection, required=True)
	level_ids = fields.Many2many(string="Level", comodel_name="ems.level")
	tsv_raw_text = fields.Text(string="Header's content (tab separated)", required=True)
	limesurvey_block_ids = fields.One2many(string="Blocks", comodel_name="ems.limesurvey_block", inverse_name="limesurvey_header_id")
	limesurvey_recipient_ids = fields.One2many(string="Recipients", comodel_name="ems.limesurvey_recipient", inverse_name="limesurvey_header_id")	
	notes = fields.Text(string="Notes")
	is_running = fields.Boolean(string="Running", default=False)

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

	def _notify(self, title, message, type, sticky=False):
		self.env["bus.bus"]._sendone(
			self.env.user.partner_id, "simple_notification", {
				"title": title, 
				"message": message, 
				"type": type,
				"sticky": sticky
			}
		)
				
	def _chatter(self, message):
		self.message_post(
            body = message,
            message_type = 'notification',
            subtype_xmlid='mail.mt_note'
        )	
	
	def _run_in_thread(self, func, max_retries=5, *args, **kwargs):
		uid = self.env.uid
		dbname = self.env.cr.dbname
		context = dict(self.env.context)
		record_ids = self.ids 
		model_name = self._name
			
		def _threaded_worker():
			db_registry = registry(dbname)
			changes = {}

			for current_try in range(max_retries):
				try:					
					with db_registry.cursor() as cr:
						env = api.Environment(cr, uid, context)
						n_self = env[model_name].browse(record_ids)
						func(n_self, changes, *args, **kwargs)
						break

				except psycopg2.errors.SerializationFailure:
					if current_try == max_retries: raise
					time.sleep(current_try)								
		
		thread = threading.Thread(target=_threaded_worker)
		thread.start()
		return thread
	
	def action_prev(self):
		for rec in self:			
			if not rec._already_running():
				rec.is_running = True
				if rec.state == 'uploaded':				
					rec.state = 'uploading'
					return rec._action_draft()								

	def action_next(self):
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
		for rec in self:			
			if not rec._already_running():
				rec.is_running = True
				if rec.state == 'draft':				
					rec.state = 'uploading'
					return rec._action_import()
				
				elif rec.state == 'uploaded':				
					rec.state = 'open'
					
				elif rec.state == 'open':				
					rec.state = 'closed'
					
				elif rec.state == 'closed':
					rec.state = 'downloaded'

				elif rec.state == 'downloaded':
					rec.state = 'draft'			

	def _already_running(self):
		if self.is_running:
			self._notify(_("LimeSurvey: already running"), _("Process already running, maybe by another user?"), "danger")		
		return self.is_running

	def _action_draft(self):		
		title = _("LimeSurvey: return to draft")
		message = _("Starting process in the background, you'll be notified on completion (it can take a while).")
		self._notify(title, message, "info")
		self.state = 'uploading'
		self.is_running = True

		def code(self, changes):
			success = True
			errors = []
			survey_ids = list(set(self.limesurvey_recipient_ids.mapped('external_id')))				
			for sid in survey_ids:
				try:					
					key = f"_delete_survey_single_{sid}"
					if not changes.get(key, False):
						self._delete_survey_single(sid)
						changes[key] = True
					for rec in self.limesurvey_recipient_ids.search([("external_id", "=", sid)]):
						# NOTE: We could remove all the entries at the end, but this ensure removing the entries only if the survery has been deleted in LimeSurvey.
						#		Slower but more scure. 
						rec.unlink()

				except Exception as e:
					success = False
					errors.append(f"Unable to remove the survey with external ID '{sid}'. {e}")

			title = _("LimeSurvey: upload surveys")
			if success:
				self.state = 'draft'
				self._notify(title, _("Return to draft process successfully completed!"), "success")	
				self._chatter(_("Return to draft: success"))
			else:
				details = "\n".join(str(e) for e in errors)
				self._notify(title, _("Return to draft process failed.") +  f" -> {details}", "warning")	
				self._chatter(_("Return to draft: with errors") + f" -> {details}")
			
			#NOTE: because this is running in another thread, a message will be sent to the client in order to load new data (see also "form_reload.js").			
			self.is_running = False
			self.reload_request()
		
		self._run_in_thread(code)
		return True
	
	def _action_import(self):
		ems_grp = self._get_ems_group()
		if not ems_grp:
			#NOTE: The LimeSurvey's API does not allow to create groups.
			raise UserError(_("LimeSurvey's EMS group not found. We're sorry, but the LimeSurvey API v6 does not allow to create survey groups. Please, use the EMS user to crate a survey group called 'EMS' and try again; the EMS will use this group in order to generate all the surveys."))		
		
		title = _("LimeSurvey: upload surveys")
		message = _("Starting process in the background, you'll be notified on completion (it can take a while).")
		self._notify(title, message, "info")

		if(self.target == "students"): surveys = self._setup_students_surveys()
		elif(self.target == "teachers"): surveys = self._setup_teachers_surveys()
		elif(self.target == "asp"): surveys = self._setup_asp_surveys()
			
		def code(self, changes):
			success = True
			exception = None
			try:				
				def upload_recipients(success):
					key = f"_upload_recipients_multi"
					if not changes.get(key, False):
						success = success and self._upload_recipients_multi(surveys)
						changes[key] = True
					return success

				key = f"_upload_surveys_multi"
				if not changes.get(key, False):
					success = self._upload_surveys_multi(surveys, ems_grp["gsid"])
					if success:
						changes[key] = True					
						# If not success, every row will contain the error detail
						# If not, we don't want to upload recipients. 
						success = success and upload_recipients(success)
				
				key = f"_upload_recipients_multi"
				if success and not changes.get(key, False):
					# We came from a retry with _upload_surveys_multi but no _upload_recipients_multi
					success = success and upload_recipients(success)

				# Always must try to save the recipients record (works like a log).
				self._store_recipients_multi(surveys)
				self.state = 'uploaded'
			except Exception as e:
				success = False
				exception = e
			finally:
				title = _("LimeSurvey: upload surveys")
				error = _("check the recipients entry for more details") if exception is None else exception	
				message = _("Importation process successfully completed!") if success else (_("Importation process failed.") +  f" -> {error}")
				self._notify(title, message, "success" if success else "warning")						
				self._chatter(_("Surveys upload: ") + (_("success") if success else (_("with errors") + f" -> {error}")))
				
				#NOTE: because this is running in another thread, a message will be sent to the client in order to load new data (see also "form_reload.js").
				self.is_running = False
				self.reload_request()		
		
		self._run_in_thread(code)
		return True
		
	def _upload_surveys_multi(self, surveys, gsid):		
		success = True
		for key in surveys:			
			try:
				self._upload_survey_single(surveys[key], gsid)				
			except Exception as e:
				success = False
				for r in surveys[key]["recipients"]:
					r["error"] = str(e)

		return success
	
	def _upload_survey_single(self, survey, gsid):		
		data = base64.b64encode(survey["raw_tsv"].encode('utf-8')).decode('utf-8')
		id = self._run_api_request("import_survey", [data, "txt"])
		
		if isinstance(id, int) or (isinstance(id, str) and id.isdigit()):				
			# TODO: importing via XML allows to set the GSID, would be nice to reduce the amount of calls to the API (is slow)!
			survey["external_id"] = id
			self._run_api_request("set_survey_properties", [id, {"gsid": gsid}])	
			self._run_api_request("activate_tokens", [id, [0]])
		else:
			raise Exception(_("Unable to import the survey with internal ID: ") + f"{survey['internal_id']}")
		
	def _upload_recipients_multi(self, surveys):			
		success = True
		for key in surveys:
			try:
				self._upload_recipient_single(surveys[key])							
			except Exception as e:
				success = False

		return success
	
	def _upload_recipient_single(self, survey):			
		id = survey["external_id"]
		recipients = survey["recipients"]
					
		errors = False		
		participants = list(map(lambda x: {k: x[k] for k in ['email', 'firstname', 'lastname']}, recipients))		
		result = self._run_api_request("add_participants", [id, participants])
						
		for index, row in enumerate(result):
			if isinstance(row, dict) and "error" in row:
				recipients[index]["error"] = row["error"]
				errors = True
			else:
				recipients[index]["token"] = row["token"]
				recipients[index]["tid"] = row["tid"]
		
		if errors:
			raise Exception(_("Unable to upload some recipients to the survey with internal ID: ") + f"{survey['internal_id']}.")
	
	def _store_recipients_multi(self, surveys):		
		for key in surveys:
			self._store_recipients_single(surveys[key])
	
	def _store_recipients_single(self, survey, recipients = None):
		if recipients is None:
			# NOTE: defaulting recipients to [] causes that comes with data when called from _store_recipients_multi
			recipients = []
			
		try:
			for r in survey["recipients"]:	
				error = False if r["error"] is None else r["error"]						
				recipients.append([0, 0, {
					"name": r["firstname"],
					"email": r["email"],
					"token": r["token"],
					"tid": r["tid"],
					"student_id": r["student_id"].id if r["student_id"] is not None else False,
					"teacher_id": r["teacher_id"].id if r["teacher_id"] is not None else False,
					"asp_id": r["asp_id"].id if r["asp_id"] is not None else False,
					"internal_id": survey["internal_id"],
					"external_id": survey["external_id"],
					"status": "success" if not error else "error",
					"error": r["error"] ,										
				}])

			self.write({
				"limesurvey_recipient_ids": recipients
			})	
		except Exception as e:
			raise Exception(_("Unable to store the 'recipent x survey' assignation: ") + str(e))

	def _delete_recipients_single(self, survey_id, part_ids):		
		error = _("Unable to delete the recipient from the current survey: ")
		result = self._run_api_request("delete_participants", [survey_id, part_ids])
		if "2" in result:	
			raise Exception(error + result["2"] )				
		elif "1" in result and result["1"] != "Deleted":			
			raise Exception(error + result['1'] )
		elif not "1" in result:
			raise Exception(error + "UNKWOWN ERROR")

	def _update_recipient_single(self, survey):			
		id = survey["external_id"]
		recipients = survey["recipients"]
					
		errors = False		
		tid = recipients[0]["tid"]
		data = list(map(lambda x: {k: x[k] for k in ['email', 'firstname', 'lastname']}, recipients))[0]
		result = self._run_api_request("set_participant_properties", [id, tid, data])

		errors = True
		if "error" in result: result["error"] = result["error"]			
		elif "emailstatus" in result:
			if result["emailstatus"] == "OK": errors = False
			else: result["error"] = result["emailstatus"]
		else: result["error"] = result["status"]
		
		if errors:
			raise Exception(_("Unable to update some recipients to the survey with internal ID: ") + f"{survey['internal_id']}.")
		
	def _count_recipient_single(self, survey_id):			
		error = _("Unable to count the recipients")
		result = self._run_api_request("list_participants", [survey_id])
		if isinstance(result, dict) and 'status' in result:
			if result['status'] == "No permission":							
				raise Exception(f"{error}: No permission")				
			elif result['status'] == "No survey participants found.":
				return 0
			else:
				# TODO: test this
				return len(result['status'])
		else:
			raise Exception(f"{error}: unkwown error.")
		
	def _delete_survey_single(self, survey_id):
		error = _("Unable to delete the survey")
		result = self._run_api_request("delete_survey", [survey_id])
		if isinstance(result, dict) and 'status' in result:
			if result['status'] == "No permission":			
				# Deleted ones appears as "no permissions", checking if exists or not...
				result = self._run_api_request("get_survey_properties", [survey_id])
				if not (isinstance(result, dict) and 'status' in result):
					raise Exception(f"{error}: No permission")
				
			elif result['status'] != "OK":
				raise Exception(f"{error}: {result['status']}")
		else:
			raise Exception(f"{error}: unkwown error.")

	def _compute_survey_data(self, student, only_key):
		name = f"{self.name}_{student.level_id.acronym}"
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
								teachings = self.env["ems.teaching"].search([("group_id", "=", enroll.group_id.id), ("subject_id", "=", enroll.subject_id.id)], order="teacher_id asc") or False
								teachers_names = "UNKNOWN" if not teachings else ", ".join(teachings.mapped("teacher_id.name"))
								tmp = self._replace_block_content(block.tsv_raw_text, block.name, student.level_id.acronym, enroll.subject_id.code, enroll.subject_id.name, student.study_id.acronym, enroll.group_id.acronym, teachers_names)
								tmp = tmp.replace("{'X'}", enroll.subject_id.code)								
								content += tmp
			if append:
				name += f" | {block.name}"	
				if not only_key:
					content += self._replace_block_content(block.tsv_raw_text, block.name, student.level_id.acronym, block.name, block.name, student.study_id.acronym, student.main_group_id.acronym)					
		
		return {
			"internal_id": self.persistent_hash(name), 
			"raw_tsv": None if only_key else content
		}

	def _replace_block_content(self, content, b_name, l_acro, s_code, s_name, d_acro, g_acro, trainer=""):
		content = content.replace("{'TITLE'}", b_name)
		content = content.replace("{'TOPIC'}", b_name)
		content = content.replace("{'LEVEL'}", l_acro)		
		content = content.replace("{'S_CODE'}", s_code) # NOTE: this is not a mistake, the block name (topic) is used here also.
		content = content.replace("{'S_NAME'}", s_name) # NOTE: this is not a mistake, the block name (topic) is used here also.
		content = content.replace("{'DEGREE'}", d_acro)
		content = content.replace("{'GROUP'}", g_acro)
		content = content.replace("{'TRAINER'}", trainer)
		return content

	def _setup_students_surveys(self):
		surveys = dict()
		for level in self.level_ids:
			# NOTE: Students without main group should be skipped, because they're not already enrolled (or have been resgined).
			students = self.env["res.partner"].search([("level_id", "=", level.id), ("main_group_id", "!=", False)])			
			for student in students:
				# NOTE: Computing just the key and then, if needed, the survey data, boosts the performance in about 81,3% (from an average of 1500ms to 280ms).
				#		The same method is used in order to share the code (in order to compute the key, the same items used to compute the content are used in the same way).
				key = self._compute_survey_data(student, True)["internal_id"]
				recipient = self._setup_student_recipient(student)
				if key in surveys: surveys[key]["recipients"].append(recipient)
				else: 
					surveys[key] = {
						"internal_id": key,
						"recipients": [recipient],
						"raw_tsv": self._compute_survey_data(student, False)["raw_tsv"]
					}					
		return surveys	
	
	def _setup_student_recipient(self, student):		
		return {
			"email": student.student_email,
			"firstname": student.name,
			"lastname": "",
			"token": None,
			"student_id": student,
			"teacher_id": None,
			"asp_id": None,
			"error": None
		}

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
	
	limesurvey_header_id = fields.Many2one(string="Survey", comodel_name="ems.limesurvey_header", required=True)
	name = fields.Char(string="Name", required=True)
	email = fields.Char(string="Email", required=True)
	external_id = fields.Char(string="Survey's ID (LimeSurvey)")
	internal_id = fields.Char(string="Survey's ID (EMS)")
	token = fields.Char(string="User's token (LimeSurvey)")
	tid = fields.Integer(string="User's ID (LimeSurvey)")
	status = fields.Selection(string='Status', selection=[('pending', 'Pending'), ('success', 'Success'), ('error', 'Error')], default='pending')
	error = fields.Char(string="Error details")

	# The recipients can be students (res_partner) or teachers/asp (hr.employee). Those are needed in order to refresh the data.
	student_id = fields.Many2one(string="Student", comodel_name="res.partner")
	teacher_id = fields.Many2one(string="Teacher", comodel_name="hr.employee")
	asp_id = fields.Many2one(string="ASP", comodel_name="hr.employee")
	
	def open_error_popup(self):
		self.ensure_one()
		return {
			'type': 'ir.actions.act_window',
			'name': 'Error details',
			'res_model': self._name,
			'res_id': self.id,
			'view_mode': 'form',
			'view_id': self.env.ref('ems.view_limesurvey_recipient_error_popup').id,
			'target': 'new', 
			'flags': {'mode': 'readonly'}
		}
	
	def refresh(self):
		# TODO: check refresh when the enrolled changed, empty surveys should be removed.
		# TODO: improve LS methods, input methods (easier) and respose check (errors, etc.).

		self.ensure_one()
		if self.student_id:
			title = _("LimeSurvey: refresh recipient")
			internal_id = self.limesurvey_header_id._compute_survey_data(self.student_id, True)["internal_id"]
			existing = self.env["ems.limesurvey_recipient"].search([("internal_id", "=", internal_id)], limit=1) or False
			if existing:
				survey = { 
					# NOTE: this is the basic survey data to work, more data will be added if needed
					"external_id": existing["external_id"],
					"internal_id": existing["internal_id"],
				}
			
			try:
				if internal_id == self.internal_id:				
					# The recipient is in the correct survey, checking if its name or email changed:
					if self.name == self.student_id.name and self.email == self.student_id.student_email:
						self.limesurvey_header_id._notify(title, _("Everything is up to date (nothing to resfresh)."), "info")
					else:
						reci = self.limesurvey_header_id._setup_student_recipient(self.student_id)
						reci["tid"] = self.tid
						
						survey["recipients"] = [reci]
						self.limesurvey_header_id._update_recipient_single(survey)
						self._completed(title)

				else:								
					self.limesurvey_header_id._notify(title, _("Refreshing the student's survey..."), "info")		
					if not existing:					
						# Uploading the survey if is a new one
						ems_grp = self.limesurvey_header_id._get_ems_group()
						survey = self.limesurvey_header_id._compute_survey_data(self.student_id, False)
						self.limesurvey_header_id._upload_survey_single(survey, ems_grp["gsid"])					
					
					# The recipients must be uploaded always (for new or existing one)
					old_survey_id = self.external_id
					survey["recipients"] = [self.limesurvey_header_id._setup_student_recipient(self.student_id)]
					self.limesurvey_header_id._upload_recipient_single(survey)					
					self.limesurvey_header_id._store_recipients_single(survey)
										
					# Remove from the old survey
					self.limesurvey_header_id._delete_recipients_single(self.external_id, [self.tid])
					count = self.limesurvey_header_id._count_recipient_single(old_survey_id)
					if(count == 0):
						self.limesurvey_header_id._delete_survey_single(old_survey_id)

					# TODO: if something fails, resotre the LimeSurvey status	
					self._completed(title)

					# NOTE: removing the entry must be the last step (otherwise any access to 'self' fails).
					self.unlink()

			except Exception as e:
				self.limesurvey_header_id._notify(title, _("Refresh process failed."), "warning")						
				self.limesurvey_header_id._chatter(_(f"Refresh for '{self.email}': ") + (_("with errors") + f" -> {e}"))

	def _completed(self, title):
		self.limesurvey_header_id._notify(title, _("Refresh process successfully completed!"), "success")
		self.limesurvey_header_id._chatter(_(f"Refresh for '{self.email}': ") + _("success"))