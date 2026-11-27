/** @odoo-module **/

import { registry } from "@web/core/registry";
import { checkActions, clickAction } from "@ems/../tests/tours/actions_dropdown_helpers";

// Issue #875: the secretary moves a confirmed enrollment to another study from its Actions
// dropdown; the template and the destination group are suggested by the wizard. Visits the
// enrollments action's kanban view too (list and form are used on the way).
registry.category("web_tour.tours").add("enrollment_study_change", {
    url: "/odoo/action-ems.action_ems_enrollments?view_type=kanban",
    steps: () => [
        {
            trigger: ".o_kanban_view .o_searchview .o_facet_remove",
            content: "Drop the default filter (enrollments not confirmed yet)",
            run: "click",
        },
        {
            trigger: ".o_kanban_view .o_kanban_record:contains('Study Change Tour Student')",
            content: "The enrollment shows on the kanban view",
        },
        {
            trigger: ".o_switch_view.o_list",
            content: "Switch to the list view",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row td:contains('Study Change Tour Student')",
            content: "Open the student's enrollment",
            run: "click",
        },
        ...checkActions({ offered: ["action_ems_change_study", "action_cancel"], notOffered: ["action_confirm"] },
            "A confirmed enrollment offers the change of studies, native actions in the same dropdown"),
        {
            trigger: "body:not(:has(.o_form_statusbar > .o_statusbar_buttons > button:not(.o_ems_actions_toggle):visible))",
            content: "No action is left loose in the header",
        },
        ...clickAction("action_ems_change_study", "Change studies"),
        {
            trigger: ".modal .o_field_widget[name='study_id'] input",
            content: "Pick the new studies",
            run: "edit SCT New Study",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:contains('SCT New Study')",
            content: "Select them",
            run: "click",
        },
        {
            trigger: ".modal .o_field_widget[name='group_id'] input:value(SCTN2A)",
            content: "The destination group is suggested from the template's course and the shift",
        },
        {
            trigger: ".modal .modal-footer button[name='action_apply']",
            content: "Apply the change",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_form_view .o_field_widget[name='ems_study_id'] :contains('SCT New Study'), body:not(:has(.modal)) .o_form_view .o_field_widget[name='ems_study_id'] input:value(SCT New Study)",
            content: "The enrollment is on the new studies",
        },
    ],
});
