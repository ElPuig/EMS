[Català](../../ca/admin/strike.md) | [Castellano](../../es/admin/strike.md) | [English](strike.md)

---

# Strikes: Managing Reasons and Escalation Threshold

**Required role:** Administrator

---

## Managing Strike Reasons

The reasons teachers pick from when issuing a strike are configurable under **Convivencia → Configuration → Strikes → Reasons**.

- Each reason has a **Name** (translatable) and a **Sequence** (drag to reorder — the first one in the list is used as the default preselected reason in the roll-call dialog).
- Use the standard **Archive** action (⚙ menu on the form, or select rows in the list and use the same menu) to retire a reason without deleting it — existing strikes keep referencing it correctly. Archived reasons are hidden by default; use **Filters → Archived** in the list to see them again, or to Unarchive one.
- The seeded "Other / General" reason (`ems.strike_reason_other`) is the system default — keep it active (not archived), since it's what the roll-call dialog preselects.

---

## Configuring the Escalation Threshold

Under **Settings → EMS Management → "Strikes Settings"**, set how many accumulated strikes trigger an escalation email to the coexistence coordinator — the coordinator is notified again every time the count reaches a further multiple of this number (e.g. with the default of 3: at 3, 6, 9 strikes...).

---

## Configuring Family Notification

The same "Strikes Settings" block also has a **Family notification** option: **All strikes** notifies the family on every strike (subject to the usual minor/authorization rule), **Kicked out only** notifies them only when the strike also has "Kicked out of class" checked. The student and the group tutor are always notified either way. New installations start on **Kicked out only**; an installation upgrading from an earlier version keeps **All strikes**.

---

## Assigning the Coexistence Role

Coexistence coordinators are assigned like any other role, under **Community → Configuration → Teachers → Roles**, by adding an employee to the "Coexistence coordinator" role. Unlike most coordination roles, this one is not limited to a single person — assign one per Head of Studies / Deputy Head of Studies branch as needed, since escalation emails are routed to whichever coordinator shares the issuing teacher's branch. See the [Teacher Roles and Permission Levels](teacher-roles.md) manual for the general role-assignment workflow.

---

[← Back to Admin manuals](index.md)
