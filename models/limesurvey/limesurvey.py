# -*- coding: utf-8 -*-

import requests, json, html, re, base64, time, traceback, io, csv
from datetime import datetime
from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError

# TO CLEAN THE BBDD DURING TESTING
# delete from ems_limesurvey_recipient;
# update ems_limesurvey_header elh set state='draft' where elh.id=1;
# update ems_limesurvey_header elh set is_running=false where elh.id=1;
# DELETE FROM mail_message WHERE model = 'ems.limesurvey_header';

survey_target_selection = [("students", "Students"), ("teachers", "Teachers"), ("asp", "ASP")]

# HOW DOES IT WORK:
# Working with external API consumes a lot of time, and Odoo timeouts too long server requests. So multithreading is needed.
# Working with multithreading is complex:
#	Odoo context and environment should be handled properly when working with multithreading (different BBDD cursors).
#	LS API calls returns important data like the LS IDs, that needs to be stored locally. 
# 	When storing changes in the BBDD, the commit can fail do to concurrent updates and Odoo performs a rollback. A retry system is needed.
#	The retry system should avoid repeated calls to the LS API, but avoiding calls means the need of persistent data between retries.
#
# SOLUTION:
#	Solved within multithreading.py -> run_in_thread() 
#		Runs setup() -> open read-only cursor that will be rollbacked. Used to load Odoo data from the BBDD to a persistent collection (dictionary).
#		Runs compute() -> no self / no cursor. API calls are time-consuming, this ensures that not related BBDD opps do not interfear with the regular Odoo ops. All changes within the persistent collection (dictionary).
#		Runs store() -> open write-allowed cursor. Moves the persistent collection data to the Odoo objects and tries to commit to the BBDD. Retries on commit fail. 
#		Runs callback() -> An extra method used to notify that the process finished (useful to request front-end data refresh).

# ems.limesurvey_header
#	We just store info about the recipients and which survey ID (internal and external) have they assigned.
#	The action_xxx methods runs actions for a batch of recipients.#		
#		Defines the "post_setup" method: all setups are shared between actions (all of them loads the same initial data), but in some concrete cases there's some extra needs, like when updating a single recipient.
#		Defines the "post_store" method: all setups are shared between actions (all of them loads the same initial data), but in some concrete cases there's some extra needs, like when deleting a single recipient.
#		Defines the "compute" method (API calls and business logic).
# 		Runs the _run_action() method which:
# 			Ensures that there's no other thread already running for the same actions. 
#			Defines the "setup" method (BBDD to persistent_data), always the same (computing survey data on upload; otherwise uses the BBDD data). The post_setup runs within it. 
#			Defines the "store" method (persistent_data to BBDD), the same for all actions.
# 			Defines the callback method (common for all actions).
# 			Calls the "run_in_thread" method seding setup, compute, store and callback.  
#
# ems.limesurvey_recipient
#	The same structure as the header but just for a single survey/recipient.
#	The action_xxx methods runs actions for a single recipient, so no need to iterate.	



# region DETACHED PUBLIC METHODS: DO NOT WORK WITH THE BBDD, JUST DICTIONARIES AND LS API CALLS. CALLED FROM HEAD AND RECIPIENTS
def do_upload_survey(ls_api, survey):	
	def code():
		survey["external_id"] = ls_api.create_survey(survey["raw_tsv"])	
	return _do(survey, code)	

def do_remove_survey(ls_api, survey):	
	def code():
		ls_api.delete_survey(survey["external_id"])
		for rec in survey["recipients"]:
			rec["external_id"] = None
			rec["internal_id"] = None
			rec["tid"] = None
			rec["token"] = None			
			rec["state"] = "pending"	
			rec["error"] = None
	return _do(survey, code)	

def do_upload_recipients(ls_api, survey):
	def code():
		# NOTE: must convert the limesurvey_recipient model to the list of API values
		parts = []			
		for r in survey["recipients"]:
			parts.append({
				"firstname": r["name"],
				"email": "" if not r["email"] else r["email"],
				"lastname": ""
			})
		
		try:
			success = True
			result = ls_api.add_participants(survey["external_id"], parts)
			# New data will come in the same order as sent
			for index, row in enumerate(result):
				rec = survey["recipients"][index]
				rec["tid"] = row["tid"]
				rec["token"] = row["token"]				
				rec["internal_id"] = survey["internal_id"]
				rec["external_id"] = survey["external_id"]
				rec["state"] = "uploaded"				
				
				if "error" in row:
					rec["error"] = row["error"]		
				else:
					rec["error"] = _email_not_empty(row["email"])				
		except Exception:
			survey["error"] = traceback.format_exc()
			success = False		
		return success		
	return _do(survey, code)	

