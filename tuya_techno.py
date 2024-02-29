import pytuya
from scapy.all import ARP, Ether, srp
import time
import colorsys
import random
import threading

def encode_color(hex):
    if len(hex) != 7 or hex[0] != '#':
        return None
    try:
        r, g, b = [int(hex[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    except ValueError:
        return None

    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return f"{int(h * 360):04x}{(int(s * 100) * 1000) // 100:04x}{(int(v * 100) * 1000) // 100:04x}"

def get_ip_from_mac(target_mac, timeout=2, retry_delay=5, max_attempts=None):
    ip_range = "192.168.0.1/24"  # Adjust the IP range as needed
    attempts = 0

    while max_attempts is None or attempts < max_attempts:
        ans, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(pdst=ip_range), timeout=timeout, verbose=False)
        
        for _, rcv in ans:
            if rcv[Ether].src == target_mac:
                return rcv[ARP].psrc
        
        time.sleep(retry_delay)  # Wait before retrying
        attempts += 1
        print("Couldn't find the bulb!")

    return None  # Return None if the MAC address wasn't found after all attempts

target_mac = "d8:1f:12:55:e5:80"

DEVICE_ID = 'bffba33e9f0dfeae8fqx2e'
LOCAL_KEY = 'Z`47TN]M{$3G%~^{'
BLACK = encode_color("#000000")

class HandleBulb:
    def __init__(self, *args, **kwargs):
        self.device = kwargs.get('device', pytuya.OutletDevice(DEVICE_ID, get_ip_from_mac(target_mac), LOCAL_KEY))
        self.stop_flag = True
        self.device.set_version(3.3)

    def start(self, **kwargs):
        self.main_thread = threading.Thread(target=self.run_loop)
        self.main_thread.start()

    def random_color(self):
        def set_red():
            red = encode_color("#ff0000")
            self.device.set_status(red, 24)

        def set_green():
            green = encode_color("#00ff00")
            self.device.set_status(green, 24)

        def set_blue():
            blue = encode_color("#0044ff")
            self.device.set_status(blue, 24)

        def set_yellow():
            yellow = encode_color("#ffff00")
            self.device.set_status(yellow, 24)

        def set_purple():
            purple = encode_color("#800080")
            self.device.set_status(purple, 24)

        def set_white():
            self.device.set_status('white', 21)

        self.device.set_status('colour', 21)
        color_functions = [set_red, set_green, set_blue, set_yellow, set_purple, set_white]
        random.choice(color_functions)()



    def run_loop(self, **kwargs):
        try:
            self.length = kwargs.get('q', 16)
            self.stop_flag = False
            self.random_color()

            for _ in range(3, self.length):
                self.device.set_status(False, 20)
                time.sleep(0.05)
                self.device.set_status(True, 20)
                time.sleep(0.05)
        
            self.device.set_status('colour', 21)
        except Exception as e:
            print(e)


    def stop(self):
        self.stop_flag = True

    