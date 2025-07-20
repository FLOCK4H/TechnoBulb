import os
from queue import Queue, Empty
import traceback
import time
import soundcard as sc
import numpy as np
import threading
from threading import Thread
import colorsys
import sys
from random import randint
import subprocess
import ctypes

# CHANGED: Use tinytuya instead of pytuya
import tinytuya  

from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

# your custom modules
from tuya_techno import HandleBulb
from credentials import DEVICE_ID_1, LOCAL_KEY_1, IP_DEVICE_1, DEVICE_ID_2, LOCAL_KEY_2, IP_DEVICE_2
import warnings

warnings.filterwarnings("ignore")

pause_event = threading.Event()
pause_event.set()

ip_address_1 = IP_DEVICE_1
ip_address_2 = IP_DEVICE_2

def write_pid_to_file(pid_file):
    with open(pid_file, 'w') as file:
        file.write(str(os.getpid()))

class TuyaCommandDispatcher:
    def __init__(self, device, cooldown=0.15):
        self.device = device
        self.cooldown = cooldown
        self.command_queue = Queue()
        self.last_sent_time = 0.0
        self.lock = threading.Lock()
        self.worker_thread = Thread(target=self._process_commands, daemon=True)
        self.worker_thread.start()

    def _process_commands(self):
        while True:
            try:
                dps, value = self.command_queue.get(timeout=1)
                now = time.time()

                with self.lock:
                    if now - self.last_sent_time >= self.cooldown:
                        try:
                            self.device.set_value(dps, value)
                            self.last_sent_time = now
                        except Exception as e:
                            print(f"[Dispatcher] set_value({dps}, {value}) failed: {e}")
                    else:
                        pass

            except Empty:
                continue

    def queue(self, dps, value):
        self.command_queue.put((dps, value))

class AlertWindow(QDialog):
    def __init__(self, msg):
        super(AlertWindow, self).__init__()
        self.setWindowTitle("Poprawnie Znaleziono Adresy IP!")
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

