/** @odoo-module **/

import { registry } from "@web/core/registry";

// The "Recipients" tab on ems.limesurvey_header's form (and ems.limesurvey_recipient's own
// add-student popup) had zero coverage - limesurvey_block_tour.js only ever opens the
// "Blocks" tab on the same header form.
registry.category("web_tour.tours").add("ems_limesurvey_recipient_add_student", {
    test: true,
    url: "/odoo/action-ems.action_limesurvey_header_tree",
    steps: () => [
        { trigger: ".o_list_view", content: "Surveys list loaded" },
        {
            trigger: ".o_list_view .o_data_cell:contains('LimeSurvey Recipient Tour Header')",
            content: "Open the seeded header",
            run: "click",
        },
        {
            trigger: ".o_notebook .nav-link:contains('Recipients')",
            content: "Open the Recipients tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='limesurvey_recipient_ids']",
            content: "The (empty) recipients list renders without crashing",
        },
        {
            trigger: "button:contains('Add a new student')",
            content: "Open the add-student popup",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='student_id'] input",
            content: "Search for the seeded student",
            run: "edit LimeSurvey Recipient Tour Student",
        },
        {
            trigger:
                ".o-autocomplete--dropdown-item:contains('LimeSurvey Recipient Tour Student')",
            content: "Select the student",
            run: "click",
        },
        {
            trigger: ".modal footer button:contains('Add')",
            content: "Add the recipient",
            run: "click",
        },
        {
            trigger:
                ".o_field_widget[name='limesurvey_recipient_ids'] .o_data_cell:contains('LimeSurvey Recipient Tour Student')",
            content: "The new recipient shows in the list",
        },
    ],
});
