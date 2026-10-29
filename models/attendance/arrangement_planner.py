# -*- coding: utf-8 -*-

from collections import defaultdict

from ..shared.schedule_report_mixin import HOUR_EPSILON
from .absence_coverage import overlaps


def schedule_shift(periods, removed, added, duties=()):
    """How a teacher's working day - from their first period to their last, lessons, guards and any
    other duty alike (`periods`) - changes if they stop teaching the `removed` periods and teach the
    `added` ones instead (`removed[i]` goes to `added[i]`): `[(kind, old, new)]`, `kind` being
    'entry' or 'exit', empty when neither moves. None when the day would get longer: coming in
    earlier is only possible leaving earlier too, and leaving later coming in later (developer
    decision, 2026-10-10).
    A lesson taken to one of their `duties` (a guard, a coordination, any non-teaching hour of their
    timetable) swaps with it: the duty goes to the hour the lesson leaves, so they are in then as
    always and their day does not change (issue #709)."""
    if not periods:
        return None
    before = (min(start for start, _stop in periods), max(stop for _start, stop in periods))
    kept = [period for period in periods if not any(overlaps(*period, *gone) for gone in removed)] + list(added)
    kept += [gone for gone, new in zip(removed, added) if any(overlaps(*new, *duty) for duty in duties)]
    after = (min(start for start, _stop in kept), max(stop for _start, stop in kept))
    if after[1] - after[0] > before[1] - before[0] + HOUR_EPSILON:
        return None
    return [(kind, old, new) for kind, old, new in (('entry', before[0], after[0]), ('exit', before[1], after[1]))
            if abs(old - new) > HOUR_EPSILON]


