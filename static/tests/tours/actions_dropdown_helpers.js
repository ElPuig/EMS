/** @odoo-module **/

// Shared by every tour driving a form's "Actions" dropdown (static/src/js/backend/
// actions_dropdown.js). Its entries only exist in the DOM while the dropdown is open, and the
// open menu is rendered in the overlay container, outside .o_form_view - so a plain
// `.o_form_view button[name=...]` trigger never finds them, and a
// `:not(:has(button[name=...]))` check on the form passes whether the entry is offered or not.
// When only one entry applies it is a plain header button instead, with no dropdown: clickAction
// and checkActions handle both cases, so a tour doesn't depend on how many entries are offered.

export const ACTIONS_TOGGLE = ".o_form_view .o_form_statusbar .o_ems_actions_toggle";
const ACTIONS_MENU = ".o-dropdown--menu.o_ems_actions_menu";
const STATUSBAR = ".o_form_view .o_form_statusbar";

export function openActions() {
    return {
        trigger: `${ACTIONS_TOGGLE}:not(.show)`,
        content: "Open the form's Actions dropdown",
        run: "click",
    };
}

export function closeActions() {
    return {
        trigger: `${ACTIONS_TOGGLE}.show`,
        content: "Close the Actions dropdown",
        run: "click",
    };
}

/** Open the dropdown, unless `name` is the lone action shown as a plain header button. */
function openActionsFor(name) {
    return {
        trigger: `${STATUSBAR} :is(.o_ems_actions_toggle:not(.show), button[name='${name}'])`,
        content: "Open the form's Actions dropdown (a lone action is a plain header button)",
        run() {
            if (this.anchor.matches(".o_ems_actions_toggle")) {
                this.anchor.click();
            }
        },
    };
}

/** Close the dropdown if it is open. */
function closeActionsIfOpen() {
    return {
        trigger: STATUSBAR,
        content: "Close the Actions dropdown, if it is open",
        run() {
            this.anchor.querySelector(".o_ems_actions_toggle.show")?.click();
        },
    };
}

/** Click one of the form's actions, from the dropdown or as the lone header button. */
export function clickAction(name, content) {
    return [
        openActionsFor(name),
        { trigger: `:is(${ACTIONS_MENU}, ${STATUSBAR}) button[name='${name}']`, content, run: "click" },
    ];
}

/**
 * Check which actions the form offers (in the open dropdown, or the lone header button), then
 * close the dropdown again. `offered` must not be empty: it is what proves the actions have
 * rendered before `notOffered` is checked.
 */
export function checkActions({ offered, notOffered = [] }, content) {
    const has = offered.map((name) => `:has(button[name='${name}'])`).join("");
    const hasNot = notOffered.map((name) => `:not(:has(button[name='${name}']))`).join("");
    return [
        openActionsFor(offered[0]),
        { trigger: `:is(${ACTIONS_MENU}, ${STATUSBAR})${has}${hasNot}`, content },
        closeActionsIfOpen(),
    ];
}

/** Exactly one action applies: it is a plain header button and there is no dropdown. */
export function loneAction(name, content) {
    return {
        trigger: `${STATUSBAR}:has(.o_statusbar_buttons > button[name='${name}']):not(:has(.o_ems_actions_toggle))`,
        content,
    };
}

/**
 * No entry applies: the dropdown itself is not rendered (and with nothing else in the header,
 * Odoo leaves out the whole status bar, so the check is on the loaded form, not the bar).
 */
export function noActions(content) {
    return {
        trigger: `.o_form_view:has(.o_form_sheet):not(:has(.o_ems_actions_toggle))`,
        content,
    };
}

/**
 * Open the form's native cog menu and check it has no Archive/Unarchive entry (a user who
 * can't archive the record gets `active` as readonly, see EmsBase.fields_get_active_readonly_
 * for_teachers), then close it. Labels are English: the tour's user must render in en_US.
 */
export function noArchiveInCog(content) {
    const cogToggle = ".o_control_panel .o_cp_action_menus button:has(.fa-cog)";
    return [
        { trigger: `${cogToggle}:not(.show)`, content: "Open the cog menu", run: "click" },
        {
            trigger: ".o-dropdown--menu:has(.dropdown-item)"
                + ":not(:has(.o_menu_item:contains('Archive')))"
                + ":not(:has(.o_menu_item:contains('Unarchive')))",
            content,
        },
        { trigger: `${cogToggle}.show`, content: "Close the cog menu", run: "click" },
    ];
}
