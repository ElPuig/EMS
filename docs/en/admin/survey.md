[Català](../../ca/admin/survey.md) | [Castellano](../../es/admin/survey.md) | [English](survey.md)

---

# Surveys: LimeSurvey Integration

**Required role:** Administrator or Quality coordinator (see [Visibility](#visibility-who-sees-which-surveys) below for the difference between the two)

---

## What a Survey Is

EMS's **Surveys** feature (**Communications → Surveys**) generates and manages LimeSurvey
questionnaires for students, teachers or ASP staff — evaluation/satisfaction surveys sent out
and tracked without leaving EMS. Not to be confused with Odoo's own native Surveys app, which
is hidden in this installation.

---

## The Survey Lifecycle

A survey moves through a fixed sequence of states as you work through it:

1. **Draft** — define the survey's **Title**, **Description**, **Target** (Students / Teachers
   / ASP) and its content **Blocks** (the questions/sections, as tab-separated templates).
2. **Compute recipients** — EMS works out who should receive the survey (filtered by Level/
   Study/Group, or by special per-subject/per-internship rules on individual blocks) and builds
   the **Recipients** list, each with their own enrollment snapshot.
3. **Upload** — the survey and its recipients are created in LimeSurvey itself via its API.
4. **Open** — the survey is live; recipients can respond. Use **Remind** to resend the
   invitation to anyone who hasn't answered yet.
5. **Close** — stops accepting responses.
6. **Download** — pulls the response data back into EMS as a CSV, ready for analysis (e.g. in
   Metabase).

You can return an uploaded/computed survey to **Draft** (recomputing recipients from scratch)
at any point before it's closed.

---

## Visibility: Who Sees Which Surveys

- **Administrators** see and can fully manage every survey, regardless of who created it.
- The **Quality coordinator** sees every survey centre-wide too (so coordinators can keep track
  of each other's work), but can only **create, edit or delete the surveys they personally
  created** — someone else's survey opens in read-only mode.
- A plain **Quality team member** (not the coordinator) keeps unrestricted create/edit access
  to every survey, same as before — this distinction only applies to the coordinator role.

---

## Deleting a Survey

- A survey can be deleted while in **Draft**, **Recipients computed**, or **Closed** state.
- Deleting a **Closed** survey also permanently deletes it from LimeSurvey — if the response
  data hasn't been downloaded yet, it is lost for good. EMS asks for confirmation before doing
  this.
- A survey that is **Uploaded**, **Open**, or otherwise mid-flight cannot be deleted directly —
  close it first.

---

[← Back to Admin manuals](index.md)
