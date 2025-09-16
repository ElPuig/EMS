# -*- coding: utf-8 -*-
import debugpy
debugpy.listen(("0.0.0.0", 5678))

from . import controllers
from . import models