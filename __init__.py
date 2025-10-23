# -*- coding: utf-8 -*-
import debugpy
import socket

while True:
    port = 5678
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(('localhost', port)) == 0:
            port += 1            
        else:
            debugpy.listen(("0.0.0.0", port))
            break        

from . import controllers
from . import models