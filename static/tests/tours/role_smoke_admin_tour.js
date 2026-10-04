/** @odoo-module **/

import { registry } from "@web/core/registry";
import { roleSmokeSteps } from "./role_smoke_common";

// See role_smoke_common.js for the crawler itself and CLAUDE.md's "Per-role smoke tours".
// Opens every EMS screen an administrator reaches (catalogs and configuration included), in
// every view mode - which is what the simple catalog create-and-save tours used to check one
// screen at a time (issue #566). Native Odoo apps are left out ("ems." actions only).
registry.category("web_tour.tours").add("ems_role_smoke_admin", {
    test: true,
    url: "/odoo",
    steps: () => roleSmokeSteps("Crawl every EMS menu/action reachable by an administrator", {
        xmlIdPrefix: "ems.",
    }),
});
