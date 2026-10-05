/** @odoo-module **/

import { registry } from "@web/core/registry";

// "My Profile" (hr.res_users_action_my) is native Odoo, only reshaped by EMS's own view
// inherits (views/community/employee/user_profile_form.xml) - a clean upgrade.sh and passing
// TransactionCase tests prove nothing about whether those xpaths actually render without
// crashing in a real browser, or whether the intended fields are really the ones left
// editable/read-only/hidden (issue #440). Two tours, not one: developer feedback 2026-09-10
// clarified the main form/Location/HR Settings must stay editable/visible for an administrator
// (any account where "can_edit" is True - see docs/en/developers/employees/user_profile.md) but
// read-only/hidden for an ordinary self-viewing user - genuinely different expectations per
// account, not just one scenario with a privileged fixture. Approvers/Manager/Coach are
// unconditionally read-only for everyone, including an administrator; "Private Information" is
// unconditionally EDITABLE for everyone, including an ordinary user - the two exceptions to the
// otherwise-uniform "can_edit" gating used for the rest of the screen.
//
// "My Profile" has no static res_id of its own - it's resolved dynamically, per logged-in user,
// by res.users.action_get() (hr/models/res_users.py), which only runs when reached through the
// real user-menu click (hr/static/src/user_menu/my_profile.js's "profile" entry). Navigating
// straight to "/odoo/action-hr.res_users_action_my" (the usual EMS-tour shortcut) bypasses that
// resolution entirely and opens a blank "New" form instead - confirmed by screenshot while
// building this tour. So both tours below, unlike every other EMS tour, actually click through
// the user menu like a real user would. This distinction also matters for a real, previously
// suspected bug that turned out to be false (see the dev doc's own "A false bug found and
// retracted" section): reproducing "can a user open their own profile" must exercise a real
// existing-record read, not an "onchange for a blank new record" simulation - that blank "New"
// form is exactly the scenario that would (correctly) fail for anyone without elevated access.

// Steps shared by both tours: navigate to "My Profile" for whichever account is logged in.
const openMyProfileSteps = (employeeName) => [
    {
        trigger: ".o_user_menu button",
        content: "Open the user menu",
        run: "click",
    },
    {
        trigger: ".dropdown-item:contains('My Profile')",
        content: "Open My Profile",
        run: "click",
    },
    {
        // Specifically the real record's own name, not just ".o_form_view" - a blank "New" form
        // (the bypassed-action_get() failure mode above) also renders an empty '.o_form_view'
        // with an empty job_title widget, so neither alone would catch it.
        trigger: `.o_form_view:contains('${employeeName}')`,
        content: "My Profile loaded for the real logged-in user, not a blank new record",
    },
];

