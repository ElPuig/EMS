/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #815: an ASP employee's job position is their department's. The employee form (opened by
// the test through its own URL) must show neither of its two job_id fields; the department form
// must show it. Logged in as a secretary (an ASP role that is not hr.group_hr_user-implying admin).
registry.category("web_tour.tours").add("ems_department_job_employee", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_field_widget[name='department_id']",
            content: "ASP employee form loaded",
        },
        {
            trigger: ".o_form_view:not(:has([name='job_id']))",
            content: "No job position field on the ASP employee form",
        },
    ],
});

registry.category("web_tour.tours").add("ems_department_job_department", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_field_widget[name='job_id']",
            content: "Job position shown on the ASP department form",
        },
    ],
});
