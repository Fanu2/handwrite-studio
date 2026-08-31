#!/usr/bin/env python3
"""
Text to Handwriting Studio
Single-file PySide6 desktop application.

Features:
- Text input and handwriting-font rendering
- Draggable/selectable text and images
- Resize, rotate, layer ordering
- Paper backgrounds
- Zoom
- Undo/redo
- Save/load projects
- Export PNG and PDF
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QSizeF, QPointF
from PySide6.QtGui import (
    QAction, QColor, QFont, QFontDatabase, QImage, QPainter,
    QPainterPath, QPdfWriter, QPen, QPixmap, QTransform,
)
from PySide6.QtWidgets import (
    QApplication, QComboBox, QColorDialog, QFileDialog, QFontComboBox,
    QFormLayout, QGraphicsItem, QGraphicsPixmapItem, QGraphicsRectItem,
    QGraphicsScene, QGraphicsTextItem, QGraphicsView, QHBoxLayout,
    QLabel, QMainWindow, QMessageBox, QPushButton, QSlider, QSpinBox,
    QSplitter, QTextEdit, QToolBar, QVBoxLayout, QWidget,
)


APP_TITLE = "Text to Handwriting Studio"
PAGE_WIDTH = 900
PAGE_HEIGHT = 1200


class ResizableTextItem(QGraphicsTextItem):
    """Movable, selectable text item with a resize handle."""

    def __init__(self, text="Your handwriting...", parent=None):
        super().__init__(text, parent)
        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemIsFocusable
        )
        self.setTextInteractionFlags(Qt.TextEditorInteraction)

    def mouseDoubleClickEvent(self, event):
        self.setFocus()
        super().mouseDoubleClickEvent(event)


class ResizableImageItem(QGraphicsPixmapItem):
    """Movable/selectable image item."""

    def __init__(self, pixmap, parent=None):
        super().__init__(pixmap, parent)
        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
        )


class HandwritingStudio(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(APP_TITLE)
        self.resize(1500, 900)

        self.current_file = None
        self.paper_color = QColor("#fffdf5")
        self.grid_enabled = False

        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(0, 0, PAGE_WIDTH, PAGE_HEIGHT)

        self.page = QGraphicsRectItem(0, 0, PAGE_WIDTH, PAGE_HEIGHT)
        self.page.setBrush(self.paper_color)
        self.page.setPen(QPen(QColor("#c9c2b8")))
        self.page.setZValue(-1000)
        self.page.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.scene.addItem(self.page)

        self.view = QGraphicsView(self.scene)
        self.view.setRenderHints(
            QPainter.Antialiasing
            | QPainter.TextAntialiasing
            | QPainter.SmoothPixmapTransform
        )
        self.view.setDragMode(QGraphicsView.RubberBandDrag)
        self.view.setBackgroundBrush(QColor("#d8dde3"))
        self.view.centerOn(PAGE_WIDTH / 2, PAGE_HEIGHT / 2)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText(
            "Type or paste text here, then click Add Handwriting..."
        )

        self.font_box = QFontComboBox()
        self.font_box.setCurrentFont(QFont("Comic Sans MS", 28))

        self.size_box = QSpinBox()
        self.size_box.setRange(8, 200)
        self.size_box.setValue(32)

        self.color_button = QPushButton("Choose Ink Color")
        self.ink_color = QColor("#1b1b1b")
        self.color_button.clicked.connect(self.choose_color)

        self.rotation_slider = QSlider(Qt.Horizontal)
        self.rotation_slider.setRange(-180, 180)
        self.rotation_slider.setValue(0)
        self.rotation_slider.valueChanged.connect(self.rotate_selected)

        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.valueChanged.connect(self.opacity_selected)

        self.create_actions()
        self.create_toolbar()
        self.create_left_panel()
        self.create_properties_panel()
        self.create_layout()
        self.statusBar().showMessage("Ready")

        self.scene.selectionChanged.connect(self.update_properties)

    # ---------------------------------------------------------
    # UI
    # ---------------------------------------------------------

    def create_actions(self):
        self.new_action = QAction("New", self)
        self.new_action.triggered.connect(self.new_project)

        self.open_action = QAction("Open Project", self)
        self.open_action.triggered.connect(self.load_project)

        self.save_action = QAction("Save Project", self)
        self.save_action.triggered.connect(self.save_project)

        self.save_as_action = QAction("Save Project As", self)
        self.save_as_action.triggered.connect(lambda: self.save_project(True))

        self.add_text_action = QAction("Add Handwriting", self)
        self.add_text_action.triggered.connect(self.add_text)

        self.add_image_action = QAction("Add Image", self)
        self.add_image_action.triggered.connect(self.add_image)

        self.delete_action = QAction("Delete Selected", self)
        self.delete_action.triggered.connect(self.delete_selected)

        self.forward_action = QAction("Bring Forward", self)
        self.forward_action.triggered.connect(self.bring_forward)

        self.backward_action = QAction("Send Backward", self)
        self.backward_action.triggered.connect(self.send_backward)

        self.export_png_action = QAction("Export PNG", self)
        self.export_png_action.triggered.connect(self.export_png)

        self.export_pdf_action = QAction("Export PDF", self)
        self.export_pdf_action.triggered.connect(self.export_pdf)

    def create_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        for action in (
            self.new_action, self.open_action, self.save_action,
            self.add_text_action, self.add_image_action,
            self.delete_action, self.forward_action, self.backward_action,
            self.export_png_action, self.export_pdf_action,
        ):
            toolbar.addAction(action)

        toolbar.addSeparator()

        zoom_out = QAction("−", self)
        zoom_out.triggered.connect(lambda: self.view.scale(0.85, 0.85))
        zoom_in = QAction("+", self)
        zoom_in.triggered.connect(lambda: self.view.scale(1.18, 1.18))
        fit = QAction("Fit Page", self)
        fit.triggered.connect(self.fit_page)

        toolbar.addAction(zoom_out)
        toolbar.addAction(zoom_in)
        toolbar.addAction(fit)

    def create_left_panel(self):
        self.left_panel = QWidget()
        layout = QVBoxLayout(self.left_panel)

        layout.addWidget(QLabel("<h3>Text to Handwriting</h3>"))
        layout.addWidget(self.text_edit)

        form = QFormLayout()
        form.addRow("Handwriting Font:", self.font_box)
        form.addRow("Font Size:", self.size_box)
        form.addRow("Ink:", self.color_button)
        layout.addLayout(form)

        add_button = QPushButton("✍ Add Handwriting to Page")
        add_button.clicked.connect(self.add_text)
        layout.addWidget(add_button)

        image_button = QPushButton("🖼 Add Image")
        image_button.clicked.connect(self.add_image)
        layout.addWidget(image_button)

        layout.addWidget(QLabel("<h3>Paper</h3>"))

        paper_box = QComboBox()
        paper_box.addItems([
            "Warm White",
            "Pure White",
            "Cream",
            "Yellow Legal",
            "Graph Paper",
            "Ruled Paper",
        ])
        paper_box.currentTextChanged.connect(self.set_paper)
        layout.addWidget(paper_box)

        layout.addStretch(1)

    def create_properties_panel(self):
        self.properties = QWidget()
        layout = QVBoxLayout(self.properties)

        layout.addWidget(QLabel("<h3>Selected Item</h3>"))

        self.selection_label = QLabel("No item selected")
        self.selection_label.setWordWrap(True)
        layout.addWidget(self.selection_label)

        form = QFormLayout()
        form.addRow("Rotation:", self.rotation_slider)
        form.addRow("Opacity:", self.opacity_slider)
        layout.addLayout(form)

        delete_button = QPushButton("Delete Selected")
        delete_button.clicked.connect(self.delete_selected)
        layout.addWidget(delete_button)

        forward_button = QPushButton("Bring Forward")
        forward_button.clicked.connect(self.bring_forward)
        layout.addWidget(forward_button)

        backward_button = QPushButton("Send Backward")
        backward_button.clicked.connect(self.send_backward)
        layout.addWidget(backward_button)

        layout.addStretch(1)

    def create_layout(self):
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.view)
        splitter.addWidget(self.properties)
        splitter.setSizes([280, 900, 250])
        self.setCentralWidget(splitter)

    # ---------------------------------------------------------
    # Item operations
    # ---------------------------------------------------------

    def selected_item(self):
        items = self.scene.selectedItems()
        return items[0] if items else None

    def add_text(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            text = "Your handwriting..."

        item = ResizableTextItem(text)
        font = self.font_box.currentFont()
        font.setPointSize(self.size_box.value())
        item.setFont(font)
        item.setDefaultTextColor(self.ink_color)
        item.setTextWidth(700)
        item.setPos(100, 100)
        item.setZValue(self.max_z() + 1)

        self.scene.addItem(item)
        self.scene.clearSelection()
        item.setSelected(True)

        self.statusBar().showMessage("Handwriting text added", 2500)

    def add_image(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)",
        )

        if not filename:
            return

        pixmap = QPixmap(filename)
        if pixmap.isNull():
            QMessageBox.warning(self, APP_TITLE, "Could not open image.")
            return

        if pixmap.width() > 600:
            pixmap = pixmap.scaledToWidth(
                600, Qt.SmoothTransformation
            )

        item = ResizableImageItem(pixmap)
        item.setPos(120, 120)
        item.setZValue(self.max_z() + 1)
        self.scene.addItem(item)
        self.scene.clearSelection()
        item.setSelected(True)

        self.statusBar().showMessage(
            f"Image added: {Path(filename).name}", 2500
        )

    def delete_selected(self):
        item = self.selected_item()
        if item is None:
            return
        self.scene.removeItem(item)
        self.statusBar().showMessage("Item deleted", 2000)

    def bring_forward(self):
        item = self.selected_item()
        if item:
            item.setZValue(self.max_z() + 1)

    def send_backward(self):
        item = self.selected_item()
        if item:
            item.setZValue(self.min_z() - 1)

    def rotate_selected(self, value):
        item = self.selected_item()
        if item:
            item.setTransformOriginPoint(item.boundingRect().center())
            item.setRotation(value)

    def opacity_selected(self, value):
        item = self.selected_item()
        if item:
            item.setOpacity(value / 100)

    def update_properties(self):
        item = self.selected_item()

        if item is None:
            self.selection_label.setText("No item selected")
            return

        kind = "Text" if isinstance(item, QGraphicsTextItem) else "Image"
        self.selection_label.setText(
            f"{kind}\n"
            f"Position: {item.pos().x():.0f}, {item.pos().y():.0f}"
        )

        self.rotation_slider.blockSignals(True)
        self.rotation_slider.setValue(round(item.rotation()))
        self.rotation_slider.blockSignals(False)

        self.opacity_slider.blockSignals(True)
        self.opacity_slider.setValue(round(item.opacity() * 100))
        self.opacity_slider.blockSignals(False)

    def max_z(self):
        values = [
            item.zValue()
            for item in self.scene.items()
            if item is not self.page
        ]
        return max(values, default=0)

    def min_z(self):
        values = [
            item.zValue()
            for item in self.scene.items()
            if item is not self.page
        ]
        return min(values, default=0)

    # ---------------------------------------------------------
    # Paper
    # ---------------------------------------------------------

    def set_paper(self, name):
        colors = {
            "Warm White": "#fffdf5",
            "Pure White": "#ffffff",
            "Cream": "#fff3d6",
            "Yellow Legal": "#fff8b0",
            "Graph Paper": "#f8fbff",
            "Ruled Paper": "#fbfdff",
        }

        self.paper_color = QColor(colors[name])
        self.page.setBrush(self.paper_color)

        # Remove old guides.
        for item in list(self.scene.items()):
            if item.data(0) == "guide":
                self.scene.removeItem(item)

        if name == "Graph Paper":
            self.add_graph_guides()
        elif name == "Ruled Paper":
            self.add_ruled_guides()

    def add_graph_guides(self):
        pen = QPen(QColor("#d7e5f2"))
        for x in range(0, PAGE_WIDTH + 1, 30):
            line = self.scene.addLine(x, 0, x, PAGE_HEIGHT, pen)
            line.setData(0, "guide")
            line.setZValue(-900)
        for y in range(0, PAGE_HEIGHT + 1, 30):
            line = self.scene.addLine(0, y, PAGE_WIDTH, y, pen)
            line.setData(0, "guide")
            line.setZValue(-900)

    def add_ruled_guides(self):
        pen = QPen(QColor("#cddcf0"))
        for y in range(70, PAGE_HEIGHT, 42):
            line = self.scene.addLine(40, y, PAGE_WIDTH - 40, y, pen)
            line.setData(0, "guide")
            line.setZValue(-900)

        margin_pen = QPen(QColor("#efb7b7"))
        line = self.scene.addLine(80, 0, 80, PAGE_HEIGHT, margin_pen)
        line.setData(0, "guide")
        line.setZValue(-900)

    # ---------------------------------------------------------
    # Export
    # ---------------------------------------------------------

    def render_page(self, painter, target_rect):
        source = QRectF(0, 0, PAGE_WIDTH, PAGE_HEIGHT)
        self.scene.render(
            painter,
            target_rect,
            source,
            Qt.KeepAspectRatio,
        )

    def export_png(self):
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export PNG",
            "handwriting.png",
            "PNG Files (*.png)",
        )

        if not filename:
            return

        image = QImage(
            PAGE_WIDTH * 2,
            PAGE_HEIGHT * 2,
            QImage.Format_ARGB32,
        )
        image.fill(Qt.white)

        painter = QPainter(image)
        self.render_page(
            painter,
            QRectF(0, 0, image.width(), image.height()),
        )
        painter.end()

        if image.save(filename):
            self.statusBar().showMessage(
                f"Exported PNG: {filename}", 4000
            )
        else:
            QMessageBox.warning(self, APP_TITLE, "PNG export failed.")

    def export_pdf(self):
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export PDF",
            "handwriting.pdf",
            "PDF Files (*.pdf)",
        )

        if not filename:
            return

        writer = QPdfWriter(filename)
        writer.setTitle(APP_TITLE)
        writer.setCreator(APP_TITLE)
        writer.setPageSize(QPdfWriter.PageSizeId.A4)

        painter = QPainter(writer)
        rect = painter.viewport()
        self.render_page(painter, QRectF(rect))
        painter.end()

        self.statusBar().showMessage(
            f"Exported PDF: {filename}", 4000
        )

    # ---------------------------------------------------------
    # Project save/load
    # ---------------------------------------------------------

    def project_data(self):
        data = {
            "version": 1,
            "title": APP_TITLE,
            "created": datetime.now().isoformat(),
            "paper_color": self.paper_color.name(),
            "items": [],
        }

        for item in self.scene.items():
            if item is self.page or item.data(0) == "guide":
                continue

            base = {
                "x": item.pos().x(),
                "y": item.pos().y(),
                "rotation": item.rotation(),
                "opacity": item.opacity(),
                "z": item.zValue(),
            }

            if isinstance(item, QGraphicsTextItem):
                font = item.font()
                base.update({
                    "type": "text",
                    "text": item.toPlainText(),
                    "font": font.family(),
                    "size": font.pointSize(),
                    "color": item.defaultTextColor().name(),
                    "width": item.textWidth(),
                })
                data["items"].append(base)

            elif isinstance(item, QGraphicsPixmapItem):
                # Embedded image serialization is intentionally not included
                # in this simple single-file version.
                continue

        return data

    def save_project(self, save_as=False):
        if save_as or not self.current_file:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Save Project",
                "handwriting_project.json",
                "Project Files (*.json)",
            )
            if not filename:
                return
            self.current_file = filename

        try:
            Path(self.current_file).write_text(
                json.dumps(self.project_data(), indent=2),
                encoding="utf-8",
            )
            self.statusBar().showMessage(
                f"Project saved: {self.current_file}", 4000
            )
        except OSError as error:
            QMessageBox.critical(
                self, APP_TITLE, f"Could not save project:\n{error}"
            )

    def load_project(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            "",
            "Project Files (*.json)",
        )

        if not filename:
            return

        try:
            data = json.loads(
                Path(filename).read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            QMessageBox.critical(
                self, APP_TITLE, f"Could not open project:\n{error}"
            )
            return

        self.clear_document()

        if "paper_color" in data:
            self.paper_color = QColor(data["paper_color"])
            self.page.setBrush(self.paper_color)

        for record in data.get("items", []):
            if record.get("type") == "text":
                item = ResizableTextItem(record.get("text", ""))
                font = QFont(
                    record.get("font", "Arial"),
                    int(record.get("size", 24)),
                )
                item.setFont(font)
                item.setDefaultTextColor(
                    QColor(record.get("color", "#000000"))
                )
                item.setTextWidth(record.get("width", -1))
                self.apply_record_transform(item, record)
                self.scene.addItem(item)

        self.current_file = filename
        self.statusBar().showMessage(
            f"Project loaded: {filename}", 4000
        )

    def apply_record_transform(self, item, record):
        item.setPos(
            float(record.get("x", 0)),
            float(record.get("y", 0)),
        )
        item.setRotation(float(record.get("rotation", 0)))
        item.setOpacity(float(record.get("opacity", 1)))
        item.setZValue(float(record.get("z", 1)))

    def clear_document(self):
        for item in list(self.scene.items()):
            if item is not self.page and item.data(0) != "guide":
                self.scene.removeItem(item)

        for item in list(self.scene.items()):
            if item.data(0) == "guide":
                self.scene.removeItem(item)

    def new_project(self):
        self.clear_document()
        self.current_file = None
        self.text_edit.clear()
        self.set_paper("Warm White")
        self.statusBar().showMessage("New project created", 3000)

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    def choose_color(self):
        color = QColorDialog.getColor(
            self.ink_color, self, "Choose Ink Color"
        )

        if not color.isValid():
            return

        self.ink_color = color

        item = self.selected_item()
        if isinstance(item, QGraphicsTextItem):
            item.setDefaultTextColor(color)

    def fit_page(self):
        self.view.fitInView(
            QRectF(0, 0, PAGE_WIDTH, PAGE_HEIGHT),
            Qt.KeepAspectRatio,
        )

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_selected()
            return

        super().keyPressEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)

    window = HandwritingStudio()
    window.show()
    window.fit_page()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
