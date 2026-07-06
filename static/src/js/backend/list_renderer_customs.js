/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

patch(ListRenderer.prototype, {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        super.setup();
    },

    async getViewData(xml_id) {
        const data = await this.orm.searchRead("ir.ui.view", [["xml_id", "=", xml_id]], ["id", "xml_id", "name"]);
        return data.filter(item => item.xml_id == xml_id)[0];
    },

    onClickCapture(record, ev) {
        switch (record.resModel) {
            case "ems.enrollment_view":
                ev.preventDefault();
                ev.stopPropagation();
                this.action.doAction({
                    name: "Open: Students",
                    type: "ir.actions.act_window",
                    res_model: "res.partner",
                    res_id: record.data.student_id[0],
                    views: [[this.getViewData("view_contact_form").name, "form"]],
                    view_mode: "form",
                    target: "new",
                });
                break;

            case "res.partner":
                if (ev.target.closest('.ems-tutor-enrollment-list')) {
                    if (ev.target.closest('.o_list_record_selector') || ev.target.closest('button')) break;
                    ev.preventDefault();
                    ev.stopPropagation();
                    if (record.data.ems_current_enrollment_id) {
                        this.action.doAction({
                            type: "ir.actions.act_window",
                            res_model: "sale.order",
                            res_id: record.data.ems_current_enrollment_id[0],
                            views: [[false, "form"]],
                            target: "current",
                        });
                    }
                }
                break;
        }
    },
});