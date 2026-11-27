/** @odoo-module **/

import { useSubEnv } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";

/**
 * The grade session's form (issue #878). Its grade matrix keeps the teacher's edits in a buffer of
 * its own until they are applied, so the record itself never looks dirty: Odoo's pager would move
 * to the next session and drop them without a word. The matrix registers its leave check here
 * (env.gradeMatrixLeaveGuard), and the pager asks it first, with the same dialog as leaving the
 * screen.
 */
export class GradeSessionFormController extends FormController {
    setup() {
        super.setup();
        this.gradeMatrixLeaveGuard = { check: null };
        useSubEnv({ gradeMatrixLeaveGuard: this.gradeMatrixLeaveGuard });
    }

    async onPagerUpdate(params) {
        const check = this.gradeMatrixLeaveGuard.check;
        if (check && (await check()) === false) {
            return;
        }
        return super.onPagerUpdate(params);
    }
}

registry.category("views").add("ems_grade_session_form", {
    ...formView,
    Controller: GradeSessionFormController,
});
