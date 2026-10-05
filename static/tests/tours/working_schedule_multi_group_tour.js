/** @odoo-module **/

import { registry } from "@web/core/registry";

// Regression tour for issue "unable to setup multiple groups when editing a schedule manually":
// a join_session slot (one teacher running an identical session for two different groups at once,
// e.g. an optional subject combining two official groups in the same room - see
// docs/en/developers/employees/working_schedule.md's own "join_session" section) is stored as ONE
// resource.calendar.attendance row with several group_ids, but the Schedule tab's edit widget used
// to only ever keep the FIRST group on its card - both on load (re-opening "Edit" on an existing
// multi-group row silently showed just one group) and on save (picking a single group silently
// dropped every other group the row already had). The group picker itself went through two designs
// the same day: a native <select multiple> first, replaced by this tag picker (AutoComplete input +
// removable pills) after developer feedback that the multi-select gave no visible "selected" state
// and needed an undiscoverable Ctrl/Shift-click - see the dev doc's own note on that. Exercises the
// real interactive flow: add two groups to one card via the AutoComplete, save, then re-open Edit to
// confirm BOTH groups are still shown as tags - a clean upgrade.sh and passing TransactionCase tests
// don't prove either of those on their own, since neither renders anything in a real browser.
registry.category("web_tour.tours").add("ems_working_schedule_multi_group", {
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
            // Typing before the switch has settled loses the text: the control panel re-renders.
            trigger: ".o_list_view .o_data_row",
            content: "List view rendered",
        },
        {
            // Search rather than expect the teacher on the list's first page: a database with
            // more than 80 teachers (like a real centre's) pushes it off that page.
            trigger: ".o_searchview_input",
            content: "Search for the tour's own teacher",
            run: "edit Multi Group Tour Teacher",
        },
        {
            trigger: ".o_searchview_input",
            content: "Confirm the search",
            run: "press Enter",
        },
        {
            trigger: ".o_searchview_facet",
            content: "Search applied",
        },
        {
            trigger: ".o_list_view .o_data_row .o_data_cell:contains('Multi Group Tour Teacher')",
            content: "Open the tour's own teacher",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_notebook .nav-link:contains('Schedule')",
            content: "Open the Schedule tab",
            run: "click",
        },
        {
            trigger: ".o_schedule_grid_toolbar button:contains('Edit')",
            content: "Enter edit mode",
            run: "click",
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_add_card",
            content: "Monday: add a card",
            run: "click",
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_card_time:first-of-type",
            content: "Fix the start time to a value the tour fully controls",
            run: function () {
                const input = document.querySelector(
                    ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_card_time:first-of-type"
                );
                input.value = "20:00";
                input.dispatchEvent(new Event("change", { bubbles: true }));
            },
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_card_time:last-of-type",
            content: "Fix the end time",
            run: function () {
                const input = document.querySelector(
                    ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_card_time:last-of-type"
                );
                input.value = "21:00";
                input.dispatchEvent(new Event("change", { bubbles: true }));
            },
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_card_subject",
            content: "Pick the subject",
            run: "selectByLabel Multi Group Tour Subject",
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_card_group_tags input",
            content: "Search for the first group",
            run: "edit Multi Group Tour Group A",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Multi Group Tour Group A')",
            content: "Add it as a tag",
            run: "click",
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_group_tag:contains('Multi Group Tour Group A')",
            content: "The first group now shows as a tag",
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_card_group_tags input",
            content: "Search for the SECOND group, on the SAME card (this is the actual regression - adding a second tag must not replace the first)",
            run: "edit Multi Group Tour Group B",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('Multi Group Tour Group B')",
            content: "Add it as a second tag",
            run: "click",
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_group_tag:contains('Multi Group Tour Group A')",
            content: "Both tags are present at once on the same card",
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_group_tag:contains('Multi Group Tour Group B')",
            content: "...the second one too",
        },
        {
            // Issue #428: an optional free-text 'topic' distinguishes several teachers of the SAME
            // subject (e.g. FP Basica's MP 3161 split into Castella/Catala/Angles) - a plain
            // <input>, not a select/autocomplete, so a straightforward fill-and-check suffices.
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_card_topic",
            content: "Fill in the topic",
            run: "edit Tour Topic",
        },
        {
            trigger: ".o_schedule_grid_toolbar button:contains('Save')",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_schedule_grid_entry:contains('Multi Group Tour Group A')",
            content: "Monday now shows the saved block naming the first group",
        },
        {
            trigger: ".o_schedule_grid_entry:contains('Multi Group Tour Group B')",
            content: "...and the second group too, in the SAME block (not truncated to just one)",
        },
        {
            trigger: ".o_schedule_grid_entry:contains('Tour Topic')",
            content: "...and the topic is shown in the block label too",
        },
        {
            trigger: ".o_schedule_grid_toolbar button:contains('Edit')",
            content: "Re-enter edit mode to confirm both groups are still shown as tags, not silently dropped back to one",
            run: "click",
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_group_tag:contains('Multi Group Tour Group A')",
            content: "The first group's tag survived the round trip",
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_group_tag:contains('Multi Group Tour Group B')",
            content: "...and so did the second one",
        },
        {
            // Not a 'input[value=...]' trigger: OWL doesn't sync the HTML attribute on change, so
            // the actual DOM property must be read imperatively instead.
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_card_topic",
            content: "The topic survived the round trip too",
            run: function () {
                const input = document.querySelector(
                    ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_card_topic"
                );
                if (input.value !== "Tour Topic") {
                    throw new Error(`Expected topic "Tour Topic" after re-opening Edit, got "${input.value}"`);
                }
            },
        },
        {
            trigger: ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_card_group_tags .o_schedule_grid_group_tag",
            content: "Exactly 2 tags, no more, no less",
            run: function () {
                const tags = document.querySelectorAll(
                    ".o_schedule_grid_day_column[data-day='0'] .o_schedule_grid_card:last-of-type .o_schedule_grid_card_group_tags .o_schedule_grid_group_tag"
                );
                if (tags.length !== 2) {
                    throw new Error(`Expected exactly 2 group tags after re-opening Edit, got ${tags.length}`);
                }
            },
        },
        {
            trigger: ".o_schedule_grid_toolbar button:contains('Cancel')",
            content: "Discard (nothing left to change)",
            run: "click",
        },
    ],
});
