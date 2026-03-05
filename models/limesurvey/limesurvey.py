# -*- coding: utf-8 -*-

import requests, json, html, re, base64, threading, psycopg2, time
from datetime import datetime
from odoo import models, fields, api, registry, _
from odoo.exceptions import UserError

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
		participants = list(map(lambda x: {k: x[k] for k in ['email', 'firstname', 'lastname']}, participants))		
		return self._run_api_request("add_participants", [survey_id, participants])		

	def delete_participants(self, survey_id, participant_ids):		
		error = _("Unable to delete some participants")
		result = self._run_api_request("delete_participants", [survey_id, participant_ids])
		if "2" in result: raise Exception(f"{error}: " + result["2"] )
		elif "1" in result and result["1"] != "Deleted": raise Exception(f"{error}: " + result['1'] )
		elif not "1" in result: raise Exception(f"{error}: " + "UNKWOWN ERROR!")

	def update_participant_data(self, survey_id, participant_id, participant_data):			
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
			elif result["status"] == "No survey participants found.": return []
			else: return result["status"]
		else:
			raise Exception(f"{error}: UNKWONW ERROR!")
	
	def count_participants(self, survey_id):			
		return len(self.list_participants(survey_id))		
		
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
		group_found = False if result is None else next((g for g in result if g['name'] == name), None)
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
			result  = self._run_api_request("invite_participants", [survey_id])
			if "2" in result: raise Exception(f"{error}: " + result["2"] )			
			elif not "1" in result: raise Exception(f"{error}: " + "UNKWOWN ERROR!")			
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
	_inherit = ['ems.base', 'mail.thread', 'mail.activity.mixin']
	
	# NOTE: this field is used to track the wizard progress.
	state = fields.Selection(string='Status', selection=[
        ('draft', 'Draft'),
		('computed', 'Recipients computed'),
		('uploading', 'Uploading surveys'),
        ('uploaded', 'Surveys uploaded'),
		('opening', 'Opening surveys'),
        ('open', 'Surveys open'),
        ('closing', 'Closing surveys'),
		('closed', 'Surveys closed'),
		('downloading', 'Downloading surveys'),
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
	
	# NOTE: This is not an Odoo field, this is used to prevent data replication on retries on multi-threading executions.
	# 		When working with threads, BBDD changes could fail due to concurrent updates. Odoo manages transactions well, 
	# 		so retries can be done, but changes to LimeSurvey must be tracked and repetitions should be avoided. This is 
	# 		for what "changes" is used for. Each LimeSurvey change is tracked in "changes", and its done only if "changes" 
	# 		does not its flag. 
	changes = {}
	
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
						
			self._notify(title , message_ok, "success")
			self._chatter(message_ok)					
			self.state = 'computed'
		except Exception as e:	
			message_ko = f"{message_ko} {e}"
			self._notify(title, message_ko, "warning")
			self._chatter(message_ko)					
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
						
			message = _("Recipients successfully removed!")
			self._notify(title , message, "success")
			self._chatter(message)					
			self.state = 'draft'
		except Exception as e:	
			message = f"{_('Recipients remove failed. ')} {e}"
			self._notify(title, message, "warning")
			self._chatter(message)					
			self.env.cr.commit() # To save the messages	(previous changes have been rollbacked).		
		finally:
			return True

	def action_reload(self):
		return self.action_compute(_("LimeSurvey: reload recipients"), _("Recipients successfully reloaded!"), _('Recipients reload failed. '))		

	# TODO: error messages are beeing displayed? It seems that _notify is not working ok...










	def action_upload(self):
		self.ensure_one()
		if not self._already_running():
			try:				
				self.is_running = True
				self.state = 'uploading'

				# EMS group verification
				ls_api = limesurvey_api(self.env)
				ems_grp = ls_api.get_group("EMS")
				if not ems_grp:
					#NOTE: The LimeSurvey's API does not allow to create groups.
					raise UserError(_("LimeSurvey's EMS group not found. We're sorry, but the LimeSurvey API v6 does not allow to create survey groups. Please, use the EMS user to crate a survey group called 'EMS' and try again; the EMS will use this group in order to generate all the surveys."))		
				
				# Background warning
				title = _("LimeSurvey: upload surveys")
				self._notify(title, _("Starting process in the background, you'll be notified on completion (it can take a while)."), "info")

				# Settings up the distinct types of surveys
				if(self.target == "students"): surveys = self._setup_students_surveys()
				elif(self.target == "teachers"): surveys = self._setup_teachers_surveys()
				elif(self.target == "asp"): surveys = self._setup_asp_surveys()
				
				# This method runs at the end, in order to store the correct state and send the notifications to the user
				def end(self, success, exception=None):
					details = _("check the recipients entry for more details") if exception is None else exception	
					message = _("Upload process successfully completed!") if success else (f"{_('Upload process failed.')} {details}")
					self._notify(title, message, "success" if success else "warning")						
					self._chatter(message)					
					self.is_running = False
					self.state = 'uploaded'	if success else 'draft'
				
				# The main code will run on another thread to prevent Odoo timeouts
				def run(self):					
					try:	
						success = True			
						ls_api = limesurvey_api(self.env)	
						gsid = ls_api.get_group("EMS")["gsid"]		
						
						# Upload the surveys and recipients
						for key in surveys:
							survey = surveys[key]
							ok = self._execute_once(self.upload_survey, f"upload_survey_{key}", gsid, survey)
							if ok: ok = self._execute_once(self.upload_recipients, f"upload_recipients{key}", survey)							
							# BBDD recipients act like a log, should be saved always if possible (contains error messages).
							self.store_recipients(survey["internal_id"], survey["external_id"], survey["recipients"])
							success = ok and success										
						
						end(self, success)
						self.reload_request()
					
					except psycopg2.errors.SerializationFailure:
						# NOTE: _run_in_thread method will retry, the surveys won't be uploaded again due the use of _execute_once.
						raise
					
					except Exception as e:
						try:							
							for key in surveys:
								ls_api.delete_survey(surveys[key]["external_id"])
							end(self, False, e)
							self.reload_request()
						except Exception as e:
							end(self, False, e)
							self.reload_request()						
				
				# Thread execution
				self._run_in_thread(run)				
			except Exception as e:
				end(self, False, e)				
			finally:
				return True
			
	# def action_draft(self):
	# 	self.ensure_one()
	# 	if not self._already_running():
	# 		try:				
	# 			self.is_running = True
	# 			self.state = 'uploading'				
				
	# 			title = _("LimeSurvey: return to draft")
	# 			self._notify(title, _("Starting process in the background, you'll be notified on completion (it can take a while)."), "info")				
				
	# 			def end(self, success, errors=[]):		
	# 				details = "\n".join(str(e) for e in errors)
	# 				message = _("Return to draft process successfully completed!") if success else f"{_('Return to draft process failed.')} {details}"	
	# 				self._notify(title, message, "success" if success else "warning")	
	# 				self._chatter(message)					
	# 				self.is_running = False
	# 				self.state = 'draft' if success else 'uploaded'
				
	# 			def run(self):									
	# 				try:	
	# 					errors = []	
	# 					success = True		
	# 					ls_api = limesurvey_api(self.env)
	# 					survey_ids = list(set(self.limesurvey_recipient_ids.mapped('external_id')))																
						
	# 					for sid in survey_ids:
	# 						try:
	# 							success = success and self._execute_once(ls_api.delete_survey, f"delete_survey_{sid}", sid)
	# 							for rec in self.limesurvey_recipient_ids.search([("external_id", "=", sid)]):								
	# 								rec.unlink()
	# 						except Exception as e:
	# 							success = False
	# 							errors.append(f"Unable to remove the survey with external ID '{sid}'. {e}")

	# 					end(self, success, errors)					
	# 					self.reload_request()
					
	# 				except psycopg2.errors.SerializationFailure:
	# 					# NOTE: _run_in_thread method will retry, the surveys won't be uploaded again due the use of _execute_once.
	# 					raise
					
	# 				except Exception as e:						
	# 					end(self, False, [e])
	# 					self.reload_request()
				
	# 			self._run_in_thread(run)				
	# 		except Exception as e:
	# 			end(self, False, e)				
	# 		finally:
	# 			return True

	def action_open(self):
		self.ensure_one()
		if not self._already_running():
			try:
				self.is_running = True
				self.state = 'opening'
				
				title = _("LimeSurvey: open surveys")
				self._notify(title, _("Starting process in the background, you'll be notified on completion (it can take a while)."), "info")
				
				def end(self, success, errors=[]):		
					details = "\n".join(str(e) for e in errors)
					message = _("Open process successfully completed!") if success else f"{_('Open process failed.')} {details}"	
					self._notify(title, message, "success" if success else "warning")	
					self._chatter(message)					
					self.is_running = False
					self.state = 'open' if success else 'uploaded'
				
				def run(self):					
					try:	
						errors = []
						success = True		
						ls_api = limesurvey_api(self.env)
						survey_ids = list(set(self.limesurvey_recipient_ids.mapped('external_id')))																
						
						for sid in survey_ids:
							try:
								self._execute_once(ls_api.activate_survey, f"activate_survey_{sid}", sid)	
								self._execute_once(ls_api.invite_participants, f"invite_participants_{sid}", sid)
							except Exception as e:
								success = False
								errors.append(f"Unable to open the survey with external ID '{sid}'. {e}")					

						end(self, success, errors)
						self.reload_request()
					
					except psycopg2.errors.SerializationFailure:
						# NOTE: _run_in_thread method will retry, the surveys won't be uploaded again due the use of _execute_once.
						raise
					
					except Exception as e:						
						end(self, False, [e])
						self.reload_request()
				
				self._run_in_thread(run)				
			except Exception as e:
				end(self, False, e)				
			finally:
				return True
	



	
	# TODO: continue here: prepare the action methods as the "action_upload". 

	def action_prev(self):
		return True
		# for rec in self:			
		# 	if not rec._already_running():
		# 		rec.is_running = True
		# 		if rec.state == 'uploaded':				
		# 			rec.state = 'uploading'
		# 			return rec._action_draft()								

	def action_remind(self):
		for rec in self:			
			if not rec._already_running():
				return True

	def action_none(self):
		return True





	def action_next(self):
		return True
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
		# for rec in self:			
		# 	if not rec._already_running():
		# 		rec.is_running = True
		# 		if rec.state == 'draft':				
		# 			rec.state = 'uploading'
		# 			return rec._action_upload()
				
		# 		elif rec.state == 'uploaded':				
		# 			rec.state = 'opening'		
		# 			return rec._action_open()

		# 		elif rec.state == 'open':				
		# 			rec.state = 'closed'
					
		# 		elif rec.state == 'closed':
		# 			rec.state = 'downloaded'

		# 		elif rec.state == 'downloaded':
		# 			rec.state = 'draft'			

	def _compute_recipients_students(self):
		reci = []
		for level in self.level_ids:
			# NOTE: Students without main group should be skipped, because they're not already enrolled (or have been resgined).			
			students = self.env["res.partner"].search([("level_id", "=", level.id), ("main_group_id", "!=", False)])			
			for student in students:
				enrollments = []
				for enroll in student.enrollment_ids:
					enrollments.append([0,0, {
						"student_id": student.id,
						"group_id": enroll.group_id.id,
						"subject_id": enroll.subject_id.id
					}])
				reci.append([0,0, {
					"name": student.name,
					"email": student.student_email,					
					"student_id": student.id,
					"limesurvey_enrollment_ids": enrollments					
				}])				
		
		# NOTE: I don't know why [[5]] fails...
		for rec in self.limesurvey_recipient_ids:
			rec.unlink()	

		self.write({
			"limesurvey_recipient_ids": reci
		})
	
	def _compute_recipients_teachers(self):
		return False

	def _compute_recipients_asp(self):
		return False

	def compute_survey_data(self, student, only_key):
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
	
	def setup_recipient_student(self, student):		
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
	
	def store_recipients(self, internal_id, external_id, recipients):		
		entities = []			
		for r in recipients:	
			error = False if r["error"] is None else r["error"]						
			entities.append([0, 0, {
				"name": r["firstname"],
				"email": r["email"],
				"token": r["token"],
				"tid": r["tid"],
				"student_id": r["student_id"].id if r["student_id"] is not None else False,
				"teacher_id": r["teacher_id"].id if r["teacher_id"] is not None else False,
				"asp_id": r["asp_id"].id if r["asp_id"] is not None else False,
				"internal_id": internal_id,
				"external_id": external_id,
				"status": "success" if not error else "error",
				"error": r["error"] ,										
			}])

		self.write({
			"limesurvey_recipient_ids": entities
		})			
	
	def upload_survey(self, gsid, survey):		
		success = True
		ls_api = limesurvey_api(self.env)

		try:
			survey["external_id"] = ls_api.create_survey(gsid, survey["raw_tsv"])
		except Exception as e:
			success = False
			survey["error"] = str(e)
			
		return success	
	
	def upload_recipients(self, survey):
		success = True		
		ls_api = limesurvey_api(self.env)
		try:
			recipients = survey["recipients"]
			result = ls_api.add_participants(survey["external_id"], recipients)
			for index, row in enumerate(result):
				if "error" in row:
					recipients[index]["error"] = row["error"]
					success = False
				else:
					recipients[index]["token"] = row["token"]
					recipients[index]["tid"] = row["tid"]
		except Exception as e:				
			success = False
			for rec in survey["recipients"]:
				rec["error"] = e

		return success	
	
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

	def _execute_once(self, func, key=None, *args, **kwargs):
		result = True
		if key is None: key = func.__func__.__name__

		if not self.changes.get(key, False):
			result = func(*args, **kwargs)
			self.changes[key] = True
		return result

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
			self.changes.clear()
			db_registry = registry(dbname)
			# NOTE: I checked that, in some environments and situations, the first run always fails due to concurrent updates.
			#		I'm not sure if waiting a second prior to the first run is faster than the first retry (which waits 0 seconds)...
			for current_try in range(max_retries):
				try:					
					with db_registry.cursor() as cr:
						env = api.Environment(cr, uid, context)
						n_self = env[model_name].browse(record_ids)
						func(n_self, *args, **kwargs)
						break

				except psycopg2.errors.SerializationFailure:
					if current_try == max_retries: raise
					time.sleep(current_try)
		
		thread = threading.Thread(target=_threaded_worker)
		thread.start()
		return thread
		
	def _already_running(self):
		if self.is_running:
			self._notify(_("LimeSurvey: already running"), _("Process already running, maybe by another user?"), "danger")		
		return self.is_running

	
	

	
	
	
	
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
				key = self.compute_survey_data(student, True)["internal_id"]
				recipient = self.setup_recipient_student(student)
				if key in surveys: surveys[key]["recipients"].append(recipient)
				else: 
					surveys[key] = {
						"internal_id": key,
						"recipients": [recipient],
						"raw_tsv": self.compute_survey_data(student, False)["raw_tsv"]
					}					
		return surveys	

	def _setup_teachers_surveys(self):
		fake = 0

	def _setup_asp_surveys(self):
		fake = 0

	def _extract_limesurvey_html_error(self, html_content):		
		match = re.search(r'<h2[^>]*class="error-title"[^>]*>(.*?)</h2>', html_content, re.IGNORECASE | re.DOTALL)
		
		if match:
			raw_text = match.group(1)			
			clean_text = " ".join(raw_text.split())			
			final_text = html.unescape(clean_text)			
			return final_text
			
		return html_content
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
	notes = fields.Text(string="Notes")	

	# The recipients can be students (res_partner) or teachers/asp (hr.employee). Those are needed in order to refresh the data.
	student_id = fields.Many2one(string="Student", comodel_name="res.partner")
	teacher_id = fields.Many2one(string="Teacher", comodel_name="hr.employee")
	asp_id = fields.Many2one(string="ASP", comodel_name="hr.employee")

	# This field is used to compute the enrollments and allow modification by an authorized user (independent of 'real' enrollments, which should be modified only by secretarial staff).
	limesurvey_enrollment_ids = fields.One2many(string="Enrollments", comodel_name="ems.limesurvey_enrollment", inverse_name="limesurvey_recipient_id")
	
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
	
	def action_restore(self):
		return True

	def action_upload(self):
		return True

	def refresh(self):
		# TODO: check refresh when the enrolled changed, empty surveys should be removed.
		# TODO: improve LS methods, input methods (easier) and respose check (errors, etc.).

		self.ensure_one()
		ls_api = limesurvey_api(self.env)

		if self.student_id:
			title = _("LimeSurvey: refresh recipient")
			internal_id = self.limesurvey_header_id.compute_survey_data(self.student_id, True)["internal_id"]
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
						reci = self.limesurvey_header_id.setup_recipient_student(self.student_id)
						reci["tid"] = self.tid
						
						survey["recipients"] = [reci]
						self._update_recipient(survey)
						self._completed(title)
				else:
					success = True								
					self.limesurvey_header_id._notify(title, _("Refreshing the student's survey..."), "info")		
					if not existing:					
						# Uploading the survey if is a new one
						gsid = ls_api.get_group("EMS")["gsid"]
						survey = self.limesurvey_header_id.compute_survey_data(self.student_id, False)
						success = self.limesurvey_header_id.upload_survey(gsid, survey)
						if not success: raise Exception(survey["error"])					
					
					# The recipients must be uploaded always (for new or existing one)
					old_survey_id = self.external_id
					survey["recipients"] = [self.limesurvey_header_id.setup_recipient_student(self.student_id)]
					success = self.limesurvey_header_id.upload_survey_recipients(survey)
					if not success: raise Exception(survey["recipients"][0]["error"])
					self.limesurvey_header_id.store_recipients(survey["internal_id"], survey["external_id"], survey["recipients"])
										
					# Remove from the old survey
					ls_api.delete_participants(self.external_id, [self.tid])
					count = ls_api.count_participants(old_survey_id)
					if(count == 0): ls_api.delete_survey(old_survey_id)

					# TODO: if something fails, resotre the LimeSurvey status	
					self._completed(title)

					# NOTE: removing the entry must be the last step (otherwise any access to 'self' fails).
					self.unlink()

			except Exception as e:
				message = f"{_('Refresh process failed.')} {e}"
				self.limesurvey_header_id._notify(title, message, "warning")						
				self.limesurvey_header_id._chatter(message)

	def _update_recipient(self, survey):			
		sid = survey["external_id"]
		rec = survey["recipients"]					
		tid = rec[0]["tid"]
		data = list(map(lambda x: {k: x[k] for k in ['email', 'firstname', 'lastname']}, rec))[0]

		ls_api = limesurvey_api(self.env)
		ls_api.update_participant_data(sid, tid, data)
		
		self.name = data["firstname"]
		self.email = data["email"]

	def _completed(self, title):
		self.limesurvey_header_id._notify(title, _("Refresh process successfully completed!"), "success")
		self.limesurvey_header_id._chatter(_(f"Refresh for '{self.email}': ") + _("success"))

class ems_limesurvey_enrollment(models.Model):
	_name = "ems.limesurvey_enrollment"
	_description = "LimeSurvey enrollment: contains a copy of the enrollment model for the related student, in order to allow changes on the fly when preparing the surveys (only secretarial staff should be allowed to modify the real enrollments)."
	_inherit = ['ems.base']

	limesurvey_recipient_id = fields.Many2one(string="Recipient", comodel_name="ems.limesurvey_recipient", required=True, ondelete="cascade") # removing the recipient should remove all its enrollments
	student_id = fields.Many2one(string="Student", related="limesurvey_recipient_id.student_id")
	group_id = fields.Many2one(string="Group", comodel_name="ems.group")
	subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject")
	inuse_subject_ids = fields.Many2many('ems.subject', compute='_compute_inuse_subject_ids', store=False) 	

	@api.depends('student_id')
	def _compute_inuse_subject_ids(self):
		for rec in self:
			rec.inuse_subject_ids = False
			if rec.student_id:
				rec.inuse_subject_ids = rec.mapped('student_id.enrollment_ids.subject_id')
