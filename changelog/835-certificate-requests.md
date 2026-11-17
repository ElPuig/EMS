# What's new

## Certificate requests, starting with the FCT certificate (issue #835):

- New Academic management > Certificates: requests for a certificate of the centre, each of a certificate type (`ems.certificate.type`) with its own approval circuit, configured by the administrator in Configuration > Certificates > Certificate types: ordered steps, each done by whoever holds a position (`ems.role`), which complete the data, issue the certificate or approve it. The administrator can do any step.
- EMS ships the FCT certificate (Formació en Centres de Treball, CFGM and CFGS): the VET coordinator completes the company's details (company, VAT number, period, hours, sBID agreement number), the Secretary issues it (number `CERT-<course>-<counter>`, from `ems.base.next_course_number`, given only on issuing) and the Director approves it ("Vist i plau"). The final PDF, in the centre language, carries both EMS stamps (`ems.report_validation_stamp`, as minutes do) and the pages of the FCT agreement appended (a PDF or photos, turned into pages), and is emailed to the applicant. Its footer names the ISO 9001 controlled document it is printed on ("PC3.02.01 Model de certificat (EMS) – Revisió: 17/11/2026"), as minutes do.
- Current students (or their family, under the convalidations' rule) request it from the portal (`/my/certificats`). Former students, who have no portal, get the same form by email (one who is not in EMS needs no contact: their full name and email open the request): the secretariat registers the request and presses Send form, which sends a link with an access token (`portal.mixin`); the same link answers requests for documentation and downloads the certificate, no login needed. The student's details are mandatory, the company's optional. The new-request form starts folded (as convalidations'), and each request's page shows the applicant what it holds: their details, the training as the centre completed it, the current step and the documentation attached.
- The applicant's emails (form, documentation requested, certificate issued, request rejected) use the card layout of the Google account emails, with a button that opens the request and says what to do there.
- A request is limited to the studies of its type's levels (FCT: CFGM and CFGS), and the portal suggests the courses EMS has for the school year of the training while taking any other one.
- Sending the form to an applicant whose mandatory details the secretariat already wrote also hands the request to its first step; the applicant may still complete or correct their details and documents from the link (portal requests too) until someone of the centre changes or acts on it.
- Every step can return the request to the previous one, ask the applicant for documentation, or reject it; the secretariat cancels or reopens. Each step is a quiet task for whoever holds its position (daily summary).
- Each certificate type can require documents ("Required attached documentation"): one line per document (FCT: the FCT agreement) saying who attaches it (the applicant and/or positions of the circuit; nobody ticked, anyone taking part) and whether its pages are added to the certificate. They must all be attached before the certificate is issued. Any request also takes optional "Other documentation", never added to the certificate.
- New contact type "Collaborating company", with its menu Educational Community > Collaborating companies and its VAT number on the form. The certificate links one, or creates it from what the applicant wrote.
- User manuals in Catalan, Spanish and English for the secretariat, the VET coordinator, the Director, students and families, and the administrator (certificate types), with screenshots.
- New security group VET coordinator (given by the "VET coordinator" position): Academic management > Certificates (and nothing else of that menu) and the collaborating companies.

# Internal changes

## Shared helpers for requests (issue #835):

- `res.partner._ems_convalidation_can_request` is now `_ems_can_file_requests_for`: convalidations and certificates share the rule of who files requests for a student.
- `ems.base.role_users(role)`: the users holding a position, extracted from `role_task_users`.