// Steps shared by both tours: the full tab order (developer feedback 2026-09-10) - Schedule,
// Work Information, HR Settings, Private Information, Account Security, Devices, Resume,
// Preferences - and that Schedule, being first, is also the tab active by default (no click
// needed to see its content). Each tab is a '<li class="nav-item">' wrapping its own
// '<a class="nav-link">' (web/static/src/core/notebook/notebook.xml) - siblings at the nav-item
// level, not the nav-link level. "HR Settings" is skipped for the ordinary-user tour: it isn't
// hidden by reordering it away, it's genuinely absent from the DOM there (invisible="not
// can_edit"), so "Work Information" sits right next to "Private Information" instead.
const tabOrderSteps = (hasHrSettingsTab) => [
    {
        trigger: ".o_form_view .o_field_widget[name='schedule_attendance_ids']",
        content: "Schedule is the default active tab (visible without clicking anything)",
    },
    {
        trigger: ".o_notebook .nav-item:has(.nav-link.active:contains('Schedule'))",
        content: "Schedule is the first tab and the one marked active",
    },
    {
        trigger: ".o_notebook .nav-item:has(.nav-link:contains('Schedule')) + .nav-item:has(.nav-link:contains('Work Information'))",
        content: "Work Information right after Schedule",
    },
    ...(hasHrSettingsTab ? [
        {
            trigger: ".o_notebook .nav-item:has(.nav-link:contains('Work Information')) + .nav-item:has(.nav-link:contains('HR Settings'))",
            content: "HR Settings right after Work Information",
        },
        {
            trigger: ".o_notebook .nav-item:has(.nav-link:contains('HR Settings')) + .nav-item:has(.nav-link:contains('Private Information'))",
            content: "Private Information right after HR Settings",
        },
    ] : [
        {
            trigger: ".o_notebook .nav-item:has(.nav-link:contains('Work Information')) + .nav-item:has(.nav-link:contains('Private Information'))",
            content: "Private Information right after Work Information (HR Settings hidden)",
        },
    ]),
    {
        trigger: ".o_notebook .nav-item:has(.nav-link:contains('Private Information')) + .nav-item:has(.nav-link:contains('Account Security'))",
        content: "Account Security right after Private Information",
    },
    {
        trigger: ".o_notebook .nav-item:has(.nav-link:contains('Account Security')) + .nav-item:has(.nav-link:contains('Devices'))",
        content: "Devices right after Account Security",
    },
    {
        trigger: ".o_notebook .nav-item:has(.nav-link:contains('Devices')) + .nav-item:has(.nav-link:contains('Resume'))",
        content: "Resume right after Devices",
    },
    {
        trigger: ".o_notebook .nav-item:has(.nav-link:contains('Resume')) + .nav-item:has(.nav-link:contains('Preferences'))",
        content: "Preferences right after Resume, last",
    },
    {
        trigger: ".o_form_view .o_field_widget[name='schedule_attendance_ids']",
        content: "Schedule tab (schedule_grid widget) rendered without crashing",
    },
];

// Steps shared by both tours: Approvers and Manager/Coach are unconditionally read-only for
// everyone, including an administrator (developer feedback 2026-09-10) - who approves what, and
// who someone's manager/coach is, are derived from the department hierarchy, never hand-edited
// from "My Profile" by anyone.
const alwaysReadOnlySteps = [
    {
        trigger: ".o_field_widget[name='employee_parent_id'].o_readonly_modifier",
        content: "Manager is unconditionally read-only",
    },
    {
        trigger: ".o_field_widget[name='coach_id'].o_readonly_modifier",
        content: "Coach is unconditionally read-only",
    },
    {
        trigger: ".o_notebook .nav-link:contains('Work Information')",
        content: "Open the Work Information tab",
        run: "click",
    },
    {
        trigger: ".o_field_widget[name='attendance_manager_id'].o_readonly_modifier .o_avatar",
        content: "Attendance approver is unconditionally read-only, with an avatar",
    },
    {
        trigger: ".o_field_widget[name='leave_manager_id'].o_readonly_modifier .o_avatar",
        content: "Absence approver is unconditionally read-only, with an avatar too",
    },
];

// Steps shared by both tours: "Private Information" is unconditionally editable, unlike the
// header/Location above (developer feedback 2026-09-10 - personal, not professional, data).
// Only checks the field is rendered editable here; the ordinary-user tour below additionally
// proves the write actually succeeds (the part a view-only check can't cover - res.users.write()
// separately blocks any hr.employee-related field for a self-edit unless "can_edit" is True,
// with no per-field exception of its own, unless EMS's own override carves one out).
const privateInformationEditableSteps = [
    {
        trigger: ".o_notebook .nav-link:contains('Private Information')",
        content: "Open the Private Information tab",
        run: "click",
    },
    {
        trigger: ".o_field_widget[name='marital']:not(.o_readonly_modifier)",
        content: "Private Information fields are editable",
    },
];