def do_open_survey(ls_api, survey):
	def code():
		sid = survey["external_id"]
		ls_api.activate_survey(sid)
		ls_api.invite_participants(sid)
	return _do(survey, code)

def do_close_survey(ls_api, survey):
	def code():
		sid = survey["external_id"]
		ls_api.deactivate_survey(sid)
		for rec in survey["recipients"]:
			rec["error"] = None
	return _do(survey, code)

def do_reopen_survey(ls_api, survey):
	def code():
		sid = survey["external_id"]
		ls_api.reactivate_survey(sid)
		for rec in survey["recipients"]:
			rec["error"] = None
	return _do(survey, code)

def do_download_survey(ls_api, survey):
	def code():
		sid = survey["external_id"]
		survey["responses"] = ls_api.export_survey_responses(sid)
		for rec in survey["recipients"]:
			rec["error"] = None
	return _do(survey, code)

def do_send_invitations(ls_api, survey):
	def code():		
		sid = survey["external_id"]		
		ls_api.invite_participants(sid)
	return _do(survey, code)

def do_send_reminders(ls_api, survey):
	def code():		
		sid = survey["external_id"]		
		ls_api.remind_participants(sid)
	return _do(survey, code)

def do_remove_recipients(ls_api, survey):
	def code():
		# NOTE: The data that should be used is always within the recipients, not the survey.
		#		The recipients should be all from the same survey, but better to be sure.
		#		Also, could have no survey, in that case must be skipped
		data = {}
		success = True
		for rec in survey["recipients"]:
			if rec["external_id"]:
				if rec["external_id"] not in data:
					data[rec["external_id"]] = [rec]
				else:
					data[rec["external_id"]].append(rec)

		for key in data:
			try:
				recs = data[key]
				tids = [r["tid"] for r in recs]
				ls_api.delete_participants(key, tids)
			except Exception:
				success = False
				for r in recs:
					r["error"] = traceback.format_exc()
		return success

	return _do(survey, code)	

def do_remove_survey_if_empty(ls_api, survey):
	def code():
		# NOTE: The data that should be used is always within the recipients, not the survey.
		#		The recipients should be all from the same survey, but better to be sure.
		data = {}
		success = True
		for rec in survey["recipients"]:
			if rec["external_id"]:
				if rec["external_id"] not in data:
					data[rec["external_id"]] = [rec]
				else:
					data[rec["external_id"]].append(rec)

		for key in data:
			try:
				recs = data[key]
				count = ls_api.count_participants(key)
				if(count == 0): ls_api.delete_survey(key)
			except Exception:
				success = False
				for r in recs:
					r["error"] = traceback.format_exc()
		return success

	return _do(survey, code)	

def do_upload_recipient_changes(ls_api, survey):
	def code():
		# NOTE: just for a single participant, but can be adapted for a batch of them if needed.
		#		Within survey: the NEW internal_id and external_id
		#		Within survey["recipients"][0]: the CURRENT internal_id and external_id
		#		If the internal_id are different, the recipient must be moved.
		#		The survey's external_id will be None if must be created.
		#		All this data has been computed in load_persistent_data().

		success = True
		rec = survey["recipients"][0]
		existing = survey["external_id"] is not None
		if existing and survey["internal_id"] == rec["internal_id"]:
			# The recipient is in the correct survey, updating participant data.				
			
			empty = _email_not_empty(rec["email"])
			if empty is None:
				ls_api.update_participant_data(rec["external_id"], rec["tid"], {
					"firstname": rec["name"],
					"email": rec["email"]
				})
			else:
				rec["error"] = empty
				success = False
		else:	
			# The recipient is NOT in the correct survey
			# Removing from the old one (the method does not remove if the recipient is not uploaded)			
			success = do_remove_recipients(ls_api, survey)
			if success: 
				success = do_remove_survey_if_empty(ls_api, survey)
				if success and existing: 
					# The survey already exists, so the IDs must be updated manually
					rec["internal_id"] = survey["internal_id"]
					rec["external_id"] = survey["external_id"]
				elif success:
					# The survey must be created, the new IDs will be computed and set automatically					
					success = do_upload_survey(ls_api, survey)
					
					# A student can be added when the surveys are already open, so the new survey should be also open
					# if success and survey["state"] == 'open':
					# 	success = do_open_survey(ls_api, survey)
						
				if success: 
					success = do_upload_recipients(ls_api, survey)
				
				if success and survey["state"] == 'open':
					# Surveys must be open always after adding the participants (sends also the invitations), otherwise just send reminders.
					if existing: success = do_send_invitations(ls_api, survey)
					else: success = do_open_survey(ls_api, survey)
		return success		
	return _do(survey, code)
