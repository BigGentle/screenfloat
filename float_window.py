import base64
import re
from PyQt6.QtCore import Qt, QPoint, QEvent, QRectF, QBuffer, QByteArray
from PyQt6.QtGui import QPixmap, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QPlainTextEdit, QGraphicsView, QGraphicsScene,
    QSlider, QLineEdit, QLabel, QFileDialog,
    QApplication
)
from screenshot_overlay import ScreenshotOverlay


class FloatWindow(QMainWindow):
    """单个悬浮窗。可创建多个实例。"""

    def __init__(self, on_new_window=None, on_save=None, on_quit=None):
        super().__init__()
        self.on_new_window = on_new_window
        self._locked = False
        self._opacity = 1.0
        self._current_zoom = 100
        self._drag_pos = None
        self._resize_edge = None
        self._resize_start_geom = None
        self._resize_margin = 6

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setStyleSheet("background: #1a1a1a;")
        self.setMouseTracking(True)

        central = QWidget()
        self.setCentralWidget(central)
        self._layout = QVBoxLayout(central)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._build_toolbar()
        self._build_image_view()
        self._build_text_area()
        self._build_zoom_controls()
        self._build_opacity_controls()

        self.setMinimumSize(250, 200)
        self.resize(400, 300)

        if on_save:
            sc = QShortcut(QKeySequence("Ctrl+S"), self)
            sc.activated.connect(on_save)
        if on_quit:
            sc = QShortcut(QKeySequence("Ctrl+Q"), self)
            sc.activated.connect(on_quit)
        if on_new_window:
            sc = QShortcut(QKeySequence("Ctrl+N"), self)
            sc.activated.connect(on_new_window)

    # ── toolbar ──────────────────────────────────────────────

    def _build_toolbar(self):
        self._toolbar = QWidget()
        self._toolbar.setStyleSheet("background: #2d2d2d;")
        self._toolbar.setFixedHeight(34)
        layout = QHBoxLayout(self._toolbar)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)
        layout.addStretch()

        btn_style = """
            QPushButton {
                background: transparent; color: #e0e0e0;
                border: none; border-radius: 4px;
                font-size: 16px; min-width: 28px; min-height: 28px;
            }
            QPushButton:hover { background: #404040; }
        """

        self.btn_new = self._make_btn("+", btn_style, self._on_new)
        self.btn_open = self._make_btn("\U0001F4C2", btn_style, self._on_open_file)
        self.btn_screenshot = self._make_btn("\U0001F4F7", btn_style, self._on_screenshot)
        self.btn_lock = self._make_btn("\U0001F513", btn_style, self._on_toggle_lock)
        self.btn_min = self._make_btn("−", btn_style, self.showMinimized)
        self.btn_close = self._make_btn("×", btn_style, self.close)
        self.btn_close.setStyleSheet(btn_style + "QPushButton:hover { background: #e74c3c; }")

        for b in [self.btn_new, self.btn_open, self.btn_screenshot, self.btn_lock, self.btn_min, self.btn_close]:
            layout.addWidget(b)

        self._layout.addWidget(self._toolbar)

    def _make_btn(self, text, style, handler):
        btn = QPushButton(text)
        btn.setStyleSheet(style)
        btn.clicked.connect(handler)
        return btn

    # ── image view ───────────────────────────────────────────

    def _build_image_view(self):
        self._scene = QGraphicsScene()
        self._view = QGraphicsView(self._scene)
        self._view.setStyleSheet("background: #1a1a1a; border: none;")
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._view.setAcceptDrops(False)
        self._view.viewport().installEventFilter(self)
        self._layout.addWidget(self._view, 1)

    # ── text area ────────────────────────────────────────────

    def _build_text_area(self):
        self.text_area = QPlainTextEdit()
        self.text_area.setPlaceholderText("添加备注...")
        self.text_area.setFixedHeight(80)
        self.text_area.setStyleSheet("""
            QPlainTextEdit {
                background: #252525; color: #e0e0e0;
                border: none; border-top: 1px solid #333;
                padding: 8px 12px; font-size: 14px;
            }
            QPlainTextEdit:focus { background: #2a2a2a; }
        """)
        self._layout.addWidget(self.text_area)

    # ── zoom controls ────────────────────────────────────────

    def _build_zoom_controls(self):
        row = QWidget()
        row.setStyleSheet("background: #252525; border-top: 1px solid #333;")
        row.setFixedHeight(36)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(8)
        layout.addStretch()

        btn_style = """
            QPushButton {
                background: #333; color: #e0e0e0;
                border: none; border-radius: 4px;
                min-width: 28px; min-height: 28px;
            }
            QPushButton:hover { background: #444; }
        """

        zoom_out = QPushButton("−")
        zoom_out.setStyleSheet(btn_style)
        zoom_out.clicked.connect(lambda: self._zoom_by(-25))
        layout.addWidget(zoom_out)

        self.zoom_input = QLineEdit("100")
        self.zoom_input.setFixedWidth(50)
        self.zoom_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_input.setStyleSheet("""
            QLineEdit {
                background: #333; color: #e0e0e0;
                border: none; border-radius: 4px;
                font-size: 12px; padding: 4px;
            }
            QLineEdit:focus { background: #444; }
        """)
        self.zoom_input.returnPressed.connect(self._on_zoom_input)
        layout.addWidget(self.zoom_input)

        pct = QLabel("%")
        pct.setStyleSheet("color: #888; font-size: 12px; background: transparent;")
        layout.addWidget(pct)

        zoom_in = QPushButton("+")
        zoom_in.setStyleSheet(btn_style)
        zoom_in.clicked.connect(lambda: self._zoom_by(25))
        layout.addWidget(zoom_in)

        reset = QPushButton("重置")
        reset.setStyleSheet(btn_style)
        reset.clicked.connect(self._zoom_reset)
        layout.addWidget(reset)

        layout.addStretch()
        self._layout.addWidget(row)

    # ── opacity controls ─────────────────────────────────────

    def _build_opacity_controls(self):
        row = QWidget()
        row.setStyleSheet("background: #252525; border-top: 1px solid #333;")
        row.setFixedHeight(36)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(8)

        left = QLabel("透")
        left.setStyleSheet("color: #888; font-size: 12px; background: transparent;")
        layout.addWidget(left)

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(30, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.setFixedWidth(120)
        self.opacity_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #444; height: 6px; border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #e0e0e0; width: 14px; height: 14px;
                border-radius: 7px; margin: -4px 0;
            }
            QSlider::handle:horizontal:hover { background: #fff; }
        """)
        self.opacity_slider.valueChanged.connect(self._on_opacity_change)
        layout.addWidget(self.opacity_slider)

        right = QLabel("实")
        right.setStyleSheet("color: #888; font-size: 12px; background: transparent;")
        layout.addWidget(right)

        self.opacity_label = QLabel("100%")
        self.opacity_label.setStyleSheet("color: #888; font-size: 12px; background: transparent;")
        layout.addWidget(self.opacity_label)

        layout.addStretch()
        self._layout.addWidget(row)

    # ── toolbar actions ──────────────────────────────────────

    def _on_new(self):
        if self.on_new_window:
            self.on_new_window()

    def _on_open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp)"
        )
        if path:
            self._load_image_from_path(path)

    def _on_screenshot(self):
        self.hide()
        QApplication.processEvents()
        screen = QApplication.primaryScreen()
        full = screen.grabWindow(0)
        overlay = ScreenshotOverlay(full)
        overlay.captured.connect(self._on_screenshot_done)
        overlay.cancelled.connect(self.show)
        overlay.show()

    def _on_screenshot_done(self, pix):
        self.show()
        self._show_pixmap(pix)
        self._image_base64 = pix

    def _on_toggle_lock(self):
        self._locked = not self._locked
        self.btn_lock.setText("\U0001F512" if self._locked else "\U0001F513")

    # ── zoom ─────────────────────────────────────────────────

    def _zoom_by(self, delta):
        self._set_zoom(self._current_zoom + delta)

    def _zoom_reset(self):
        self._view.resetTransform()
        self._current_zoom = 100
        self.zoom_input.setText("100")
        self._fit_to_window()

    def _on_zoom_input(self):
        try:
            v = int(self.zoom_input.text())
            self._set_zoom(v)
        except ValueError:
            self.zoom_input.setText(str(self._current_zoom))

    def _set_zoom(self, percent):
        percent = max(25, min(300, percent))
        if self._current_zoom <= 0 or percent <= 0:
            return
        scale = percent / self._current_zoom
        self._view.scale(scale, scale)
        self._current_zoom = percent
        self.zoom_input.setText(str(percent))

    # ── opacity ──────────────────────────────────────────────

    def _on_opacity_change(self, value):
        self._opacity = value / 100
        self.opacity_label.setText(f"{value}%")
        self.setWindowOpacity(self._opacity)

    # ── image loading ────────────────────────────────────────

    def _load_image_from_path(self, path):
        if not path:
            return
        pix = QPixmap(path)
        if not pix.isNull():
            self._show_pixmap(pix)
            self._image_base64 = self._pixmap_to_base64(pix)

    def _show_pixmap(self, pix):
        self._view.setUpdatesEnabled(False)
        self._scene.clear()
        self._view.resetTransform()
        self._view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self._scene.addPixmap(pix)
        self._scene.setSceneRect(QRectF(pix.rect()))
        self._current_zoom = 100
        self.zoom_input.setText("100")
        self._view.setUpdatesEnabled(True)
        self._fit_to_window()
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def _fit_to_window(self):
        vr = self._view.viewport()
        if vr and vr.width() > 0 and vr.height() > 0:
            self._view.fitInView(
                self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
            )

    def _pixmap_to_base64(self, pix):
        buf = QBuffer()
        buf.open(QBuffer.OpenModeFlag.WriteOnly)
        pix.save(buf, "PNG")
        return "data:image/png;base64," + base64.b64encode(buf.data().data()).decode()

    def load_image_base64(self, data: str):
        if not data or data == "about:blank":
            return
        match = re.match(r"data:image/\w+;base64,(.+)", data)
        if not match:
            return
        try:
            raw = base64.b64decode(match.group(1))
            pix = QPixmap()
            pix.loadFromData(raw)
            if not pix.isNull():
                self._show_pixmap(pix)
                self._image_base64 = pix
        except Exception:
            pass

    # ── window move & resize ─────────────────────────────────

    def _in_toolbar(self, pos):
        return pos.y() <= self._toolbar.geometry().bottom()

    def _edge_hit(self, pos):
        r = self._resize_margin
        w, h = self.width(), self.height()
        x, y = pos.x(), pos.y()

        left = x < r
        right = x > w - r
        top = y < r
        bottom = y > h - r

        if left and top:
            return "top-left"
        if right and top:
            return "top-right"
        if left and bottom:
            return "bottom-left"
        if right and bottom:
            return "bottom-right"
        if left:
            return "left"
        if right:
            return "right"
        if top:
            return "top"
        if bottom:
            return "bottom"
        return None

    def _edge_cursor(self, edge):
        cursors = {
            "top-left": Qt.CursorShape.SizeFDiagCursor,
            "bottom-right": Qt.CursorShape.SizeFDiagCursor,
            "top-right": Qt.CursorShape.SizeBDiagCursor,
            "bottom-left": Qt.CursorShape.SizeBDiagCursor,
            "left": Qt.CursorShape.SizeHorCursor,
            "right": Qt.CursorShape.SizeHorCursor,
            "top": Qt.CursorShape.SizeVerCursor,
            "bottom": Qt.CursorShape.SizeVerCursor,
        }
        return cursors.get(edge, Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self._locked:
            super().mousePressEvent(event)
            return

        pos = event.position().toPoint()
        edge = self._edge_hit(pos)

        if edge:
            self._resize_edge = edge
            self._resize_start_geom = self.geometry()
            self._drag_start_global = event.globalPosition().toPoint()
        elif self._in_toolbar(pos):
            self._drag_pos = event.globalPosition().toPoint()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resize_edge is not None:
            self._do_resize(event.globalPosition().toPoint())
        elif self._drag_pos is not None:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.move(self.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()
        else:
            # Update cursor for edge hovering
            pos = event.position().toPoint()
            edge = self._edge_hit(pos)
            self.setCursor(self._edge_cursor(edge) if edge else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._resize_edge = None
        self._resize_start_geom = None
        super().mouseReleaseEvent(event)

    def _do_resize(self, global_pos):
        delta = global_pos - self._drag_start_global
        g = self._resize_start_geom
        edge = self._resize_edge

        new_x, new_y, new_w, new_h = g.x(), g.y(), g.width(), g.height()

        if "left" in edge:
            new_x = g.x() + delta.x()
            new_w = max(self.minimumWidth(), g.width() - delta.x())
        elif "right" in edge:
            new_w = max(self.minimumWidth(), g.width() + delta.x())

        if "top" in edge:
            new_y = g.y() + delta.y()
            new_h = max(self.minimumHeight(), g.height() - delta.y())
        elif "bottom" in edge:
            new_h = max(self.minimumHeight(), g.height() + delta.y())

        self.setGeometry(new_x, new_y, new_w, new_h)

    # ── event overrides ──────────────────────────────────────

    def eventFilter(self, obj, event):
        if obj is self._view.viewport() and event.type() == QEvent.Type.Wheel:
            delta = 10 if event.angleDelta().y() > 0 else -10
            self._zoom_by(delta)
            return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_V and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            pix = QApplication.clipboard().pixmap()
            if not pix.isNull():
                self._show_pixmap(pix)
                self._image_base64 = pix
                return
        super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                self._load_image_from_path(path)
                break

    # ── serialization ────────────────────────────────────────

    def to_dict(self):
        g = self.geometry()
        d = {
            "x": g.x(), "y": g.y(),
            "width": g.width(), "height": g.height(),
            "text": self.text_area.toPlainText(),
            "locked": self._locked,
            "opacity": self._opacity,
        }
        if hasattr(self, "_image_base64"):
            if isinstance(self._image_base64, str):
                d["imageData"] = self._image_base64
            else:
                d["imageData"] = self._pixmap_to_base64(self._image_base64)
        return d

    def apply_options(self, opts: dict):
        if "x" in opts and "y" in opts:
            self.move(opts["x"], opts["y"])
        if "width" in opts and "height" in opts:
            self.resize(opts["width"], opts["height"])
        if opts.get("text"):
            self.text_area.setPlainText(opts["text"])
        if opts.get("locked"):
            self._locked = True
            self.btn_lock.setText("\U0001F512")
        if opts.get("opacity"):
            self._opacity = opts["opacity"]
            self.setWindowOpacity(self._opacity)
            self.opacity_slider.setValue(int(self._opacity * 100))
            self.opacity_label.setText(f"{int(self._opacity * 100)}%")
        if opts.get("imageData"):
            self.load_image_base64(opts["imageData"])
