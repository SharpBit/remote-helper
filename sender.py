import ast
import asyncio
import sys
from zlib import compress
import random

import cv2
import numpy as np
import websockets
from mss import mss
from PyQt5.QtCore import QPoint, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QKeySequence, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow, QShortcut
from screeninfo import get_monitors

monitor = get_monitors()[0]
thread_event_loop = asyncio.new_event_loop()


class ScreenshareThread(QThread):
    draw_on_pixmap = pyqtSignal(tuple)
    erase = pyqtSignal(bool)

    async def share_screen(self):
        uri = "ws://10.0.0.17:8765"
        async with websockets.connect(uri) as websocket:
            with mss() as sct:
                while True:
                    # Capture the screen
                    print(f'here {random.randint(1, 2)}')
                    img = sct.grab(sct.monitors[0])
                    img_array = np.array(img)
                    img_array = np.flip(img_array[:, :, :3], 2)
                    img_resized = cv2.resize(img_array, (1280, 720), interpolation=cv2.INTER_CUBIC)
                    compressed_bytes = compress(img_resized.tobytes(), 9)

                    # Send shape, then bytes
                    await websocket.send(str(img_resized.shape))
                    await websocket.send(compressed_bytes)

    async def get_drawings(self):
        uri = "ws://10.0.0.17:8765"
        async with websockets.connect(uri) as websocket:
            while True:
                raw = await websocket.recv()
                if isinstance(raw, str):
                    data = ast.literal_eval(raw)
                    if isinstance(data, tuple) and len(data) == 2:
                        qpoints = [QPoint(*point) for point in data]
                        self.draw_on_pixmap.emit(tuple(qpoints))
                    elif isinstance(data, bool):
                        self.erase.emit(data)

    async def start_funcs(self, loop):
        f1 = loop.create_task(self.share_screen())
        f2 = loop.create_task(self.get_drawings())
        await asyncio.wait([f1, f2])

    def run(self):
        asyncio.set_event_loop(thread_event_loop)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.start_funcs(loop))


class Canvas(QMainWindow):

    def __init__(self):
        super().__init__()
        self.drawing = False
        self.last_point = QPoint()
        self.shortcut = QShortcut(QKeySequence("Ctrl+Shift+2"), self)
        self.shortcut.activated.connect(self.clear_screen)
        self.initUI()

    def initUI(self):
        self.setGeometry(0, 0, monitor.width, monitor.height)

        self.drawing_label = QLabel(self)
        self.drawing_label.setPixmap(QPixmap(monitor.width, monitor.height))
        self.drawing_label.pixmap().fill(Qt.transparent)

        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        th = ScreenshareThread(self)
        th.draw_on_pixmap.connect(self.draw_line)
        th.erase.connect(self.erase)
        th.start()

        self.showFullScreen()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.drawing_label.pixmap())

    @pyqtSlot(tuple)
    def draw_line(self, points):
        painter = QPainter(self.drawing_label.pixmap())
        painter.setPen(QPen(Qt.magenta, 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(*points)
        self.update()

    @pyqtSlot(bool)
    def erase(self, _):
        self.clear_screen()

    @pyqtSlot()
    def clear_screen(self):
        self.drawing_label.setPixmap(QPixmap(self.width(), self.height()))
        self.drawing_label.pixmap().fill(Qt.transparent)
        self.update()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = Canvas()

    sys.exit(app.exec_())
