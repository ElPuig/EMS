# -*- coding: utf-8 -*-

import requests, json, html, re
from odoo import models, fields, api, _
from odoo.exceptions import UserError

survey_recipient_selection = [("students", "Students"), ("teachers", "Teachers"), ("asp", "ASP")]

class ems_limesurvey_header(models.Model):
	_name = "ems.limesurvey_header"
	_description = "LimeSurvey header: contains the survey's header and its content."
	_inherit = ['ems.base']
	
	name = fields.Char(string="Name", required=True)
	recipient = fields.Selection(string="Recipient", selection=survey_recipient_selection)
	level = fields.Many2many(string="Level", comodel_name="ems.level")
	tsv_raw_text = fields.Text(string="Header's content (tab separated)", required=True)
	limesurvey_block_ids = fields.One2many(string="Blocks", comodel_name="ems.limesurvey_block", inverse_name="limesurvey_header_id")
	notes = fields.Text(string="Notes")

	@api.depends("name", "recipient", "level")
	def _compute_display_name(self):			
		for rec in self:				
			recipient = dict(survey_recipient_selection).get(rec.recipient)		
			if not rec.level and not rec.recipient:
				rec.display_name = "" if not rec.name else rec.name
			elif not rec.level:
				rec.display_name = "%s: %s" % (rec.name, recipient)
			else:
				levels = []
				for l in rec.level:
					levels.append(l.acronym)
				level_str = str.join(", ", levels)				
				rec.display_name = "%s: %s (%s)" % (rec.name, recipient, level_str) if rec.recipient else "%s (%s)" % (rec.name, level_str)

	def action_test(self):
		# TODO: Expected behaviour:
		#		1. Check if exists the main "ems" group:
		#			1.1. If exists, keeps its ID.
		#			1.2. If don't, fires exceptions and requires to create manually the group using the same user (suggest also the description).
		#
		#		2. Every survey will be created into the same group, because the EMS will keep track between every recipient and its survey.
		#		3. The surveys will be created as {DisplayName} - yyyyMMddHHmmssmmmmm
		#		4. A new sheet called "Current recipients" will contain the relation between recipients (Name, email, survey_recipient_selection, limesurvey survey name, limsurvey survey link).
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
			# The API does not allow to create groups.
			raise UserError("<TODO>")
			#ems_grp = self._create_group("ems", "DO NOT TOUCH! This group has been automatically created and is managed by the EMS.") 
		
		if not ems_grp:
			return {
					'type': 'ir.actions.client',
					'tag': 'display_notification',
					'params': {
						'title': 'No encontrado',
						'message': f"No existe ningún grupo con el nombre '{self.name}'",
						'type': 'warning',
						'sticky': False,
					}
				}
		else:
			return {
				'effect': {
					'fadeout': 'slow',
					'message': f"¡Éxito! El grupo existe. ID: {ems_grp['gsid']}",
					'type': 'rainbow_man',
				}
			}			


	def _run_api_request(self, method, params=[]):
		self.ensure_one()
		headers = {'content-type': 'application/json'}
		session_key = self._get_session_key(headers)

		if not session_key:
			raise UserError(_("Unable to get the LimeSurvey's session key."))
		
		try:
			session = [self._get_session_key(headers)]
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
		group_found = False if result is None else next((g for g in result if g['name'] == "ems"), None)
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
	special_course = fields.Integer(string="Course", default=1)
	special_wpi_enrolled = fields.Boolean(string="WorkPlace Intership (if enrolled)", default=False)
	special_subject_enrolled = fields.Boolean(string="Subject (all enrolled)", default=False)
	notes = fields.Text(string="Notes")	

