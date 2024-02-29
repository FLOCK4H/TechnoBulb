import os
from scapy.all import ARP, Ether, srp
from queue import Queue
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from PySide6.QtSvg import *
import time
import pytuya
import soundcard as sc
import numpy as np
import threading
import colorsys
import sys
from random import randint
from tuya_techno import HandleBulb
import subprocess
import ctypes

pause_event = threading.Event()
pause_event.set()

def get_ip_from_mac(target_mac, timeout=2, retry_delay=5, max_attempts=None):
    ip_range = "192.168.0.1/24" # Change this IP range if its not yours
    attempts = 0

    while max_attempts is None or attempts < max_attempts:
        ans, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(pdst=ip_range), timeout=timeout, verbose=False)
        
        for _, rcv in ans:
            if rcv[Ether].src == target_mac:
                return rcv[ARP].psrc
        
        time.sleep(retry_delay)  # wait before retrying
        attempts += 1
        print("Couldn't find the bulb!")

    return None  # return None if the MAC address wasn't found after all attempts

target_mac = "" # bulb mac
ip_address = get_ip_from_mac(target_mac)

pc_address = "" # pc mac
pc_ip_address = get_ip_from_mac(pc_address)


DEVICE_ID = '' # bulb ID
LOCAL_KEY = '' # resynced bulb's local key

def write_pid_to_file(pid_file):
    with open(pid_file, 'w') as file:
        file.write(str(os.getpid()))

class AlertWindow(QDialog):
    def __init__(self, msg):
        super(AlertWindow, self).__init__()
        self.setWindowTitle("IP Adresses found!")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setMinimumSize(300,150)
        self.setWindowIcon(QIcon("imgs/techno_bulb.png"))
        label = QLabel(msg, self)

        label.setAlignment(Qt.AlignLeft)
        label.move(0,0)
        self.auto_close_timer = QTimer(self) 
        self.auto_close_timer.setInterval(6000)
        self.auto_close_timer.setSingleShot(True)
        self.auto_close_timer.timeout.connect(self.accept) 
        self.auto_close_timer.start()

