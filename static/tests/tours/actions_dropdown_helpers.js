/** @odoo-module **/

// Shared by every tour driving a form's "Actions" dropdown (static/src/js/backend/
// actions_dropdown.js). Its entries only exist in the DOM while the dropdown is open, and the
// open menu is rendered in the overlay container, outside .o_form_view - so a plain
// `.o_form_view button[name=...]` trigger never finds them, and a
// `:not(:has(button[name=...]))` check on the form passes whether the entry is offered or not.

export const ACTIONS_TOGGLE = ".o_form_view .o_form_statusbar .o_ems_actions_toggle";
const ACTIONS_MENU = ".o-dropdown--menu.o_ems_actions_menu";

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

/** Open the dropdown and click one of its entries. */
export function clickAction(name, content) {
    return [
        openActions(),
        { trigger: `${ACTIONS_MENU} button[name='${name}']`, content, run: "click" },
    ];
}

/**
 * Open the dropdown, check which entries it offers, and close it again. `offered` must not be
 * empty: it is what proves the menu has rendered before `notOffered` is checked.
 */
export function checkActions({ offered, notOffered = [] }, content) {
    const has = offered.map((name) => `:has(button[name='${name}'])`).join("");
    const hasNot = notOffered.map((name) => `:not(:has(button[name='${name}']))`).join("");
    return [
        openActions(),
        { trigger: `${ACTIONS_MENU}${has}${hasNot}`, content },
        closeActions(),
    ];
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
