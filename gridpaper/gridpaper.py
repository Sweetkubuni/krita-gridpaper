"""Grid Paper Layer — adds a graph-paper grid as a new paint layer.

Standard grid sizes follow common printable graph paper:
imperial 1/4", 1/5", 1/8", 1/10" and metric 1 cm, 5 mm, 4 mm, 2 mm.
The pixel spacing is derived from the document resolution (DPI), so the
squares come out at true physical size when printed at 100%.
"""

from krita import Extension, Krita

try:
    from PyQt5.QtCore import QByteArray
    from PyQt5.QtGui import QColor, QImage, QPainter
    from PyQt5.QtWidgets import (
        QColorDialog,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QLabel,
        QMessageBox,
        QPushButton,
        QSpinBox,
        QVBoxLayout,
    )
except ImportError:  # Krita builds on Qt 6
    from PyQt6.QtCore import QByteArray
    from PyQt6.QtGui import QColor, QImage, QPainter
    from PyQt6.QtWidgets import (
        QColorDialog,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QLabel,
        QMessageBox,
        QPushButton,
        QSpinBox,
        QVBoxLayout,
    )

ARGB32 = QImage.Format.Format_ARGB32
COMP_SOURCE = QPainter.CompositionMode.CompositionMode_Source

MM_PER_INCH = 25.4

# (combo label, short name for the layer, square size in inches)
GRID_SIZES = [
    ("1/4 inch  (4 squares per inch)", "1/4 in", 1 / 4),
    ("1/5 inch  (5 squares per inch)", "1/5 in", 1 / 5),
    ("1/8 inch  (8 squares per inch)", "1/8 in", 1 / 8),
    ("1/10 inch (10 squares per inch)", "1/10 in", 1 / 10),
    ("1 cm (10 mm)", "1 cm", 10 / MM_PER_INCH),
    ("5 mm", "5 mm", 5 / MM_PER_INCH),
    ("4 mm", "4 mm", 4 / MM_PER_INCH),
    ("2 mm", "2 mm", 2 / MM_PER_INCH),
]

SETTINGS_GROUP = "gridpaper"


def render_grid(width, height, spacing, line_w, color, accent_every, accent_w, accent_color):
    """Draw the grid into a transparent ARGB32 image.

    Line positions are round(i * spacing) so fractional spacings (e.g. metric
    sizes at 300 DPI) stay drift-free across the canvas. Normal lines are drawn
    first and accent lines second, so accent lines stay unbroken at crossings.
    """
    img = QImage(width, height, ARGB32)
    img.fill(0)
    painter = QPainter(img)
    painter.setCompositionMode(COMP_SOURCE)

    def draw_lines(vertical, accent_pass):
        limit = width if vertical else height
        i = 0
        while True:
            pos = round(i * spacing)
            if pos > limit:
                break
            is_accent = accent_every > 0 and i % accent_every == 0
            if is_accent == accent_pass:
                w = accent_w if is_accent else line_w
                c = accent_color if is_accent else color
                start = pos - w // 2
                if vertical:
                    painter.fillRect(start, 0, w, height, c)
                else:
                    painter.fillRect(0, start, width, w, c)
            i += 1

    for accent_pass in (False, True):
        draw_lines(True, accent_pass)
        draw_lines(False, accent_pass)
    painter.end()
    return img


