/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { registry } from '@web/core/registry';

export class StudentListController extends ListController {
    getStaticActionMenuItems() {
        // Same as StudentPopupFormController (form_controller_custom.js): archiving
        // student(s) already opens the withdrawal wizard, which has its own
        // confirmation — skip Odoo's generic "are you sure?" dialog when every
        // selected record is a student, one or several. Non-student selections
        // (family, provider) keep the default archive confirmation.
        const menuItems = super.getStaticActionMenuItems();
        const defaultCallback = menuItems.archive.callback;
        menuItems.archive.callback = () => {
            const selection = this.model.root.selection;
            const allStudents = selection.length > 0 &&
                selection.every((record) => record.data.contact_type === 'student');
            if (allStudents) {
                this.toggleArchiveState(true);
            } else {
                defaultCallback();
            }
        };
        return menuItems;
    }
}

registry.category("views").add("student_list", {
    ...listView,
    Controller: StudentListController,
});
