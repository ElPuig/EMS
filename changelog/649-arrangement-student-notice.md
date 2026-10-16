# What's new

## Guard arrangements prepare a notice for the students about the lessons that change time:

- When an internal arrangement on the guard duty board moves a lesson into another time block, or swaps two lessons, the group's students now get a draft notice (students only, never the families) listing every lesson of the group that changes time that day, with its subject and its usual and new time span in the centre's timezone (issue #649).
- One draft per group and day, kept up to date by the board: applying another arrangement adds its lessons, withdrawing or replacing one takes them out, and the draft is deleted when nothing is left. Deleting a families' draft (which discards the moves waiting for it) updates it too. A draft is only rewritten when its lessons change, so the planner's own edits survive other board actions.
- Once the notice has been sent, a later change proposes a new draft marked as a correction, listing the lessons as they are now and those back at their usual time; none when the lessons go back to what was sent.
- The arrangement never waits for this notice: it is in effect as before. Applying a plan opens the families' draft first if there is one, otherwise the students' draft; a swap applied on its own opens the students' draft.
- The notice belongs to whoever applied the arrangement (a Department or Seminar Chief included), who reviews and sends it from the notice form; its groups and recipients are locked to the group's students (new constraint `_check_arrangement_recipients`, new form banner). New fields: `ems.notice.arrangement_date`/`arrangement_group_id`/`arrangement_lessons`, `ems.absence_cover.student_notice_id`.
- The `ems_absence_arrangement` tour is split in two (`ems_absence_arrangement_result` checks the board afterwards), since applying the plan now opens the students' notice form.