class GridDialog(QDialog):
    def __init__(self, resolution, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Graph Paper Grid Layer")
        self.resolution = resolution
        app = Krita.instance()

        self.size_combo = QComboBox()
        for label, _, _ in GRID_SIZES:
            self.size_combo.addItem(label)
        self.size_combo.setCurrentIndex(
            int(app.readSetting(SETTINGS_GROUP, "sizeIndex", "0") or 0) % len(GRID_SIZES)
        )

        self.px_label = QLabel()

        self.line_width = QSpinBox()
        self.line_width.setRange(1, 50)
        self.line_width.setSuffix(" px")
        self.line_width.setValue(int(app.readSetting(SETTINGS_GROUP, "lineWidth", "1") or 1))

        self.line_color = QColor(app.readSetting(SETTINGS_GROUP, "lineColor", "#ff9fc5e8") or "#ff9fc5e8")
        self.color_btn = QPushButton()
        self.color_btn.clicked.connect(lambda: self._pick_color(False))

        self.accent_every = QSpinBox()
        self.accent_every.setRange(0, 50)
        self.accent_every.setSpecialValueText("Off")
        self.accent_every.setValue(int(app.readSetting(SETTINGS_GROUP, "accentEvery", "0") or 0))
        self.accent_every.valueChanged.connect(self._update_enabled)

        self.accent_width = QSpinBox()
        self.accent_width.setRange(1, 50)
        self.accent_width.setSuffix(" px")
        self.accent_width.setValue(int(app.readSetting(SETTINGS_GROUP, "accentWidth", "2") or 2))

        self.accent_color = QColor(app.readSetting(SETTINGS_GROUP, "accentColor", "#ff6fa8dc") or "#ff6fa8dc")
        self.accent_color_btn = QPushButton()
        self.accent_color_btn.clicked.connect(lambda: self._pick_color(True))

        form = QFormLayout()
        form.addRow("Grid size:", self.size_combo)
        form.addRow("", self.px_label)
        form.addRow("Line width:", self.line_width)
        form.addRow("Line color:", self.color_btn)
        form.addRow("Bold line every:", self.accent_every)
        form.addRow("Bold line width:", self.accent_width)
        form.addRow("Bold line color:", self.accent_color_btn)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self.size_combo.currentIndexChanged.connect(self._update_px_label)
        self._update_px_label()
        self._update_enabled()
        self._refresh_swatches()

    def spacing_px(self):
        return GRID_SIZES[self.size_combo.currentIndex()][2] * self.resolution

    def _update_px_label(self):
        self.px_label.setText(
            "Square: %.1f px at %d DPI" % (self.spacing_px(), self.resolution)
        )

    def _update_enabled(self):
        on = self.accent_every.value() > 0
        self.accent_width.setEnabled(on)
        self.accent_color_btn.setEnabled(on)

    def _pick_color(self, accent):
        current = self.accent_color if accent else self.line_color
        picked = QColorDialog.getColor(
            current, self, "Grid line color",
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if picked.isValid():
            if accent:
                self.accent_color = picked
            else:
                self.line_color = picked
            self._refresh_swatches()

    def _refresh_swatches(self):
        for btn, color in ((self.color_btn, self.line_color),
                           (self.accent_color_btn, self.accent_color)):
            btn.setText(color.name(QColor.NameFormat.HexArgb))
            btn.setStyleSheet(
                "background-color: %s; color: %s;"
                % (color.name(), "black" if color.lightness() > 127 else "white")
            )

    def save_settings(self):
        app = Krita.instance()
        app.writeSetting(SETTINGS_GROUP, "sizeIndex", str(self.size_combo.currentIndex()))
        app.writeSetting(SETTINGS_GROUP, "lineWidth", str(self.line_width.value()))
        app.writeSetting(SETTINGS_GROUP, "lineColor", self.line_color.name(QColor.NameFormat.HexArgb))
        app.writeSetting(SETTINGS_GROUP, "accentEvery", str(self.accent_every.value()))
        app.writeSetting(SETTINGS_GROUP, "accentWidth", str(self.accent_width.value()))
        app.writeSetting(SETTINGS_GROUP, "accentColor", self.accent_color.name(QColor.NameFormat.HexArgb))


class GridPaperExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)

    def setup(self):
        pass

    def createActions(self, window):
        action = window.createAction(
            "gridpaper_add_layer", "Add Graph Paper Grid Layer...", "tools/scripts"
        )
        action.triggered.connect(self.show_dialog)

    def _parent_widget(self):
        win = Krita.instance().activeWindow()
        return win.qwindow() if win else None

    def show_dialog(self):
        app = Krita.instance()
        doc = app.activeDocument()
        parent = self._parent_widget()
        if doc is None:
            QMessageBox.information(parent, "Grid Paper", "Open a document first.")
            return

        resolution = doc.resolution() or 300
        dialog = GridDialog(resolution, parent)
        if not dialog.exec():
            return
        dialog.save_settings()

        _, short_name, inches = GRID_SIZES[dialog.size_combo.currentIndex()]
        spacing = inches * resolution
        line_w = dialog.line_width.value()
        accent_every = dialog.accent_every.value()
        accent_w = dialog.accent_width.value() if accent_every else 0

        if spacing <= max(line_w, accent_w) + 1:
            QMessageBox.warning(
                parent, "Grid Paper",
                "At %d DPI a %s square is only %.1f px — thinner than the grid "
                "lines, so the layer would come out solid. Use a smaller line "
                "width or a larger grid size." % (resolution, short_name, spacing),
            )
            return

        img = render_grid(
            doc.width(), doc.height(), spacing, line_w, dialog.line_color,
            accent_every, accent_w, dialog.accent_color,
        )

        node = doc.createNode("Grid %s" % short_name, "paintlayer")
        doc.rootNode().addChildNode(node, None)

        # setPixelData below writes 8-bit BGRA; convert the layer if the
        # document uses another model/depth (layers may differ from the doc).
        if node.colorModel() != "RGBA" or node.colorDepth() != "U8":
            profiles = app.profiles("RGBA", "U8")
            profile = next((p for p in profiles if "srgb" in p.lower()), profiles[0] if profiles else "")
            if profile:
                node.setColorSpace("RGBA", "U8", profile)

        ptr = img.bits()
        ptr.setsize(img.sizeInBytes() if hasattr(img, "sizeInBytes") else img.byteCount())
        node.setPixelData(QByteArray(bytes(ptr)), 0, 0, img.width(), img.height())
        doc.refreshProjection()
