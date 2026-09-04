/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #391: the Head of Studies may now create and edit teachers, private information
// included (both ems.group_head_of_studies and ems.group_tac imply hr.group_hr_user).
// Backend tests (tests/test_employee_staff_permissions.py) prove the ACL and the record rules
// are right, but they never render anything. Only a real browser proves the Teachers screen
// actually offers a "New" button to this user, that the Google Workspace header buttons show
// up, that the personal email is reachable from the main screen, and that the form saves -
// the save being what triggers _ems_create_personal_calendar, which needs its own
// resource.calendar ACL line to work.
registry.category("web_tour.tours").add("ems_employee_staff_permissions", {
    test: true,
    url: "/odoo/action-ems.action_employee_kanban",
    steps: () => [
        {
            trigger: ".o_control_panel",
            content: "Teachers loaded for the Head of Studies",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        // --- editing an existing teacher ------------------------------------
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('0000 Staff Perms Teacher')",
            content: "Open the tour's own teacher",
            run: "click",
        },
        {
            trigger: ".o_statusbar_buttons button[name='action_create_google_account']",
            content: "The Google Workspace button is visible to the Head of Studies",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "The name is editable, not locked behind a read-only form",
            run: "edit 0000 Staff Perms Teacher Renamed",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save the renamed teacher",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved",
            content: "The edit was accepted",
        },
        {
            trigger: ".o_breadcrumb a",
            content: "Back to the list",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('0000 Staff Perms Teacher Renamed')",
            content: "The rename really persisted (checked in the list, not via input[value])",
        },
        // --- creating a brand-new teacher -----------------------------------
        {
            trigger: ".o_list_button_add",
            content: "Create a new teacher",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='name'] input",
            content: "Name the new teacher",
            run: "edit 0000 Staff Perms Created",
        },
        {
            // The personal address is where the Google Workspace credentials are actually
            // delivered, so the employee form marks it required on new teaching staff. The
            // field carries groups="hr.group_hr_user": before this issue it was absent from this
            // user's form entirely - and with it the "required", which is why a Head of Studies
            // could create a teacher with no way to send them their credentials. Reaching it
            // here at all is the regression test for that.
            //
            // form.xml renders this field twice on purpose: once in its original place inside
            // the "Private Information" tab, and once on the main screen so a required field
            // is not buried in a tab while the record is being created. No step here opens a
            // tab, and tour triggers only match visible elements, so this necessarily matches
            // the main-screen occurrence - which is what makes it a regression test for that
            // second occurrence existing at all.
            trigger: ".o_form_view .o_field_widget[name='private_email'] input",
            content: "The personal email sits on the main screen, no tab navigation needed",
            run: "edit staff.perms.created@example.com",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save the new teacher",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved",
            content: "The new teacher was created, personal calendar included",
        },
        {
            trigger: ".o_breadcrumb a",
            content: "Back to the list once more",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('0000 Staff Perms Created')",
            content: "The new teacher shows up in the list",
        },
    ],
});
