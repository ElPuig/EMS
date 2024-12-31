/** @odoo-module */

import { ListController } from "@web/views/list/list_controller";
import { listView } from '@web/views/list/list_view';
import { useService } from "@web/core/utils/hooks";
import { registry } from '@web/core/registry';

export class SubjectViewListController extends ListController {
   setup() {
      this.action = useService("action");
      super.setup();
   }
   onClick() {
      this.action.doAction({
         type: 'ir.actions.act_window',
         res_model: 'ems.subject',                
         res_id: false,
         views: [[false, "form"]],                               
         target: 'current', //with 'new' the form opens as a modal window.
      });
   }
}

registry.category("views").add("subjectview_create_button", {
   ...listView,
   Controller: SubjectViewListController,
   buttonTemplate: "ems.web.ListView.Buttons",   
});