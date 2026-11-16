# What's new

## Student walkout calendar: how the hours are counted is a setting (#828):
- Settings > Student Walkout Settings > Calendar gets three controls next to the hours of each phase and of the notice: kind of hours (real hours, or school hours = only the group's class hours from its timetable), when the count starts (real hours only: from the moment of the proposal, or when the group receives the email within its schedule) and whether the days the group has no class (weekends, public holidays, school breaks) count (real hours only, off by default). The notice for the Head of Studies is counted the same way as the phases.
- Counting from the proposal starts the phase at that very moment and sends every email of the proposal (students and tutor) at once, whatever the time: the one exception to "student emails only during school hours". With phases of 24 h and 24 h of notice, a proposal made on Monday can be for Friday.
- A read-only example below the controls, recomputed as they change and before saving, shows a sample group (class 8:00-15:00, Monday to Friday) proposing on a Friday at 17:00: when its vote ends, when the joining ends (the latest the minute reaches the Head of Studies) and the first possible walkout day, plus one sentence on what the combination means. It runs the very same calendar functions as a real proposal, only with a sample timetable and every weekday as a school day.
- Each proposal stores the rule it was opened with (`hours_kind`, `count_from`, `count_days_off`, next to `phase_hours`/`notice_hours`), so changing the settings never moves a running call. The portal form and the "too late" error explain the count in force.
- No migration: the new company fields default to today's count (real hours, from when the group receives the email, days without class not counted), so an upgraded installation behaves as before until changed in Settings; a new installation counts from the proposal (`post_init_hook`). Existing proposals get the same defaults.

# Fixes

## Student walkout settings always showed "0 levels allowed":
- The count next to "Levels and courses" had no dependency, and Odoo never computes such a field for the new record the settings form opens, so it always read 0 whatever the levels said. It now depends on the company, like Odoo's own language count in the general settings. Regression test included (it failed before the fix).

# Internal changes

## One counting core for school days and class hours (#828):
- `ems.datetime_utils.ems_add_school_hours()`/`ems_school_hours_between()` take optional class `windows` (count only those hours) and an injectable `school_days` provider; new `ems_class_send_moment()` holds the "next class" logic that `ems.group._ems_school_send_time()` used to carry inline, and `ems.group._ems_class_windows()` extracts a group's class windows. The walkout builds a single plan per calendar (`_ems_plan`) instead of re-reading the groups' schedules per step.
- The unused "lead time" settings field (`walkout_lead_hours`) is gone, replaced by the example; field labels no longer say "school hours". Obsolete ca/es translations removed, new ones added and verified in the database.
- Tests for every combination (weekends, a public holiday, a school break, outside class hours, school hours with and without a timetable, the vote's end starting the joining at once, a call keeping its rule, the example's values), a settings tour as settings administrator, and updated manuals (families, tutors, Head of Studies; ca/es/en) with a new settings screenshot and a refreshed portal one.
- Characterization tests for the shared counting (`ems_add_school_hours`, `ems_school_hours_between`, `ems.group._ems_school_send_time`: night, weekend, holidays, boundaries, class windows with a break, archived schedules, the default clock) written against the pre-refactor API and run green both on the previous code and on the new one; a split group whose halves have different timetables is covered too. Checked under faketime at 00:30, 9:30 and 23:30 local.
