# watchdog.py
import pytuya
import time
import sys
import os
from scapy.all import ARP, Ether, srp
import psutil
import socket
import ctypes  # Import ctypes for MessageBox
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import  *

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

        # Set up a QTimer
        self.auto_close_timer = QTimer(self)  # Parent the QTimer to the message box
        self.auto_close_timer.setInterval(5000)  # Set the interval to 5000 milliseconds (5 seconds)
        self.auto_close_timer.setSingleShot(True)  # Ensure that the timer only triggers once
        self.auto_close_timer.timeout.connect(self.accept)  # Connect the timer's timeout signal to the accept slot, which closes the dialog
        self.auto_close_timer.start()  # Start the timer

def get_ip_from_mac(target_mac):
    ip_range = "192.168.0.1/24"
    ans, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(pdst=ip_range), timeout=2, verbose=False)
    
    for _, rcv in ans:
        if rcv[Ether].src == target_mac:
            return rcv[ARP].psrc

target_mac = "d8:1f:12:55:e5:80"  # Replace with your device's MAC address
ip_address = get_ip_from_mac(target_mac)
pc_address = "00:e0:4c:4d:1b:82"
pc_ip_address = get_ip_from_mac(pc_address)
print(ip_address)

def show_custom_message(title, message):
    # Ensure that the QApplication instance exists
    app = QApplication.instance() or QApplication(sys.argv)
    msg_box = CustomMessageBox(title, message)
    msg_box.exec()
    # Cleanup the QApplication instance to avoid any interference with the main loop
    app.exit()

# Constants for socket communication
HOST = str(pc_ip_address)
PORT = 5000

DEVICE_ID = 'bffba33e9f0dfeae8fqx2e'
LOCAL_KEY = 'Z`47TN]M{$3G%~^{'


class Watchdog:
    def __init__(self, device_id, ip_address, local_key):
        self.device = pytuya.OutletDevice(device_id, ip_address, local_key)
        self.device.set_version(3.3)
        self.main_app_pid = None
        self.bulb_state = False

    def show_popup(self, title, message):
        # Invoke the function to show the custom message box
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
        while True:
            time.sleep(10)
            self.main_app_pid = self.read_main_app_pid('techno_bulb.pid')
            self.state_helper()
            if self.main_app_pid is None or not self.is_main_app_running(self.main_app_pid):
                if self.bulb_state == True:
                    self.show_popup("Watchdog Alert", "Main app is not running. Shutting the bulb.")

                    print("Main app is not running.")
                    try:
                        self.device.set_status("white", 21)
                        time.sleep(2)
                        self.device.set_status(False, 20)
                        time.sleep(1)
                        sys.exit()
                    except Exception as e:
                        print(str(e))
            else:
                print("Hello, the app is running, any needs?")

    def state_helper(self, **kwargs):
        try:
            self.dataDict = self.device.status()
            print(self.dataDict)
            if self.dataDict['dps']:
                if self.dataDict['dps']['20'] == True:
                    self.bulb_state = True
                    print('true')
                elif self.dataDict['dps']['20'] == False:
                    self.bulb_state = False
                    print('false')

        except ValueError as e:
            pass
        except TypeError as e:
            pass
        except Exception as e:
            print(f"Exception in watchdog: {e}")


if __name__ == "__main__":
    watchdog = Watchdog(DEVICE_ID, ip_address, LOCAL_KEY)
    watchdog.start()