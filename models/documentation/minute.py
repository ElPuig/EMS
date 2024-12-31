# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime

class minute(models.Model):
	_name = "ems.minute"
	_description = "Minute: Defines a meeting minute (department meeting, workgroup meeting, evaluation meeting...)."
	
	date = fields.Datetime(string="Date", default=datetime.today(), required=True)
	type = fields.Selection(string="Type", default="department", selection=[("department", "Department meeting"), ("workgroup", "Workgroup meeting"), ("evaluation", "Evaluation meeting")], required=True) #TODO: more types?	
	nature = fields.Selection(string="Nature", default="ordinary", selection=[("ordinary", "Ordinary"), ("extraordinary", "Extraordinary")], required=True)
	modality = fields.Selection(string="Modality", default="in-person", selection=[("in-person", "In-person"), ("online", "Online"), ("hybrid", "Hybrid")], required=True)	

	space_id = fields.Many2one(string="Space", comodel_name="ems.space", required=True)
	department_id = fields.Many2one(string="Department", comodel_name="hr.department")
	workgroup_id = fields.Many2one(string="Workgroup", comodel_name="ems.workgroup")	

	#Note: foreign to the same table should be declared manually
	assistant_ids = fields.Many2many(string="Assistants", comodel_name="res.partner", relation="ems_minute_assistant_rel", column1="ems_minute_id", column2="res_partner_id", domain="[('type','=','contact')]", required=True) 
	abstent_ids = fields.Many2many(string="Abstents", comodel_name="res.partner", relation="ems_minute_absetnt_rel", column1="ems_minute_id", column2="res_partner_id", domain="[('type','=','contact')]") 
	
	members = fields.Char(string="Memebers", compute='_compute_members')
	abstract = fields.Char(string="Abstract or main topic", size=255, required=True)
	
	@api.depends('type', 'workgroup_id', 'department_id', 'nature')
	def _compute_display_name(self):              
		for rec in self:
			rec.display_name = "%s: %s (%s)" % (dict(rec._fields['type'].selection).get(rec.type), rec.workgroup_id.name if type == "workgroup" else rec.department_id.name, dict(rec._fields['nature'].selection).get(rec.nature))

	@api.depends("type")
	def _compute_members(self):
		for rec in self:
			rec.members = "Workgroup: %s" % rec.workgroup_id.name if rec.type == "workgroup" else "Department: %s" % rec.department_id.name

	#TODO: Should also set the permissions for the record (department and also workgroup <-- NEW)
	#	   https://www.cybrosys.com/blog/how-to-create-record-rule-in-odoo-16

	#TODO:
	#	Minute types: should be able to create new ones, specifying the content.
	#		Regular:
	#			1. Last record approval (if exists).
	#			2. Last agreements review (if exists).
	#			3. Regular meeting content (each entry has title/topic + content). Note: pending topics of the last meeting could be added first.
	#			4. Current agreements.
	#			5. Pending topics (maybe automatically computed)
	#			6. Attachments (this will allow to attach any custom document).
	#			7. Signature
	#				7.1. By the user who created the record (will be signed by clicking on a button).
	#				7.2. By another user who aproves it, should be loaded as manager of the previous one, but this could limit some scenearios so it"s better to let it free.
	#			 		 The redactor adds the aprover, and a notification will be sent. The aprover can aprove the record or not.
	#			 		 The record can be edited, but then it becomes desaproved.
	# 					 Once aproved, all the members can read the minute (maybe a PDF?) 
	#			0. Changes registry, only when something has changed, maybe every PDF can be stored and available. 
	#
	#		Department:
	#			1. Exactly as the "regular" one, but between 2 and 3, an entry for harmonization.
	#		
	#		Workgroup (open): 
	# 			TODO
	#		Workgroup (regular): 
	# 			TODO
	#		Workgroup (clone): 
	# 			TODO
	#		Avaluation (pre / 1st / 2nd / 3th): 
	# 			TODO

	# The main idea is to define the minute type with its content, and the create the entry (from scratch or using a previous one) in order to write the regular meeting content. 
	# A wizard will be used in order to fill the minute, it will be clearer the barrier between setup and redacting. 

	# IDEA: maybe the department could inherit from a workgroup (or viceversa), so the minute can use just a single type of members (simplification). 




