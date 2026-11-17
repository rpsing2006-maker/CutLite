from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QListWidget, QListWidgetItem, QFileDialog, QApplication
from PySide6.QtGui import QDrag, QPixmap, QIcon
from PySide6.QtCore import Signal, Qt, QMimeData, QPoint
import os

class MediaListWidget(QListWidget):
    """
    Custom QListWidget that initiates a drag with custom MIME type
    'application/x-cutlite-media' containing the imported file path.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDefaultDropAction(Qt.CopyAction)
        self.drag_start_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.position()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton) or not self.drag_start_pos:
            super().mouseMoveEvent(event)
            return

        if (event.position() - self.drag_start_pos).manhattanLength() > QApplication.startDragDistance():
            item = self.currentItem()
            if item:
                file_path = item.data(Qt.UserRole)
                if not file_path:
                    file_path = item.text()

                drag = QDrag(self)
                mime_data = QMimeData()
                # Use custom mime type as well as plain text for compatibility
                mime_data.setData("application/x-cutlite-media", file_path.encode("utf-8"))
                mime_data.setText(f"MEDIA:{file_path}")
                drag.setMimeData(mime_data)

                # Set drag visual thumbnail if available
                thumb_path = item.data(Qt.UserRole + 1)
                if thumb_path and os.path.exists(thumb_path):
                    pix = QPixmap(thumb_path)
                    if not pix.isNull():
                        drag.setPixmap(pix.scaledToHeight(50, Qt.SmoothTransformation))
                        drag.setHotSpot(QPoint(25, 25))

                drag.exec(Qt.CopyAction)
                self.drag_start_pos = None
                return

        super().mouseMoveEvent(event)


class MediaPanel(QWidget):
    # Signal emitted when files are imported
    files_imported = Signal(list)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self.import_btn = QPushButton("Import Media")
        self.import_btn.setStyleSheet("padding: 10px; background-color: #0d47a1; color: white; font-weight: bold;")
        self.import_btn.clicked.connect(self._import_files)
        
        self.media_list = MediaListWidget()
        self.media_list.setStyleSheet("""
            QListWidget { background-color: #2b2b2b; color: white; border: none; padding: 4px; }
            QListWidget::item { padding: 6px; margin: 2px 0px; border-radius: 4px; background-color: #383838; }
            QListWidget::item:hover { background-color: #4a4a4a; }
            QListWidget::item:selected { background-color: #0d47a1; }
        """)

        layout.addWidget(self.import_btn)
        layout.addWidget(self.media_list)

    def _import_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Import Video Files", "", "Video Files (*.mp4 *.mov *.avi *.mkv *.m4v *.webm)"
        )
        if files:
            self.files_imported.emit(files)

    def add_media_item(self, clip):
        """Adds a clip to the Project Media list widget with thumbnail and metadata."""
        item = QListWidgetItem(f"{clip.name} [{clip.total_duration:.1f}s]")
        item.setData(Qt.UserRole, clip.file_path)
        if hasattr(clip, 'thumbnail_path') and os.path.exists(clip.thumbnail_path):
            item.setData(Qt.UserRole + 1, clip.thumbnail_path)
            item.setIcon(QIcon(clip.thumbnail_path))
        self.media_list.addItem(item)
