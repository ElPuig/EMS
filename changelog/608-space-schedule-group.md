# Changes:

## A classroom's schedule shows the group in each block:
- In a classroom's own occupation schedule (Schedule tab of the space and its PDF), each block now says which group or groups are in the room at that time, in place of the room's own name, which every block only repeated (developer's decision, 2026-10-11). A co-taught block names each group once; a block with no group (a duty booked in the room) shows nothing there.
- New `ems.schedule_report_mixin._schedule_report_block_detail()` hook (the block's room by default, overridden by `ems.space` to return its groups), exposed as `'detail'` on each block of `get_schedule_report_lines()` and printed by the shared `ems.schedule_report_grid` template, so the group's, the student's and the portal's schedules keep showing the room unchanged. The on-screen widget mirrors it for `ems.space`.
- Backend tests in TestSpaceSchedule (groups instead of the room, each once; a group's schedule still shows the room; PDF), a new step in the `ems_space_schedule_tab` tour, admin manual (3 languages) with its screenshot regenerated, developer doc updated. No new translatable strings.
