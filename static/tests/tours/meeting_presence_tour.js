/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #521, the manager's side: a secretary creates a meeting attendance (the convened teachers
// are loaded on save), starts it, closes it and reopens it, and finds it in the list. Runs as a
// secretary - not admin - since that is a role that convenes staff meetings and does not imply
// hr.group_hr_user (the fixture teacher is read through hr.employee.public).
registry.category("web_tour.tours").add("ems_meeting_presence_manage", {
    test: true,
    url: "/odoo/action-ems.action_meeting_presence",
    steps: () => [
        {
            trigger: ".o_list_view",
            content: "The meeting attendance list loads for the secretary",
        },
        {
            trigger: ".o_list_button_add",
            content: "Create a meeting attendance",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name=name] input",
            content: "Name the meeting",
            run: "edit Tour staff meeting",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save: the convened teachers are loaded",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name=line_ids] .o_data_row:contains('0000 Tour Presence Teacher')",
            content: "The fixture teacher is in the convened list, still pending",
        },
        {
            trigger: "button[name=action_open]",
            content: "Start the attendance",
            run: "click",
        },
        {
            trigger: ".o_statusbar_status .o_arrow_button_current:contains('Open')",
            content: "The meeting is open",
        },
        {
            trigger: ".o_field_widget[name=kiosk_url]",
            content: "The kiosk link is shown while it is open",
        },
        {
            trigger: "button[name=action_open_kiosk]",
            content: "The kiosk button is there (not clicked: it would open a new tab)",
        },
        {
            trigger: "button[name=action_close]",
            content: "Close the attendance",
            run: "click",
        },
        {
            trigger: ".modal-footer .btn-primary",
            content: "Confirm that whoever did not pass their tag is marked absent",
            run: "click",
        },
        {
            trigger: ".o_statusbar_status .o_arrow_button_current:contains('Closed')",
            content: "The meeting is closed",
        },
        {
            trigger: ".o_field_widget[name=line_ids] .o_data_row:contains('0000 Tour Presence Teacher'):contains('Absent')",
            content: "Closing marked the teacher who did not pass the tag as absent",
        },
        {
            trigger: "button[name=action_reopen]",
            content: "A closed attendance can be reopened",
            run: "click",
        },
        {
            trigger: ".o_statusbar_status .o_arrow_button_current:contains('Open')",
            content: "Open again",
        },
        {
            trigger: ".breadcrumb-item:contains('Meeting attendance')",
            content: "Back to the list",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row:contains('Tour staff meeting')",
            content: "The new meeting attendance is listed",
        },
        {
            trigger: "body:not(:has(.o_error_dialog))",
            content: "No client-side error along the way",
        },
    ],
});

// The kiosk page a laptop at the door keeps open, anonymous, started on /ems/presence/<token>
// (see tests/test_meeting_presence_tour.py). Typing the tag's UID and pressing Enter is exactly
// what an NFC reader does.
const scan = (barcode) => [
    {
        trigger: ".o_ems_presence_input",
        content: `Pass the tag ${barcode}`,
        run: `edit ${barcode}`,
    },
    {
        trigger: ".o_ems_presence_input",
        content: "The reader ends with Enter",
        run: "press Enter",
    },
];

// The names list of a kiosk column, after the page worked out its font and columns. The fonts it
// measures with have to be there first (it measures again when they arrive), and a beat is left
// for that second fit to land.
const fittedList = async (column) => {
    await document.fonts.ready;
    await new Promise((resolve) => setTimeout(resolve, 300));
    return document.querySelector(`${column} .o_ems_presence_names[data-fitted]`);
};

registry.category("web_tour.tours").add("ems_meeting_presence_kiosk", {
    test: true,
    steps: () => [
        {
            trigger: ".o_ems_presence_title:contains('Kiosk tour meeting')",
            content: "The kiosk shows the meeting",
        },
        {
            trigger: ".o_ems_presence_prompt",
            content: "Nobody has passed a tag yet",
        },
        {
            trigger: ".o_ems_presence_convened li:contains('Kiosk Tour Teacher')",
            content: "The convened teacher is on the left, still to come",
        },
        {
            trigger: ".o_ems_presence_attendees:not(:has(li))",
            content: "Nobody is in yet",
        },
        {
            trigger: ".o_ems_presence_convened .o_ems_presence_names[data-fitted]",
            content: "A single name is shown big, not squeezed into the smallest text",
            run: async () => {
                const list = await fittedList(".o_ems_presence_convened");
                const size = parseFloat(getComputedStyle(list).fontSize);
                if (size < 24) {
                    throw new Error(`A lone name should be shown big, got ${size}px`);
                }
            },
        },
        ...scan("TESTKIOSK001"),
        {
            trigger: ".o_ems_presence_card_success .o_ems_presence_card_title:contains('Kiosk Tour Teacher')",
            content: "A convened teacher is registered: green card with their name",
        },
        {
            trigger: ".o_ems_presence_attendees li:contains('Kiosk Tour Teacher')",
            content: "They moved to the attendees on the right...",
        },
        {
            trigger: ".o_ems_presence_convened:not(:has(li)) .o_ems_presence_all_in:contains('Everyone has registered')",
            content: "...and the list of those still to come is empty",
        },
        ...scan("TESTKIOSK001"),
        {
            trigger: ".o_ems_presence_card_info .o_ems_presence_card_subtitle:contains('Already registered')",
            content: "The same tag again: already registered",
        },
        ...scan("NOSUCHTAG"),
        {
            trigger: ".o_ems_presence_card_danger .o_ems_presence_card_title:contains('Unknown tag')",
            content: "A tag nobody owns: red card",
        },
        ...scan("TESTKIOSK002"),
        {
            trigger: ".o_ems_presence_card_warning .o_ems_presence_card_title:contains('Kiosk Tour Guest')",
            content: "Someone who was not convened is registered but flagged",
        },
        {
            trigger: ".o_ems_presence_attendees li.o_ems_presence_not_convened:contains('Kiosk Tour Guest')",
            content: "They are among the attendees, flagged as not convened",
        },
        {
            trigger: ".o_ems_presence_attendees .o_ems_presence_list_count:contains('2')",
            content: "Two people are in",
        },
        {
            trigger: "body:not(:has(.o_error_dialog))",
            content: "No client-side error along the way",
        },
    ],
});

