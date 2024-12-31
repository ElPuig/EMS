# -*- coding: utf-8 -*-
# from odoo import http


# class Ems(http.Controller):
#     @http.route('/ems/ems/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/ems/ems/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('ems.listing', {
#             'root': '/ems/ems/',
#             'objects': http.request.env['ems.ems'].search([]),
#         })

#     @http.route('/ems/ems/objects/<model("ems.ems"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('ems.object', {
#             'object': obj
#         })
