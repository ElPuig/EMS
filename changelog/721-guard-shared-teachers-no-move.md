# Changes

## Guard duty board: only a teacher's own area moves them (issue #721):

- Some teachers are shared between ESO/BTX and VET, and ESO/BTX organises its guards outside the board. On 2026-10-28 a VET department chief took an ESO/BTX teacher's VET lesson to the hour of their ESO guard (a regular guard counts as free since #709), and ESO lost that guard without knowing.
- New rule, decided by who is deciding rather than by the group of the class, so it works both ways: only someone of the teacher's area (the area of their department, or of a department named in "Also managed by the departments") may change their timetable or send them to cover a class. Direction and the administrator always can; a teacher with no area is anybody's; a guard taking a class themselves is unaffected.
- Applies to the detected swaps, moved lessons and joins (a co-teacher of another area stays on guard at the lesson, with the warning "organised by another area"), to the manual arrangement's teacher list and to the guard teachers offered to send. The server checks again when applying.
- `ems.course._can_move_teacher()`, cached per board load (at most 15 ms of a 0.43 s board load on real data). Developer doc ("Teachers of another area") and the teachers' guard duty manual in ca/es/en updated; ca/es translations added.

## Guard duty board: the hour of a timetable change is chosen inside its sentence:

- In "Only tell the families" (and in the corrections), the selector of how much of the change to tell no longer sits on the right of the step: it replaces the hour inside the sentence ("SMX2A: Could leave at [11:00]."), or the whole change when the options differ in kind (starting later or no classes, the usual timetable in a correction). Requested by the developer while testing #721.
