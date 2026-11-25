# What's new

## Certificates (the approver can attest with an accrediting document):

- The Director cannot issue certificates but can attest ("fer constar"). Until a certificate is issued, whoever holds the post of its approving step can now Attest the request instead of waiting for it: once every mandatory detail and document is in, EMS generates an accrediting document ("Document acreditatiu") with the same text after "FA CONSTAR:" instead of "CERTIFICA:", its own number series (DACR-2026-27-0001, so the CERT registry keeps no gaps) and a single signature, the attester's; it is emailed to the applicant with its own email and the request closes.
- The attester can preview it first (See the accrediting document draft). The request records which document it ended with (list column and a ribbon on the form), and the portal offers "Download the accrediting document".
- Available in every certificate type with an approving step; the administrator can only attest when holding that post.

# Changes

## Certificates (documents required by step, and other documentation can go into the certificate):

- A certificate type's documents are no longer switched on and off as a whole by "Required attached documentation": every request gets each document, and each one says the step it is required before, as the type's details do (empty: optional). Unticking that single switch also hid the documents to append, so certificates were being issued without their FCT agreement.
- Who attaches a document is no longer chosen by position: whoever takes part in the circuit always may, and "Applicant" says whether the applicant may too.
- Other documentation is now a list of documents, each with its own name, files and "Add to the certificate" choice, appended after the type's documents; those the applicant uploads from the portal arrive unticked.
- A migration keeps existing types working: documents that were required become required before issuing (the FCT agreement always), the old "anyone" documents let the applicant attach them, open requests get their documents and the existing other documentation becomes one document per file.

## Certificates (whoever issues a certificate never approves it):

- The person who issued a certificate is left out of its approving step, whatever posts they hold and the administrator included: no task, not in Pending for me, no Approve button, and the server refuses it.
