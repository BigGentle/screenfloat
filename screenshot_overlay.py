from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QPixmap
from PyQt6.QtWidgets import QWidget


class ScreenshotOverlay(QWidget):
    captured = pyqtSignal(QPixmap)
    cancelled = pyqtSignal()

    def __init__(self, fullscreen_pixmap: QPixmap):
        super().__init__()
        self._full = fullscreen_pixmap
        self._start = QPoint()
        self._end = QPoint()
        self._selecting = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setCursor(Qt.CursorShape.CrossCursor)

        # Cover all screens
        geo = QRect()
        from PyQt6.QtWidgets import QApplication
        for screen in QApplication.screens():
            geo = geo.united(screen.geometry())
        self.setGeometry(geo)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw fullscreen background
        p.drawPixmap(self.rect(), self._full)

        # Dark mask
        mask = QColor(0, 0, 0, 120)
        p.fillRect(self.rect(), mask)

        if self._selecting and self._start != self._end:
            r = self._selection_rect()
            # Cut out selection — show original image
            p.setCompositionMode(QPainter.CompositionMode.CompositionModeSourceOver)
            p.drawPixmap(r, self._full, r)

            # Selection border
            pen = QPen(QColor(255, 255, 255), 1, Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r)

        p.end()

    def _selection_rect(self):
        return QRect(self._start, self._end).normalized()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.pos()
            self._end = event.pos()
            self._selecting = True
            self.update()

    def mouseMoveEvent(self, event):
        if self._selecting:
            self._end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._selecting:
            self._end = event.pos()
            self._selecting = False
            r = self._selection_rect()
            if r.width() > 4 and r.height() > 4:
                cropped = self._full.copy(r)
                self.captured.emit(cropped)
            else:
                self.cancelled.emit()
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._selecting = False
            self.cancelled.emit()
            self.close()
