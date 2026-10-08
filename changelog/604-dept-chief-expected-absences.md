# What's new

## Department and Seminar Chiefs can enter expected absences (issue #604):

- Department and Seminar Chiefs can now create, edit and delete expected absences (Absences > Management > Expected absences), for the teachers of their own department only, for the exceptional case of a teacher who phones or writes to warn they will be away and cannot use EMS. Until now only the Head of Studies, their Deputy, Direction and the administrator could.
- Access moves from `ems.group_head_of_studies` to `ems.group_department_chief` (which Head of Studies, Deputy and Director imply), with the same hierarchy/department record rule (`rule_absence_pending_hierarchy`), so a chief reaches their own department and nothing else; the administrator keeps reaching every teacher.
- Menu: Absences > Management now opens to Department/Seminar Chiefs for this single entry. "Requested absences" now states the absence managers' group explicitly so it stays hidden from them, and "My Time Off" is listed for chiefs too, since "Absences" becomes a dropdown for them.
- Tests: chief/seminar-chief reach (own department only, through the real department cascade), menu visibility, and the expected-absences tour now runs as a Department Chief. Manuals updated (teachers' guard duty schedule gets an "Entering an expected absence" section; Head of Studies' absences manual and developer docs adjusted), in the three languages.
