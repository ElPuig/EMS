/** @odoo-module **/
import { registry } from "@web/core/registry";
import { graphView } from "@web/views/graph/graph_view";
import { GraphRenderer } from "@web/views/graph/graph_renderer";
import { pivotView } from "@web/views/pivot/pivot_view";
import { PivotRenderer } from "@web/views/pivot/pivot_renderer";
import { usePrintAttendanceReport } from "@ems/js/backend/attendance_report_print";

// The 'Attendance reports' screen (pivot/graph on ems.attendance_session_line): a print button next
// to the pivot's download one, and in the graph's toolbar, opens the PDF report wizard. Teachers
// never found it in the ⚙ menu alone (attendance_report_analysis_cog_menu.js, kept as well).
// The toolbar (buttonTemplate) is rendered by the renderer, hence the handler there. Loaded in
// web.assets_backend_lazy, like the pivot and graph views it extends (see __manifest__.py).

export class AttendanceReportPivotRenderer extends PivotRenderer {
    setup() {
        super.setup();
        this.onPrintReportClicked = usePrintAttendanceReport();
    }
}

export class AttendanceReportGraphRenderer extends GraphRenderer {
    setup() {
        super.setup();
        this.onPrintReportClicked = usePrintAttendanceReport();
    }
}

registry.category("views").add("ems_attendance_report_pivot", {
    ...pivotView,
    Renderer: AttendanceReportPivotRenderer,
    buttonTemplate: "ems.AttendanceReportPivot.Buttons",
});

registry.category("views").add("ems_attendance_report_graph", {
    ...graphView,
    Renderer: AttendanceReportGraphRenderer,
    buttonTemplate: "ems.AttendanceReportGraph.Buttons",
});
