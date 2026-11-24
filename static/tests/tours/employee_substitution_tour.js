/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #748, as the Head of Studies (the least privileged role that edits a teacher): declaring
// a substitution from the substitute's form warns that their schedule will be replaced, and on
// saving shows the "Substitute" ribbon and the copy of the replaced teacher's guard duty in the
// Schedule tab; the replaced teacher's form shows the "Substituted" ribbon and who replaces them.
// Visits the list, the form and the kanban of the Teachers action.
registry.category("web_tour.tours").add("ems_employee_substitution", {
    test: true,
    url: "/odoo/action-ems.action_employee_kanban",
    steps: () => [
        {
            trigger: ".o_kanban_view .o_kanban_record:contains('0000 TSUBT Substitute')",
            content: "Teachers kanban loaded, with the substitute",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('0000 TSUBT Substitute')",
            content: "Open the substitute",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Teaching')",
            content: "Open the Teaching tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='substitute_of_id'] input",
            content: "Pick the teacher being replaced",
            run: "edit TSUBT Titular",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('0000 TSUBT Titular')",
            content: "Select them",
            run: "click",
        },
        {
            trigger: ".modal:contains('The schedule will be replaced') .modal-footer .btn-primary",
            content: "Warned that the schedule will be replaced: close the warning",
            run: "click",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_form_saved .ribbon span:contains('Substitute')",
            content: "The substitute's ribbon shows once saved",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Schedule')",
            content: "Open the Schedule tab",
            run: "click",
        },
        {
            trigger: ".o_schedule_grid_entry:contains('08:00-09:00')",
            content: "The replaced teacher's guard duty has been copied",
        },
        {
            trigger: ".o_breadcrumb .o_back_button a, .o_breadcrumb .breadcrumb-item a",
            content: "Back to the list",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('0000 TSUBT Titular')",
            content: "Open the replaced teacher",
            run: "click",
        },
        {
            trigger: ".o_form_view .ribbon span:contains('Substituted')",
            content: "The replaced teacher's ribbon",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Teaching')",
            content: "Open the Teaching tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='substituted_by_ids'] .o_tag:contains('0000 TSUBT Substitute')",
            content: "Who replaces them",
        },
    ],
});
