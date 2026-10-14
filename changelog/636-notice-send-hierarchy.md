# Fixes

## Notices: the chain of command can send a subordinate's draft (issue #636):

- A Deputy Head of Studies opening a draft notice written by a Department Chief of their own branch got an access error when clicking "Send": the record rules let Heads of Studies read every notice but only edit or send the ones they created themselves.
- The edit rules of ems.notice/ems.notice.line (Head of Studies, Quality coordinator, Department/Seminar chiefs) now also match the notices of everyone below the user in the chain of command, resolved like tutor-scoped rights (create_uid.employee_ids.tutor_scope_user_ids: the chiefs above the creator through parent_id, plus the Director). A Head of Studies of another branch, or a peer Department Chief, still only reads it; admins and the Director keep editing every notice.
- The form's Send now / Schedule sending / Cancel buttons moved into its "Actions" dropdown and are hidden, through a new non-stored can_manage field, for anyone who may only read the notice, so nobody is offered a button that ends in an access error.
- The "Schedule" button was translated as "Horari"/"Horario" (timetable): it is now labelled "Schedule sending" ("Programar enviament"/"Programar envío").
- New TransactionCase coverage (TestNoticeHierarchyAccess) and a tour (TestNoticeHierarchyTour) logged in as the Head of Studies above the chief and as one of another branch; the existing notice tour now sends from the Actions dropdown. Developer and user manuals (admin, head_of_studies, teachers) updated in the three languages.
