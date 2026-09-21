/** @odoo-module **/

import { registry } from "@web/core/registry";

// Staff absences render on Odoo's own Time Off screens, extended by views/time_off/leave.xml.
// Neither ./upgrade.sh nor the TransactionCase tests open a browser, so this is what actually
// proves the inherited list and form still render with the EMS fields on them - and that the
// Direction check is editable and round-trips to the list.
registry.category("web_tour.tours").add("ems_absence_request", {
    test: true,
    url: "/odoo/action-hr_holidays.hr_leave_action_holiday_allocation_id",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "The Time Off list loads with the EMS columns inherited into it",
        },
        {
            trigger: ".o_list_button_add:contains('New absence')",
            content: "The create button says what it creates. A list view's button is a single "
                + "shared template, so this guards a change made globally under a model check",
        },
        {
            // A cell, not the row: clicking the <tr> itself only selects it.
            trigger: ".o_list_view .o_data_row:contains('Tour Absent Teacher') td[name='ems_type_short_name']",
            content: "The seeded absence is listed, open it",
            run: "click",
        },
        {
            trigger: ".o_form_view",
            content: "The request form opened",
        },
        {
            // The nine options are shown in full, like the original Google form: several of
            // them are the legal wording the employee declares by choosing them.
            trigger: ".o_form_view .o_field_widget[name='holiday_status_id'] input[type='radio']",
            content: "The absence type is a radio list, not a dropdown",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='holiday_status_id'] label .fw-bold",
            content: "And the short name - the part before the colon, the one lists and the "
                + "calendar show - is set in bold inside each option",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='ems_full_day']",
            content: "The whole-day flag renders on the inherited form",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='ems_counts_hours']",
            content: "So does the monthly-report flag, visible to the approver",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='ems_head_state']",
            content: "The Head's own column shows on the form",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='ems_direction_state']",
            content: "And Direction's, which does not depend on it: either can come first",
        },
        {
            trigger: ".o_form_view .o_form_statusbar button[name='action_ems_direction_done']",
            content: "Direction approves from the header, before the Head has decided",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Absent Teacher') td[name='ems_status']:contains('Pending Head')",
            content: "Taking a decision goes back to the list, where only the Head's approval "
                + "is now missing",
        },
        {
            // Checked in the list, not via input[value=...]: OWL does not sync the HTML
            // attribute, so the list is the only honest read-back after a save.
            trigger: ".o_list_view .o_data_row:contains('Tour Absent Teacher') "
                + "td[name='ems_direction_state'] .text-bg-success:contains('Done')",
            content: "Direction's check round-tripped to the list, as a green badge - the "
                + "column shows for every reader, not just Direction",
        },
    ],
});

// "Vista general" is the centre-wide absence calendar, the only calendar screen left in the
// menu once the employee dashboard was hidden. It is a different view under a different action
// from the request tour above, and an OWL template inheritance error only ever surfaces in a
// browser, never in ./upgrade.sh - which merely checks the XML parses.
registry.category("web_tour.tours").add("ems_absence_dashboard", {
    test: true,
    url: "/odoo/action-hr_holidays.action_hr_holidays_dashboard",
    steps: () => [
        {
            trigger: ".o_calendar_view",
            content: "The absence dashboard loads (its templates compile)",
        },
        {
            trigger: ".btn-time-off:contains('Absence request')",
            content: "The create button says what it creates, instead of a bare 'New'",
        },
        {
            trigger: "body:not(:has(a:contains('New Allocation Request')))",
            content: "And the allocation request card is gone: allocations are a blocking quota "
                + "mechanism every EMS absence type opts out of",
        },
    ],
});

// Removing the justification of an absence is destructive and irreversible, and the people who
// click that "x" are reviewing dozens of requests in a row. This is the whole point of the
// ems_attachment_confirm widget, so it needs a browser to prove it: the dialog appears, and
// cancelling it really does leave the file alone.
//
// The request it runs on is deliberately of a type that does not require a document
// ("Justified absence") and is already approved: Odoo hides the attachment on both counts, and
// the centre files a justification for any absence and mostly after the fact, so this also
// proves the two conditions really are gone from the inherited form.
registry.category("web_tour.tours").add("ems_absence_justification", {
    test: true,
    url: "/odoo/action-hr_holidays.hr_leave_action_holiday_allocation_id",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Documented Teacher') td[name='ems_type_short_name']",
            content: "Open the request that carries a supporting document",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='supported_attachment_ids']",
            content: "The justification is on the form of an approved request whose type asks "
                + "for no document at all - neither condition hides it any more",
        },
        {
            trigger: ".o_form_view .o_attachment:contains('justificant')",
            content: "Its justification is attached",
        },
        {
            trigger: ".o_form_view .o_attachment:contains('justificant') .o_attachment_delete",
            content: "Ask to remove it",
            run: "click",
        },
        {
            trigger: ".modal:contains('Remove the supporting document')",
            content: "A confirmation is asked for, instead of the file just disappearing",
        },
        {
            trigger: ".modal-footer button:contains('Cancel')",
            content: "Back out of it",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_attachment:contains('justificant')",
            content: "The justification is still there - cancelling really cancels",
        },
        {
            trigger: ".o_form_view .o_attachment:contains('justificant') .o_attachment_delete",
            content: "Ask again, and confirm this time",
            run: "click",
        },
        {
            trigger: ".modal-footer button:contains('Remove')",
            content: "Confirm the removal",
            run: "click",
        },
        {
            trigger: ".o_form_view:not(:has(.o_attachment:contains('justificant')))",
            content: "And now it is gone",
        },
        {
            // Removing an attachment leaves the record dirty; a tour that ends on an unsaved
            // form is a failure, and leaving it unsaved would not prove the removal persisted.
            trigger: ".o_form_button_save",
            content: "Save the request without its justification",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved",
            content: "Saved, so the removal really went through",
        },
    ],
});

