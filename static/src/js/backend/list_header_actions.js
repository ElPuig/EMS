/** @odoo-module **/

import { Component } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { patch } from "@web/core/utils/patch";
import { ListController } from "@web/views/list/list_controller";
import { MultiRecordViewButton } from "@web/views/view_button/multi_record_view_button";

/**
 * A list's "Actions" dropdown, the list counterpart of the form one (actions_dropdown.js): the
 * header buttons shown for a selection become the entries of one "Actions" button instead of a
 * row of loose buttons. Opt-in per list, with class="o_ems_header_actions" on the <list>, or per
 * action, with 'ems_header_actions': 1 in its context (for a list shared with a native app, such
 * as the enrollments' sale.order one). Each entry is still Odoo's own MultiRecordViewButton, so it
 * keeps its `invisible=`, `groups=` and `confirm=`. A lone button stays loose, as on a form (issue
 * #639): a dropdown hiding a single action only makes it harder to find. Small screens are left
 * alone: Odoo already moves header buttons into the cog menu there. See docs/en/developers/shared/actions_dropdown.md.
 */
export class EmsListActionsDropdown extends Component {
    static template = "ems.ListActionsDropdown";
    static components = { Dropdown, DropdownItem, MultiRecordViewButton };
    static props = {
        buttons: Array,
        list: Object,
        domain: { type: Array, optional: true },
    };
}

export const EMS_HEADER_ACTIONS_CLASS = "o_ems_header_actions";

ListController.components = { ...ListController.components, EmsListActionsDropdown };

patch(ListController.prototype, {
    get emsHeaderActions() {
        if (this.env.isSmall) {
            return false;
        }
        const classes = (this.props.archInfo.className || "").split(" ");
        return classes.includes(EMS_HEADER_ACTIONS_CLASS) || Boolean(this.props.context.ems_header_actions);
    },

    get emsHeaderActionButtons() {
        return this.archInfo.headerButtons.filter(
            (button) => button.display !== "always" && !this.evalViewModifier(button.invisible)
        );
    },

    /** The dropdown is only worth it with two entries or more: a lone one stays a plain button. */
    get emsHeaderActionsDropdown() {
        return this.emsHeaderActions && this.emsHeaderActionButtons.length > 1;
    },
});
