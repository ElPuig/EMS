# -*- coding: utf-8 -*-

# commitment, the letter mobilities sign, and the EU Survey they answer, before them.
from . import commitment, eu_survey
# evaluation first: the models below inherit it (and call imports application, which imports plan_rating).
from . import (evaluation, call, application, interview, plan_rating, partner, resolution, offer, claim,
               mobility, self_assessment, project, grant, export)
from . import group_mobility
# document_review after group_mobility: it extends the documents of both kinds of mobility.
from . import document_review
from . import attachment
# electronic_signature after document_review: it signs the documents' signature lines through sign_oca.
from . import electronic_signature
