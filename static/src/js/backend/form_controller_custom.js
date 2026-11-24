/** @odoo-module **/

import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { useService } from "@web/core/utils/hooks";
import { registry } from '@web/core/registry';

export class StudentPopupFormController extends FormController {
    setup() {
        this.action = useService("action");
        super.setup();
        this.orm = useService("orm");
        this.dialog = useService("dialog");

        var self = this;
        owl.onMounted(function(){
            const items = document.getElementsByClassName("o_expand_button");
            if(items.length > 0){
                items[0].onclick = function() {
                    self.action.doAction({
                        type: 'ir.actions.act_window',
                        res_model: 'res.partner',    //self.props.record.model.config.resModel
                        res_id: self.props.resId,
                        views: [[false, "form"]],
                        target: 'current', //with 'new' the form opens as a modal window.
                   });
                };
            }
        });
    }

    async onWillSaveRecord(record, changes) {
        // Issue #842: changing the main email of a student or family contact asks whether to
        // update (or give) their portal access, and the answer travels in this same save as
        // `portal_email_decision` (consumed by res.partner.write). Closing the dialog does not
        // save. See get_portal_email_question in models/contacts/portal.py.
        if (!record.resId || !("email" in changes)) {
            return super.onWillSaveRecord(...arguments);
        }
        const question = await this.orm.call("res.partner", "get_portal_email_question", [
            record.resId, changes.email]);
        if (!question) {
            return super.onWillSaveRecord(...arguments);
        }
        return new Promise((resolve) => {
            this.dialog.add(ConfirmationDialog, {
                title: question.title,
                body: question.message,
                confirmLabel: question.confirm,
                confirm: () => {
                    changes.portal_email_decision = "apply";
                    resolve(true);
                },
                cancelLabel: question.cancel,
                cancel: () => {
                    changes.portal_email_decision = "keep";
                    resolve(true);
                },
                dismiss: () => resolve(false),
            }, { onClose: () => resolve(false) });
        });
    }

    getStaticActionMenuItems() {
        // Archiving a student already opens the withdrawal wizard (see toggle_active
        // on res.partner), which has its own "this withdraws immediately" confirmation
        // — skip Odoo's generic "are you sure you want to archive?" dialog so the wizard
        // opens directly, same as hr.employee's departure wizard (EmployeeFormController).
        const menuItems = super.getStaticActionMenuItems();
        if (this.model.root.data.contact_type === 'student') {
            menuItems.archive.callback = () => this.model.root.archive();
        }
        return menuItems;
    }
 }
 
 registry.category("views").add("studentpopup_expand_button", {
    ...formView,
    Controller: StudentPopupFormController,    
 });