def encode_color(hex_str, brightness=1.0):
    """Convert #RRGGBB into a TinyTuya HSV string (hex)."""
    if len(hex_str) != 7 or hex_str[0] != '#':
        return None
    try:
        r, g, b = [int(hex_str[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    except ValueError:
        return None

    h, s, _ = colorsys.rgb_to_hsv(r, g, b)
    v = max(0.05, min(brightness, 1.0))  # clamp between 0.05–1.0

    hue = int(h * 360)
    sat = int(s * 1000)
    val = int(v * 1000)

    return f"{hue:04x}{sat:04x}{val:04x}"


class AudioThread(QThread):
    def __init__(self, m_app, device_1, device_2, color_map, magnitude_threshold=0.4):
        super().__init__()
        self.m_app = m_app
        self.device_1 = device_1  # this is a tinytuya device object
        self.device_2 = device_2  # this is a tinytuya device object
        self.dispatcher1 = TuyaCommandDispatcher(self.device_1, cooldown=0.225)
        self.dispatcher2 = TuyaCommandDispatcher(self.device_2, cooldown=0.325)
        self.color_map = color_map
        self.magnitude_threshold = magnitude_threshold
        self.current_color = '#FFFFFF'
        self.helper = HandleBulb()
        self.bulb_addr = AlertWindow(f"""
            Adres IP Żarówki 1: '{ip_address_1}'
            Adres IP Żarówki 2: '{ip_address_2}'
            ————————————————
            Device ID 1: '{DEVICE_ID_1}'
            Local Key 1: '{LOCAL_KEY_1}' 
            Device ID 2: '{DEVICE_ID_2}'
            Local Key 2: '{LOCAL_KEY_2}' 
        """)
        self.bulb_addr.exec()

    def strobe(self):
        try:
            self.helper.start(q=randint(8, 26))
        except Exception as e:
            print(f"Exception in strobe: {e}")

    def run(self):
        SAMPLE_RATE = 48000
        CHUNK_SIZE = int(SAMPLE_RATE / 40)

        self.strobe()
        # Switch device to 'colour' mode => DPS 21 = 'colour'
        # (or set_value(21, 'colour'))
        try:
            self.dispatcher1.queue(21, 'colour')
            self.dispatcher2.queue(21, 'colour')
        except Exception as e:
            print(f"set colour mode failed: {e}")

        speaker_name = str(sc.default_speaker().name)
        with sc.get_microphone(id=speaker_name, include_loopback=True).recorder(samplerate=SAMPLE_RATE) as mic:
            while True:
                if not pause_event.is_set():
                    print("Paused")
                    time.sleep(1)
                    # switch to white mode
                    self.dispatcher1.queue(21, 'white')
                    self.dispatcher2.queue(21, 'white')

                pause_event.wait()

                data = mic.record(numframes=CHUNK_SIZE)
                freq_data = np.fft.fft(data[:, 0])
                freq = np.fft.fftfreq(len(freq_data), 1 / SAMPLE_RATE)
                magnitude = np.abs(freq_data)

                mask = (freq >= 800) & (freq < 25000)
                max_magnitude = np.nanmax(magnitude[mask])

                if max_magnitude == 0:
                    hexi_color = encode_color('#000000')
                    if hexi_color:
                        try:
                            self.dispatcher1.queue(24, hexi_color)  # DPS 24 is color hex
                            self.dispatcher2.queue(24, hexi_color)  # DPS 24 is color hex
                        except Exception as e:
                            print(f"Exception in AudioThread: {e}")

                if 90 < max_magnitude < 100:
                    self.strobe()
                    time.sleep(2)
                    try:
                        self.dispatcher1.queue(21, 'colour')
                        self.dispatcher2.queue(21, 'colour')
                    except Exception as e:
                        print(str(e))

                if np.isnan(max_magnitude) or (max_magnitude < self.magnitude_threshold):
                    continue

                # pick color from color_map
                color_index = int(
                    max_magnitude / (np.max(magnitude)) * (len(self.color_map) - 1)
                )
                color_qcol = self.color_map[color_index]
                hex_color = color_qcol.name()  # e.g. "#RRGGBB"
                encoded_color = encode_color(hex_color, brightness=1.0)  # HHHHSSSSVVVV

                try:
                    if encoded_color and encoded_color != self.current_color:
                        # set DPS 24 => color
                        self.dispatcher1.queue(24, encoded_color)
                        self.dispatcher2.queue(24, encoded_color)
                        self.current_color = encoded_color
                except Exception as e:
                    print(f"Error setting color: {e}")


def interpolate_color(start_color, end_color, fraction):
    return QColor.fromRgbF(
        start_color.redF() + (end_color.redF() - start_color.redF()) * fraction,
        start_color.greenF() + (end_color.greenF() - start_color.greenF()) * fraction,
        start_color.blueF() + (end_color.blueF() - start_color.blueF()) * fraction
    )

def generate_color_gradient(start_color, end_color, num_colors):
    return [
        interpolate_color(start_color, end_color, i / float(num_colors - 1))
        for i in range(num_colors)
    ]

def generate_color_map(num_colors):
    segment_size = num_colors // 5

    # Segment 1: Red to Yellow
    seg1 = generate_color_gradient(QColor.fromHsvF(0, 1, 1),
                                   QColor.fromHsvF(1/6, 1, 1), segment_size)
    # Segment 2: Green to Blue
    seg2 = generate_color_gradient(QColor.fromHsvF(1/3, 1, 1),
                                   QColor.fromHsvF(2/3, 1, 1), segment_size)
    # Segment 3: Pink to Red
    seg3 = generate_color_gradient(QColor.fromHsvF(5/6, 1, 1),
                                   QColor.fromHsvF(0, 1, 1), segment_size)
    # Segment 4: repeat green-blue
    seg4 = seg2.copy()
    seg5 = seg3.copy()

    full_map = seg1 + seg2 + seg3 + seg4 + seg5
    if len(full_map) < num_colors:
        full_map.extend(full_map[-1:] * (num_colors - len(full_map)))
    return full_map

data_queue = Queue()


class InvisibleMainWindow(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        screen_geom = QApplication.primaryScreen().geometry()
        self.nx, self.ny = screen_geom.x(), screen_geom.y()
        self.nw, self.nh = screen_geom.width(), screen_geom.height()

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
        super().__init__(parent, *args, **kwargs)
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.buffer = None
        self.parent = parent
        self.setGeometry(QRect(QPoint(0, 0), QSize(256, 256)))
        self.add_button()
        rButton = RotaryButton(self)
        rButton.show()

    def add_button(self):
        mini_icon = QIcon()
        mini_icon.addPixmap(QPixmap(os.path.abspath("imgs/minimize.svg")))
        if not os.path.exists(os.path.abspath("imgs/minimize.svg")):
            print(f"File not found. Current CWD: {os.getcwd()}")
            return
        self.minimize = QPushButton(self)
        self.minimize.setStyleSheet("background: transparent;")
        self.minimize.setIcon(mini_icon)
        self.minimize.setIconSize(QSize(32, 20))
        self.minimize.setFixedSize(43, 33)
        self.minimize.clicked.connect(lambda: self.parent.showMinimized())
        self.minimize.move(self.width() - 45, 0)
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
        self.setGeometry(QRect(QPoint(parent.width() // 2 - 128, parent.height() // 2 - 128), QSize(256, 256)))
        self.setStyleSheet("background: transparent;")


class TechnoController:
    def __init__(self):
        # CHANGED: create a TinyTuya.OutletDevice
        self.device_1 = tinytuya.OutletDevice(
            dev_id=DEVICE_ID_1,
            address=ip_address_1,
            local_key=LOCAL_KEY_1,
            version=3.3
        )
        self.device_2 = tinytuya.OutletDevice(
            dev_id=DEVICE_ID_2,
            address=ip_address_2,
            local_key=LOCAL_KEY_2,
            version=3.5
        )
        self.bulb_state = False
        # optionally keep TCP socket open
        self.device_1.set_socketPersistent(True)
        self.device_2.set_socketPersistent(True)

        # read status now
        self.bulb_status()
        num_colors = 100 * 4
        self.color_map = generate_color_map(num_colors)
        self.bulb_color = 'colour'

        self.user32 = ctypes.windll.user32

    def set_strobe(self):
        try:
            # There's no direct 'strobe' in TinyTuya for a bulb; you'd do:
            # self.device.set_value(21, 'strobe') if your device recognized that
            self.device_1.set_value(21, 'strobe')
            self.device_2.set_value(21, 'strobe')
        except Exception as e:
            print(f"Strobe error: {e}")

    def cPopUp(self, title, text, **kwargs):
        parm = kwargs.get('parm', 0)
        return self.user32.MessageBoxW(0, title, text, parm)

    def get_bulb_color(self):
        # check self.dataDict for DPS 21
        if '21' in self.dataDict['dps']:
            mode = self.dataDict['dps']['21']
            if mode == 'white':
                self.bulb_color = 'white'
            elif mode == 'colour':
                self.bulb_color = 'colour'
            else:
                self.bulb_color = mode
                self.cPopUp('Alert! Bulb state changed!',
                            f"Bulb not in mode `colour` or `white`, but: {self.bulb_color}",
                            parm=0 | 0x30)

    def verify_bulb_color(self):
        try:
            if self.bulb_color != 'colour' and pause_event.is_set():
                self.device_1.set_value(21, 'colour')
                self.device_2.set_value(21, 'colour')
        except Exception as e:
            print(f"Exception in verify_bulb_color: {e}")

    def bulb_status(self):
        self.worker = BulbStatusWorker(self.device_1, self.device_2)
        self.worker.status_ready.connect(self._handle_status)
        self.worker.start()

    def _handle_status(self, resp1, resp2):
        if "Error" in resp1 or "Error" in resp2:
            print(f"Status error: {resp1} {resp2}")
            return
        self.dataDict = resp1  # Only store device_1's status for now
        print("Device1 status:", resp1)
        print("Device2 status:", resp2)
        self.get_bulb_color()
        self.verify_bulb_color()
        dps = resp1.get("dps", {})
        if "20" in dps:
            self.bulb_state = dps["20"] is True

    def bulb_handler(self, **kwargs):
        try:
            self.bulb_status()
            for device in [self.device_1, self.device_2]:
                if (not self.bulb_state) or (self.bulb_color == 'white' and pause_event.is_set()):
                    device.set_value(20, True)
                    device.set_value(21, 'colour')
                else:
                    print("Bulb handler resting, or it's already on colour mode.")
        except Exception as e:
            print(f"Exception in bulb_handler: {e}")

    def start_techno(self, m_app):
        self.timer2 = QTimer()
        self.timer2.timeout.connect(self.bulb_handler)
        self.timer2.start(30000)

        self.audio_thread = AudioThread(m_app, self.device_1, self.device_2, self.color_map)
        self.audio_thread.start()

class BulbStatusWorker(QThread):
    status_ready = Signal(dict, dict)

    def __init__(self, device_1, device_2):
        super().__init__()
        self.device_1 = device_1
        self.device_2 = device_2

    def run(self):
        try:
            resp1 = self.device_1.status()
            resp2 = self.device_2.status()
            self.status_ready.emit(resp1, resp2)
        except Exception as e:
            print(f"[BulbStatusWorker] Exception: {e}")

def main():
    pid_file = 'techno_bulb.pid'
    write_pid_to_file(pid_file)

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

if __name__ == "__main__":
    main()