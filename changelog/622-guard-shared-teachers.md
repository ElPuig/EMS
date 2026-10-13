# Changes:
## Absences of shared teachers are organised by the department of the group (issue #622):
- Who organises an absence from the guard duty board (sending, changing or releasing a guard, internal arrangements, late entry / early leave notices) is now decided by whose students lose the class, not by the absent teacher's department: a class of a group whose study names a managing department is organised by that department's Department Chief and Seminar Chief and whoever is above them (area manager, Direction, administrator), and by nobody else. A Foreign Languages teacher's lesson with a Computer Science group is covered by the Computer Science chiefs; her lesson with an Administration group, by the Administration ones.
- New field "Managed by the department" on the study (`ems.study.managing_department_id`), edited by the administrator; the group form shows the resulting department(s) read-only (`ems.group.managing_department_ids`). A reinforcement group, which has no study, follows the studies of its main groups.
- A study with no managing department (ESO/BTX, whose departments are by subject) keeps the previous behaviour: the absent teacher's own chain of command. A teacher's own guard duty (WC, break), which has no group, also stays with their chain.
- The absent teacher's own Department Chief and Head of Studies can no longer organise a class of a group managed by another department.
- Expected absences: a chief can also enter one for a teacher of another department who teaches a group their department manages.
- Department and Seminar Chiefs can send notices to the groups their department manages, besides those it teaches.
- Migration 18.0.0.37.0 (and the clean-install hook) sets each study's managing department to the one whose teachers give more than half of its groups' classes; studies where no department reaches half stay blank. Check the result on Educational Community > Configuration > Curriculum > Studies after deploying.

# Internal changes:
## Department chiefs resolved in one place:
- `hr.department._chief_users()` walks a department's Department/Seminar Chiefs up its parent chain; the notices' "groups their department teaches" scope and the new group-managing scope both use it.
