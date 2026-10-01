/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #458: a group's reference classroom (space_id) follows the room of its tutorship. The
// seeded group (TestGroupReferenceSpaceTour) was created in an old room and then got a tutorship
// block in another one; both views of the groups action must show the tutorship's room.
registry.category("web_tour.tours").add("ems_group_reference_space", {
    test: true,
    url: "/odoo/action-ems.action_group_tree",
    steps: () => [
        {
            trigger: ".o_searchview_input",
            content: "Search for the seeded group",
            run: "edit Tour Reference Space Group",
        },
        {
            trigger: ".o_searchview_input",
            content: "Confirm the search",
            run: "press Enter",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Tour Reference Space Group') td:contains('Tour Tutorship Space')",
            content: "The list shows the tutorship's room as the reference classroom",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('Tour Reference Space Group')",
            content: "Open the group",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='space_id']:contains('Tour Tutorship Space'), .o_form_view .o_field_widget[name='space_id'] input",
            content: "The form shows the tutorship's room too",
            run: () => {
                const field = document.querySelector(".o_form_view .o_field_widget[name='space_id']");
                const input = field.querySelector("input");
                const text = input ? input.value : field.textContent;
                if (!text.includes("Tour Tutorship Space")) {
                    throw new Error(`Expected the tutorship's room in space_id, found '${text}'`);
                }
            },
        },
    ],
});
