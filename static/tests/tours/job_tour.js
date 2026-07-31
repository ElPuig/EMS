/** @odoo-module **/

import { registry } from "@web/core/registry";

// hr.job (Job Positions): had zero browser coverage. The EMS-added employee_type/group_id
// fields (models/employees/job.py) are NOT exercised here - both sit inside native hr.job's
// "Recruitment" notebook page, which is hardcoded invisible="1" in hr's own view (not a
// domain EMS could override), so neither is actually reachable through this form; the dev DB
// confirms they're populated exclusively via data/cat/hr.job.csv, never through the UI (see
// CLAUDE.md's data/ conventions). This tour covers what a user can actually do here: create
// a job position by name.
registry.category("web_tour.tours").add("ems_job_crud", {
    test: true,
    url: "/odoo/action-ems.action_job_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Job positions list loaded",
        },
        {
            trigger: ".o_list_button_add",
            content: "Create a new job position",
            run: "click",
        },
        {
            // hr.job's native form renders name via widget="text" (a <textarea>, allowing
            // multi-line job titles), not a plain Char <input>.
            trigger: ".o_form_view .o_field_widget[name='name'] textarea",
            content: "Fill in the name",
            run: "edit Tour Job Position",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_button_save:not(:visible)",
            content: "Save completed",
        },
        {
            trigger: ".o_breadcrumb:contains('Tour Job Position')",
            content: "The job position was created and saved",
        },
    ],
});
