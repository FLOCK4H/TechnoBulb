# watchdog.py
import time
import sys
import os
import psutil
import tinytuya

from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from credentials import DEVICE_ID_1, LOCAL_KEY_1, IP_DEVICE_1, DEVICE_ID_2, LOCAL_KEY_2, IP_DEVICE_2

class CustomMessageBox(QMessageBox):
    def __init__(self, title, message):
        super().__init__()
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.setWindowTitle(title)
        self.setText(message)
        self.setStyleSheet("""
            QMessageBox { background-color: #b0c0f0; }
            QMessageBox QLabel { color: #123; }
            QPushButton { background-color: #81a1ff; border: 1px solid #507acc; }
            QPushButton:hover { background-color: #91a9f9; }
        """)
        self.setStandardButtons(QMessageBox.Ok)
        self.auto_close_timer = QTimer(self)
        self.auto_close_timer.setInterval(5000)
        self.auto_close_timer.setSingleShot(True)
        self.auto_close_timer.timeout.connect(self.accept)
        self.auto_close_timer.start()

def show_custom_message(title, message):
    app = QApplication.instance() or QApplication(sys.argv)
    msg_box = CustomMessageBox(title, message)
    msg_box.exec()
    app.exit()

class Watchdog:
    def __init__(self):
        # CHANGED to tinytuya
        self.device1 = tinytuya.OutletDevice(
            dev_id=DEVICE_ID_1,
            address=IP_DEVICE_1,
            local_key=LOCAL_KEY_1,
            version=3.3
        )
        self.device2 = tinytuya.OutletDevice(
            dev_id=DEVICE_ID_2,
            address=IP_DEVICE_2,
            local_key=LOCAL_KEY_2,
            version=3.5
        )
        # self.device.set_socketPersistent(True)
        self.main_app_pid = None
        self.bulb_state1 = False
        self.bulb_state2 = False

    def show_popup(self, title, message):
        show_custom_message(title, message)

    def read_main_app_pid(self, pid_file):
        try:
            with open(pid_file, 'r') as file:
                return int(file.read().strip())
        except FileNotFoundError:
            print("PID file not found. Main app may not be running.")
            return None

    def is_main_app_running(self, pid):
        return psutil.pid_exists(pid)

    def start(self):
        try:
            while True:
                time.sleep(10)
                self.main_app_pid = self.read_main_app_pid('techno_bulb.pid')
                self.state_helper()

                if self.main_app_pid is None or not self.is_main_app_running(self.main_app_pid):
                    if self.bulb_state1 or self.bulb_state2:
                        self.show_popup("Watchdog Alert", "Main app not running. Shutting the bulb.")
                        print("Main app is not running.")
                        try:
                            # set white mode
                            self.device1.set_value(21, 'white')
                            self.device2.set_value(21, 'white')
                            time.sleep(2)
                            # turn off
                            self.device1.set_value(20, False)
                            self.device2.set_value(20, False)
                            time.sleep(1)
                            sys.exit()
                        except Exception as e:
                            print(f"Watchdog shutting down error: {e}")
                            raise e
                else:
                    print("Hello, the app is running, any needs?")
        except Exception as e:
            print(e)
            exit(1)

    def state_helper(self):
        resp = self.device1.status()
        if "Error" in resp:
            print(f"Watchdog device.status() error: {resp}")
            return
        dps = resp.get('dps', {})
        print("Watchdog DPS:", dps)
        # check DPS 20
        if '20' in dps:
            self.bulb_state1 = bool(dps['20'])

        resp = self.device2.status()
        if "Error" in resp:
            print(f"Watchdog device.status() error: {resp}")
            return
        dps = resp.get('dps', {})
        print("Watchdog DPS:", dps)
        # check DPS 20
        if '20' in dps:
            self.bulb_state2 = bool(dps['20'])

if __name__ == "__main__":
    try:
        wd = Watchdog()
        wd.start()
    except Exception as e:
        print(e)
        exit(1)
