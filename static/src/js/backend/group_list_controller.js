/** @odoo-module **/

import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { registry } from '@web/core/registry';
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class EmsGroupListController extends ListController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.action = useService("action");
    }

    getStaticActionMenuItems() {
        // Same as EmsGroupFormController (group_form_controller.js): pre-check via RPC and, only
        // if the selection has active students, show a single ConfirmationDialog of our own
        // instead of Odoo's generic "are you sure?" one followed by our RedirectWarning.
        const menuItems = super.getStaticActionMenuItems();
        menuItems.archive.callback = () => this.onArchiveGroups();
        return menuItems;
    }

    async onArchiveGroups() {
        const resIds = this.model.root.selection.map((record) => record.resId);
        const message = await this.orm.call("ems.group", "get_archive_confirmation_message", [resIds]);
        if (!message) {
            return this.toggleArchiveState(true);
        }
        this.dialog.add(ConfirmationDialog, {
            title: _t("Archive these groups?"),
            body: message,
            confirmLabel: _t("Proceed"),
            confirm: async () => {
                const action = await this.orm.call("ems.group", "action_confirm_archive", [resIds]);
                if (action) {
                    this.action.doAction(action);
                }
            },
            cancel: () => {},
        });
    }
}

registry.category("views").add("ems_group_list", {
    ...listView,
    Controller: EmsGroupListController,
});
