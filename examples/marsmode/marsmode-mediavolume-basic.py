
# marsmode-mediavolume-basic

import binascii
import time
import random
from panda import Panda

p = Panda()

p.set_can_speed_kbps(0,500)
p.set_can_speed_kbps(1,500)
p.set_safety_mode(Panda.SAFETY_ALLOUTPUT)

while True:
    try:
        p.can_send(0x3c2,b"\x29\x55\x3f\x00\x00\x00\x00\x00",0) # vol down
        time.sleep(0.3)
        p.can_send(0x3c2,b"\x29\x55\x01\x00\x00\x00\x00\x00",0) # vol up
        time.sleep(4+random.uniform(0,4))
    except Exception as e:
        print("Exception caught ",e)
        time.sleep(1.2)

        # reset panda device or crash out for libusb
        p = Panda()

        p.set_can_speed_kbps(0,500)
        p.set_safety_mode(Panda.SAFETY_ALLOUTPUT)