# endregion

# region ATTACHED & SHARED METHODS BETWEEN HEADER AND RECIPIENT
def run_action(self, title, action, status_w, status_ok, status_ko, compute, persistent_data, compute_survey_data=False, post_setup=None, post_store=None):
	self.ensure_one()
	if not self.already_running():
		def setup(self):			
			persistent_data["success"] = True
			persistent_data["ls_api"] = limesurvey_api(self.env)
			try:
				# TODO: maybe is better to use diferent load_persistent_data methods for teachers or ASP...
				persistent_data["surveys"] = load_persistent_data(self, compute_survey_data)
				if post_setup is not None: post_setup(self)
			except Exception:
				persistent_data["success"] = False
				persistent_data["error"] = traceback.format_exc()
					
		def store(self):
			# Store: Moves data from persistent_data to Odoo objects in order to store changes in the BBDD.
			# All actions must do this. Also it will be retried if commit fails.
			# NOTE: "original" is an Odoo recipient entry, must be restores to the current BBDD env/context. 
			for key in persistent_data.get("surveys", []):
				survey = persistent_data["surveys"][key]
				for rec in survey.get("recipients", []):
					original = rec["original"].with_env(self.env)
					original.write({
						"tid": rec.get("tid", None),
						"token": rec.get("token", None),
						"error": rec.get("error", None),
						"state": rec.get("state", None),
						"internal_id": rec.get("internal_id", None),
						"external_id": rec.get("external_id", None)				
					})
			if post_store is not None: post_store(self)
						
		def callback(self):
			error = persistent_data.get("error", None)
			success = error is None
			message = f"{action}  {_('process successfully completed!')}" if success else (f"{action}  {_('process failed.')} {error}")

			if not success: self.chatter(message)
			self.notify(title, message, "success" if success else "warning")
			self.is_running = False
			self.state = status_ok if success else status_ko
			
			if self._name == 'ems.limesurvey_recipient':
				if error and not self.error: self.error = error
				elif not error: self.error = False
			self.reload_request()
			
		try:
			self.is_running = True
			self.state = status_w				
			self.notify(title, _("Starting process in the background, you'll be notified on completion (it can take a while)."), "info")												
			self.run_in_thread(setup, compute, store, callback)
		except Exception:
			callback(self, traceback.format_exc())
		finally:
			return True		
			
def load_persistent_data(self, compute_survey_data=True):
	surveys = {}
	def load_recipient(head, rec):
		# NOTE: Computing just the key and then, if needed, the survey data, boosts the performance in about 81,3% (from an average of 1500ms to 280ms).
		#		The same method is used in order to share the code (in order to compute the key, the same items used to compute the content are used in the same way).		
		internal_id = None
		external_id = None

		if compute_survey_data:
			internal_id = head.compute_survey_data(rec, True)["internal_id"]
			existing = self.env["ems.limesurvey_recipient"].search([("internal_id", "=", internal_id)], limit=1) or False
			if existing: external_id = existing["external_id"]	
		else:
			internal_id = rec.internal_id
			external_id = rec.external_id

		if internal_id in surveys: surveys[internal_id]["recipients"].append(rec.copy_data())
		else: 
			surveys[internal_id] = {
				"internal_id": internal_id,
				"external_id": external_id,
				"recipients": [rec.copy_data()],
				"raw_tsv": None if not compute_survey_data else head.compute_survey_data(rec, False)["raw_tsv"]
			}

	if self._name == 'ems.limesurvey_recipient': 
		load_recipient(self.limesurvey_header_id, self)
	elif self._name == 'ems.limesurvey_header':
		for rec in self.limesurvey_recipient_ids:
			load_recipient(self, rec)
	else: 
		raise NotImplemented("This method only works for 'ems.limesurvey_recipient' and 'ems.limesurvey_header'")		
	return surveys	
# endregion

