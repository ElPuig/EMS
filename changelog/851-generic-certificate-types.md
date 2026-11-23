# Changes

## Generic certificate types (details and text configured per type):

- Certificate requests were meant to be generic, but everything a certificate says was FCT's and fixed in the code: a "Kind" selection (only FCT), the request's columns (company, VAT number, period, hours, school year, agreement number), the checks of the coordinator's step, the portal form and the sentence printed on the PDF. A second type could only reuse FCT's fields and text (issue #851, follow-up of #835).
- Each certificate type now defines, from Academic management > Configuration > Certificates > Certificate types, its own **Certificate details** (label, key, data type: short or long text, number, date, yes/no, school year or collaborating company; whether the applicant is asked for it, mandatory or optional; and the step of the circuit that can't be done until it is filled in) and its **Certificate text**, translatable, where `{key}` prints a detail, `[...]` a part only printed when its details have a value, and a blank line starts a paragraph. The student's full name, identity document and study stay common to every type.
- The request keeps one line per detail of its type (new model `ems.certificate.value`), edited in the **Certificate details** tab, with the ones the current step still needs highlighted. The portal offers one form per type, each with its own details; the request's page shows them as the centre completed them.
- The "Kind" field is gone. FCT is now just a type defined as data (its details and text); the FCT labels "From"/"To" became "Start date"/"End date".
- Fixed: changing a draft request's type failed ("Record does not exist") when the new type required other documents.
- Odoo's `fields.Properties` was ruled out for the details: its labels can't be translated and its definitions can't say who fills a detail in or by which step.

# Internal changes

## Migration for the certificate types:

- `migrations/18.0.0.51.0/post-migrate.py` writes the FCT type's text (en/ca/es; the type is noupdate) and gives every existing request the lines of its type's details. The old FCT columns are dropped by Odoo; their values are not moved, since no request had been processed in production yet (the feature hadn't been announced). The folder is named after the next feature version: rename or fold it when preparing the release.

## Example certificate text on the type form:

- Under the help of "Certificate text", the type form shows an example for a grades certificate (details school_year and average, the average as an optional part), translated to Catalan and Spanish.

## Close audit of the certificate types:

- New test for the details' values: a wrong number or date from the portal form is left out, each data type is displayed as such, what the current step requires is highlighted until filled in, and a closed request's details can't be changed.
- The request's document lines and detail lines are kept in step with its type by one shared helper (they were two copies of the same code), creating the missing lines in one batch.
- The manual screenshots of the certificate list, the certificate details, the type form and the three portal screens were regenerated; their test now pins the FCT type as seeded, whatever other types the database has.
