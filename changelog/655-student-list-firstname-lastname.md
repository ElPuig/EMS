# Changes

## Students list: first name and last name columns, sorted by last name:

- Educational Community > Students, list view: first name and last name are now columns of their own, and the list is sorted by last name (then first name), the same order as the roll-call. The complete name is hidden by default and can be shown again from the optional columns menu.
- Its own primary list view (`ems.view_student_list`, child of `base.view_partner_tree`, so every EMS student column still applies) bound to the Students action's list mode only, after the kanban, which is still what the menu opens on. Families and Providers keep the shared contact list as it was.
- Tours that opened a student by clicking the cell with their complete name now go through a shared helper (`static/tests/tours/student_list_helpers.js`): they search the student first, since a test student is no longer on the first page once the list is sorted by last name, and find the row by the last name column.
- Teachers' manual (students list) and its screenshot updated in Catalan, Spanish and English.