# region DETACHED PRIVATE METHODS
def _do(survey, code, *args, **kwargs):
	# Ensures that all operations works in the same way (storing errors in recipients if needed).
	try:
		success = code(*args, **kwargs)
	except Exception as e:
		success = False
		for rec in survey["recipients"]:
			rec["error"] = traceback.format_exc()
	return True if success is None else success

def _email_not_empty(email):
	if not email or len(email) == 0:
		return "Empty email address!"
	else:
		return None

def _clean_trainer(value):
	if value and value.strip().lower().startswith("trainer:"):
		return value[len("trainer:"):].strip()
	return value or ""

def _build_csv(env, all_responses):
	year = env.company.current_course_id.start if env.company.current_course_id else ""
	output = io.StringIO()
	writer = csv.writer(output)
	writer.writerow(["evaluation_id", "timestamp", "year", "level", "department", "degree", "group", "subject_code", "subject_name", "trainer", "topic", "question_sort", "question_type", "value"])

	evaluation_id = 0
	for response in all_responses:
		timestamp = response.get("submitdate", "")

		prefixes = [re.match(r'^([A-Z]+\d*)level$', k).group(1)
					for k in response if re.match(r'^([A-Z]+\d*)level$', k)]

		for prefix in prefixes:
			evaluation_id += 1
			level        = response.get(f"{prefix}level", "")
			topic        = response.get(f"{prefix}topic", "")
			subject_code = response.get(f"{prefix}subjectcode", "")
			subject_name = response.get(f"{prefix}subjectname", "")
			degree       = response.get(f"{prefix}degree", "")
			group        = response.get(f"{prefix}group", "")
			trainer      = _clean_trainer(response.get(f"{prefix}trainer", ""))
			department   = "DEPARTMENT"

			numeric_keys = sorted(
				[k for k in response if re.match(rf'^{re.escape(prefix)}questions\[{re.escape(prefix)}\d+\]$', k)],
				key=lambda k: int(re.search(r'\d+', k.split('[')[1]).group())
			)
			for sort, key in enumerate(numeric_keys, start=1):
				writer.writerow([evaluation_id, timestamp, year, level, department, degree, group, subject_code, subject_name, trainer, topic, sort, "Numeric", response.get(key, "")])

			comment = response.get(f"{prefix}comments", "")
			if comment:
				writer.writerow([evaluation_id, timestamp, year, level, department, degree, group, subject_code, subject_name, trainer, topic, "", "Text", comment])

	return output.getvalue()
# endregion
class limesurvey_api():
	def __init__(self, env):
		self.limesurvey_api = env.company.limesurvey_api
		self.limesurvey_usr = env.company.limesurvey_usr
		self.limesurvey_pwd = env.company.limesurvey_pwd
		self.limesurvey_gid = env.company.limesurvey_gid

	def create_survey(self, raw_tsv):		
		data = base64.b64encode(raw_tsv.encode('utf-8')).decode('utf-8')
		result  = self._run_api_request("import_survey", [data, "txt"])
		
		if isinstance(result, int) or (isinstance(result, str) and result.isdigit()): 
			try:
				self._run_api_request("set_survey_properties", [result,  {"gsid": self.limesurvey_gid}])
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

	def deactivate_survey(self, survey_id):
		error = _("Unable to deactivate the survey")
		try:
			result = self._run_api_request("set_survey_properties", [survey_id, {"expires": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}])
			if not isinstance(result, dict) or not result.get("expires"):
				raise Exception(f"{error}: {result}")
		except Exception as e:
			raise Exception(f"{error}: {e}")

	def reactivate_survey(self, survey_id):
		error = _("Unable to reactivate the survey")
		try:
			result = self._run_api_request("set_survey_properties", [survey_id, {"expires": None}])
			if not isinstance(result, dict) or not result.get("expires"):
				raise Exception(f"{error}: {result}")
		except Exception as e:
			raise Exception(f"{error}: {e}")

	def export_survey_responses(self, survey_id):
		error = _("Unable to export survey responses")
		try:
			result = self._run_api_request("export_responses", [int(survey_id), "json", None, "complete", "code", "long"])
			if isinstance(result, dict):
				status = result.get("status", "")
				if "No Data" in status: return []
				raise Exception(status or str(result))
			decoded = base64.b64decode(result).decode("utf-8")
			data = json.loads(decoded)
			if isinstance(data, dict) and "responses" in data:
				return data["responses"]
			elif isinstance(data, list):
				return data
			raise Exception(f"Unexpected response format: {type(data)}")
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

	def _parse_api_response(self, response, context="LimeSurvey API"):
		if response.status_code != 200:
			raise UserError(f"{context} error: {response.reason}\n\n{self._extract_limesurvey_html_error(response.text)}")

		try:
			data = response.json()
		except Exception:
			raise UserError(f"{context} error: the response is not valid JSON.\n\n{response.text[:500]}")

		if data.get('error'):
			raise UserError(f"{context} error: {data.get('error')}")

		return data

	def _run_api_request(self, method, params=[]):
		headers = {'content-type': 'application/json'}
		session_key = self._get_session_key(headers)

		if not session_key:
			raise UserError(_("Unable to get the LimeSurvey's session key."))

		try:
			payload = {
                "method": method,
                "params": [session_key, *params],
                "id": 1
            }

			response = requests.post(self.limesurvey_api, data=json.dumps(payload), headers=headers)
			result = self._parse_api_response(response, "LimeSurvey API call").get('result')

			if result is None:
				raise UserError(f"LimeSurvey API call error: unknown (maybe permissions?)")
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
			"params": [self.limesurvey_usr, self.limesurvey_pwd],
			"id": 1
		}
		response = requests.post(self.limesurvey_api, data=json.dumps(payload), headers=headers)
		return self._parse_api_response(response, "LimeSurvey session key").get('result')
	
	def _release_session_key(self, session_key, headers):		
		payload = {
			"method": "release_session_key",
			"params": [session_key],
			"id": 1
		}
		requests.post(self.limesurvey_api, data=json.dumps(payload), headers=headers)
