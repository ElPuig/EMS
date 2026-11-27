# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import models
from odoo.tools import format_date

# Session states whose grades the student sees (issue #878): published (claims period) and final.
PORTAL_GRADE_STATES = ("published", "final")


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _ems_grades_portal_url(self):
        return f"{self.get_base_url()}/my/calificaciones"

    def _ems_portal_grade_rounds(self):
        """The student's grades shown on the portal and in the non-official PDF (issue #878): one
        entry per round with a published or final session, newest first, each with its subjects
        (final grade, or the internal one as provisional while some outcome is pending) and their
        outcomes' scores.

        sudo: a portal user has no access to the grade models; the caller resolves the student
        (get_portal_student()), so it only ever reads that student's lines. Two searches in all."""
        self.ensure_one()
        subject_lines = self.env["ems.grade_subject_line"].sudo().search([
            ("student_id", "=", self.id),
            ("session_state", "in", PORTAL_GRADE_STATES),
        ])
        if not subject_lines:
            return []
        outcome_lines = self.env["ems.grade_outcome_line"].sudo().search([
            ("student_id", "=", self.id),
            ("grade_session_id", "in", subject_lines.grade_session_id.ids),
        ])
        outcomes_by_session = defaultdict(list)
        for line in outcome_lines.sorted(lambda line: line.outcome_id.acronym or ""):
            outcomes_by_session[line.grade_session_id.id].append({
                "acronym": line.outcome_id.acronym,
                "name": line.outcome_id.name,
                "score": line.score if line.is_scored else None,
                "provisional": line.is_provisional,
                # Passed in an earlier round of the same subject: carried over, not re-evaluated.
                "carried": line.is_locked,
            })

        labels = dict(self.env["ems.grade_session"]._fields["round"]._description_selection(self.env))
        rounds = defaultdict(list)
        for line in subject_lines.sorted(lambda line: (line.subject_id.code or "", line.id)):
            session = line.grade_session_id
            # A final grade only exists once every outcome is evaluated; until then the grids show
            # the internal grade as provisional, and so does the portal.
            score = line.final_score
            if line.is_convalidated:
                status = "convalidated"
            elif line.has_final:
                status = "pass" if line.final_score >= 5 else "fail"
            elif line.internal_is_scored:
                status, score = "provisional", line.internal_score
            else:
                status, score = "pending", None
            rounds[session.round].append({
                "code": line.subject_id.code,
                "name": line.subject_id.name,
                "score": score,
                "status": status,
                "outcomes": [] if line.is_convalidated else outcomes_by_session[session.id],
                "claim_from": session.claim_date_from,
                "claim_to": session.claim_date_to,
                "published": session.state == "published",
            })
        return [
            {"round": round_key, "label": labels.get(round_key, round_key), "subjects": rounds[round_key]}
            for round_key in sorted(rounds, reverse=True)
        ]


class EmsGradeSession(models.Model):
    _inherit = "ems.grade_session"

    def _ems_announce_publication(self):
        """Email every student of these sessions that their grades are in the portal (issue #878):
        one email per student and round, whatever the number of their subjects, to the student and
        whoever is kept informed about them (_ems_informed_recipients: the family while a minor).
        No grades in it, only the link and the claims period. Queued, not sent on the spot."""
        template = self.env.ref("ems.email_template_grades_published").sudo()
        labels_by_lang = {}
        lines = self.sudo().grade_subject_line_ids.filtered("student_id")
        sessions_by_student_round = defaultdict(lambda: self.browse())
        for line in lines:
            sessions_by_student_round[(line.student_id, line.grade_session_id.round)] |= line.grade_session_id
        for (student, round_key), sessions in sessions_by_student_round.items():
            claim_from = min(sessions.filtered("claim_date_from").mapped("claim_date_from"), default=None)
            claim_to = max(sessions.filtered("claim_date_to").mapped("claim_date_to"), default=None)
            for recipient in student._ems_informed_recipients().filtered("email"):
                lang = recipient.lang or student.lang or self.env.lang
                if lang not in labels_by_lang:
                    labels_by_lang[lang] = dict(self.with_context(lang=lang)._fields["round"]._description_selection(
                        self.with_context(lang=lang).env))
                template.with_context(
                    lang=lang,
                    ems_round_label=labels_by_lang[lang].get(round_key, round_key),
                    ems_claim_from=format_date(self.env, claim_from, lang_code=lang) if claim_from else "",
                    ems_claim_to=format_date(self.env, claim_to, lang_code=lang) if claim_to else "",
                ).send_mail(student.id, force_send=False, email_values={"email_to": recipient.email})
