from odoo import http
from odoo.http import request

class EmsController(http.Controller):
    @http.route("/ems/check_group", type="json", auth="user")
    def check_group(self, group_id):
        return request.env.user.has_group(group_id)