// A staff meeting: over a hundred people, some with very long names, half of them already in. Every
// name must show, whole, in both lists: nobody scrolls to find themselves and nothing is cut off.
const assertEveryNameShows = (column, expected) => ({
    trigger: `${column} .o_ems_presence_names[data-fitted]`,
    content: `Every name of ${column} shows, whole, without scrolling`,
    run: async () => {
        const list = await fittedList(column);
        const names = [...list.querySelectorAll("li")];
        if (names.length !== expected) {
            throw new Error(`${column}: expected ${expected} names, found ${names.length}`);
        }
        if (list.scrollHeight > list.clientHeight + 1 || list.scrollWidth > list.clientWidth + 1) {
            throw new Error(`${column}: the list overflows (${list.scrollWidth}x${list.scrollHeight} in ${list.clientWidth}x${list.clientHeight})`);
        }
        const cut = [...list.querySelectorAll("li, .o_ems_presence_person")].filter(
            (el) => el.scrollWidth > el.clientWidth + 1
        );
        if (cut.length) {
            throw new Error(`${column}: ${cut.length} names are cut off, e.g. ${cut[0].textContent}`);
        }
        const size = parseFloat(getComputedStyle(list).fontSize);
        if (size < 9) {
            throw new Error(`${column}: font of ${size}px is unreadable`);
        }
    },
});

registry.category("web_tour.tours").add("ems_meeting_presence_kiosk_crowd", {
    test: true,
    steps: () => [
        assertEveryNameShows(".o_ems_presence_convened", 70),
        assertEveryNameShows(".o_ems_presence_attendees", 40),
        {
            trigger: "body:not(:has(.o_error_dialog))",
            content: "No client-side error along the way",
        },
    ],
});

// In production the kiosk is the clock-in kiosk's twin: no box to type in, and the keys are taken
// for a tag only if they come at a reader's speed. The tour plays the reader (and a person).
const pressKeys = async (keys, gapMs) => {
    for (const key of keys) {
        document.body.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
        if (gapMs) {
            await new Promise((resolve) => setTimeout(resolve, gapMs));
        }
    }
};

registry.category("web_tour.tours").add("ems_meeting_presence_kiosk_reader", {
    test: true,
    steps: () => [
        {
            trigger: ".o_ems_presence_prompt",
            content: "The kiosk is open",
        },
        {
            trigger: "body:not(:has(.o_ems_presence_input, .o_ems_presence_form))",
            content: "There is no box to type a code in",
        },
        {
            trigger: ".o_ems_presence_prompt",
            content: "Somebody types a valid code by hand, key by key, and presses Enter: nothing happens",
            run: async () => {
                await pressKeys([..."TESTREADER01", "Enter"], 250);
                await new Promise((resolve) => setTimeout(resolve, 400));
                if (document.querySelector(".o_ems_presence_card")) {
                    throw new Error("Typing by hand must not register anybody");
                }
                if (document.querySelector(".o_ems_presence_attendees li")) {
                    throw new Error("Typing by hand must not add an attendee");
                }
            },
        },
        {
            trigger: ".o_ems_presence_prompt",
            content: "The reader types the tag in a burst and ends with Enter",
            run: () => pressKeys([..."TESTREADER01", "Enter"]),
        },
        {
            trigger: ".o_ems_presence_card_success .o_ems_presence_card_title:contains('Reader Tour Teacher')",
            content: "The tag is registered",
        },
        {
            trigger: ".o_ems_presence_attendees li:contains('Reader Tour Teacher')",
            content: "...and the teacher is among the attendees",
        },
        {
            trigger: ".o_ems_presence_attendees li:contains('Reader Tour Teacher')",
            content: "A reader that sends no Enter is taken too, once it goes quiet",
            run: () => pressKeys([..."TESTREADER02"]),
        },
        {
            trigger: ".o_ems_presence_attendees li:contains('Reader Tour Second')",
            content: "The second tag is registered",
        },
    ],
});
