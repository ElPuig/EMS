/** @odoo-module **/

import { Component } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { append, createElement } from "@web/core/utils/xml";
import { FormCompiler } from "@web/views/form/form_compiler";
import { FormRenderer } from "@web/views/form/form_renderer";
import { StatusBarButtons } from "@web/views/form/status_bar_buttons/status_bar_buttons";
import { toStringExpression } from "@web/views/utils";

/**
 * A form's "Actions" dropdown: every button of a `<div name="ems_actions" string="...">` inside
 * `<header>` becomes one entry of a single header button, instead of a row of header buttons.
 * Each entry is still a plain ViewButton, so it keeps its own `invisible=`, `groups=` and
 * `confirm=`, and the dropdown is not rendered at all when none of them is visible.
 * See docs/en/developers/shared/actions_dropdown.md.
 */
export class EmsActionsDropdown extends StatusBarButtons {
    static template = "ems.ActionsDropdown";
    static components = { Dropdown, DropdownItem };
    static props = {
        slots: { type: Object, optional: 1 },
        string: String,
    };
}

Object.assign(FormRenderer.components, { EmsActionsDropdown });

/** @this {FormCompiler} */
function compileActionsDropdown(el, params) {
    const dropdown = createElement("EmsActionsDropdown", {
        string: toStringExpression(el.getAttribute("string") || ""),
    });
    let slotId = 0;
    for (const child of el.children) {
        const button = this.compileNode(child, params);
        if (!button) {
            continue;
        }
        const slot = createElement("t", {
            "t-set-slot": `action_${slotId++}`,
            isVisible: button.getAttribute("t-if") || true,
        });
        append(slot, button);
        append(dropdown, slot);
    }
    return slotId ? dropdown : "";
}

registry.category("form_compilers").add("ems_actions_dropdown", {
    selector: "div[name='ems_actions']",
    fn: compileActionsDropdown,
});

patch(FormCompiler.prototype, {
    compileHeader(el, params) {
        // On a small screen Odoo moves every header button into the cog menu, one entry each:
        // unwrap the dropdown there so its buttons join them, rather than nesting a dropdown
        // inside the cog menu.
        if (params.asDropdownItems && el.querySelector(":scope > div[name='ems_actions']")) {
            el = el.cloneNode(true);
            for (const div of el.querySelectorAll(":scope > div[name='ems_actions']")) {
                div.replaceWith(...div.childNodes);
            }
        }
        return super.compileHeader(el, params);
    },
});
