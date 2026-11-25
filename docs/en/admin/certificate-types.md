[Català](../../ca/admin/certificate-types.md) | [Castellano](../../es/admin/certificate-types.md) | [English](certificate-types.md)

---

# Certificate types and approval circuits

Configure which certificates students may request, which documents they need and who does each step until they are issued.

**Required role:** Administrator.

---

## Access

Navigate to: **Academic management → Configuration → Certificates → Certificate types**.

EMS includes the **FCT (Formació en Centres de Treball)** type. Your changes to it are kept when EMS is upgraded.

![The FCT certificate type](../../assets/admin/certificats-07-tipus.png)

---

## The type's fields

- **Levels that may request it** — current students of these levels may request it from the portal, and the request only accepts studies of these levels. Left empty, the type is not offered on the portal and its requests are only registered by the secretariat.
- **Description** — what the applicant reads above the form.

---

## Certificate details

Every certificate already has the student's **full name**, **identity document** and **study**. Under **Certificate details**, add a line for each other detail the certificate needs:

- **Detail** — its name, as the applicant and the staff read it (for example, *Hours*).
- **Key** — how the certificate text writes it, between braces: lowercase letters, digits and `_` (for example, `hours`). It can't be `name`, `document` or `study`, which are already taken. If you change it, the text is updated in every language.
- **Data type** — **Short text**, **Long text**, **Number** (it may have decimals, such as an average grade of 7.45), **Date**, **Yes/No**, **School year** (written as 2024-25 or 2024-2025, with consecutive years, and kept as 2024-25; the form suggests the courses EMS has) or **Collaborating company** (the applicant writes the name and VAT number, and the centre links the company).
- **Applicant** — **Required**: the form asks for it and it must be filled in to submit the request; **Optional**: the form asks for it; **Not asked**: only the centre fills it in.
- **Required before** — the step of the circuit that can't be done until it is filled in (nor any later one). Leave it empty if the circuit never requires it. To choose a step, save the circuit first.
- **Hint** — what to write and how, with an example (for example, *As YYYY-YY, e.g. 2024-25.*). The applicant reads it under the detail, and the staff next to it in the request.
- **Not before** (optional column, dates only) — another date of the type it cannot be earlier than: for FCT, the end date is not before the start date.

In a request, the staff fill in these details in the **Certificate details** tab. The ones still empty that the current step requires are highlighted.

---

## Certificate text

**Certificate text** is what the certificate says after "CERTIFIES:". The heading with the name and post of whoever issues it, the closing, the place, the date and the stamps are the same for every certificate.

- Write a detail's key between braces where its value goes: `{hours}`. Under the text you can see every key you can use. A **Collaborating company** detail also has its VAT number, `{company_vat}` if its key is `company`.
- A part between square brackets is only printed when every detail inside it has a value: `[, with VAT number {company_vat}]`.
- A blank line starts a new paragraph.

The text is translated like the other names: write it in each language with the language selector of the field. EMS doesn't let you save a text that uses a key the type doesn't have.

FCT's text, for example:

> That {name}, with identity document {document}, a student of {study}, did {hours} hours of workplace training (FCT) in the school year {school_year} at the company {company}[, with VAT number {company_vat}], from {start} to {end}.

---

## Documents

In **Documents**, add a line per document the requests of this type must have attached:

- **Document** — the document's name (for example, *FCT agreement*).
- **Applicant** — the applicant may attach it too, from the portal or from the link. Whoever takes part in the circuit always may.
- **Required before** — the step that cannot be done until the document is attached (nor any later one). Empty: it is optional. In the FCT type, the agreement is required before the certificate is issued.
- **Add to the certificate** — the document's pages are appended to the certificate's PDF.

Besides, any request takes **Other documentation**: each document attached there says whether it is added to the certificate.

---

## Approval circuit

Each line is a step, in order:

- **Name** — what whoever does the step sees.
- **Posts** — one or more positions. Whoever holds any of them gets the task and may do the step; once one of them does it, the others' task closes. Positions and their holders are configured in [Positions](teacher-roles.md).

To give a step to the secretariat's staff, add the **Secretary technician** position to it and assign that position to each of them. Whoever holds it also gets access to the secretariat. The FCT type's first step comes with it, together with the VET coordinator.
- **Action**:
  - **Complete the data** — completes the information and hands the request on.
  - **Issue the certificate** — gives the certificate its number and the issuing stamp.
  - **Approve** — adds the approval stamp.

The circuit must have exactly one **Issue the certificate** step, and the **Approve** steps go after it. The last step generates the PDF and sends it to the applicant.

The administrator may do any step of any request.

Whoever issued a certificate cannot do its **Approve** step, even holding that step's position or being the administrator.

Whoever holds the position of an **Approve** step may also **Attest** the request until the certificate is issued: an accrediting document (numbered `DACR`) signed by them only is generated, and the request closes. It is available in every type with an **Approve** step. The administrator may only do it holding that position.
