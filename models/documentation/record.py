# -*- coding: utf-8 -*-

from odoo import models, fields, api

class record(models.Model):
	_name = "ems.record"
	_description = "Record: Defines a record (meeting, evaluacion, etc.)."
	
	date = fields.Datetime(string="Date", required=True)
	nature = fields.Selection(string="Nature", selection=[("Ordinary", "ordinary"), ("Extraordinary", "extraordinary")])
	modality = fields.Selection(string="Modality", selection=[("In person", "in person"), ("Online", "online"), ("Hybrid", "hybrid")])
	space_id = fields.Many2one(string="Space", comodel_name="ems.space")
	assistant_ids = fields.Many2many(string="Assistants", comodel_name="res.partner") 
	abstent_ids = fields.Many2many(string="Abstents", comodel_name="res.partner") 

	#TODO: Should also set the permissions for the record (department and also workgroup <-- NEW)
	#	   https://www.cybrosys.com/blog/how-to-create-record-rule-in-odoo-16

	#index -> should be computed using the record section but some content is fixed
	#	1. Last record approval (if exists).
	#	2. Last agreements review.
	#	3. Regular meeting content. where each record section should have.
	#		3.1. Title.
	#		3.2. The content or another section.
	#		NOTE: pending topics of the last meeting could be added.
	#	4. Agreements
	#	5. Pending topics.
	#	6. Signature
	#		6.1. By the user who created the record (will be signed by clicking on a button).
	#		6.2. By another user who aproves it, should be loaded as manager of the previous one, but this could limit some scenearios so it"s better to let it free.
	#			 The redactor adds the aprover, and a notification will be sent. The aprover can aprove the record or not.
	#			 The record can be edited, but then it becomes desaproved. 
	#
	#	7. Attachments (this will allow to attach any custom document).
	#
	#	PENDING: changes registry?



