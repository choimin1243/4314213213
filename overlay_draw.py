import sys
import os
from datetime import datetime

from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import (
    QColor, QPainter, QPen, QPixmap, QGuiApplication, QKeySequence, QFont
)
from PySide6.QtWidgets import QApplication, QWidget


def timestamp_name(prefix="capture", ext="png"):
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"


class Overlay(QWidget):
    def __init__(self):
        super().__init__()

        # Window: full-screen transparent overlay, always on top
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool  # taskbar에 덜 보이게
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setMouseTracking(True)

        self.screen = QGuiApplication.primaryScreen()
        geo = self.screen.geometry()
        self.setGeometry(geo)

        # Canvas to draw with alpha
        self.canvas = QPixmap(self.size())
        self.canvas.fill(Qt.transparent)

        self.drawing = False
        self.last_pos = QPoint()

        # Pen / eraser state
        self.mode = "pen"  # "pen" or "eraser"
        self.pen_color = QColor(255, 0, 0, 220)  # red-ish with alpha
        self.pen_width = 6
        self.eraser_width = 30

        self.show_help = True

    # ---------- Drawing ----------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drawing = True
            self.last_pos = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if not self.drawing:
            return
        cur = event.position().toPoint()
        self._draw_line(self.last_pos, cur)
        self.last_pos = cur
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drawing = False

    def _draw_line(self, p1: QPoint, p2: QPoint):
        painter = QPainter(self.canvas)
        painter.setRenderHint(QPainter.Antialiasing, True)

        if self.mode == "eraser":
            # "지우개": alpha를 0으로 지우기 (투명으로 클리어)
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            pen = QPen(Qt.transparent, self.eraser_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
        else:
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            pen = QPen(self.pen_color, self.pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)

        painter.drawLine(p1, p2)
        painter.end()

    # ---------- Capture ----------
    def capture_with_annotations(self):
        # 1) Hide overlay so underlying screen can be captured cleanly
        self.hide()
        QGuiApplication.processEvents()

        screen = QGuiApplication.primaryScreen()
        raw = screen.grabWindow(0)  # whole desktop (primary screen)

        # 2) Composite: screen + our canvas (annotations)
        # handle HiDPI: align sizes via devicePixelRatio
        dpr = raw.devicePixelRatio()
        raw_size = raw.size()  # in device-independent pixels
        # canvas is in widget coords (same as raw_size usually), scale if needed
        canvas_scaled = self.canvas
        if canvas_scaled.size() != raw_size:
            canvas_scaled = self.canvas.scaled(raw_size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

        result = QPixmap(raw_size)
        result.fill(Qt.transparent)

        painter = QPainter(result)
        painter.drawPixmap(0, 0, raw)
        painter.drawPixmap(0, 0, canvas_scaled)
        painter.end()

        # 3) Save
        out_dir = os.path.join(os.getcwd(), "captures")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, timestamp_name("capture_annotated", "png"))
        ok = result.save(out_path, "PNG")

        # 4) Show overlay again
        self.show()
        QGuiApplication.processEvents()

        return ok, out_path

    def clear_canvas(self):
        self.canvas.fill(Qt.transparent)
        self.update()

    # ---------- UI ----------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # draw the current canvas on the transparent window
        painter.drawPixmap(0, 0, self.canvas)

        # help HUD
        if self.show_help:
            self._draw_help(painter)

        painter.end()

    def _draw_help(self, painter: QPainter):
        pad = 14
        lines = [
            "투명 오버레이 펜/지우개/캡쳐",
            "",
            "좌클릭 드래그: 그리기",
            "P: 펜 모드",
            "E: 지우개 모드",
            "[: 펜 굵기 -    ]: 펜 굵기 +",
            "-: 지우개 굵기 -  =: 지우개 굵기 +",
            "C: 전체 지우기",
            "S: (화면+주석) 캡쳐 저장 (captures/)",
            "H: 도움말 토글",
            "Esc: 종료",
            "",
            f"MODE: {self.mode} | Pen={self.pen_width}px | Eraser={self.eraser_width}px",
        ]

        font = QFont("Malgun Gothic", 10)
        painter.setFont(font)

        # estimate box size
        line_h = 18
        box_w = 520
        box_h = pad * 2 + line_h * len(lines)

        # semi-transparent background box
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 140))
        painter.drawRoundedRect(QRect(20, 20, box_w, box_h), 12, 12)

        painter.setPen(QColor(255, 255, 255, 230))
        x = 20 + pad
        y = 20 + pad + line_h
        for t in lines:
            painter.drawText(x, y, t)
            y += line_h

    def keyPressEvent(self, event):
        k = event.key()

        if k == Qt.Key_Escape:
            QApplication.quit()
            return

        if k == Qt.Key_P:
            self.mode = "pen"
            self.update()
            return

        if k == Qt.Key_E:
            self.mode = "eraser"
            self.update()
            return

        if k == Qt.Key_C:
            self.clear_canvas()
            return

        if k == Qt.Key_H:
            self.show_help = not self.show_help
            self.update()
            return

        if k == Qt.Key_S:
            ok, path = self.capture_with_annotations()
            # 캡쳐 성공/실패는 HUD에 따로 표시하지 않고, 폴더에 저장만.
            # 필요하면 여기서 print로 콘솔 로그를 남길 수 있음.
            return

        # Pen width adjust: [ and ]
        if k == Qt.Key_BracketLeft:
            self.pen_width = max(1, self.pen_width - 1)
            self.update()
            return
        if k == Qt.Key_BracketRight:
            self.pen_width = min(50, self.pen_width + 1)
            self.update()
            return

        # Eraser width adjust: - and =
        if k == Qt.Key_Minus:
            self.eraser_width = max(5, self.eraser_width - 5)
            self.update()
            return
        if k == Qt.Key_Equal:
            self.eraser_width = min(200, self.eraser_width + 5)
            self.update()
            return


def main():
    app = QApplication(sys.argv)
    w = Overlay()
    w.showFullScreen()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