class ems_limesurvey_header(models.Model):
	_name = "ems.limesurvey_header"
	_description = "LimeSurvey header: contains the survey's header and its content."
	_inherit = ['ems.base', 'ems.multithreading']
	
	# NOTE: this field is used to track the wizard progress.
	state = fields.Selection(string='State', selection=[
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
		('reopening', 'Re-opening surveys'),
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
	limesurvey_block_ids = fields.One2many(string="Blocks", comodel_name="ems.limesurvey_block", inverse_name="limesurvey_header_id", copy=True)
	limesurvey_recipient_ids = fields.One2many(string="Recipients", comodel_name="ems.limesurvey_recipient", inverse_name="limesurvey_header_id")	
	is_running = fields.Boolean(string="Running", default=False)
	notes = fields.Text(string="Notes")
	csv_data = fields.Binary(string="Survey Results CSV", attachment=True)
	csv_filename = fields.Char(string="CSV Filename")		
	
	# region MAIN ACTIONS (OVER A SET OF SURVEYS/RECIPIENTS)
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
		
		persistent_data = {}		
		def compute():
			# Compute: business login and LimeSurvey API calls. Time-consuming, so no BBDD cursor is open.
			# Cannot work with Odoo objects: self don't provided (no BBDDD cursor!).
			success = persistent_data["success"]
			if success:
				for key in persistent_data["surveys"]:
					ls_api = persistent_data["ls_api"]
					survey = persistent_data["surveys"][key]
					success = success and do_upload_survey(ls_api, survey)
					if success: success = success and do_upload_recipients(ls_api, survey)			
				if not success: persistent_data["error"] = _("Something failed when trying to upload a survey or its recipients, please check the recipient entries for more details.")
				persistent_data["success"] = success
		return run_action(self, _("LimeSurvey: upload surveys"), _("Upload"), "uploading", "uploaded", "computed", compute, persistent_data, True)

	def action_remove(self):
		persistent_data = {}		
		def compute():			
			success = persistent_data["success"]
			if success:
				for key in persistent_data["surveys"]:
					ls_api = persistent_data["ls_api"]
					survey = persistent_data["surveys"][key]

					success = success and do_remove_survey(ls_api, survey)
					if not success: persistent_data["error"] = _("Something failed when trying to remove a survey or its recipients, please check the recipient entries for more details.")
				persistent_data["success"] = success		
		return run_action(self, _("LimeSurvey: remove surveys"), _("Remove"), "removing", "computed", "uploaded", compute, persistent_data)				
	
	def action_open(self):	
		persistent_data = {}		
		def compute():			
			success = persistent_data["success"]
			if success:
				for key in persistent_data["surveys"]:
					ls_api = persistent_data["ls_api"]
					survey = persistent_data["surveys"][key]

					success = success and do_open_survey(ls_api, survey)
					if not success: persistent_data["error"] = _("Something failed when trying to open a survey or send the invitations, please check the recipient entries for more details.")
				persistent_data["success"] = success		
		return run_action(self, _("LimeSurvey: open surveys"), _("Open"), "opening", "open", "uploaded", compute, persistent_data)				

	def action_close(self):
		persistent_data = {}
		def compute():
			success = persistent_data["success"]
			if success:
				for key in persistent_data["surveys"]:
					ls_api = persistent_data["ls_api"]
					survey = persistent_data["surveys"][key]
					success = success and do_close_survey(ls_api, survey)
					if not success: persistent_data["error"] = _("Something failed when trying to close a survey, please check the recipient entries for more details.")
				persistent_data["success"] = success
		return run_action(self, _("LimeSurvey: close surveys"), _("Close"), "closing", "closed", "open", compute, persistent_data)

	def action_reopen(self):
		persistent_data = {}
		def compute():
			success = persistent_data["success"]
			if success:
				for key in persistent_data["surveys"]:
					ls_api = persistent_data["ls_api"]
					survey = persistent_data["surveys"][key]
					success = success and do_reopen_survey(ls_api, survey)
					if not success: persistent_data["error"] = _("Something failed when trying to reopen a survey, please check the recipient entries for more details.")
				persistent_data["success"] = success
		def post_store(self):
			if persistent_data.get("success"):
				self.csv_data = False
				self.csv_filename = False
		return run_action(self, _("LimeSurvey: reopen surveys"), _("Reopen"), "reopening", "open", "closed", compute, persistent_data, post_store=post_store)

	def action_download(self):
		persistent_data = {}

		def compute():
			success = persistent_data["success"]
			if success:
				all_responses = []
				for key in persistent_data["surveys"]:
					ls_api = persistent_data["ls_api"]
					survey = persistent_data["surveys"][key]
					if not survey.get("external_id"): continue
					success = success and do_download_survey(ls_api, survey)
					if success:
						all_responses.extend(survey.get("responses", []))
					else:
						persistent_data["error"] = _("Something failed when trying to download survey responses, please check the recipient entries for more details.")
						break
				persistent_data["success"] = success
				persistent_data["all_responses"] = all_responses

		def post_store(self):
			if persistent_data.get("success"):
				csv_content = _build_csv(self.env, persistent_data.get("all_responses", []))
				self.csv_data = base64.b64encode(csv_content.encode("utf-8")).decode("utf-8")
				self.csv_filename = f"survey_results_{fields.Date.today()}.csv"

		return run_action(self, _("LimeSurvey: download surveys"), _("Download"), "downloading", "closed", "closed", compute, persistent_data, post_store=post_store)

	def action_get_csv(self):
		self.ensure_one()
		return {
			'type': 'ir.actions.act_url',
			'url': f'/web/content?model=ems.limesurvey_header&id={self.id}&field=csv_data&filename={self.csv_filename}&download=true',
			'target': 'new',
		}

	def action_remind(self):
		persistent_data = {}		
		def compute():			
			success = persistent_data["success"]
			if success:
				for key in persistent_data["surveys"]:
					ls_api = persistent_data["ls_api"]
					survey = persistent_data["surveys"][key]

					success = success and do_send_reminders(ls_api, survey)
					if not success: persistent_data["error"] = _("Something failed when trying to send reminders for a survey, please check the recipient entries for more details.")
				persistent_data["success"] = success		
		return run_action(self, _("LimeSurvey: sending reminders"), _("Remind"), "reminding", "open", "uploaded", compute, persistent_data)
		
	def action_none(self):
		return True
	# endregion

	# region OTHER ACTIONS (POPUPS AND SO)
	def open_add_student_popup(self):
		self.ensure_one()
		return {
			'type': 'ir.actions.act_window',
			'name': _('Select the student to add'),
			'res_model': 'ems.limesurvey_recipient',
			'view_mode': 'form',
			'view_id': self.env.ref('ems.view_limesurvey_recipient_add_student_popup').id,
			'target': 'new'			
		}
	# endregion	
	
	# region PUBLIC COMPUTE / STORE METHODS		
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
						#		Warning: tutorship is a subject too and the student will be enrolled, but tutorship blocks works different, so tutorship-subjects will be ignored,
						#		just regular subject will be taken in count. 
						qID = 4
						for enroll in recipient.limesurvey_enrollment_ids.filtered(lambda e: not e.subject_id.is_tutorship):
							survey_name += f" | {block.name}_{enroll.subject_id.code}_{enroll.group_id.display_name}"
							if not only_key:								
								title = f"{enroll.subject_id.acronym}: {enroll.subject_id.name} | {enroll.group_id.display_name}"
								
								teachings = self.env["ems.teaching"].search([("group_id", "=", enroll.group_id.id), ("subject_id", "=", enroll.subject_id.id)], order="teacher_id asc") or False
								teachers_names = "" if not teachings else ", ".join(teachings.mapped("teacher_id.name"))
								if len(teacher_name) > 0: title += f" | {teachers_names}"
								
								tmp = replace_block_content(block.tsv_raw_text, title, recipient.level_id.acronym, enroll.subject_id.code, enroll.subject_id.name, recipient.student_id.study_id.acronym, enroll.student_id.main_group_id.display_name, teachers_names)
								tmp = tmp.replace("{'X'}", str(qID))
								content += tmp
								qID += 1
			if append:				
				survey_name += f" | {block.name}"	
				if not only_key:
					std_id = recipient.student_id
					
					teacher_name = ""
					if block.special_tutorship:						
						teacher_name = "" if not std_id or not std_id.main_group_id or not std_id.main_group_id.tutor_id else std_id.main_group_id.tutor_id.display_name
						survey_name += f" {std_id.main_group_id.display_name}"

					study = "NONE" if not std_id or not std_id.study_id else std_id.study_id.acronym
					group = "NONE" if not std_id or not std_id.main_group_id else std_id.main_group_id.display_name
					content += replace_block_content(block.tsv_raw_text, block.name, recipient.level_id.acronym, block.name, block.name, study, group, teacher_name)

		return {
			"internal_id": self.persistent_hash(survey_name), 
			"raw_tsv": None if only_key else content
		}
			
	def fill_recipients_data(self, recipients):
		# NOTE: The limesurvey_recipient_ids entries will be reset if an exception occurs, but LS opps will be done and won't be repeated (execute_once).
		#		So, it's important to store changes in a non-attached object, and do it even if the LS opps have been completed (commit retry support).
		for rec in recipients:
			original = rec["original"].with_env(self.env)
			original.write({
				"tid": rec.get("tid", None),
				"token": rec.get("token", None),
				"error": rec.get("error", None),
				"state": rec.get("state", None),
				"internal_id": rec.get("internal_id", None),
				"external_id": rec.get("external_id", None)				
			})			
	# endregion

	# region PRIVATE COMPUTE METHODS	
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
			
			email = False 
			if student.student_email: email = student.student_email
			if not email: email = student.email
			
			rec_ids.append([0,0, {
				"name": student.name,
				"email": email,
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

	# region PRIVATE ONCHANGE METHODS (JUST FOR VIEWS)
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
	special_tutorship = fields.Boolean(string="Tutorship", default=False)
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
	
	state = fields.Selection(string='State', selection=[
		('manual', 'Manual'), 
		('pending', 'Pending'), 
		('uploaded', 'Uploaded'), 
		('uploading', 'Uploading'), 
		('reminding', 'Reminding'),
		('deleting', 'Deleting')
	], default='pending')

	limesurvey_header_id = fields.Many2one(string="Survey", comodel_name="ems.limesurvey_header", required=True)
	header_state = fields.Selection(string="Header's sate", related="limesurvey_header_id.state", store=False)
	level_id = fields.Many2one(string='Level', comodel_name='ems.level')  
	name = fields.Char(string="Name", required=True)
	email = fields.Char(string="Email")
	external_id = fields.Char(string="Survey's ID (LimeSurvey)")
	internal_id = fields.Char(string="Survey's ID (EMS)")
	token = fields.Char(string="User's token (LimeSurvey)")
	tid = fields.Integer(string="User's ID (LimeSurvey)")	
	error = fields.Char(string="Error details")
	is_running = fields.Boolean(string="Running", default=False)

	notes = fields.Text(string="Notes")	

	# The recipients can be students (res_partner) or teachers/asp (hr.employee). Those are needed in order to refresh the data.
	student_id = fields.Many2one(string="Student", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]")
	teacher_id = fields.Many2one(string="Teacher", comodel_name="hr.employee")
	asp_id = fields.Many2one(string="ASP", comodel_name="hr.employee")

	# The following "inuse" fields are used to manually add recipients
	inuse_student_ids = fields.Many2many('res.partner', compute='_compute_inuse_student_ids', store=False) 		


	# This field is used to compute the enrollments and allow modification by an authorized user (independent of 'real' enrollments, which should be modified only by secretarial staff).
	limesurvey_enrollment_ids = fields.One2many(string="Enrollments", comodel_name="ems.limesurvey_enrollment", inverse_name="limesurvey_recipient_id")
	wpi_enrolled = fields.Boolean(string="WPI enrolled")
	
	# region MAIN ACTIONS	
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
		persistent_data = {}

		def post_setup(self):
			# This method runs post-setup, it will be used to computed extra data in order to know if the recipient must be moved to another survey			
			(key, survey), = persistent_data["surveys"].items()
			survey["state"] = self.limesurvey_header_id.state						

		def compute():			
			success = persistent_data["success"]
			if success:
				for key in persistent_data["surveys"]:
					ls_api = persistent_data["ls_api"]
					survey = persistent_data["surveys"][key]					
					success = success and do_upload_recipient_changes(ls_api, survey)
				if not success: persistent_data["error"] = _("Something failed when trying to upload the changes for a recipient, please check the recipient entries for more details.")
				persistent_data["success"] = success
		return run_action(self, _("LimeSurvey: upload changes"), _("Upload"), "uploading", self.state, self.state, compute, persistent_data, True, post_setup)
	
	def action_remind(self):					
		persistent_data = {}		
		def compute():						
			for key in persistent_data["surveys"]:
				ls_api = persistent_data["ls_api"]
				survey = persistent_data["surveys"][key]					
				success = do_send_reminders(ls_api, survey)
			if not success: persistent_data["error"] = _("Something failed when trying to send a reminder to a recipient, please check the recipient entries for more details.")
			persistent_data["success"] = success
		return run_action(self, _("LimeSurvey: send reminder"), _("Remind"), "reminding", self.state, self.state, compute, persistent_data)
	
	def action_delete(self):					
		persistent_data = {}		
		def compute():						
			for key in persistent_data["surveys"]:
				ls_api = persistent_data["ls_api"]
				survey = persistent_data["surveys"][key]					
				success = do_remove_recipients(ls_api, survey)
				if success: success = do_remove_survey_if_empty(ls_api, survey)
			if not success: persistent_data["error"] = _("Something failed when trying to delete a recipient, please check the recipient entries for more details.")
			persistent_data["success"] = success
		
		def post_store(self):
			success = persistent_data.get("success", False)
			if success: self.unlink()

		return run_action(self, _("LimeSurvey: delete reminder"), _("Delete"), "deleting", self.state, self.state, compute, persistent_data, post_store=post_store)

	def action_none(self):
		return True	
	# endregion

	# region OTHER ACTIONS (POPUPS AND SO)
	def open_error_popup(self):
		self.ensure_one()
		return {
			'type': 'ir.actions.act_window',
			'name': _('Error details'),
			'res_model': self._name,
			'res_id': self.id,
			'view_mode': 'form',
			'view_id': self.env.ref('ems.view_limesurvey_recipient_error_popup').id,
			'target': 'new', 
			'flags': {'mode': 'readonly'}
		}
	# endregion	

	# region PUBLIC DATA MANAGEMENT METHODS (CREATE / COPY / ETC)
	@api.model_create_multi
	def create(self, values):
		for v in values:
			if v.get("state", "pending") == "manual":
				s = self.env["res.partner"].browse([v["student_id"]])
				if not "name" in v:
					v["name"] = s.name
				if not "email" in v:
					v["email"] = s.student_email
		
		recips = super().create(values)
		for r in recips:
			if r.state == "manual":
				r.state = "pending"
				r.action_restore()

				if r.limesurvey_header_id.state in ("uploaded", "open"):
					# NOTE: commit needed, otherwise the action cannot work properly
					#		action_upload will also open the survey (if new and should be open), send the invitations (if needed), etc.
					r.state = "uploaded"
					self.env.cr.commit() 
					r.action_upload()							
		return recips

	def copy_data(self):
		data = self.read()[0]
		data["original"] = self
		return data		
	# endregion
	
	# region PRIVATE AUX METHODS
	@api.depends('state')
	def _compute_inuse_student_ids(self):
		for rec in self:
			rec.inuse_student_ids = False
			if rec.state == "manual":
				rec.inuse_student_ids = rec.mapped('limesurvey_header_id.limesurvey_recipient_ids.student_id')	
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
