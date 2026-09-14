/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #453: every active group's form shows its public, no-login schedule PDF link, ready to
// copy. Driven by a plain teacher (least-privileged role with access to Groups), through the
// Groups list and into the form. Structural selectors only (field name + the slug the fixture
// determines), so the account's language doesn't matter.
registry.category("web_tour.tours").add("ems_group_public_schedule", {
    test: true,
    url: "/odoo/action-ems.action_group_tree",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "Groups list loaded",
        },
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded group",
            run: "edit Tour Public Schedule TGPT",
        },
        {
            trigger: ".o_searchview_input",
            content: "Confirm the search",
            run: "press Enter",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('Tour Public Schedule TGPT')",
            content: "Open it",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='public_schedule_url']:contains('/ems/schedule/tour-public-schedule-tgpt.pdf')",
            content: "The public schedule link is shown",
        },
        {
            trigger: ".o_form_view div[name='public_schedule_url'] a.o_form_uri[target='_blank'][href$='/ems/schedule/tour-public-schedule-tgpt.pdf']",
            content: "The link opens the PDF in a new tab",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='public_schedule_url'] .o_clipboard_button",
            content: "It can be copied",
        },
    ],
});
