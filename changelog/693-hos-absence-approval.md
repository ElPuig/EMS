# Changes

## Area Managers validate their own absence (Direction reviews it afterwards):

- The Head of Studies, the Deputy Head of Studies and the Secretary are now the approver (`leave_manager_id`) of their own absence, instead of the Director: they acknowledge and validate their own request, supporting document included, and Direction then reviews it like anybody else's. Before, the Director had to do both the Head's step and Direction's own, and the Area Manager was shown an Approve button on their own request that ended in an access error ("An approved absence request can no longer be changed").
- The "approved requests are closed to their own employee" guard lets through only what the Head's own steps write (state, approvers, calendar meeting, document state), so an Area Manager still cannot edit their own approved absence, and still cannot undo a decision on it (Direction can).
- The officers' "Waiting For Me" filter now also lists the reader's own pending requests when they are their own approver.
- An Area Manager's attendance corrections still go to the Director (`attendance_manager_id` no longer mirrors `leave_manager_id` in that one case).
- Migration (`18.0.0.41.1` post-migrate, manifest bumped to 18.0.0.41.1): recomputes the approver of every Area Manager and hands their open requests (Pending, Pending validation) over to them, with their activity and followers, without emailing anybody.
- Head of Studies and Secretary manuals (ca/es/en) and developer docs updated.

# Related with

- Closes #693
