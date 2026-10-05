/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { blockingActionFormView, overlayLines } from "./blocking_action_form";

/**
 * Blocking overlay for the contact data request assistant (issue #507). Sending to a whole group,
 * study or level creates the requests, invites whoever lacks portal access and queues an email
 * per recipient, which looks frozen behind Odoo's small "Loading" pill. See
 * blocking_action_form.js for why there is no live progress counter.
 */
registry.category("views").add(
    "ems_contact_data_request_send_form",
    blockingActionFormView({
        action_apply: (data) => overlayLines(
            _t("Processing the requests…"),
            "",
            _t("Each student, or the family of a minor, is emailed the link to the portal."),
            data.grant_portal ? _t("Whoever lacks portal access is invited to it.") : null,
            _t("This can take a while — do not close this window."),
        ),
    }),
);
