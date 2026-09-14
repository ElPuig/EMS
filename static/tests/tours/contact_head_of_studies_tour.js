/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #448: a Head/Deputy Head of Studies (not the student's own tutor) reported the
// personal-data block hidden and an AccessError deleting a family contact. tests/
// test_student_data_reader.py and test_contact_relation_wizard.py already prove the
// permission wiring at the ORM level - this tour proves the real click path actually works
// in a browser: the block renders, the "Add contact" wizard saves, and the inline unlink
// button (the literal AccessError the developer hit - see form.xml, not routed through any
// sudo()) actually deletes. Deliberately NOT the full admin/secretary tour
// (ems_contact_tabs_and_relation_wizard): this fix only extends write access to the
// student's own contact data and family relations, not to enrollments/grades/attendance -
// a Head of Studies who isn't this student's tutor still can't edit the Studies tab, so
// reusing that tour end to end would fail on an out-of-scope step for the wrong reason.
registry.category("web_tour.tours").add("ems_contact_head_of_studies_full_access", {
    test: true,
    url: "/odoo/action-ems.action_student_kanban",
    steps: () => [
        {
            trigger: ".o_control_panel",
            content: "Educational Community loaded",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('HoS Contact Tour Student')",
            content: "Open the seeded student",
            run: "click",
        },
        {
            trigger: ".o_form_view label:contains('Personal email')",
            content: "The personal-data block (invisible=\"read_only_user\") now renders for a "
                + "Head of Studies who is not this student's own tutor",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Contacts & Addresses')",
            content: "Open the Contacts & Addresses tab, home of the relation wizard button",
            run: "click",
        },
        {
            trigger: ".o_form_view button[name='action_open_relation_wizard']",
            content: "\"Add contact\" is visible (also gated by read_only_user) - click it",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='type_selection_id'] input",
            content: "Choose a relation type",
            run: "edit Father",
        },
        {
            trigger: ".o-autocomplete--dropdown-menu li:contains('Father')",
            content: "Select the Father relation type",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='is_new_contact'] input",
            content: "Check 'New contact' to reveal the new-contact fields",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='firstname'] input",
            content: "Fill in first name",
            run: "edit HoS",
        },
        {
            trigger: ".modal .o_field_widget[name='lastname'] input",
            content: "Fill in last name",
            run: "edit Tour Father",
        },
        {
            trigger: ".modal .o_field_widget[name='phone'] input",
            content: "Fill in phone (at least one contact method is required)",
            run: "edit 600000000",
        },
        {
            trigger: ".modal .o_field_widget[name='document_id'] input",
            content: "Fill in document ID (at least one identification document is required)",
            run: "edit 12345678A",
        },
        {
            trigger: ".modal-footer .btn-primary",
            content: "Save the new family contact - the wizard's own sudo()'d action_save()",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='relation_all_ids'] .o_data_row td:contains('HoS Tour Father')",
            content: "The new relation shows up in the Addresses tab list",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='relation_all_ids'] .o_data_row:has(td:contains('HoS Tour Father')) button[name='unlink']",
            content: "Delete the relation via the inline button - a plain object-method call with "
                + "no sudo(), so this is the real AccessError the developer hit",
            run: "click",
        },
        {
            trigger: ".modal .modal-footer button:contains('Ok')",
            content: "Confirm the delete",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='relation_all_ids']:not(:has(td:contains('HoS Tour Father')))",
            content: "The relation is gone - the unlink actually succeeded",
        },
    ],
});
