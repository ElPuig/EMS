[Català](../../ca/admin/certificate-types.md) | [Castellano](../../es/admin/certificate-types.md) | [English](certificate-types.md)

---

# Certificate types and approval circuits

Configure which certificates students may request, which documentation they require and who does each step until they are issued.

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
- **Key** — how the certificate text writes it, between braces: lowercase letters, digits and `_` (for example, `hours`). It can't be `name`, `document` or `study`, which are already taken.
- **Data type** — **Short text**, **Long text**, **Number**, **Date**, **Yes/No**, **School year** (the form suggests the courses EMS has) or **Collaborating company** (the applicant writes the name and VAT number, and the centre links the company).
- **Applicant** — **Required**: the form asks for it and it must be filled in to submit the request; **Optional**: the form asks for it; **Not asked**: only the centre fills it in.
- **Required before** — the step of the circuit that can't be done until it is filled in (nor any later one). Leave it empty if the circuit never requires it. To choose a step, save the circuit first.
- **Hint** (optional column) — a short text the applicant reads under the detail.

In a request, the staff fill in these details in the **Certificate details** tab. The ones still empty that the current step requires are highlighted.

---

## Certificate text

**Certificate text** is what the certificate says after "CERTIFIES:". The heading with the secretary's name, the closing, the place, the date and the stamps are the same for every certificate.

- Write a detail's key between braces where its value goes: `{hours}`. Under the text you can see every key you can use. A **Collaborating company** detail also has its VAT number, `{company_vat}` if its key is `company`.
- A part between square brackets is only printed when every detail inside it has a value: `[, with VAT number {company_vat}]`.
- A blank line starts a new paragraph.

The text is translated like the other names: write it in each language with the language selector of the field. EMS doesn't let you save a text that uses a key the type doesn't have.

FCT's text, for example:

> That {name}, with identity document {document}, a student of {study}, did {hours} hours of workplace training (FCT) in the school year {school_year} at the company {company}[, with VAT number {company_vat}], from {start} to {end}.

---

## Required attached documentation

Tick **Required attached documentation** and add a line per document that must be attached before the certificate is issued:

- **Document** — the document's name (for example, *FCT agreement*).
- **Applicant** — the applicant may attach it from the portal or from the link.
- **Positions** — whoever holds these positions may attach it (only positions of the circuit can be chosen).
- **Add to the certificate** — the document's pages are appended to the certificate's PDF.

With neither **Applicant** nor any position ticked, anyone taking part may attach it. The administrator always can.

Besides the required documents, any request takes optional **Other documentation**, which is not added to the certificate.

---

## Approval circuit

Each line is a step, in order:

- **Name** — what whoever does the step sees.
- **Post** — whoever holds it gets the task and does the step. Positions and their holders are configured in [Positions](teacher-roles.md).
- **Action**:
  - **Complete the data** — completes the information and hands the request on.
  - **Issue the certificate** — gives the certificate its number and the issuing stamp.
  - **Approve** — adds the approval stamp.

The circuit must have exactly one **Issue the certificate** step, and the **Approve** steps go after it. The last step generates the PDF and sends it to the applicant.

The administrator may do any step of any request.
