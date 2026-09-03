[Català](../../ca/admin/absences.md) | [Castellano](../../es/admin/absences.md) | [English](absences.md)

---

# Configuring staff absences

**Role required:** Administrator

---

## The two settings

**Settings > EMS > Staff Absence Settings**:

| Setting | Default | What it does |
|---|---|---|
| Whole-day absence | 7:30 | Hours a whole-day absence is worth. It always counts that much, however many lessons the person had scheduled that day |
| Health absence allowance | 15:00 | Hours of self-declared health absence each person may use per course |

The allowance **warns, it does not block**: someone going over it is warned and the request is flagged for the Head of Studies, but it goes through.

---

## The absence type catalogue

**Absences > Configuration > Time Off Types**. There are nine, and each one's name is the full wording of the leave it grants.

Each type carries four flags that decide how new requests come proposed:

| Flag | Ticked on |
|---|---|
| Adds the hours to the monthly report | All but `Sick leave` |
| Consumes the health allowance | `Health` only |
| Whole day by default | `Health` and `Invasive medical test` |
| Filed through ATRI | `ATRI` only |

These are **proposals**: the absence manager can change them request by request.

---

## Who approves

Not configured here. It comes from the org chart: everyone's approver is **the manager of their top-level department**, set on the department's own form (the *Area Manager* field).

If an area's absences end up with no approver, check that person **has an EMS user account**: the approver has to be a user, not just an employee record.