registry.category("web_tour.tours").add("ems_user_profile_tabs_ordinary_user", {
    test: true,
    url: "/odoo",
    steps: () => [
        ...openMyProfileSteps("Ordinary Profile Tour Teacher"),
        ...tabOrderSteps(false),
        // Header: "Request Time off" stays, "Request Allocation" is hidden for everybody.
        {
            trigger: ".o_form_statusbar button:contains('Request Time off')",
            content: "\"Request Time off\" is in the header",
        },
        {
            trigger: ".o_form_view:not(:has(.o_form_statusbar button:contains('Request Allocation')))",
            content: "\"Request Allocation\" is hidden",
        },
        // 1. Main form (header): read-only for an ordinary self-viewing user - only the photo is
        // editable regardless, which doesn't need a separate check here.
        {
            trigger: ".o_field_widget[name='job_title'].o_readonly_modifier",
            content: "Job title is read-only for an ordinary user",
        },
        {
            trigger: ".o_field_widget[name='work_location_id'].o_readonly_modifier",
            content: "Work location is read-only for an ordinary user",
        },
        ...alwaysReadOnlySteps,
        // 2. Preferences tab: only "Disable profile picture" and "Language" remain.
        {
            trigger: ".o_notebook .nav-link:contains('Preferences')",
            content: "Open the Preferences tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='image_disabled']",
            content: "\"Disable profile picture\" is visible",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='lang']",
            content: "\"Language\" is visible",
        },
        {
            trigger: ".o_form_view:not(:has(.o_field_widget[name='email']))",
            content: "Email is hidden from Preferences",
        },
        // Daily pending-tasks digest: on by default, and the user can turn their own off (saved
        // with the Private Information edit below; the Python side checks the stored value).
        {
            trigger: ".o_form_view .o_field_widget[name='ems_task_digest'] input:checked",
            content: "The daily summary of pending tasks is on by default",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='ems_task_digest'] input:not(:checked)",
            content: "The daily summary of pending tasks is turned off",
        },
        // The attendance issues report only concerns whoever tutors a group: not this teacher.
        {
            trigger: ".o_form_view:not(:has(.o_field_widget[name='ems_attendance_report_moment']))",
            content: "The attendance issues report option is hidden from a non-tutor",
        },
        {
            trigger: ".o_form_view:not(:has(.o_field_widget[name='tz']))",
            content: "Timezone is hidden from Preferences",
        },
        {
            trigger: ".o_form_view:not(:has(.o_field_widget[name='signature']))",
            content: "Signature is hidden from Preferences",
        },
        {
            trigger: ".o_form_view:not(:has(.o_field_widget[name='calendar_default_privacy']))",
            content: "\"Calendar Default Privacy\" is hidden from Preferences",
        },
        // 3. Work Information tab: "Location" is read-only for an ordinary user.
        {
            trigger: ".o_notebook .nav-link:contains('Work Information')",
            content: "Open the Work Information tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='department_id'].o_readonly_modifier",
            content: "Department is read-only for an ordinary user",
        },
        {
            trigger: ".o_field_widget[name='address_id'].o_readonly_modifier",
            content: "Address is read-only for an ordinary user",
        },
        // 4. "HR Settings" tab: hidden entirely for an ordinary user.
        {
            trigger: ".o_form_view:not(:has(.o_notebook .nav-link:contains('HR Settings')))",
            content: "HR Settings tab is hidden for an ordinary user",
        },
        // "Private Information": editable, and an actual save genuinely succeeds - the real
        // proof res.users.write()'s own carve-out works, not just that the view looks editable.
        ...privateInformationEditableSteps,
        {
            trigger: ".o_field_widget[name='emergency_contact'] input",
            content: "Edit a Private Information field",
            run: "edit Ordinary Tour Emergency Contact",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_view:not(:has(.modal)) .o_field_widget[name='emergency_contact'] input:value('Ordinary Tour Emergency Contact')",
            content: "Save succeeded, no AccessError - the value persisted",
        },
        // Waiting for the value alone isn't the true end of the save: the record's own
        // "isDirty" recompute (which drives the '.o_form_dirty' class / Discard button) lands a
        // render tick AFTER the field value itself is already visible in the DOM - ending the
        // tour right on the previous step could still catch '.o_form_dirty' transiently present,
        // which Odoo's own post-tour harness (odoo/tests/common.py, browser_js's "_check_form")
        // treats as a real failure ("Tour finished with an open form view in edition mode"),
        // since it has no way to tell a real leftover unsaved change apart from this one-tick
        // race. Confirmed via a throwaway diagnostic step here (2026-09-11): the exact same
        // check found ZERO '.o_form_dirty' nodes one step later, with nothing else changed -
        // proving this is a timing artifact of ending the tour too early, not an actual
        // leftover-dirty-state bug in the save path itself.
        {
            trigger: ".o_form_view:not(.o_form_dirty)",
            content: "The form has actually settled (no dirty state left) before the tour ends",
        },
    ],
});

