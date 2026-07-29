import hashlib, traceback
from markupsafe import Markup
from odoo import models, fields, _

class EmsBase(models.AbstractModel):
    _name = 'ems.base'
    _description = 'EMS base model\'s code)'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    user_is_admin = fields.Boolean(default=lambda self: self.get_user_is_admin(), store=False)
    user_is_tutor = fields.Boolean(default=lambda self: self.get_user_is_tutor(), store=False)
    active = fields.Boolean(default=True)

    # TODO: Some Odoo models define this method to archive them and also their related fields.
    #       Implement this in all our models! Needed, for example, to avoid deleting sessions.
    def action_archive(self):
        for record in self:
            record.active = False

    # The current user is admin.
    def get_user_is_admin(self):
        return self.env.user.has_group('ems.group_academic_admin')

    # The current user is tutor of some group.
    def get_user_is_tutor(self):
        for employee in self.env.user.employee_ids:
            if employee.tutorship_ids != False and len(employee.tutorship_ids) > 0:
                return True
        return False

    # The current user is the tutor of the current model's instance.
    def get_user_is_tutor_of_self(self):
        if 'tutor_id' in self.env[self._name]._fields:
            return self.tutor_id.id != False and self.tutor_id.user_id == self.env.user

    # Returns a hashcode which is persistent between execution (not like the Python's native one).
    def persistent_hash(self, data):
        data_bytes = str(data).encode('utf-8')
        digest = hashlib.sha256(data_bytes)
        return digest.hexdigest()

    # Safe <ul><li>...</li></ul> from plain strings - each item is HTML-escaped by
    # Markup(...).format(). Markup('').join(...) (not plain str.join) keeps the Markup type
    # through the join, or the outer format() below would re-escape the already-escaped
    # fragments and show literal &lt;li&gt; tags instead of a real list - the same subtle
    # gotcha independently found and fixed in every wizard that builds this kind of HTML.
    def build_html_list(self, items):
        if not items:
            return Markup("")
        return Markup("<ul>{}</ul>").format(
            Markup("").join(Markup("<li>{}</li>").format(item) for item in items)
        )

    # Shared body for an "already in use, exclude from picker" Many2many compute: `False`
    # unless `condition(record)` is truthy, in which case `record.mapped(mapped_path)`. The
    # field's own @api.depends stays on the caller's concrete compute method - only the body
    # is shared, since Odoo requires the decorator on the actual method that owns the field.
    def compute_exclusion_ids(self, field_name, condition, mapped_path):
        for record in self:
            record[field_name] = False
            if condition(record):
                record[field_name] = record.mapped(mapped_path)

    # To send a notification (won't be sent till a BBDD commit)
    def notify(self, title, message, notification_type, sticky=False):
        # notification_type: success; warning; danger; info
        # NOTE: uses _bus_send (user channel) instead of bus.bus._sendone (partner channel) — the partner
        # channel is not reliably subscribed in Odoo v18 multi-worker production environments.
        self.env.user._bus_send("simple_notification", {
            "title": title,
            "message": message,
            "type": notification_type,
            "sticky": sticky
        })

    # Writes a regular log message in the chatter. 
    def chatter(self, message):
        self.message_post(
            body = message,
            message_type = 'notification',
            subtype_xmlid='mail.mt_note'
        )

    # Writes an exception (using a red warning block) in the chatter.
    def chatter_exception(self, exception):
        # NOTE: exception/traceback text is untrusted (an exception message can echo raw
        # user/DB-derived content, e.g. an uploaded file's cell value in a ValidationError) -
        # Markup(...).format() auto-escapes plain-str args, unlike a plain f-string, which
        # would have inserted it into the HTML unescaped.
        self.chatter(
            Markup(
                """
                <div class="alert alert-danger mb-0" role="alert">
                    <h5 class="alert-heading mb-1">
                        <i class="fa fa-exclamation-triangle me-1"></i>
                        {}
                    </h5>
                    <p class="mb-2">{}</p>
                    <hr class="mt-1 mb-2">

                    <details>
                        <summary class="text-muted fw-bold" style="cursor: pointer;">
                            <i class="fa fa-bug me-1"></i> {}
                        </summary>

                        <pre class="mt-2 p-2 bg-light border text-dark rounded" style="font-size: 0.85em; white-space: pre-wrap; max-height: 250px; overflow-y: auto;">{}</pre>
                    </details>
                </div>
                """
            ).format(
                _("An error occurred during the process"),
                str(exception),
                _("See technical details (Exception)"),
                traceback.format_exc(),
            )
        )