def encode_color(hex):
    if len(hex) != 7 or hex[0] != '#':
        return None
    try:
        r, g, b = [int(hex[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    except ValueError:
        return None

    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return f"{int(h * 360):04x}{(int(s * 100) * 1000) // 100:04x}{(int(v * 100) * 1000) // 100:04x}"

class AudioThread(QThread):
    def __init__(self, m_app, device, color_map, sleep_time=0.1, magnitude_threshold=0.4):
        super().__init__()
        self.m_app = m_app
        self.device = device
        self.color_map = color_map
        self.sleep_time = sleep_time
        self.magnitude_threshold = magnitude_threshold
        self.current_color = '#FFFFFF'
        self.helper = HandleBulb()
        self.bulb_addr = AlertWindow("""
            Bulb IP: '{}'
            Your IP: '{}'
            ⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
            Device ID: '{}'
            Local Key: '{}' 
        """.format(ip_address, pc_ip_address, DEVICE_ID, LOCAL_KEY))
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.bulb_addr.exec()

    def strobe(self):
        try:

            self.helper.start(q=randint(8, 26))
        except Exception as e:
            print(f"Exception in Verification of the Bulb's Color: {e}")

    def run(self):
        SAMPLE_RATE = 48000
        CHUNK_SIZE = int(SAMPLE_RATE / 40)
        next_run_time = time.time()

        self.strobe()
        time.sleep(2)
        try:
            self.device.set_status('colour', 21)
        except Exception as e:
            print(str(e))

        with sc.get_microphone(id=str(sc.default_speaker().name), include_loopback=True).recorder(samplerate=SAMPLE_RATE) as mic:
            global pause_event
            while True:
                pause_event.wait()

                current_time = time.time()
                if current_time < next_run_time:
                    continue

                next_run_time = current_time + self.sleep_time
                
                data = mic.record(numframes=CHUNK_SIZE)
                freq_data = np.fft.fft(data[:, 0])
                freq = np.fft.fftfreq(len(freq_data), 1 / SAMPLE_RATE)
                magnitude = np.abs(freq_data)
                

                mask = (freq >= 800) & (freq < 20000) # lower frequencies are too aggressive
                max_magnitude = np.nanmax(magnitude[mask])

                if max_magnitude == 0:
                    hexi_color = encode_color('#000000')
                    try:
                        self.device.set_status(hexi_color, 24)
                    except Exception as e:
                        print(f"Exception in AudioThread: {e}")

                if max_magnitude > 74 and max_magnitude < 100:
                    self.strobe()
                    time.sleep(2)
                    try:
                        self.device.set_status('colour', 21)
                    except Exception as e:
                        print(str(e))

                if np.isnan(max_magnitude) or (max_magnitude) < self.magnitude_threshold:
                    continue

                color_index = int(max_magnitude / (np.max(magnitude)) * (len(self.color_map) - 1))
                color = self.color_map[color_index]
                hex_color = color.name()
                encoded_color = encode_color(hex_color)
                try:
                    if encoded_color != self.current_color:
                        self.device.set_status(encoded_color, 24)
                        self.current_color = encoded_color
                        
                except Exception as e:
                    print(str(e))


def interpolate_color(start_color, end_color, fraction):
    """Interpolate between two QColor objects by a fraction."""
    return QColor.fromRgbF(
        start_color.redF()   + (end_color.redF()   - start_color.redF())   * fraction,
        start_color.greenF() + (end_color.greenF() - start_color.greenF()) * fraction,
        start_color.blueF()  + (end_color.blueF()  - start_color.blueF())  * fraction
    )

def generate_color_gradient(start_color, end_color, num_colors):
    """gradient between two QColor objects"""
    return [interpolate_color(start_color, end_color, i / float(num_colors - 1)) for i in range(num_colors)]

def generate_color_map(num_colors):
    segment_size = num_colors // 5

    # Segment 1: Red to Yellow
    segment_1 = generate_color_gradient(QColor.fromHsvF(0, 1, 1), QColor.fromHsvF(1/6, 1, 1), segment_size)

    # Segment 2: Green to Blue
    segment_2 = generate_color_gradient(QColor.fromHsvF(1/3, 1, 1), QColor.fromHsvF(2/3, 1, 1), segment_size)

    # Segment 3: Pink to Red
    segment_3 = generate_color_gradient(QColor.fromHsvF(5/6, 1, 1), QColor.fromHsvF(0, 1, 1), segment_size)

    # Segment 4: Green to Blue (replicated)
    segment_4 = segment_2.copy()

    # Segment 5: Pink to Red (replicated)
    segment_5 = segment_3.copy()

    # Combining all the segments into one color map
    full_color_map = segment_1 + segment_2 + segment_3 + segment_4 + segment_5

    # Handle rounding errors
    if len(full_color_map) < num_colors:
        full_color_map.extend(full_color_map[-1:] * (num_colors - len(full_color_map)))

    return full_color_map

#  ___________ ___________ _________ ___________ ___________
# [red-yellow][green-blue][pink-red][red-yellow][green-blue]
# ‾‾‾‾‾‾‾‾‾‾‾ ‾‾‾‾‾‾‾‾‾‾‾ ‾‾‾‾‾‾‾‾‾ ‾‾‾‾‾‾‾‾‾‾‾ ‾‾‾‾‾‾‾‾‾‾‾

def generate_frequency_bands(min_freq, max_freq, num_bands):
    return np.linspace(min_freq, max_freq, num_bands + 1)

data_queue = Queue()

class InvisibleMainWindow(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.nx, self.ny, self.nw, self.nh = QApplication.primaryScreen().geometry().x(), QApplication.primaryScreen().geometry().y(), QApplication.primaryScreen().geometry().width(), QApplication.primaryScreen().geometry().height()
        self.init_me()
        self.show()
        self.techno_main = TechnoMain(self)
        self.techno_main.show()
        self.paused = False

    def init_me(self):
        self.resize(312, 312)
        self.move(self.nw / 2 - 156, self.nh / 2 - 156)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def keyPressEvent(self, event):
        global pause_event 
        if event.key() == Qt.Key_P:
            if pause_event.is_set():
                pause_event.clear() 
            else:
                pause_event.set()
            print("Toggled pause state.")
            event.accept()

class TechnoMain(QWidget):
    def __init__(self, parent=None, *args, **kwargs):
        super(TechnoMain, self).__init__(parent, *args, **kwargs)
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.buffer = None
        self.parent = parent
        self.setGeometry(QRect(QPoint(0,0), QSize(256,256)))
        self.add_button()
        rButton = RotaryButton(self)
        rButton.show()

    def add_button(self):
        mini_icon = QIcon()
        mini_icon.addPixmap(QPixmap(os.path.abspath("imgs/minimize.svg")))
        if not os.path.exists(os.path.abspath("imgs/minimize.svg")):
            print(f"File not found")
            print(os.getcwd())
            return
        self.minimize = QPushButton(self)
        self.minimize.setStyleSheet("background: transparent;")
        self.minimize.setIcon(mini_icon)
        self.minimize.setIconSize(QSize(32, 20))
        self.minimize.setFixedSize(43, 33)
        self.minimize.clicked.connect(lambda: self.parent.showMinimized())
        self.minimize.move(self.width() - 45,0)
        self.minimize.show()

    def paintEvent(self, event):
        if not self.buffer or self.buffer.size() != self.size():
            self.buffer = QPixmap(self.size())
            self.buffer.fill(Qt.transparent)
            painter = QPainter(self.buffer)
            self.drawContent(painter)
            painter.end()

        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.buffer)

    def drawContent(self, painter):
        gradient = QLinearGradient(self.rect().topLeft(), self.rect().bottomRight())
        gradient.setColorAt(0, QColor(12, 12, 31, 205))
        gradient.setColorAt(1, QColor(12, 12, 31, 225))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 16, 16)

    def mousePressEvent(self, event):
        self._old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        delta = QPoint(event.globalPosition().toPoint() - self._old_pos)
        self.parent.move(self.parent.x() + delta.x(), self.parent.y() + delta.y())
        self._old_pos = event.globalPosition().toPoint()

class RotaryButton(QPushButton):
    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.techtext = QIcon()
        self.techtext.addPixmap("imgs/techtext.svg")
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setIconSize(QSize(220, 220))
        self.setIcon(self.techtext)
        self.setGeometry(QRect(QPoint(parent.width() / 2 - 128, parent.height() / 2 - 128), QSize(256, 256)))
        self.setStyleSheet(""" 
            background: transparent;
        """)

class TechnoController:
    def __init__(self):
        self.device = pytuya.OutletDevice(DEVICE_ID, ip_address, LOCAL_KEY)
        self.device.set_version(3.3)
        self.bulb_state = False
        self.bulb_status()
        num_colors = 100 * 4
        self.color_map = generate_color_map(num_colors)
        self.bulb_color = 'colour'

        self.user32 = ctypes.windll.user32

    def set_strobe(self):
        try:
            self.device.set_status('strobe', 21)
        except Exception as e:
            print(str(e))

    def cPopUp(self, title, text, **kwargs):
        parm = kwargs.get('parm', 0)
        return self.user32.MessageBoxW(0, title, text, parm)

    def get_bulb_color(self):
        if self.dataDict['dps']['21'] == 'white':
            self.bulb_color = 'white'
        elif self.dataDict['dps']['21'] == 'colour':
            self.bulb_color = 'colour'
        else:
            current_mode = self.dataDict['dps']['21']
            self.bulb_color = current_mode
            self.cPopUp('Alert! Bulb state changed!', f"The bulb is not in mode `colour` or `white` but: {self.bulb_color}", parm=0 | 0x30)

    def verify_bulb_color(self):
        try:
            if self.bulb_color != 'colour':
                self.device.set_status('colour', 21)
        except Exception as e:
            print(f"Exception in Verification of the Bulb's Color: {e}")

    def bulb_status(self):
        try:
            self.dataDict = self.device.status()
            if self.dataDict != None:
                print(self.dataDict)
                self.get_bulb_color()
                self.verify_bulb_color()
                if self.dataDict.get('dps'):
                    if self.dataDict['dps']:
                        if self.dataDict['dps']['20'] == True:
                            self.bulb_state = True
                        elif self.dataDict['dps']['20'] == False:
                            self.bulb_state = False
                        else:
                            return
                        
        except Exception as e:
            print(f"Exception raised: {e}")
            
    def bulb_handler(self, **kwargs):
        try:
            self.bulb_status()
            if self.bulb_state == False or self.bulb_color == 'white':
                self.device.set_status(True, 20)
                self.device.set_status('colour', 21)
            elif self.bulb_state == True:
                print("Bulb handler resting...")
        except Exception as e:
            print(f"F those exceptions blud: {e}")

    def start_techno(self, m_app): 
        self.timer2 = QTimer()
        self.timer2.timeout.connect(self.bulb_handler)
        self.timer2.start(7500)

        self.audio_thread = AudioThread(m_app, self.device, self.color_map)
        self.audio_thread.start()

def main():
    pid_file = 'techno_bulb.pid'
    write_pid_to_file(pid_file)
    
    # Start the watchdog process detached from the parent process
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    watchdog_process = subprocess.Popen(
        [sys.executable, 'watchdog.py'],
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )

    app = QApplication([])
    techno_controller = TechnoController()
    m_app = InvisibleMainWindow()
    techno_controller.start_techno(m_app)
    retval = app.exec()

    sys.exit(retval)

main()



    