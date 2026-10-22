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

    async onWillSaveRecord(record, changes) {
        // Issue #688: the halves of a split group usually share their tutor, delegate and
        // sub-delegate, but may have their own (co-tutors, a delegate per half). Saving only fills
        // the other halves' blanks; when it would replace one they already have (linking a half, or
        // changing a shared value), ask: replicate it, or keep each half's own. Closing the dialog
        // does not save. See get_joinable_confirmation_message in models/contacts/group.py.
        this.joinableReplicate = null;
        const shared = ["tutor_id", "delegate_id", "subdelegate_id"];
        const halves = record.data.joinable_group_ids.currentIds;
        if (!halves.length || !["joinable_group_ids", ...shared].some((field) => field in changes)) {
            return super.onWillSaveRecord(...arguments);
        }
        const values = Object.fromEntries(shared.map(
            (field) => [field, record.data[field] ? record.data[field][0] : false]));
        const question = await this.orm.call("ems.group", "get_joinable_confirmation_message", [
            record.resId ? [record.resId] : [], halves, values]);
        if (!question) {
            return super.onWillSaveRecord(...arguments);
        }
        return new Promise((resolve) => {
            this.dialog.add(ConfirmationDialog, {
                title: _t("Replicate to the other halves?"),
                body: question.message,
                confirmLabel: _t("Replicate"),
                confirm: () => {
                    this.joinableReplicate = question.replicate;
                    resolve(true);
                },
                cancelLabel: _t("Keep each half's own"),
                cancel: () => resolve(true),
                dismiss: () => resolve(false),
            }, { onClose: () => resolve(false) });
        });
    }

    async onRecordSaved(record, changes) {
        const replicate = this.joinableReplicate;
        this.joinableReplicate = null;
        if (replicate) {
            await this.orm.call("ems.group", "action_replicate_joinable_fields", [[record.resId], replicate]);
        }
        return super.onRecordSaved(...arguments);
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
