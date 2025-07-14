# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import xml.etree.ElementTree as ET
import base64

class ims_working_schedule(models.Model):
	_inherit = 'resource.calendar'

	def action_import_planner_data(self):
		raise ValidationError("HOLA")

class ims_working_schedules_import_wizard(models.TransientModel):
	_name = "ims.working_schedules_import_wizard"
	_description = "Working schedules: import wizard."

	attachment_id = fields.Many2one(string="Attachment", comodel_name="ir.attachment", domain="[('res_model', '=', 'ims.working_schedules_import_wizard')]")
	file = fields.Binary(string="Planner file (XML)", related="attachment_id.datas")

	def import_planner_data(self):	
		for rec in self:			
			raise ValidationError("HOLA")
		
	@api.model_create_multi
	def create(self, values):
		for item in values:
			if 'file' not in item or not item.get('file'):
				raise ValidationError("No XML file has been loaded. Please, provide an XML file and try again.")
			else:				
				file = item.get('file')
				xml_content = base64.b64decode(file)
				tree = ET.ElementTree(ET.fromstring(xml_content))
				
				root = tree.getroot()
				for teacherNode in root:					
					email = teacherNode.attrib['name'].split(' ')[0]
					# TODO: find the teacher using the email
					
					for dayNode in teacherNode:
						number = dayNode.attrib['name'].split(' ')[0]
						# TODO: convert the number to the proper object (1: Monday, 2: Tuesday...)
												
						for hourNode in dayNode:
							# Ignore empty hours (lack of activities)
							id = None
							subject = None
							group = None
							
							for content in hourNode:
								if content.tag == 'Activity':
									id = content.attrib['id'].split(' ')[0]
								elif content.tag == 'Subject':
									subject = content.attrib['name'].split(' ')[0]
								elif content.tag == 'Students':
									group = content.attrib['name'].split(' ')[0]														
							
							if id is not None:
								# TODO: load the subject and the group
								fake = 0			

		return None
				