// Refusing is the one absence decision nobody at the centre can undo: Odoo reserves resetting
// a refused request to its Time Off Administrator group, which res.users
// ._ems_sync_time_off_groups leaves nobody holding, so the employee has to file the whole
// request again. Both buttons that cause it are one stray click away from the Approve button
// beside them, so both are confirmed first - and only a browser can prove a dialog appears.
registry.category("web_tour.tours").add("ems_absence_refuse_confirm", {
    test: true,
    url: "/odoo/action-hr_holidays.hr_leave_action_holiday_allocation_id",
    steps: () => [
        {
            // The list's own Refuse button: a bare "x" icon at the end of the row, sitting
            // right next to Approve. This is the one that gets clicked by accident.
            trigger: ".o_list_view .o_data_row:contains('Tour Absent Teacher') button[name='action_refuse']",
            content: "Refuse the pending request straight from the list",
            run: "click",
        },
        {
            trigger: ".modal:contains('cannot be reopened')",
            content: "It asks first, and says why it matters",
        },
        {
            trigger: ".modal-footer button:contains('Cancel')",
            content: "Back out of it",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Absent Teacher') .o_field_widget[name='ems_status']:contains('Pending')",
            content: "The request is still pending - cancelling really cancels",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Absent Teacher') td[name='ems_type_short_name']",
            content: "Open the same request",
            run: "click",
        },
        {
            // '.o_form_statusbar', not 'header': a form's <header> is rendered as that div,
            // so a literal header selector matches nothing.
            trigger: ".o_form_view .o_form_statusbar button[name='action_refuse']",
            content: "The form has the same button, and the same confirmation",
            run: "click",
        },
        {
            trigger: ".modal:contains('Refuse this absence request')",
            content: "This one names the decision in its title too, which a list view's schema "
                + "does not allow",
        },
        {
            trigger: ".modal-footer button:contains('Refuse')",
            content: "Confirm, and the request is refused for good",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Absent Teacher') td[name='ems_status']:contains('Refused')",
            content: "Refused, and back on the list",
        },
    ],
});

// Filing a request has to be a deliberate act: the whole point of ems_submitted is that Odoo's
// own autosave cannot create an absence on its own. This drives the real flow, and checks the
// button stays disabled until the request is actually complete - otherwise it would set the
// flag, fail to save, and then hide itself on a request nobody ever filed.
registry.category("web_tour.tours").add("ems_absence_submit", {
    test: true,
    url: "/odoo/action-hr_holidays.hr_leave_action_my",
    steps: () => [
        {
            trigger: ".o_list_button_add",
            content: "Start a new request",
            run: "click",
        },
        {
            trigger: ".o_form_view:not(:has(.o_field_widget[name='ems_direction_state']))",
            content: "Direction's check is not on a request being written - they cannot have "
                + "verified a justification for something that does not exist yet",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='holiday_status_id']:not(:has(input[type='radio']:checked))",
            content: "No absence type is preselected: choosing one is a declaration, not a default",
        },
        {
            // The tooltip is on a wrapper, since a disabled button emits no hover events.
            trigger: "span[data-tooltip*='Choose the type of absence'] .o_ems_absence_submit[disabled]",
            content: "Nothing chosen yet, so there is nothing to send - and it says so",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='holiday_status_id'] input[type='radio']",
            content: "Pick an absence type from the radio list",
            run: "click",
        },
        {
            trigger: ".o_ems_absence_submit[disabled]",
            content: "Still disabled: both times are 00:00, so no hours are being requested",
        },
        {
            // The seeded types are ordered, and ATRI is the last radio option. Picked
            // before the whole-day tick on purpose: changing the type re-proposes that
            // type's own defaults, which would undo it.
            trigger: ".o_form_view .o_field_widget[name='holiday_status_id'] input[type='radio']:last",
            content: "Switch to the ATRI absence type",
            run: "click",
        },
        {
            trigger: ".o_form_view a[href*='atriportal.gencat.cat/ATRI-ng']",
            content: "Picking ATRI points the employee at the portal the leave is really "
                + "granted on, without waiting for them to find out later",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='ems_full_day'] input",
            content: "Ask for the whole day, which removes the need for times",
            run: "click",
        },
        {
            trigger: "span[data-tooltip*='Accept the responsible declaration'] .o_ems_absence_submit[disabled]",
            content: "Still disabled, and saying why: the declaration is unsigned",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='ems_responsible_declaration'] input",
            content: "Accept the responsible declaration, which every absence needs",
            run: "click",
        },
        {
            trigger: ".o_ems_absence_submit:not([disabled])",
            content: "Now the request can be sent",
            run: "click",
        },
        {
            trigger: ".modal:contains('Send the absence request')",
            content: "The confirmation is asked for before anything is filed",
        },
        {
            trigger: ".modal-footer button:contains('Send request')",
            content: "Confirm",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved",
            content: "Only now is the request saved",
        },
    ],
});

