/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { serverNow } from "@ems/js/backend/server_clock";

// Issue #692: a class whose teacher has not checked in is on the guard duty board's absences table.
// The guard on duty says the teacher is in the classroom: the class in progress leaves the table,
// the one already over stays. Seed data: TestGuardBoardUncheckedTour (today, 10:30).
const pastLesson = "td:has(.o_guard_board_block_time:contains('08:00-09:00'))";
const currentLesson = "td:has(.o_guard_board_block_time:contains('10:00-11:00'))";
const teacher = "Tour Unchecked Teacher";

const openAbsencesTable = [
    {
        trigger: ".o_guard_board_view_tabs .nav-link:contains('Absences table')",
        content: "Switch to the absences table (the board opens on today, morning)",
        run: "click",
    },
    {
        trigger: `${currentLesson} .o_guard_board_absence_manageable:contains('${teacher}'):has(.o_guard_board_unchecked_tag)`,
        content: "The class in progress is on the table, marked as not checked in",
    },
    {
        trigger: `${pastLesson} .o_guard_board_absence_row:contains('${teacher}'):has(.o_guard_board_unchecked_tag)`,
        content: "So is the one already over",
    },
    {
        trigger: `${currentLesson}.o_guard_board_guard_cell .o_guard_board_guard_badge:contains('Tour Unchecked Late Guard'):has(.fa-clock-o)`,
        content: "A guard who has not checked in carries the clock icon (issue #725)...",
    },
    {
        trigger: `${currentLesson}.o_guard_board_guard_cell .o_guard_board_guard_badge:contains('Tour Unchecked Guard'):not(:has(.fa-clock-o))`,
        content: "...and one who has, not",
    },
];

const stillOnlyThePastLesson = [
    {
        trigger: `${currentLesson}:not(:has(.o_guard_board_absence_row:contains('${teacher}')))`,
        content: "The class in progress has left the table",
    },
    {
        trigger: `${pastLesson} .o_guard_board_absence_row:contains('${teacher}')`,
        content: "The one already over stays",
    },
];

registry.category("web_tour.tours").add("ems_guard_board_unchecked", {
    test: true,
    url: "/odoo/action-ems.action_guard_duty_board",
    steps: () => [
        ...openAbsencesTable,
        {
            trigger: `${currentLesson} .o_guard_board_absence_manageable:contains('${teacher}')`,
            content: "Open the class",
            run: "click",
        },
        {
            trigger: ".modal .o_guard_unchecked_cover",
            content: "The guard can also cover it themselves",
        },
        {
            trigger: ".modal .o_guard_unchecked_present",
            content: "Say the teacher is in the classroom",
            run: "click",
        },
        ...stillOnlyThePastLesson,
    ],
});

// No reload: someone else checks the teacher in meanwhile (here, a direct call), the server tells
// every open board through the bus, and this one takes the class off the table.
registry.category("web_tour.tours").add("ems_guard_board_unchecked_refresh", {
    test: true,
    url: "/odoo/action-ems.action_guard_duty_board",
    steps: () => [
        ...openAbsencesTable,
        {
            trigger: `${currentLesson} .o_guard_board_absence_manageable:contains('${teacher}')`,
            content: "Check the teacher in from elsewhere",
            run: async () => {
                const search = (model, domain) => rpc(`/web/dataset/call_kw/${model}/search`, {
                    model, method: "search", args: [domain], kwargs: {},
                });
                const [teacherId] = await search("hr.employee", [["name", "=", teacher]]);
                const [groupId] = await search("ems.group", [["acronym", "=", "TGBUT"]]);
                await rpc("/web/dataset/call_kw/ems.absence_cover/board_mark_present", {
                    model: "ems.absence_cover",
                    method: "board_mark_present",
                    args: [serverNow().toISODate(), 10, 11, teacherId, groupId],
                    kwargs: {},
                });
            },
        },
        ...stillOnlyThePastLesson,
    ],
});

registry.category("web_tour.tours").add("ems_guard_board_unchecked_form", {
    test: true,
    steps: () => [
        {
            trigger: ".o_form_view .o_field_widget[name='ems_checked_in_by_id']:contains('Tour Unchecked Guard')",
            content: "The check-in says who registered it",
        },
    ],
});

// The guard covers the class themselves from the same dialog: straight away, with no second
// confirmation (as for "They are in the classroom").
registry.category("web_tour.tours").add("ems_guard_board_unchecked_cover", {
    test: true,
    url: "/odoo/action-ems.action_guard_duty_board",
    steps: () => [
        ...openAbsencesTable,
        {
            trigger: `${currentLesson} .o_guard_board_absence_manageable:contains('${teacher}')`,
            content: "Open the class",
            run: "click",
        },
        {
            trigger: ".modal .o_guard_unchecked_cover",
            content: "Cover it myself",
            run: "click",
        },
        {
            trigger: `body:not(:has(.modal)) ${currentLesson} .o_guard_board_absence_row:contains('${teacher}') .o_guard_board_cover_tag:contains('Tour Unchecked Guard')`,
            content: "Covered at once, with no confirmation dialog in between",
        },
    ],
});
