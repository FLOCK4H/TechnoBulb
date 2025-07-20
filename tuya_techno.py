import tinytuya
import time
import colorsys
import random
import threading

from credentials import IP_DEVICE_1, DEVICE_ID_1, LOCAL_KEY_1, IP_DEVICE_2, DEVICE_ID_2, LOCAL_KEY_2

def encode_color(hex_str):
    if len(hex_str) != 7 or hex_str[0] != '#':
        return None
    try:
        r, g, b = [int(hex_str[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    except ValueError:
        return None

    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    hue = int(h * 360)
    sat = int(s * 1000)
    val = int(v * 1000)
    return f"{hue:04x}{sat:04x}{val:04x}"

BLACK = encode_color("#000000")

class HandleBulb:
    def __init__(self, *args, **kwargs):
        self.stop_flag = True

        self.device1 = kwargs.get('device', tinytuya.OutletDevice(
            dev_id=DEVICE_ID_1,
            address=IP_DEVICE_1,
            local_key=LOCAL_KEY_1,
            version=3.3
        ))

        self.device2 = kwargs.get('device', tinytuya.OutletDevice(
            dev_id=DEVICE_ID_2,
            address=IP_DEVICE_2,
            local_key=LOCAL_KEY_2,
            version=3.5
        ))

    def start(self, **kwargs):
        self.main_thread = threading.Thread(target=self.run_loop, kwargs=kwargs)
        self.main_thread.start()

    def random_color(self):
        def set_red():
            red = encode_color("#ff0000")
            self.device1.set_value(24, red)
            self.device2.set_value(24, red)

        def set_green():
            green = encode_color("#00ff00")
            self.device1.set_value(24, green)
            self.device2.set_value(24, green)

        def set_blue():
            blue = encode_color("#0044ff")
            self.device1.set_value(24, blue)
            self.device2.set_value(24, blue)

        def set_yellow():
            yellow = encode_color("#ffff00")
            self.device1.set_value(24, yellow)
            self.device2.set_value(24, yellow)

        def set_purple():
            purple = encode_color("#800080")
            self.device1.set_value(24, purple)
            self.device2.set_value(24, purple)

        def set_white():
            # For many bulbs: DPS 21 => 'white'
            self.device1.set_value(21, 'white')
            self.device2.set_value(21, 'white')

        self.device1.set_value(21, 'colour')
        self.device2.set_value(21, 'colour')
        color_functions = [set_red, set_green, set_blue, set_yellow, set_purple, set_white]
        random.choice(color_functions)()

    def run_loop(self, **kwargs):
        try:
            length = 5
            self.stop_flag = False
            self.random_color()

            for _ in range(1, length):
                # switch off
                self.device1.set_value(20, False)
                self.device2.set_value(20, False)
                time.sleep(0.15)
                # switch on
                self.device1.set_value(20, True)
                self.device2.set_value(20, True)
                time.sleep(0.15)

            self.device1.set_value(21, 'colour')
            self.device2.set_value(21, 'colour')
        except Exception as e:
            print(f"HandleBulb run_loop error: {e}")

    def stop(self):
        self.stop_flag = True
