/** @odoo-module **/

import { registry } from "@web/core/registry";

// The EMS-added tabs on hr.employee's own form (Schedule, Teaching — views/community/
// employee/form.xml) are never rendered by any other existing tour: employee_google_
// workspace_tour.js only ever checks the header buttons from the list view, never opening
// the form far enough to reach these tabs. A clean upgrade and passing TransactionCase
// tests don't prove the schedule_grid widget or the Teaching tab's embedded lists render
// without crashing in a real browser — this tour is what actually proves that.
registry.category("web_tour.tours").add("ems_employee_form_tabs", {
    test: true,
    url: "/odoo/action-ems.action_employee_kanban",
    steps: () => [
        {
            trigger: ".o_control_panel",
            content: "Teachers loaded",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to list view",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('Employee Form Tour')",
            content: "Open the tour's own teacher",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-item:first-child .nav-link.active[name='schedule']",
            content: "Schedule is the first tab and the one open by default",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Schedule')",
            content: "Open the Schedule tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='schedule_attendance_ids']",
            content: "Schedule tab (schedule_grid widget) rendered without crashing",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Teaching')",
            content: "Open the Teaching tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='tutorship_ids']",
            content: "Teaching tab (Tutorships/Coordination/Subjects) rendered without crashing",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Human Resources')",
            content: "Open the Human Resources tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='teaching_reduction_ids'] input",
            content: "Pick a teaching hour reduction type",
            run: "edit Reduction",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Reduction for teachers aged 55 and over')",
            content: "Select the seeded R55 reduction type",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='teaching_reduction_ids'] .o_tag:contains('Reduction for teachers aged 55 and over')",
            content: "Reduction type tag added",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='teaching_reduction_ids'] .o_tag:contains('Reduction for teachers aged 55 and over')",
            content: "Reduction type tag confirmed after save",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Schedule')",
            content: "Open the Schedule tab",
            run: "click",
        },
        {
            trigger: ".o_schedule_grid_summary_column:contains('Reduction for teachers aged 55 and over')",
            content: "Reduction type shows up in the weekly teaching hours breakdown",
        },
    ],
});
