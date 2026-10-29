[Català](../../ca/secretary/student-documents.md) | [Castellano](../../es/secretary/student-documents.md) | [English](student-documents.md)

---

# Reviewing student documents

This guide explains how to review the documents students and families submit — ID cards, medical cards, IBANs and supporting documents for bonifications/exemptions — and what happens when you approve, reject or reopen one.

---

## Contents

1. [Where to review documents](#where-to-review-documents)
2. [Adding a document the family sent by email](#adding-a-document-the-family-sent-by-email)
3. [Approving, rejecting, cancelling](#approving-rejecting-cancelling)
4. [What approving an IBAN does](#what-approving-an-iban-does)
5. [What approving a benefit document does](#what-approving-a-benefit-document-does)
6. [Notifications](#notifications)
7. [Downloading Google credentials](#downloading-google-credentials)

---

## Where to review documents

Go to **Academic Management > Student Documents**. The list opens showing only **Pending** submissions by default (remove the filter to see everything). This is the only screen where documents are reviewed. The list on the student's own record (**Documentation** section of the **Secretary** tab) shows their documents and is where you add new ones (see the next section).

![Student documents list filtered to Pending, with the approve (✓) and reject (✗) icons on each row](../../assets/secretary/documents-01-pendents.png)

## Adding a document the family sent by email

When a family can't upload a document from the portal and emails it to you instead (ID card, medical card, IBAN, proof of a bonification...), you can register it yourselves on the student's record:

1. Open the student's record and go to the **Secretary** tab.
2. In the **Documentation** section, click **Add a line**.
3. Choose the **Document type** and fill it in:
   - **Bank account (IBAN):** the IBAN, the account holder and, if needed, the expiry date.
   - **Bonification / Exemption:** the benefit type and the proof file.
   - **Any other type:** the file (the PDF or image you were sent) and, if needed, the expiry date.
4. Click **Save & Close** and save the student's record.

![Dialog to add a document from the student's record](../../assets/secretary/documents-03-afegir.png)

The document is **approved** straight away, since you have already checked it: it creates no review task and sends no email to the family. It has the same effects as approving it (an IBAN becomes the student's active bank account, a bonification is added to their benefits) and replaces the previously approved document of the same type. Once saved, its type, file and data can no longer be changed: to correct it, add a new one.

## Approving, rejecting, cancelling

- **Approve** (✓ from the list, or the form's **Actions** dropdown): marks the document as reviewed and applies its side effects (see below). If another document of the same type was already approved for this student, it is removed automatically — only the latest approved one is kept.
- **Reject** (✗ from the list, or the **Actions** dropdown): write the reason first (in the **Rejection reason** field) — a single click on Reject immediately closes the submission, there is no separate confirmation step.
- **Cancel submission**: in the form's **Actions** dropdown, when you need to withdraw a submission without marking it rejected (e.g. it was uploaded by mistake).
- **Reset to pending**: available on an approved/rejected document, in case a decision needs to be revisited — it reopens the review (a fresh task is assigned to the reviewers again).

![A pending IBAN document, with the Actions dropdown open (Approve, Reject, Cancel submission) and the Rejection reason field](../../assets/secretary/documents-02-revisio.png)

## What approving an IBAN does

Approving an IBAN document sets it as the student's active bank account: any other bank account they had is deactivated, and this one is marked as usable for direct-debit payments. If the exact same IBAN was already registered (inactive), it is reactivated with the updated account holder name instead of creating a duplicate.

You can only have **one pending** IBAN submission per student at a time — a second one is blocked until the first is approved, rejected or cancelled.

## What approving a benefit document does

Approving a benefit/exemption document creates the corresponding entry in the student's benefits (see [Managing student and family contacts](student-contacts.md#bonifications-and-exemptions)), replacing any previous benefit of the **same** type — a student can hold several different active benefits at once (e.g. large family **and** a scholarship), so approving one type never removes an unrelated one.

## Notifications

The student is notified by email when their document is approved or rejected. Reviewers (configured in *Academic Management > Configuration > Enrollment > Task Assignment*) get a to-do task instead of an email for each new pending submission — check your Activities for "Review document: ...".

## Downloading Google credentials

To download the Google credentials PDF of several students at once: in **Educational Community → Students**, list view, tick the students, open **Actions** and click **Download Google credentials**. A ZIP with one PDF per student is downloaded.

---

[← Back to Secretariat index](index.md)
