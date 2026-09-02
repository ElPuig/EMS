/** @odoo-module **/

import { registry } from "@web/core/registry";

// Browser coverage for the per-subject destination-placement fix (D20,
// docs/en/developers/settings/course_transition_wizard.md): confirming a repeater's
// mixed enrollment (a current-course tutorship + a subject pending from an earlier
// course) must land the pending subject's ems.enrollment in THAT course's own group,
// not the order's own destination group. Deliberately confirms an INDIVIDUAL enrollment
// (the everyday "Confirm" button on a matrícula) rather than the course transition
// wizard's own Apply — that button is never tour-tested (see course_transition_tour.js),
// since it mass-deletes the outgoing course's operational records and the wizard's own
// tour stops at the preview on purpose. Both paths share the exact same
// _ems_apply_destination_placement() code, so this still exercises the real fix.
registry.category("web_tour.tours").add("enrollment_placement_pending_subject", {
    test: true,
    url: "/odoo/action-ems.action_ems_enrollments",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Enrollments list loaded",
        },
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded repeater's student",
            run: "edit Enrollment Placement Tour Student",
        },
        {
            trigger: ".o_searchview_input",
            content: "Confirm the search",
            run: "press Enter",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('Enrollment Placement Tour Student')",
            content: "Open the seeded repeater's enrollment",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='ems_group_id'] input",
            content: "Enrollment form loaded with its (2nd-course) destination group",
        },
        {
            trigger: ".o_form_view button[name='action_confirm']:visible",
            content: "Confirm the enrollment",
            run: "click",
        },
        {
            trigger: "body:not(:has(.o_form_view button[name='action_confirm']:visible))",
            content: "Confirmation applied - the placement helper has run",
        },
        {
            trigger: ".o_breadcrumb .o_back_button, .o_breadcrumb a:first",
            content: "Back to the enrollments list",
            run: "click",
        },
        // --- Verify the pending subject landed in its OWN (1st-course) group ---
        {
            trigger: ".o_control_panel",
            content: "Navigate to the Groups list",
            run: () => {
                window.location.href = "/odoo/action-ems.action_group_tree";
            },
        },
        {
            trigger: ".o_list_view",
            content: "Groups list loaded",
        },
        {
            trigger: ".o_searchview_input",
            content: "Search for the 1st-course destination group",
            run: "edit EPT1A",
        },
        {
            trigger: ".o_searchview_input",
            content: "Confirm the search",
            run: "press Enter",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('EPT1A')",
            content: "Open the 1st-course group",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Enrolled')",
            content: "Open the Enrolled tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='enrollment_view_ids'] .o_data_row " +
                "td:contains('Enrollment Placement Tour Student')",
            content: "The repeater shows up in the 1st-course group's own enrolled list",
        },
        {
            trigger: ".o_field_widget[name='enrollment_view_ids'] .o_data_row:has(" +
                "td:contains('Enrollment Placement Tour Student')) " +
                ".o_field_tags:contains('Pending Subject Tour')",
            content: "...specifically enrolled in the pending subject, not just any subject",
        },
    ],
});
