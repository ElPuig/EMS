/** @odoo-module **/

import { registry } from "@web/core/registry";

// Issue #575: a colleague's presence dot is identical on the Teachers kanban and on their own
// form, for a plain teacher (no HR rights), in every colour. The form used to show a checked-in colleague
// grey ("Out of working hours"): its state was computed with the viewer's rights, which can't read
// the last check-in. Seed data comes from TestEmployeePresenceTour
// (tests/test_employee_presence_tour.py): one colleague per colour.
const COLLEAGUES = [
    { name: "0000 Presence Green", icon: "fa-circle", color: "text-success" },
    { name: "0000 Presence Yellow", icon: "fa-circle", color: "o_icon_employee_absent" },
    { name: "0000 Presence Grey", icon: "fa-circle", color: "text-muted" },
    { name: "0000 Presence Plane", icon: "fa-plane", color: "o_icon_employee_absent" },
];

let kanbanClasses = "";

function dotClasses(element) {
    return [...element.querySelector(".hr_presence").classList].sort().join(" ");
}

function stepsFor({ name, icon, color }) {
    return [
        {
            trigger: `.o_kanban_record:contains('${name}') .hr_presence.${icon}.${color}`,
            content: `${name}: the expected dot on the kanban`,
            run: () => {
                const card = [...document.querySelectorAll(".o_kanban_record")].find((c) => c.textContent.includes(name));
                kanbanClasses = dotClasses(card);
            },
        },
        {
            trigger: `.o_kanban_record:contains('${name}')`,
            content: `Open ${name}'s form`,
            run: "click",
        },
        {
            trigger: `.o_form_view:contains('${name}') .o_employee_availability .hr_presence`,
            content: `${name}: exactly the same dot on the form`,
            run: () => {
                const formClasses = dotClasses(document.querySelector(".o_form_view .o_employee_availability"));
                if (formClasses !== kanbanClasses) {
                    throw new Error(`${name}: kanban "${kanbanClasses}" but form "${formClasses}"`);
                }
            },
        },
        {
            trigger: ".o_breadcrumb .breadcrumb-item:first-child a",
            content: "Back to the kanban",
            run: "click",
        },
    ];
}

registry.category("web_tour.tours").add("ems_employee_presence", {
    test: true,
    url: "/odoo/action-ems.action_employee_kanban",
    steps: () => COLLEAGUES.flatMap(stepsFor),
});
