/** @odoo-module **/

import { registry } from "@web/core/registry";

// A Department Chief writing a notice from Communications > Notices: only the groups their
// department teaches are offered (ems.notice.available_group_ids). Seed data comes from
// TestNoticeDepartmentChiefTour (tests/test_notice_department_chief_tour.py).
registry.category("web_tour.tours").add("ems_notice_department_chief", {
    test: true,
    url: "/odoo/action-ems.action_communication_list",
    steps: () => [
        {
            trigger: ".o_list_button_add",
            content: "The chief reaches the notices list and creates a notice",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='subject'] input",
            content: "Fill in the subject",
            run: "edit Department notice",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='group_ids'] input",
            content: "Look for a group the department does not teach",
            run: "edit TNDCB",
        },
        {
            trigger: ".o-autocomplete--dropdown-menu:not(:has(.o-autocomplete--dropdown-item:contains('TNDCB')))",
            content: "It is not offered",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='group_ids'] input",
            content: "Look for the department's own group",
            run: "edit TNDCA",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('TNDCA')",
            content: "It is offered: select it",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='message'] .note-editable",
            content: "Type the message",
            run: "editor Department message",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved",
            content: "Saved",
        },
    ],
});
