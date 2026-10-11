[Català](../../ca/admin/convalidation-settings.md) | [Castellano](../../es/admin/convalidation-settings.md) | [English](convalidation-settings.md)

---

# Convalidation settings

Configure when convalidation requests can be submitted from the portal, the texts of the official resolution the Director issues and the reasons offered when documentation is requested.

**Required role:** Administrator (Settings)

---

## Access

Navigate to: **Settings → EMS Management → Convalidations Settings**

---

## Request period

The **request period** sets when new convalidation requests can be submitted from the portal. It repeats every year, with no year to update: change it only if the centre changes the dates.

![Request period in the settings](../../assets/admin/convalidations-settings.png)

1. Under **Opens**, choose the day, month and time the period starts.
2. Under **Closes**, choose the day, month and time it ends. The closing minute is still part of the period.
3. Save.

By default the period runs from **1 October at 08:00** to **31 March at 23:59**. Times are in the centre's local time.

The period can cross the new year, as the default one does: if the opening comes later in the calendar than the closing, it runs from the opening to the end of the year, and from 1 January to the closing.

The settings accept neither a day that does not exist in its month (not even 29 February, so the period is the same every year) nor a period that opens and closes at the same moment.

### What the period limits and what it does not

| Who | During the period | Outside the period |
|-----|-------------------|--------------------|
| Students and families, on the portal | Submit new requests, check their own, answer the centre, cancel pending ones | Everything except submitting new requests. The portal says when the period opens |
| Head of Studies, Director, secretariat | Everything | Everything: they can register paper requests and process any request at any time |

---

## Resolution texts

The resolution the Director issues is always generated in Catalan. Three settings adjust its content:

![Resolution grounds of law](../../assets/admin/convalidations-settings-resolution.png)

| Setting | What it does |
|---------|--------------|
| **Resolution: grounds of law** | One text for each request ground (prior studies, professional certificate, other), added to Royal Decree 1085/2020, article 8. |
| **Resolution: appeal** | The footer saying how and before whom the resolution can be appealed. |
| **Resolution: signed by delegation** | When checked, the resolution says **Per delegació** and shows the name of whoever resolved it instead of whoever holds the Director position. |

An empty text means the standard one is used. The standard appeal text names the competent body only in general terms: write the specific body once the centre has confirmed it. Write the texts in Catalan, the resolution's language.

1. Write the texts you want to customise and, if needed, check **Resolution: signed by delegation**.
2. Save.

Changes apply to resolutions issued from then on.

---

## Documentation request reasons

When the Head of Studies asks an applicant for more documentation, they pick a reason from a list. You maintain that list.

**Required role:** EMS administrator

Navigate to: **Academic management → Configuration → Convalidations → Documentation request reasons**

- **Name:** the text the applicant reads in the email and on the portal. Write it in each language with the language button next to the field.
- **Order:** drag the rows to sort them. The first one comes selected when documentation is requested, so put the most usual reason first (by default, **Missing official grade certificate from the previous centre**).
- To stop offering a reason without losing the requests that used it, archive it.

---

## Refusal reasons per subject

When the Head of Studies refuses to convalidate a module, they pick the reason from a list. You maintain that list.

**Required role:** EMS administrator

Navigate to: **Academic management → Configuration → Convalidations → Refusal reasons per subject**

- **Name:** the text the resolution and the portal show for the refused module. Write it in each language with the language button next to the field.
- **Order:** drag the rows to sort them. The first one comes selected when a module is refused, so put the most usual reason first (by default, **The contents are not equivalent**).
- To stop offering a reason without losing the requests that used it, archive it.

---

See [Convalidations](../head_of_studies/convalidations.md) for how requests are processed, and the [families' manual](../families/manual-convalidacions.md) for what students see.

---

[← Back to the index](index.md)
