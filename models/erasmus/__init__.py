# -*- coding: utf-8 -*-

# commitment, the letter mobilities sign, and the EU Survey they answer, before them.
from . import commitment, eu_survey
# payee before the mobilities: both kinds of payee inherit it (issue #764).
from . import payee
# evaluation first: the models below inherit it (and call imports application, which imports plan_rating).
from . import (evaluation, call, application, interview, plan_rating, partner, resolution, offer, claim,
               mobility, self_assessment, project, grant, export)
from . import group_mobility
# economy after group_mobility: it adds the economic figures to both kinds of mobility (issue #762).
from . import economy
# pocket_money after economy: the group participants' pocket money payments (issue #764).
from . import pocket_money
# document_review after group_mobility: it extends the documents of both kinds of mobility.
from . import document_review
from . import attachment
# electronic_signature after document_review: it signs the documents' signature lines through sign_oca.
from . import electronic_signature
from . import history, ir_http
from . import satisfaction, quality
# The backend screens of staff calls, after every model they extend.
from . import staff_backend, staff_wizards