class ArrangementPlanner:
    """Finds the internal arrangements (issue #645) that leave a set of groups' day with as few
    lessons lost and as few hours without class inside the centre as possible: sequences of moved
    lessons, each teacher filling the gap the previous one left, until the last gap reaches the
    start or the end of the day (or a break) and is solved by telling the families.

    Works on the groups linked that day by shared lessons (moving a shared lesson changes every one
    of them), on plain data the board already read once: no query, so it can explore many
    combinations. Everything about the timetable that needs the ORM comes in as data or as the
    `free` callable; the change rules (what a late entry, an early leave or a longer break is)
    are the board's own, through `course`.

    - `blocks`: `{group id: [{'hour_from', 'hour_to', 'teachers', 'away', 'filled'}]}`, each group's
      day block by block (see ems.course._get_group_day_blocks): its teachers' ids, those away or
      whose lesson went elsewhere, and whether somebody already covers it.
    - `breaks`: `{group id: [(hour_from, hour_to)]}`, its level's breaks that day.
    - `communicated`: `{group id: {side: change}}`, what the families were already told per side.
    - `teachers`: `{teacher id: {'lessons': [((hour_from, hour_to), frozenset(group ids), subject id)],
      'periods': [(hour_from, hour_to)], 'duties': [(hour_from, hour_to)], 'vacated': [(hour_from, hour_to)]}}`:
      their own lessons with these groups, every period of their day, those of them with no class
      (see schedule_shift), and their lessons another arrangement already moved.
    - `sessions`: `[(lesson, frozenset(group ids), frozenset(teacher ids), frozenset(away ids))]`,
      the lessons of these groups with the teachers who give them together, and which of them are
      away then (issue #678): co-teachers are a pack, the lesson moves with all of them (see
      ems.course._arrangement_sessions).
    - `free(teacher id, hour_from, hour_to)`: whether they can be with a group then.
    - `enabled`: `{group id: change types}`, the timetable changes each group may have (see
      ems.course._enabled_absence_changes).
    - `swaps`: the lesson swaps the timetable allows (see ems.course._get_arrangement_options),
      as steps: they combine with moves like any other step.
    - `partners`: `{group id: frozenset(group ids)}`, the other halves of a split group (issue
      #660): groups sharing some lesson in the weekly timetable.
    - `fixed`: the teachers whose day must not change (issue #721: another area organises them,
      see ems.course._can_move_teacher). No step moves, joins or swaps a lesson of theirs; a
      co-teacher among them stays on guard at the lesson, like one who is busy.

    A step is a hashable tuple `(kind, teachers, lesson, target, group ids, absents, stays, joined)`:
    'move', 'swap' or 'join'; the pack that teaches its `lesson` in the gap (`target`) for those
    groups; in a swap the absent teachers who teach `lesson` instead (empty otherwise); the
    co-teachers who cannot follow the lesson (busy or away in the gap, or their day would get
    longer) but are in at its usual time, who stay on guard while it is gone; and in a join the
    other halves it is taught together with (empty otherwise). A teacher away at the lesson can
    still take it to a gap where they are in: their own lesson is taught after all. A join (issue
    #660) is a move whose target is not a free hour of the teachers but one where they teach the
    same subject to the other half of the group: both halves are taught together then, and the
    lesson it leaves is a gap like a move's. Teachers and groups as frozensets of ids, periods as
    `(hour_from, hour_to)`."""

    MAX_MOVES = 4
    BEAM = 30

    def __init__(self, course, blocks, breaks, communicated, now_hour, teachers, sessions, free, enabled, swaps=(),
                 partners=None, fixed=frozenset()):
        self.course = course
        self.blocks = blocks
        self.breaks = breaks
        self.communicated = communicated
        self.now_hour = now_hour
        self.teachers = teachers
        self.sessions = sessions
        self.free = free
        self.swaps = list(swaps)
        self.partners = partners or {}
        self.fixed = fixed
        self.enabled = enabled

    # The state a sequence of steps leaves the groups' day in.

    def simulate(self, steps):
        day = {group_id: [dict(block, away=set(block['away'])) for block in blocks]
               for group_id, blocks in self.blocks.items()}
        for kind, teachers, lesson, target, group_ids, _absents, stays, _joined in steps:
            for group_id in group_ids:
                for block in day[group_id]:
                    if overlaps(block['hour_from'], block['hour_to'], *target):
                        block['filled'] = True
                    if overlaps(block['hour_from'], block['hour_to'], *lesson):
                        # The lesson is gone: whoever stays behind is on guard, not with the group.
                        block['away'] |= teachers | stays
                        if kind == 'swap':
                            block['filled'] = True  # the absent teachers teach it instead
        for group_id, blocks in day.items():
            for block in blocks:
                block['empty'] = bool(block['teachers']) and block['teachers'] <= block['away'] and not block['filled']
                block['taught'] = (block['teachers'] - block['away']).union(*(
                    step[1] for step in steps if group_id in step[4] and overlaps(block['hour_from'], block['hour_to'], *step[3])
                ), *(step[5] for step in steps if group_id in step[4] and overlaps(block['hour_from'], block['hour_to'], *step[2])))
        return day

    def _is_past(self, change, blocks):
        return self.now_hour is not None and self.course._change_start(change, blocks) <= self.now_hour

    def _side_options(self, group_id, blocks):
        """`{side: (options, communicated)}` of one group's simulated day: the changes still to come
        it allows, from the smallest to the largest, and what the families were told on that side."""
        allowed = self.course._allowed_absence_changes(blocks, self.breaks.get(group_id, ()), self.enabled[group_id])
        return {side: ([option for option in options if not self._is_past(option, blocks)],
                       self.communicated.get(group_id, {}).get(side))
                for side, options in allowed.items()}

    def _evaluate(self, steps):
        """`(score, notices)`. The notices are the largest change each side allows that nobody was
        told yet, `(group id, side, change)`. The score, lower is better:
        1. lessons the students lose;
        2. of those, the hours they spend in the centre without class: with a guard, or in a
           longer break - coming in later or leaving earlier is what avoids them;
        3. of those, the ones that need a guard - a longer break still does: the students under 18
           cannot leave the centre (issue #679);
        4. notices to the families;
        5. co-taught lessons moved without all of their teachers (issue #678);
        6. teachers who move a lesson;
        7. runs of a teacher's lessons with a group cut in two (two hours in a row of the same
           subject are better kept together);
        8. changes to somebody's entry or exit time."""
        day = self.simulate(steps)
        lost = idle = guards = 0
        notices = []
        for group_id, blocks in day.items():
            told, untold = self._windows(group_id, blocks)
            notices += [(group_id, side, change) for side, change in untold]
            windows = told + [change for _side, change in untold]
            for block in blocks:
                if block['empty']:
                    lost += 1
                    if self._needs_guard(block, windows):
                        idle += 1
                        guards += 1
        shifts = self._shifts(steps)
        broken = sum(1 for step in steps if step[6])
        moves = len(frozenset().union(*(step[1] for step in steps)))
        return (lost, idle, guards, len(notices), broken, moves, self._runs(day),
                sum(len(changes) for changes in shifts.values())), notices

    def _windows(self, group_id, blocks):
        """`(told, untold)` for one group's simulated day: the changes its families were told that
        still free its lessons (still valid, or past: a stale one is the correction box's business,
        not a plan's), and `(side, change)`, the largest change each side nobody was told about
        allows."""
        told, untold = [], []
        for side, (options, communicated) in self._side_options(group_id, blocks).items():
            if communicated:
                if self._is_past(communicated, blocks) or any(
                        self.course._same_change(communicated, option) for option in options):
                    told.append(communicated)
            elif options:
                untold.append((side, options[-1]))
        return told, untold

    def _needs_guard(self, block, windows):
        """Whether an empty block needs a guard all the same: none of the changes `windows` frees
        the group from it, or only a longer break (the students under 18 stay in, issue #679)."""
        return all(window[0] == 'long_break' for window in windows
                   if self.course._change_window_contains(window, block['hour_from'], block['hour_to']))

    def gaps(self, steps, notices):
        """The classes still to come that `steps` leave without anybody and that need a guard all
        the same (issue #710): no change the families were told, nor one of `notices` (`(group id,
        change)`, those applied with the steps), frees the group from them. `[(group id,
        (hour_from, hour_to))]`, by time."""
        gaps = []
        for group_id, blocks in self.simulate(steps).items():
            told, _untold = self._windows(group_id, blocks)
            windows = told + [change for notice_group, change in notices if notice_group == group_id]
            gaps += [(group_id, (block['hour_from'], block['hour_to'])) for block in blocks
                     if block['empty'] and self._needs_guard(block, windows)
                     and (self.now_hour is None or block['hour_to'] > self.now_hour + HOUR_EPSILON)]
        return sorted(gaps, key=lambda gap: (gap[1], gap[0]))

    @staticmethod
    def _runs(day):
        """How many runs of consecutive lessons each teacher has with each group, in all."""
        runs = 0
        for blocks in day.values():
            previous = set()
            for block in blocks:
                runs += len(block['taught'] - previous)
                previous = block['taught']
        return runs

    def _shifts(self, steps):
        """`{teacher id: [(kind, old, new)]}` for every teacher the steps move; None for a teacher
        whose day they would lengthen."""
        removed, added = defaultdict(list), defaultdict(list)
        for _kind, teachers, lesson, target, _groups, absents, _stays, _joined in steps:
            for teacher_id in teachers:
                removed[teacher_id].append(lesson)
                added[teacher_id].append(target)
            # In a swap the absent teachers teach the other lesson instead of their own.
            for teacher_id in absents:
                removed[teacher_id].append(target)
                added[teacher_id].append(lesson)
        return {teacher_id: schedule_shift(self.teachers[teacher_id]['periods'], removed[teacher_id], added[teacher_id],
                                           self.teachers[teacher_id].get('duties', ()))
                for teacher_id in removed}

    # The steps possible from a state.

    def _keeps_days(self, steps, step):
        shifts = self._shifts([*steps, step])
        return all(shifts.get(teacher_id) is not None for teacher_id in step[1] | step[5])

    def _steps(self, steps, day):
        holes = defaultdict(set)
        for group_id, blocks in day.items():
            for block in blocks:
                if block['empty']:
                    holes[(block['hour_from'], block['hour_to'])].add(group_id)
        # Where each teacher already is because of a step: in the gap they fill, and in a swap the
        # absent teachers at the other lesson.
        taken = [(teacher_id, step[3]) for step in steps for teacher_id in step[1]] + \
                [(teacher_id, step[2]) for step in steps for teacher_id in step[5]]
        vacated = {(teacher_id, step[2]) for step in steps for teacher_id in step[1] | step[6]}

        def busy(teacher_id, period):
            return teacher_id in self.fixed or any(
                other == teacher_id and overlaps(*other_period, *period) for other, other_period in taken)

        for step in self.swaps:
            _kind, teachers, lesson, target, group_ids, absents, stays, _joined = step
            if step not in steps and target in holes and group_ids <= holes[target] \
                    and not any((teacher_id, lesson) in vacated for teacher_id in teachers | stays) \
                    and not any(busy(teacher_id, target) for teacher_id in teachers) \
                    and not any(busy(teacher_id, lesson) for teacher_id in absents) \
                    and self._keeps_days(steps, step):
                yield step
        for target, group_ids in sorted(holes.items()):
            for lesson, lesson_groups, pack, away in self.sessions:
                # Every group of the lesson must have the gap: a shared lesson moves for all of
                # them, and none may end up with a lesson where it already had one.
                if overlaps(*lesson, *target) or not lesson_groups <= group_ids \
                        or any((teacher_id, lesson) in vacated or any(
                            overlaps(*lesson, *other) for other in self.teachers[teacher_id]['vacated'])
                            for teacher_id in pack):
                    continue
                # The whole pack follows the lesson (issue #678); whoever cannot stays on guard.
                movers = {teacher_id for teacher_id in pack if not busy(teacher_id, target) and self.free(teacher_id, *target)}
                movers = self._keeping_days(steps, movers, lesson, target, lesson_groups)
                if movers:
                    yield ('move', movers, lesson, target, lesson_groups, frozenset(), pack - movers - away, frozenset())
        yield from self._join_steps(steps, day, holes, busy, vacated)

    def _keeping_days(self, steps, movers, lesson, target, lesson_groups):
        """Those of `movers` whose working day taking `lesson` to `target` does not lengthen."""
        shifts = self._shifts([*steps, ('move', frozenset(movers), lesson, target, lesson_groups, frozenset(), frozenset(),
                                         frozenset())])
        return frozenset(teacher_id for teacher_id in movers if shifts.get(teacher_id) is not None)

    def _join_steps(self, steps, day, holes, busy, vacated):
        """The joins (issue #660) into the gaps of `holes`: the teachers of a lesson who, in a gap of
        its groups, are teaching the same subject to another half of them (a partner, see
        `partners`) bring it there, so both halves are taught together. They must really be with
        the other half then (not away, not moved). Co-teachers are a pack (issue #678): those of the
        lesson who are not with the other half then stay on guard at its usual time."""
        if not self.partners:
            return
        for target, group_ids in sorted(holes.items()):
            for lesson, lesson_groups, pack, away in self.sessions:
                if overlaps(*lesson, *target) or not lesson_groups <= group_ids \
                        or not all(self.partners.get(group_id) for group_id in lesson_groups) \
                        or any((teacher_id, lesson) in vacated or any(
                            overlaps(*lesson, *other) for other in self.teachers[teacher_id]['vacated'])
                            for teacher_id in pack):
                    continue
                joins = defaultdict(set)
                for teacher_id in pack:
                    if busy(teacher_id, target):
                        continue
                    lessons = self.teachers[teacher_id]['lessons']
                    subjects = {subject for period, groups, subject in lessons
                                if subject and period == lesson and groups & lesson_groups}
                    for joint, joint_groups, subject in lessons:
                        if subject in subjects and overlaps(*joint, *target) and not joint_groups & lesson_groups \
                                and all(self.partners[group_id] & joint_groups for group_id in lesson_groups) \
                                and all(any(teacher_id in block['taught'] for block in day.get(group_id, ())
                                            if overlaps(block['hour_from'], block['hour_to'], *target))
                                        for group_id in joint_groups):
                            joins[joint_groups].add(teacher_id)
                for joint_groups, movers in sorted(joins.items(), key=lambda item: sorted(item[0])):
                    movers = self._keeping_days(steps, movers, lesson, target, lesson_groups)
                    if movers:
                        yield ('join', movers, lesson, target, lesson_groups, frozenset(), pack - movers - away, joint_groups)

    # Search.

    def plans(self, limit=3):
        """The best plans, `[{'steps', 'notices', 'score', 'depends', 'notice_depends', 'shifts'}]`:
        a beam search over moves, joins and swaps (at most MAX_MOVES steps). Only those better
        than leaving the day as it is in lessons lost, hours without class, guards or notices: one
        that only moves the gap to another hour, still needing a guard, is no proposal (issue
        #711). And none that merely adds steps to another one that does as well."""
        base, _notices = self._evaluate(())
        candidates = {}
        frontier, seen = [()], {frozenset()}
        for _depth in range(self.MAX_MOVES):
            expanded = []
            for steps in frontier:
                day = self.simulate(steps)
                for step in self._steps(steps, day):
                    new = (*steps, step)
                    key = frozenset(new)
                    if key in seen:
                        continue
                    seen.add(key)
                    score, notices = self._evaluate(new)
                    expanded.append((score, new, notices))
            expanded.sort(key=lambda item: item[0])
            candidates.update({frozenset(steps): (score, steps, notices) for score, steps, notices in expanded})
            frontier = [steps for _score, steps, _notices in expanded[:self.BEAM]]
            if not frontier:
                break
        kept = [(score, steps, notices) for score, steps, notices in candidates.values() if score[:4] < base[:4]]
        kept = [(score, steps, notices) for score, steps, notices in kept if not any(
            frozenset(other) < frozenset(steps) and other_score[:4] <= score[:4]
            for other_score, other, _other_notices in kept)]
        kept.sort(key=lambda item: (item[0], [(step[0] != 'swap', step[3], sorted(step[1])) for step in item[1]]))
        # Two ways to the very same day (a swap seen from each of its two absences) are one plan.
        unique, seen_days = [], set()
        for score, steps, notices in kept:
            day = self.simulate(steps)
            signature = (frozenset((group_id, index, frozenset(block['taught'])) for group_id, blocks in day.items()
                                   for index, block in enumerate(blocks)), tuple(sorted(notices)))
            if signature not in seen_days:
                seen_days.add(signature)
                unique.append((score, steps, notices))
        return [self._plan(score, steps, notices) for score, steps, notices in unique[:limit]]

    def _plan(self, score, steps, notices):
        """One plan with its steps' dependencies: a move into a gap another step left needs that
        step, and a notice needs the moves whose lessons left free are part of what it frees."""
        created = []
        depends = []
        for index, step in enumerate(steps):
            depends.append(sorted({other for other, (group_id, period) in created
                                   if group_id in step[4] and overlaps(*period, *step[3])}))
            if step[0] in ('move', 'join'):
                created += [(index, (group_id, step[2])) for group_id in step[4]]
        notice_depends = [sorted({other for other, (group_id, period) in created if group_id == notice_group
                                  and self.course._change_window_contains(change, *period)})
                          for notice_group, _side, change in notices]
        return {'steps': list(steps), 'notices': notices, 'score': score, 'depends': depends,
                'notice_depends': notice_depends, 'shifts': self._shifts(steps)}

    def check(self, steps, notices):
        """Whether `steps` (in order) and `notices` (`(group id, change)`) can be applied as they are
        now: each move into a gap still there, with a teacher still free, nobody's day longer; each
        notice one of the changes the resulting day allows, on a side the families were not told
        about yet. Returns the error, or None."""
        applied = ()
        for step in steps:
            if step not in set(self._steps(applied, self.simulate(applied))):
                return 'step'
            applied = (*applied, step)
        day = self.simulate(applied)
        for group_id, change in notices:
            sides = self._side_options(group_id, day.get(group_id, []))
            if not any(not communicated and any(self.course._same_change(change, option) for option in options)
                       for options, communicated in sides.values()):
                return 'notice'
        return None