// The per-employee report, the spreadsheet's "Total per profe" tab. Worth a browser: the health
// hours column only means anything with its per-group total, and a report that still offered a
// "New" button would invite filing an absence from a screen that has no send button on it.
registry.category("web_tour.tours").add("ems_absence_report", {
    test: true,
    url: "/odoo/action-hr_holidays.action_hr_available_holidays_report",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "The per-employee report loads",
        },
        {
            trigger: ".o_list_view th[data-name='ems_health_hours']",
            content: "The health hours column is there - the figure that has to stay under the "
                + "yearly allowance",
        },
        {
            trigger: ".o_control_panel:not(:has(.o_list_button_add))",
            content: "And there is no way to create an absence from a report",
        },
        {
            trigger: ".o_searchview_facet:contains('Current Course')",
            content: "Filtered by the school year, not the calendar year",
        },
    ],
});

// The monthly report, the spreadsheet's "Totals per mes" tab. The two figures it exists for are
// the summed hours and the number of absences behind them, and both come from the grouping, so
// a browser is the only place to check they actually appear.
registry.category("web_tour.tours").add("ems_absence_monthly_report", {
    test: true,
    url: "/odoo/action-ems.action_absence_monthly_report",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "The monthly report loads",
        },
        {
            trigger: ".o_searchview_facet:contains('Month')",
            content: "Grouped by month out of the box",
        },
        {
            trigger: ".o_list_view th[data-name='ems_counted_hours']",
            content: "With the hours that count towards the monthly report",
        },
        {
            trigger: ".o_control_panel:not(:has(.o_list_button_add))",
            content: "And no way to file an absence from a report",
        },
    ],
});

// Direction's side of the double approval. It lands on its own "Waiting For Me" - what the Head
// has approved and Direction has not reviewed yet - and reviews it from the row, without opening
// anything, with its own buttons beside its own column. The Head's Approve is not on offer: on
// somebody else's request it would decide for the Head instead of recording Direction's review.
registry.category("web_tour.tours").add("ems_absence_direction_review", {
    test: true,
    url: "/odoo/action-hr_holidays.hr_leave_action_action_approve_department",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Reviewed Teacher')",
            content: "The request the Head approved is waiting for Direction",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Absent Teacher')",
            content: "So is the one nobody has decided yet: either approval can come first",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Reviewed Teacher'):not(:has(button[name='action_approve'])):not(:has(button[name='action_refuse']))",
            content: "And Direction is not offered the Head's buttons on it",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Reviewed Teacher') button[name='action_ems_direction_missing_doc']",
            content: "The document has not arrived: say so from the row",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Reviewed Teacher') td[name='ems_status']:contains('Pending Document')",
            content: "It stays on Direction's list, now waiting for the document",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Reviewed Teacher') td[name='ems_type_short_name']",
            content: "Open it",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_statusbar button[name='action_ems_direction_done']",
            content: "The document is in: Direction approves from the header",
            run: "click",
        },
        {
            trigger: ".o_list_view:not(:has(.o_data_row:contains('Tour Reviewed Teacher')))",
            content: "Back on the list, which it has left: approved by both, nothing left for "
                + "Direction",
        },
        {
            trigger: ".o_switch_view.o_kanban",
            content: "The kanban of the same action renders too",
            run: "click",
        },
        {
            trigger: ".o_kanban_view",
            content: "Kanban loaded",
        },
    ],
});

// The Head's side: Approve/Refuse beside the Head's column, none of Direction's buttons, and an
// approval that leaves the request waiting for Direction.
registry.category("web_tour.tours").add("ems_absence_head_approval", {
    test: true,
    url: "/odoo/action-hr_holidays.hr_leave_action_holiday_allocation_id",
    steps: () => [
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Absent Teacher'):not(:has(button[name='action_ems_direction_done']))",
            content: "Direction's buttons are Direction's alone",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Absent Teacher') button[name='action_approve']",
            content: "The Head approves from the row",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Absent Teacher') td[name='ems_head_state']:contains('Approved')",
            content: "The Head's column says so",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Absent Teacher') td[name='ems_status']:contains('Pending Direction')",
            content: "And the request now waits for Direction",
        },
        {
            trigger: ".o_switch_view.o_kanban",
            content: "The kanban of the same action renders too",
            run: "click",
        },
        {
            trigger: ".o_kanban_view",
            content: "Kanban loaded",
        },
    ],
});