registry.category("web_tour.tours").add("ems_user_profile_tabs_administrator", {
    test: true,
    url: "/odoo",
    steps: () => [
        ...openMyProfileSteps("Administrator Profile Tour Teacher"),
        {
            trigger: ".o_form_view:not(:has(.o_form_statusbar button:contains('Request Allocation')))",
            content: "\"Request Allocation\" is hidden for an administrator too",
        },
        ...tabOrderSteps(true),
        // 1. Main form (header): stays editable for an administrator.
        {
            trigger: ".o_field_widget[name='job_title']:not(.o_readonly_modifier)",
            content: "Job title stays editable for an administrator",
        },
        {
            trigger: ".o_field_widget[name='work_location_id']:not(.o_readonly_modifier)",
            content: "Work location stays editable for an administrator",
        },
        ...alwaysReadOnlySteps,
        // 2. Preferences tab: same trimming applies regardless of privilege.
        {
            trigger: ".o_notebook .nav-link:contains('Preferences')",
            content: "Open the Preferences tab",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='image_disabled']",
            content: "\"Disable profile picture\" is visible",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='lang']",
            content: "\"Language\" is visible",
        },
        // Nothing stays hidden from Preferences for an administrator (developer feedback
        // 2026-09-10) - email/timezone/signature/calendar privacy all show up too.
        {
            trigger: ".o_form_view .o_field_widget[name='email']",
            content: "Email is visible for an administrator",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='tz']",
            content: "Timezone is visible for an administrator",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='signature']",
            content: "Signature is visible for an administrator",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='calendar_default_privacy']",
            content: "\"Calendar Default Privacy\" is visible for an administrator",
        },
        // 3. Work Information tab: "Location" stays editable for an administrator.
        {
            trigger: ".o_notebook .nav-link:contains('Work Information')",
            content: "Open the Work Information tab",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='department_id']:not(.o_readonly_modifier)",
            content: "Department stays editable for an administrator",
        },
        {
            trigger: ".o_field_widget[name='address_id']:not(.o_readonly_modifier)",
            content: "Address stays editable for an administrator",
        },
        // 4. "HR Settings" tab: reachable and editable for an administrator.
        {
            trigger: ".o_notebook .nav-link:contains('HR Settings')",
            content: "HR Settings tab is visible for an administrator",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='employee_type']:not(.o_readonly_modifier)",
            content: "Employee Type stays editable for an administrator",
        },
        // "Private Information": editable for an administrator too (was already the case
        // natively - "can_edit" - but still worth a positive check here for completeness).
        ...privateInformationEditableSteps,
    ],
});

// A group tutor chooses when they receive their attendance issues report
// (models/attendance/attendance_report_schedule.py); the time only shows for "At a fixed time".
registry.category("web_tour.tours").add("ems_user_profile_attendance_report_tutor", {
    test: true,
    url: "/odoo",
    steps: () => [
        ...openMyProfileSteps("Tutor Profile Tour Teacher"),
        {
            trigger: ".o_notebook .nav-link:contains('Preferences')",
            content: "Open the Preferences tab",
            run: "click",
        },
        {
            trigger: ".o_form_view:not(:has(.o_field_widget[name='ems_attendance_report_time']))",
            content: "No time to pick for the default moment",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='ems_attendance_report_moment'] select",
            content: "Choose to receive the report at a fixed time",
            run: "selectByLabel At a fixed time",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='ems_attendance_report_time'] input",
            content: "Set the time",
            run: "edit 21:20",
        },
        {
            trigger: ".o_form_button_save",
            content: "Save",
            run: "click",
        },
        {
            trigger: ".o_form_view:not(.o_form_dirty) .o_field_widget[name='ems_attendance_report_time'] input:value('21:20')",
            content: "Saved",
        },
    ],
});
