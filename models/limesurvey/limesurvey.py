# -*- coding: utf-8 -*-

import requests, json, html, re, base64, time
from datetime import datetime
from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError

# TO CLEAN THE BBDD DURING TESTING
# delete from ems_limesurvey_recipient;
# update ems_limesurvey_header elh set state='draft' where elh.id=1;
# update ems_limesurvey_header elh set is_running=false where elh.id=1;
# DELETE FROM mail_message WHERE model = 'ems.limesurvey_header';

survey_target_selection = [("students", "Students"), ("teachers", "Teachers"), ("asp", "ASP")]

# NOTE: This class contains the method to call the LimeSurvey's API. Is used by "header" and "recipients" models. 
#		To avoid confussion: participants -> LimeSurvey; recipients -> EMS. 
class limesurvey_api():
	def __init__(self, env):
		self.env = env

	def create_survey(self, gsid, raw_tsv):		
		data = base64.b64encode(raw_tsv.encode('utf-8')).decode('utf-8')
		result  = self._run_api_request("import_survey", [data, "txt"])
		
		if isinstance(result, int) or (isinstance(result, str) and result.isdigit()): 
			try:
				self._run_api_request("set_survey_properties", [result,  {"gsid": gsid}])
				self._run_api_request("activate_tokens", [result, [0]])
				return result
			except:
				self.delete_survey(result)
				raise			
		else: 			
			raise Exception(f"{_('Unable to create the survey.')} {result}")
	
	def add_participants(self, survey_id, participants):
		# TODO: errors?				
		return self._run_api_request("add_participants", [survey_id, participants])		

	def delete_participants(self, survey_id, participant_ids):		
		error = _("Unable to delete some participants")
		result = self._run_api_request("delete_participants", [survey_id, participant_ids])
		values = list(result.values())

		# Trying to delete something that does not exists, is not an error for us (maybe it's a retry).
		if not "Deleted" in values and not "Invalid token ID" in values:
			raise Exception(f"{error}: " + " | ".join(values))

	def update_participant_data(self, survey_id, participant_id, participant_data):			
		error = _("Unable to update some participants")
		result = self._run_api_request("set_participant_properties", [survey_id, participant_id, participant_data])

		if "error" in result: raise Exception(f"{error}: " + result["error"])
		elif not "emailstatus" in result: raise Exception(f"{error}: " + str(result["status"]))
		elif result["emailstatus"] != "OK": raise Exception(f"{error}: " + result["emailstatus"])

	def list_participants(self, survey_id):	
		# TODO: errors?		
		return self._run_api_request("list_participants", [survey_id])
	
	def count_participants(self, survey_id):	
		list = 	self.list_participants(survey_id)
		if "status" in list and list["status"] == "No survey participants found.": return 0
		else: return len(list)
		
	def delete_survey(self, survey_id):
		error = _("Unable to delete the survey")
		result = self._run_api_request("delete_survey", [survey_id])
		if "status" in result:
			if result["status"] == "No permission":			
				# Deleted ones appears as "no permissions", checking if exists or not...
				result = self._run_api_request("get_survey_properties", [survey_id])
				if not "status" in result: raise Exception(f"{error}: No permission.")
			elif result["status"] != "OK":
				raise Exception(f"{error}: {result['status']}")
		else:
			raise Exception(f"{error}: UNKWONW ERROR!")
	
	def get_group(self, name):
		result = self._run_api_request("list_survey_groups", [None])		
		group_found = False if result is None else next((g for g in result if g['name'].lower() == name), None)
		return None if not group_found else group_found	

	def activate_survey(self, survey_id):
		error = _("Unable to activate the survey")
		try:
			self._run_api_request("set_survey_properties", [survey_id,  {"expires": None, "startdate": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}])		
			result  = self._run_api_request("activate_survey", [survey_id])	
			if "status" not in result:
				raise Exception(f"{error}: {result}")
			if "status" in result and result["status"] not in ("OK", "Error: Survey already active"):
				raise Exception(f"{error}: {result['status']}")			
		except Exception as e: 			
			raise Exception(f"{error}: {e}")
		
	def invite_participants(self, survey_id):
		error = _("Unable to invite some participants")		
		try:
			for current_try in range(5):
				result  = self._run_api_request("invite_participants", [survey_id])
				if "status" not in result: raise Exception(f"{error}: " + "UNKWOWN ERROR!")
				elif result["status"] in ("0 left to send", "Error: No candidate tokens"): break
				else: time.sleep(15*(current_try))
		except Exception as e:
			raise Exception(f"{error}: {e}")

	def remind_participants(self, survey_id, part_ids=None):
		error = _("Unable to invite some participants")		
		try:
			data = [survey_id]
			if part_ids is not None: data.append(part_ids)

			for current_try in range(5):
				result  = self._run_api_request("remind_participants", [survey_id])
				if "status" not in result: raise Exception(f"{error}: " + "UNKWOWN ERROR!")
				elif result["status"] in ("0 left to send", "Error: No candidate tokens"): break
				else: time.sleep(15*(current_try))
		except Exception as e:
			raise Exception(f"{error}: {e}")

	def _run_api_request(self, method, params=[]):
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
class ems_limesurvey_header(models.Model):
	_name = "ems.limesurvey_header"
	_description = "LimeSurvey header: contains the survey's header and its content."
	_inherit = ['ems.base', 'ems.multithreading']
	
	# NOTE: this field is used to track the wizard progress.
	state = fields.Selection(string='Status', selection=[
        ('draft', 'Draft'),
		('computed', 'Recipients computed'),
		('removing', 'Removing surveys'),
		('uploading', 'Uploading surveys'),
        ('uploaded', 'Surveys uploaded'),
		('opening', 'Opening surveys'),
        ('open', 'Surveys open'),
		('reminding', 'Sending reminders'),
        ('closing', 'Closing surveys'),
		('closed', 'Surveys closed'),
		('downloading', 'Downloading surveys'),
		('downloaded', 'Data downloaded')
    ], default='draft', tracking=True)

	name = fields.Char(string="Name", required=True)
	title = fields.Char(string="Title", required=True)
	description = fields.Char(string="Description", required=True)
	target = fields.Selection(string="Target", selection=survey_target_selection, required=True)
	level_ids = fields.Many2many(string="Level", comodel_name="ems.level")
	study_ids = fields.Many2many(string="Studies", comodel_name="ems.study")
	group_ids = fields.Many2many(string="Groups", comodel_name="ems.group")
	tsv_raw_text = fields.Text(string="Header's content (tab separated)", required=True)
	limesurvey_block_ids = fields.One2many(string="Blocks", comodel_name="ems.limesurvey_block", inverse_name="limesurvey_header_id")
	limesurvey_recipient_ids = fields.One2many(string="Recipients", comodel_name="ems.limesurvey_recipient", inverse_name="limesurvey_header_id")	
	is_running = fields.Boolean(string="Running", default=False)
	notes = fields.Text(string="Notes")		
	
	# region MAIN ACTIONS
	def action_compute(self, title=None, message_ok=None, message_ko=None):
		self.ensure_one()

		# NOTE: there's no API integration when computing recipients, multithreading not needed
		try:	
			if title is None: title = _("LimeSurvey: compute recipients")
			if message_ok is None: message_ok = _("Recipients successfully computed!")
			if message_ko is None: message_ko =_('Recipients compute failed. ')

			# Settings up the distinct types of surveys
			if(self.target == "students"): self._compute_recipients_students()
			elif(self.target == "teachers"): self._compute_recipients_teachers()
			elif(self.target == "asp"): self._compute_recipients_asp()
						
			self.state = 'computed'
			self.notify(title , message_ok, "success")			
		except Exception as e:	
			self.chatter_exception(e)
			self.notify(title,  f"{message_ko} {e}", "warning")					
			self.env.cr.commit() # To save the messages	(previous changes have been rollbacked).		
		finally:
			return True

	def action_draft(self):
		self.ensure_one()

		# NOTE: there's no API integration when computing recipients, multithreading not needed
		try:	
			title = _("LimeSurvey: return to draft")			
			for rec in self.limesurvey_recipient_ids:
				rec.unlink()					
						
			self.state = 'draft'
			self.notify(title , _("Recipients successfully removed!"), "success")
		except Exception as e:
			self.chatter_exception(e)
			self.notify(title, f"{_('Recipients remove failed. ')} {e}", "warning")			
			self.env.cr.commit() # To save the messages	(previous changes have been rollbacked).		
		finally:
			return True

	def action_reload(self):
		return self.action_compute(_("LimeSurvey: reload recipients"), _("Recipients successfully reloaded!"), _('Recipients reload failed. '))		

	def action_upload(self):			
		if not self.env.company.limesurvey_gid:
			raise UserError(_("LimeSurvey's group ID not found. We're sorry, but the LimeSurvey API v6 does not allow to create survey groups. Please, provide a valid group ID; the EMS will use this group in order to generate all the surveys within it."))		
		
		# NOTE: The action will run in a diferent thread with retries if the commit fails. In order to avoid LS repetitions (like creating the same survey twice)
		#		this kind of calls will be executed only once, but the returned data must be persistent between retries (Odoo models rollback changes on exceptions).
		#		This is the reason because the "survey" is created here as an empty one, and shared across methods, so its data will prevail between retries. 
		surveys = {}
		
		# NOTE: pre method will be executed in the same thread as the current one
		def pre(self):
			if(self.target == "students"): self._compute_students_surveys(surveys)
			elif(self.target == "teachers"): self._compute_teachers_surveys(surveys)
			elif(self.target == "asp"): self._compute_asp_surveys(surveys)

		# NOTE: run method will be executed in a new thread (will run un the background); callback is called to notify the result and request for a front soft-update.
		def run(self, callback):					
			success = True										
			for key in surveys:
				survey = surveys[key]				
				ok = self.execute_once(self.upload_survey, f"upload_survey_{key}", survey)							
				if ok: ok = self.execute_once(self.upload_recipients, f"upload_recipients_{key}", survey["internal_id"], survey["external_id"], survey["recipients"])							
				self.store_recipients_data(survey["recipients"])
				success = ok and success																				
			callback(self, success)
				
		return self._run_action(_("LimeSurvey: upload surveys"), _("Upload"), "uploading", "uploaded", "computed", run, pre=pre)
	
	def action_remove(self):		
		def run(self, callback):					
			ls_api = limesurvey_api(self.env)
			surveys = list(set(self.limesurvey_recipient_ids.mapped("external_id")))
			for sid in surveys:							
				self.execute_once(ls_api.delete_survey, f"delete_survey_{sid}", sid)						
				for rec in self.limesurvey_recipient_ids.search([("external_id", "=", sid)]):
					rec.external_id = None
					rec.internal_id = None
					rec.tid = None
					rec.token = None
					rec.status = "pending"
			callback(self, True)
				
		return self._run_action(_("LimeSurvey: remove surveys"), _("Remove"), "removing", "computed", "uploaded", run)		
	
	def action_open(self):		
		def run(self, callback):					
			errors = []
			success = True														
			
			ls_api = limesurvey_api(self.env)
			survey_ids = list(set(self.limesurvey_recipient_ids.mapped('external_id')))	
			for sid in survey_ids:
				try:
					self.execute_once(ls_api.activate_survey, f"activate_survey_{sid}", sid)	
					self.execute_once(ls_api.invite_participants, f"invite_participants_{sid}", sid)
				except Exception as e:
					success = False
					errors.append(f"Unable to open the survey with external ID '{sid}'. {e}")					
			callback(self, success, None if len(errors) == 0 else errors)
		
		return self._run_action(_("LimeSurvey: open surveys"), _("Open"), "opening", "open", "uploaded", run)
		
	def action_close(self):		
		self.notify("Not implemented", "Comming soon...", "danger")
		return False

	def action_remind(self):
		def run(self, callback):
			errors = []
			success = True														
			
			ls_api = limesurvey_api(self.env)
			survey_ids = list(set(self.limesurvey_recipient_ids.mapped('external_id')))	
			for sid in survey_ids:
				try:
					self.execute_once(ls_api.remind_participants, f"remind_participants_{sid}", sid)
				except Exception as e:
					success = False
					errors.append(f"Unable to send reminders for the survey with external ID '{sid}'. {e}")	
			callback(self, success, None if len(errors) == 0 else errors)
		
		return self._run_action(_("LimeSurvey: send surveys"), _("Remind"), "open", "open", "reminding", run)		
	
	def action_none(self):
		return True
	# endregion	
	
	# region PUBLIC METHODS (CAN BE CALLED INDIVIDUALLY FROM A CONCRETE RECIPIENT)
	def compute_survey_data(self, recipient, only_key):
		survey_name = f"{self.name}_{recipient.level_id.acronym}"
		if not only_key:
			content = self.tsv_raw_text
			#content = content.replace("{'SID'}", "str(key)") # it's better to set it automatically and relate it with our hash internally
			#content = content.replace("{'GSID'}", str(gsid)) # ignored by the import engine using TSV... should we change to XML import?
			content = content.replace("{'TITLE'}", self.title)
			content = content.replace("{'DESCRIPTION'}", self.description)

		def replace_block_content(content, b_name, l_acro, s_code, s_name, d_acro, g_acro, trainer=""):
			content = content.replace("{'TITLE'}", b_name)
			content = content.replace("{'TOPIC'}", b_name)
			content = content.replace("{'LEVEL'}", l_acro)		
			content = content.replace("{'S_CODE'}", s_code) # NOTE: this is not a mistake, the block name (topic) is used here also.
			content = content.replace("{'S_NAME'}", s_name) # NOTE: this is not a mistake, the block name (topic) is used here also.
			content = content.replace("{'DEGREE'}", d_acro)
			content = content.replace("{'GROUP'}", g_acro)
			content = content.replace("{'TRAINER'}", trainer)
			
			if recipient.student_id:
				content = content.replace("{'RECIPIENT'}", "STUDENTS")
			elif recipient.teacher_id:
				content = content.replace("{'RECIPIENT'}", "TEACHERS")
			elif recipient.asp_id:
				content = content.replace("{'RECIPIENT'}", "ASP")
			else:
				content = content.replace("{'RECIPIENT'}", "UNKNOWN")
			return content

		# NOTE: real enrollment data is not used, because modifying the survey content should be allowed by someone without permissions, the recipient's one is used instead.
		# TODO: check behaviour with teachers and ASP
		for block in self.limesurvey_block_ids:
			append = not block.special
			if block.special:
				if block.special_course_filter == 0 or (block.special_course_filter > 0 and recipient.student_id and block.special_course_filter == recipient.student_id.main_group_id.course):
					# NOTE: special_course can be combined with WPI or Subject.
					if not block.special_subject_enrolled and not block.special_wpi_enrolled: append = True	# Just course filter							
					elif block.special_wpi_enrolled and recipient.student_id and recipient.wpi_enrolled: append = True
					elif block.special_subject_enrolled and recipient.student_id:
						# NOTE: Repeat the block for every enrolled subject. Each question must have a unique numerical id, for subject it should star with 4 (400, 4001, 4002...)
						qID = 4
						for enroll in recipient.limesurvey_enrollment_ids:
							survey_name += f" | {block.name}_{enroll.subject_id.code}_{enroll.group_id.display_name}"
							if not only_key:
								teachings = self.env["ems.teaching"].search([("group_id", "=", enroll.group_id.id), ("subject_id", "=", enroll.subject_id.id)], order="teacher_id asc") or False
								teachers_names = "UNKNOWN" if not teachings else ", ".join(teachings.mapped("teacher_id.name"))
								title = f"{enroll.subject_id.acronym}: {enroll.subject_id.name} | {enroll.group_id.display_name} | {teachers_names}"
								tmp = replace_block_content(block.tsv_raw_text, title, recipient.level_id.acronym, enroll.subject_id.code, enroll.subject_id.name, recipient.student_id.study_id.acronym, enroll.student_id.main_group_id.acronym, teachers_names)
								tmp = tmp.replace("{'X'}", str(qID))
								content += tmp
								qID += 1
			if append:
				survey_name += f" | {block.name}"	
				if not only_key:
					study = "NONE" if not recipient.student_id else recipient.student_id.study_id.acronym
					group = "NONE" if not recipient.student_id else recipient.student_id.main_group_id.acronym
					content += replace_block_content(block.tsv_raw_text, block.name, recipient.level_id.acronym, block.name, block.name, study, group)					

		return {
			"internal_id": self.persistent_hash(survey_name), 
			"raw_tsv": None if only_key else content
		}
			
	def store_recipients_data(self, recipients):
		# NOTE: The limesurvey_recipient_ids entries will be reset if an exception occurs, but LS opps will be done and won't be repeated (execute_once).
		#		So, it's important to store changes in a non-attached object, and do it even if the LS opps have been completed (commit retry support).
		for rec in recipients:
			original = rec["original"].with_env(self.env)
			original.write({
				"tid": rec["tid"],
				"token": rec["token"],
				"error": rec["error"],
				"status": rec["status"],
				"internal_id": rec["internal_id"],
				"external_id": rec["external_id"]
			})			

	def upload_survey(self, survey):		
		success = True
		ls_api = limesurvey_api(self.env)

		try:
			survey["external_id"] = ls_api.create_survey(self.env.company.limesurvey_gid, survey["raw_tsv"])
		except Exception as e:
			success = False
			survey["error"] = str(e)
			
		return success	
	
	def upload_recipients(self, internal_id, external_id, recipients):
		success = True		
		ls_api = limesurvey_api(self.env)
		
		try:			
			# NOTE: must convert the limesurvey_recipient model to the list of API values
			parts = []
			for r in recipients:				
				parts.append({
					"firstname": r["name"],
					"email": r["email"],
					"lastname": ""
				})
			result = ls_api.add_participants(external_id, parts)

			# New data will come in the same order as sent
			for index, row in enumerate(result):
				rec = recipients[index]
				if "error" in row:
					success = False
					rec["error"] = row["error"]		
					rec["status"] = "error"

				else:
					rec["tid"] = row["tid"]
					rec["token"] = row["token"]
					rec["internal_id"] = internal_id
					rec["external_id"] = external_id
					rec["status"] = "success"
		
		except Exception as e:				
			success = False
			for rec in recipients:
				rec["error"] = e
				rec["status"] = "error"

		return success	
	# endregion

	# region PRIVATE ONCHANGE/COMPUTE/STORE METHODS	
	@api.onchange('level_ids')
	def _onchange_level_ids(self):	
		ids = []
		for rec in self:
			for std in self.study_ids:
				if std.level_id.id in self.level_ids._origin.ids:
					ids.append(std.id)
			rec.study_ids = [Command.set(ids)]

	@api.onchange('study_ids')
	def _onchange_study_ids(self):
		ids = []
		for rec in self:
			for grp in self.group_ids:
				if grp.study_id.id in self.study_ids._origin.ids:
					ids.append(grp.id)
			rec.group_ids = [Command.set(ids)]

	def _compute_recipients_students(self):		
		# NOTE: Students without main group should be skipped, because they're not already enrolled (or have been resgined).
		# TODO: this will change with Juan's enrollment changes. 
		domain = [("main_group_id", "!=", False)]

		if self.level_ids:
			domain.append(("level_id", "in", self.level_ids.ids))
		
		if self.study_ids:
			domain.append(("study_id", "in", self.study_ids.ids))

		if self.group_ids:
			domain.append(("main_group_id", "in", self.group_ids.ids))

		rec_ids = []				
		students = self.env["res.partner"].search(domain)
		for student in students:
			enrollments = []
			for enroll in student.enrollment_ids:
				enrollments.append([0,0, {
					"student_id": student.id,
					"group_id": enroll.group_id.id,
					"subject_id": enroll.subject_id.id,
				}])
				
			rec_ids.append([0,0, {
				"name": student.name,
				"email": student.student_email,
				"level_id": student.level_id.id,
				"student_id": student.id,
				"wpi_enrolled": student.wpi_enrolled,
				"limesurvey_enrollment_ids": enrollments					
			}])				
		
		# NOTE: I don't know why [[5]] fails...
		for rec in self.limesurvey_recipient_ids:
			rec.unlink()	

		self.write({
			"limesurvey_recipient_ids": rec_ids
		})
	
	def _compute_recipients_teachers(self):
		# TODO: WARNING: do not repeat teachers (for example, if the same teacher is in CFGM and CFGS). Which level should be used? The first one?
		raise NotImplemented("Coming soon...")

	def _compute_recipients_asp(self):
		raise NotImplemented("Coming soon...")

	def _compute_students_surveys(self, surveys):
		for rec in self.limesurvey_recipient_ids:
			# NOTE: Computing just the key and then, if needed, the survey data, boosts the performance in about 81,3% (from an average of 1500ms to 280ms).
			#		The same method is used in order to share the code (in order to compute the key, the same items used to compute the content are used in the same way).			
			key = self.compute_survey_data(rec, True)["internal_id"]						
			if key in surveys: surveys[key]["recipients"].append(rec.copy_data())
			else: 
				surveys[key] = {
					"internal_id": key,
					"recipients": [rec.copy_data()],
					"raw_tsv": self.compute_survey_data(rec, False)["raw_tsv"]
				}					
		return surveys		

	def _compute_teachers_surveys(self, surveys):
		raise NotImplemented("Coming soon...")

	def _compute_asp_surveys(self, surveys):
		raise NotImplemented("Coming soon...")
	# endregion	
	
	# region PRIVATE AUX METHODS	
	def _end(self, success, title, action, status_ok, status_ko, exception=None):
		details = _("check the recipients entry for more details") if exception is None else exception	
		message = f"{action}  {_('process successfully completed!')}" if success else (f"{action}  {_('process failed.')} {details}")

		if not success: self.chatter(message)
		self.notify(title, message, "success" if success else "warning")
		self.is_running = False
		self.state = status_ok if success else status_ko
		
	def _run_action(self, title, action, status_w, status_ok, status_ko, code, pre=None):
		self.ensure_one()
		if not self.already_running():			
			try:
				self.is_running = True
				self.state = status_w				
				self.notify(title, _("Starting process in the background, you'll be notified on completion (it can take a while)."), "info")
				
				if pre is not None: 
					pre(self)

				def callback(self, success, error=None):
					self._end(success, title, action, status_ok, status_ko, error)
					self.reload_request()

				self.run_in_thread(code, callback=callback)
			except Exception as e:
				self._end(False, title, action, status_ok, status_ko, e)
			finally:
				return True
	# endregion
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
	_inherit = ['ems.base', 'ems.multithreading']
	
	limesurvey_header_id = fields.Many2one(string="Survey", comodel_name="ems.limesurvey_header", required=True)
	level_id = fields.Many2one(string='Level', comodel_name='ems.level')  
	name = fields.Char(string="Name", required=True)
	email = fields.Char(string="Email", required=True)
	external_id = fields.Char(string="Survey's ID (LimeSurvey)")
	internal_id = fields.Char(string="Survey's ID (EMS)")
	token = fields.Char(string="User's token (LimeSurvey)")
	tid = fields.Integer(string="User's ID (LimeSurvey)")
	state = fields.Selection(string="State", related="limesurvey_header_id.state")
	status = fields.Selection(string='Status', selection=[('pending', 'Pending'), ('success', 'Success'), ('error', 'Error')], default='pending')
	error = fields.Char(string="Error details")
	is_running = fields.Boolean(string="Running", default=False)

	notes = fields.Text(string="Notes")	

	# The recipients can be students (res_partner) or teachers/asp (hr.employee). Those are needed in order to refresh the data.
	student_id = fields.Many2one(string="Student", comodel_name="res.partner")
	teacher_id = fields.Many2one(string="Teacher", comodel_name="hr.employee")
	asp_id = fields.Many2one(string="ASP", comodel_name="hr.employee")

	# This field is used to compute the enrollments and allow modification by an authorized user (independent of 'real' enrollments, which should be modified only by secretarial staff).
	limesurvey_enrollment_ids = fields.One2many(string="Enrollments", comodel_name="ems.limesurvey_enrollment", inverse_name="limesurvey_recipient_id")
	wpi_enrolled = fields.Boolean(string="WPI enrolled")
	
	# region MAIN ACTIONS
	def action_none(self):
		return True
	
	def action_restore(self):
		if self.student_id:
			self.name = self.student_id.name
			self.email = self.student_id.student_email
			self.level_id = self.student_id.level_id

			enrollments = [[5]]
			for enroll in self.student_id.enrollment_ids:
				enrollments.append([0,0, {
					"student_id": self.student_id.id,
					"group_id": enroll.group_id.id,
					"subject_id": enroll.subject_id.id
				}])
			self.limesurvey_enrollment_ids = enrollments
		else:
			return False		

	def action_upload(self):
		survey={}
		def run(self, callback):					
			if self.student_id:				
				success = self._upload_student(survey)
				callback(self, success)			
			
			elif self.teacher_id:
				raise NotImplemented("Coming soon...")
			
			elif self.asp_id:
				raise NotImplemented("Coming soon...")
			
			else:
				raise Exception("Recipient not specified.")			
		
		return self._run_action(_("LimeSurvey: refresh recipient"), _("Refresh"), run)	
	
	def action_remind(self):
		self.ensure_one()
		def run(self, callback):
			sid = self.external_id
			ls_api = limesurvey_api(self.env)					
			self.execute_once(ls_api.remind_participants, f"remind_participants_{sid}", sid, [self.tid])
			callback(self, True)				

		return self._run_action(_("LimeSurvey: refresh recipient"), _("Refresh"), run)			
	# endregion

	# region PUBLIC METHODS (CAN BE CALLED INDIVIDUALLY FOR A CONCRETE RECIPIENT)
	def copy_data(self):
		data = self.read()[0]
		data["original"] = self
		return data

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
	# endregion

	# region PRIVATE AUX METHODS
	def _upload_student(self, survey):
		# NOTE: the 'survey' must be created BEFORE this method runs in another thread, in order to store data between executions on retries. 		
		header = self.limesurvey_header_id			
		ls_api = limesurvey_api(self.env)
		internal_id = header.compute_survey_data(self, True)["internal_id"]
		existing = self.env["ems.limesurvey_recipient"].search([("internal_id", "=", internal_id)], limit=1) or False

		# A survey template must be prepared (only if empty due to retries if a commit failed)
		if survey.get("internal_id", None) is None:
			survey["internal_id"] = internal_id
			survey["recipients"] = [self.copy_data()]
			
		success = True
		if existing and internal_id == self.internal_id:				
			# The recipient is in the correct survey, updating participant data.
			self.execute_once(ls_api.update_participant_data, f"update_participant_data_{self.tid}", existing["external_id"], self.tid, {
				"firstname": self.name,
				"email": self.email
			})
		else:	
			# The recipient is NOT in the correct survey
			if existing: survey["external_id"] = survey.get("external_id", existing["external_id"])
			else:
				# The "upload_survey" method stores the external_id (LS) into the survey dictionary.
				survey["raw_tsv"] = survey.get("raw_tsv", header.compute_survey_data(self, False)["raw_tsv"])			
				success = self.execute_once(header.upload_survey, f"upload_survey_{internal_id}", survey)				
			
			if success:				
				# The participant must be removed from the old survey
				old_survey_id = self.external_id
				self.execute_once(ls_api.delete_participants, f"delete_participants_{self.tid}", old_survey_id, [self.tid])		

				# Remove the old survey if empty, we don't care if counting fails due to retries by failed commits.
				try:	
					count = -1
					count = ls_api.count_participants(old_survey_id)
				finally:
					if(count == 0): self.execute_once(ls_api.delete_survey, f"delete_survey_{old_survey_id}", old_survey_id)
				
				# The participant must be uploaded to the survey						
				self.execute_once(header.upload_recipients, f"upload_recipients_{survey['internal_id']}", survey["internal_id"], survey["external_id"], survey["recipients"])
				
				# Always tries to store the recipient data with error messages and so...
				header.store_recipients_data(survey["recipients"])
		return success
	
	def _end(self, success, title, action, exception=None):
		message = f"{action}  {_('process successfully completed!')}" if success else (f"{action}  {_('process failed.')} {exception}")

		if success: self.error = None
		else:
			self.error = str(exception)
			self.chatter(message)

		self.notify(title, message, "success" if success else "warning")
		self.is_running = False
		
	def _run_action(self, title, action, code, pre=None):
		self.ensure_one()
		if not self.already_running():			
			try:
				self.is_running = True
				self.notify(title, _("Starting process in the background, you'll be notified on completion (it can take a while)."), "info")
				
				if pre is not None: 
					pre(self)

				def callback(self, success, error=None):
					self._end(success, title, action, error)
					self.reload_request()

				self.run_in_thread(code, callback=callback)
			except Exception as e:
				self._end(False, title, action, e)
			finally:
				return True
	# endregion
class ems_limesurvey_enrollment(models.Model):
	_name = "ems.limesurvey_enrollment"
	_description = "LimeSurvey enrollment: contains a copy of the enrollment model for the related student, in order to allow changes on the fly when preparing the surveys (only secretarial staff should be allowed to modify the real enrollments)."
	_inherit = ['ems.base']

	limesurvey_recipient_id = fields.Many2one(string="Recipient", comodel_name="ems.limesurvey_recipient", required=True, ondelete="cascade") # removing the recipient should remove all its enrollments
	student_id = fields.Many2one(string="Student", related="limesurvey_recipient_id.student_id")
	study_id = fields.Many2one(string="Study", related="student_id.study_id")
	group_id = fields.Many2one(string="Group", comodel_name="ems.group")
	subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject")
	inuse_subject_ids = fields.Many2many('ems.subject', compute='_compute_inuse_subject_ids', store=False) 		

	@api.depends('student_id')
	def _compute_inuse_subject_ids(self):
		for rec in self:
			rec.inuse_subject_ids = False
			if rec.student_id:
				rec.inuse_subject_ids = rec.mapped('student_id.enrollment_ids.subject_id')
