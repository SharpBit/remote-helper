import ast
import asyncio
import sys
from zlib import decompress
import random

import numpy as np
import websockets
from PyQt5.QtCore import QPoint, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QImage, QKeySequence, QPainter, QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow, QShortcut
from screeninfo import get_monitors

monitor = get_monitors()[0]
thread_event_loop = asyncio.new_event_loop()


class Thread(QThread):
    change_pixmap = pyqtSignal(QImage)

    async def receive_screen(self):
        uri = "ws://10.0.0.17:8765"
        async with websockets.connect(uri) as websocket:
            while True:
                raw = await websocket.recv()
                if isinstance(raw, str):
                    shape = ast.literal_eval(raw)
                    if not isinstance(shape, tuple) or len(shape) < 3:  # ignore the drawing points
                        continue
                else:  # ignore the bytes
                    continue

                compressed_bytes = await websocket.recv()

                while not isinstance(compressed_bytes, bytes):
                    print(f'here {random.randint(1, 2)}')
                    compressed_bytes = await websocket.recv()

                flat_img_array = np.frombuffer(decompress(compressed_bytes), dtype=np.uint8)
                rgb_image = flat_img_array.reshape(shape)

                h, w, ch = rgb_image.shape
                bytes_per_lines = ch * w
                image = QImage(rgb_image.data, w, h, bytes_per_lines, QImage.Format_RGB888)
                self.change_pixmap.emit(image)

    def run(self):
        asyncio.set_event_loop(thread_event_loop)
        asyncio.get_event_loop().run_until_complete(self.receive_screen())


class Canvas(QMainWindow):
    def __init__(self):
        super().__init__()
        self.drawing = False
        self.last_point = QPoint()
        self.shortcut = QShortcut(QKeySequence("Ctrl+Shift+2"), self)
        self.shortcut.activated.connect(self.clear_screen)

        self.initUI()

    @pyqtSlot(QImage)
    def set_image(self, image):
        # modify so it takes the image received from the socket
        scaled_img = image.scaled(self.width(), self.height(), Qt.KeepAspectRatio)
        self.video_label.setPixmap(QPixmap.fromImage(scaled_img))

    def initUI(self):
        self.setGeometry(QApplication.desktop().availableGeometry())

        self.video_label = QLabel(self)
        self.video_label.resize(self.width(), self.height())

        self.drawing_label = QLabel(self.video_label)
        self.drawing_label.setPixmap(QPixmap(self.width(), self.height()))
        self.drawing_label.pixmap().fill(Qt.transparent)

        th = Thread(self)
        th.change_pixmap.connect(self.set_image)
        th.start()

        self.showMaximized()

    def resizeEvent(self, event):
        pixmap = self.drawing_label.pixmap()
        self.drawing_label.setPixmap(pixmap.scaled(self.width(), self.height()))
        self.drawing_label.resize(self.width(), self.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.drawing_label.pixmap())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drawing = True
            self.last_point = event.pos()

    async def send_websocket(self, *points, erase=False):
        uri = "ws://10.0.0.17:8765"
        async with websockets.connect(uri) as websocket:
            if points:
                await websocket.send(str(tuple(points)))
            elif erase:
                await websocket.send(str(erase))
            else:
                raise ValueError("neither points nor erase sent")

    def mouseMoveEvent(self, event):
        if event.buttons() and Qt.LeftButton and self.drawing:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.send_websocket(
                (self.last_point.x(), self.last_point.y()), (event.pos().x(), event.pos().y())
            ))
            self.last_point = event.pos()

    def mouseReleaseEvent(self, event):
        if event.button == Qt.LeftButton:
            self.drawing = False

    @pyqtSlot()
    def clear_screen(self):
        asyncio.get_event_loop().run_until_complete(self.send_websocket(erase=True))


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = Canvas()
    sys.exit(app.exec_())
