[Català](../../ca/secretary/authorizations.md) | [Castellano](../../es/secretary/authorizations.md) | [English](authorizations.md)

---

# Sending authorizations during the course

This guide explains how to create an authorization that comes up once the course has already started — a form published by the Departament d'Educació, an outing agreed in a tutoring meeting — send it to the students it concerns, and follow up their answers.

---

## Contents

1. [Creating the authorization form](#creating-the-authorization-form)
2. [Sending it to the students](#sending-it-to-the-students)
3. [What the family receives](#what-the-family-receives)
4. [Following up the answers](#following-up-the-answers)
5. [Answering on a family's behalf](#answering-on-a-familys-behalf)

---

## Creating the authorization form

Go to **Academic Management > Configuration > Authorization Forms** and click **New**.

![Authorization form](../../assets/secretary/authorizations-template-form.png)

Fill in:

- **Title**: what the student and the family will see in the list, e.g. *Museum visit (November)*.
- **Applies on**: choose **Sent during the course**. Authorizations you create this way are never attached to an enrollment; they only reach a student when you send them from the assistant described below. Leave **Enrollment process** for the forms that are part of the enrollment itself.
- **Mandatory to Respond**: mark it if the student must answer it.
- **Acceptance Only**: mark it if there is no "reject" option — the family can only accept.
- **Template Download URL**: a link to the paper form, if there is one.
- **Authorization Type**: pick *Image Rights*, *Scholar Trips*, *Health Data* or *Share with Family* to have the answer update the corresponding indicator on the student's record. Leave *Other / General* otherwise.
- **Applies to Levels** / **Applies to Studies**: leave both empty for a form that concerns everybody. If you fill in both, a student must match both to be offered it.

In the **Legal Text** tab, write the text the family will read before answering. You can use `{{student_name}}`, `{{academic_year}}` and `{{study_name}}`: each one is replaced by the student's own data.

In the **Data Fields** tab, add any extra data you need to collect on acceptance (e.g. *Emergency phone number*). Mark **Required when accepting** for the ones that cannot be left blank.

Save.

## Sending it to the students

Go to **Academic Management > Enrollment > Send Authorizations**, or select the students in a list and use **Actions > Send authorizations**.

![Send authorizations assistant](../../assets/secretary/authorizations-send-wizard.png)

Fill in:

- **Authorizations to send**: one or more forms. They all go out in the same email.
- **Academic Year**: the year the authorization belongs to.
- **Send to**: how the students are chosen.
  - **Selected students**: the ones you picked in the list, or the ones you add by hand here.
  - **Groups / studies / levels**: every student enrolled this year in the groups, studies or levels you choose.
  - **Each template's own scope**: every enrolled student matching the levels and studies set on the form itself.
- **Send notification email**: leave it on to email the students. Turn it off to have the authorization appear on the portal without an email.

**Recipients (preview)** lists who is about to be written to, which address it goes to, and a note for anyone who needs your attention: *Already requested* for a student who already has that form (they are skipped), *No family contact found* or *Recipient without email* for a student nobody can be written to.

Click **Send**. The summary tells you how many authorizations were sent, how many emails were queued and how many students were skipped.

You can send the same form again later to new students: the ones who already have it are never asked twice, and an answer already given is never reset.

To send the form you are looking at without leaving it, use the **Send to Students** button in the header of the authorization form itself.

## What the family receives

One email per student, listing every authorization sent in that batch and linking to the portal. Adult students are written to directly; for a student under 18 it is the family contacts who receive it.

The student and the family find the authorizations in **Enrollment and authorizations** on the portal, whether or not the enrollment for that year is already confirmed.

## Following up the answers

Go to **Academic Management > Enrollment > Authorizations**. The list opens on the current academic year.

![Authorizations list](../../assets/secretary/authorizations-list.png)

- Filter by **Pending**, **Accepted** or **Rejected**, and by **Sent during the course** or **From an enrollment**.
- Group by authorization, student, academic year or status.
- Search by group to see one class at a time.
- The **Document** column holds the response certificate, generated automatically when the family answers from the portal. Click it to download the PDF, which carries the legal text, the data provided, the date and who answered.

## Answering on a family's behalf

When a family hands in the signed form on paper, open the authorization from that same list, set the **Status**, and attach the scanned document in the **Document** field. The status cannot be changed without attaching it.

---

[← Back to the secretariat index](index.md)
