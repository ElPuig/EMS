/** @odoo-module **/

import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { registry } from '@web/core/registry';
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class EmsGroupFormController extends FormController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.action = useService("action");
    }

    getStaticActionMenuItems() {
        // Archiving a group already asks its own confirmation when it still has active
        // students (see _archive_confirmation_message in models/contacts/group.py). Rather
        // than letting that show up as Odoo's generic RedirectWarning dialog ("Odoo Warning"
        // title, no control over button labels) AFTER Odoo's own "are you sure you want to
        // archive?" ConfirmationDialog, this pre-checks via RPC and - only if needed - shows a
        // single, properly-titled ConfirmationDialog of our own instead of either one.
        const menuItems = super.getStaticActionMenuItems();
        menuItems.archive.callback = () => this.onArchiveGroup();
        return menuItems;
    }

    async onArchiveGroup() {
        const resId = this.model.root.resId;
        const message = await this.orm.call("ems.group", "get_archive_confirmation_message", [[resId]]);
        if (!message) {
            return this.model.root.archive();
        }
        this.dialog.add(ConfirmationDialog, {
            title: _t("Archive this group?"),
            body: message,
            confirmLabel: _t("Proceed"),
            confirm: async () => {
                const action = await this.orm.call("ems.group", "action_confirm_archive", [[resId]]);
                if (action) {
                    this.action.doAction(action);
                }
            },
            cancel: () => {},
        });
    }
}

registry.category("views").add("ems_group_form", {
    ...formView,
    Controller: EmsGroupFormController,
});
