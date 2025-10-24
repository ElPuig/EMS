# -*- coding: utf-8 -*-
# import debugpy
# import os

# is_worker = bool(os.environ.get('ODOO_WORKER_TYPE'))
# if not is_worker:
#     debugpy.configure({"subProcess": True})

#     try:
#         debugpy.listen(("0.0.0.0", 5678))
#     except RuntimeError as e:
#         print(f"   ERROR running debugpy: {e}.")        

from . import controllers
from . import models