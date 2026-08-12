/** @odoo-module **/

import { registry } from "@web/core/registry";

// ems.notice (action_communication_list): a bulk-email screen with three widget types that
// had never been driven in a real browser - widget="html" (a rich-text editor, provided by
// html_editor and swapped in for the plain "html" field registration), widget="statusbar" on
// state, and widget="many2many_tags" on group_ids, whose onchange auto-populates the
// recipient list (notice_line_ids). This tour creates a real notice end-to-end, through to
// "Send now", verified against the DB afterward - with_delay() alone only queues a
// queue.job row, it does not execute it, so this never risks a real send (see
// tests/test_notice.py's own docstring for the same reasoning).
registry.category("web_tour.tours").add("ems_notice_create_and_send", {
    test: true,
    url: "/odoo/action-ems.action_communication_list",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Notices list loaded",
        },
        {
            trigger: ".o_list_button_add",
            content: "Create a new notice",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='subject'] input",
            content: "Fill in the subject",
            run: "edit Tour Notice Subject",
        },
        {
            // ems.group.name is computed ({study.acronym}{course}{group.acronym}) - the
            // seeded group's is 'TNOTT1NOTC' (see test_notice_tour.py).
            trigger: ".o_form_view .o_field_widget[name='group_ids'] input",
            content: "Search for the seeded group",
            run: "edit TNOTT1NOTC",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('TNOTT1NOTC')",
            content: "Select it from the dropdown",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='group_ids'] .o_tag",
            content: "Group tag added",
        },
        {
            trigger: ".o_field_widget[name='notice_line_ids'] .o_data_row td:contains('notice.tour.student@example.com')",
            content: "The onchange auto-populated the recipient list from the group's students",
        },
        {
            // widget="html" (via html_editor) renders a contenteditable div, not an
            // <input>/<textarea> - the generic "edit" action only supports those two tags
            // (see hoot-dom's isEditable()), so it fails here with "target should be
            // editable". Odoo's tour engine has a dedicated "editor <text>" action built
            // for exactly this (see mail's own composer tours for the same pattern).
            trigger: ".o_form_view .o_field_widget[name='message'] .note-editable",
            content: "Type the message into the rich-text editor",
            run: "editor Tour message body",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save the notice",
            run: "click",
        },
        {
            trigger: ".o_form_button_save:not(:visible)",
            content: "Save completed",
        },
        {
            trigger: ".o_statusbar_status button[data-value='draft'].o_arrow_button_current",
            content: "State starts as Draft",
        },
        {
            trigger: ".o_form_view button[name='action_send']:contains('Send now')",
            content: "Send now",
            run: "click",
        },
        {
            trigger: ".o_statusbar_status button[data-value='scheduled'].o_arrow_button_current",
            content: "State transitioned to Scheduled - the recipient's send job was queued",
        },
    ],
});

// The "Open error details" button on a notice line (invisible="not exception") had zero
// coverage - its popup view (ems.view_notice_line_exception_popup) had never been rendered.
// Reuses the notice created by ems_notice_create_and_send above (run first, in the same test
// method) - its line's real notification_id (queued by "Send now") is forced into a failed
// state with exc_info set directly in Python, since making a queue.job actually fail would
// need real async execution, which --test-enable never does.
registry.category("web_tour.tours").add("ems_notice_exception_popup", {
    test: true,
    url: "/odoo/action-ems.action_communication_list",
    steps: () => [
        { trigger: ".o_list_view", content: "Notices list loaded" },
        {
            trigger: ".o_list_view .o_data_cell:contains('Tour Notice Subject')",
            content: "Open the seeded (already sent) notice",
            run: "click",
        },
        {
            trigger:
                ".o_field_widget[name='notice_line_ids'] .o_data_row:has(.o_data_cell:contains('notice.tour.student@example.com')) button[name='open_exception_popup']",
            content: "Open the error-details popup for the failed notification",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='exception']:contains('Notice delivery failed (tour fixture).')",
            content: "The exception text is shown in the readonly popup",
        },
        {
            trigger: ".modal footer button:contains('Close')",
            content: "Close the popup",
            run: "click",
        },
    ],
});
