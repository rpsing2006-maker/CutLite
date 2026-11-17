from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QApplication
from PySide6.QtGui import QPainter, QColor, QPen, QPixmap, QDrag
from PySide6.QtCore import Qt, Signal, QRect, QMimeData
import os

class TimelineTrackWidget(QWidget):
    seek_requested = Signal(float)
    clip_selected = Signal(int)
    reorder_requested = Signal(int, int)
    media_dropped = Signal(str, int)  # (file_path, insert_at_index)

    def __init__(self, project):
        super().__init__()
        self.project = project
        self.setMinimumHeight(120)
        self.playhead_global_sec = 0.0
        self.selected_index = -1
        
        # Enable Drag and Drop
        self.setAcceptDrops(True)
        self.action_mode = None
        self.drag_start_pos = None

    def set_playhead(self, global_sec):
        self.playhead_global_sec = global_sec
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Top 20px is the Ruler/Scrub zone
            if event.position().y() <= 20:
                self.action_mode = 'scrub'
                self._handle_scrub(event)
            else:
                # Bottom area is the Clip Selection/Drag zone
                self.action_mode = 'select_or_drag'
                self.drag_start_pos = event.position()
                
                total_dur = self.project.total_duration
                if total_dur > 0:
                    x = max(0, min(event.position().x(), self.width()))
                    global_sec = (x / self.width()) * total_dur
                    idx, _ = self.project.get_clip_at_global_time(global_sec)
                    self.selected_index = idx
                    self.clip_selected.emit(idx)
                    self.update()

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton): return

        if self.action_mode == 'scrub':
            self._handle_scrub(event)
        elif self.action_mode == 'select_or_drag' and self.drag_start_pos:
            # If dragged far enough, initiate Reorder Drag (identified by REORDER: prefix)
            if (event.position() - self.drag_start_pos).manhattanLength() > QApplication.startDragDistance():
                if self.selected_index >= 0:
                    drag = QDrag(self)
                    mime_data = QMimeData()
                    mime_data.setData("application/x-cutlite-reorder", str(self.selected_index).encode("utf-8"))
                    mime_data.setText(f"REORDER:{self.selected_index}")
                    drag.setMimeData(mime_data)
                    drag.exec(Qt.MoveAction)
                    self.action_mode = None

    def _handle_scrub(self, event):
        total_dur = self.project.total_duration
        if total_dur <= 0: return
        x = max(0, min(event.position().x(), self.width()))
        global_sec = (x / self.width()) * total_dur
        self.playhead_global_sec = global_sec
        self.update()
        self.seek_requested.emit(global_sec)

    # --- Drag and Drop Overrides ---
    def dragEnterEvent(self, event):
        mime = event.mimeData()
        if (mime.hasFormat("application/x-cutlite-media") or 
            mime.hasFormat("application/x-cutlite-reorder") or 
            mime.hasUrls() or 
            mime.hasText()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def _get_drop_insert_index(self, x_pos: float) -> int:
        total_dur = self.project.total_duration
        if total_dur <= 0 or not self.project.timeline:
            return 0
        ratio = max(0.0, min(1.0, x_pos / float(self.width())))
        global_sec = ratio * total_dur
        idx, _ = self.project.get_clip_at_global_time(global_sec)
        # If dropping past halfway through the clip, insert after it
        accumulated = sum(c.timeline_duration for c in self.project.timeline[:idx])
        mid_time = accumulated + (self.project.timeline[idx].timeline_duration / 2.0)
        return idx + 1 if global_sec > mid_time else idx

    def dropEvent(self, event):
        mime = event.mimeData()
        x = event.position().x()

        # 1. Dropped from Project Media Panel via custom MIME or MEDIA: text
        if mime.hasFormat("application/x-cutlite-media"):
            file_path = bytes(mime.data("application/x-cutlite-media")).decode("utf-8")
            insert_idx = self._get_drop_insert_index(x)
            self.media_dropped.emit(file_path, insert_idx)
            event.acceptProposedAction()
            return

        # 2. Reordering clips within timeline
        if mime.hasFormat("application/x-cutlite-reorder"):
            from_idx = int(bytes(mime.data("application/x-cutlite-reorder")).decode("utf-8"))
            total_dur = self.project.total_duration
            if total_dur > 0:
                global_sec = (x / self.width()) * total_dur
                to_idx, _ = self.project.get_clip_at_global_time(global_sec)
                if from_idx != to_idx:
                    self.reorder_requested.emit(from_idx, to_idx)
                    self.selected_index = to_idx
            event.acceptProposedAction()
            return

        # 3. String-based fallback (MEDIA: or REORDER: or plain index)
        if mime.hasText():
            text = mime.text().strip()
            if text.startswith("MEDIA:"):
                file_path = text[6:]
                insert_idx = self._get_drop_insert_index(x)
                self.media_dropped.emit(file_path, insert_idx)
                event.acceptProposedAction()
                return
            elif text.startswith("REORDER:"):
                try:
                    from_idx = int(text[8:])
                    total_dur = self.project.total_duration
                    if total_dur > 0:
                        global_sec = (x / self.width()) * total_dur
                        to_idx, _ = self.project.get_clip_at_global_time(global_sec)
                        if from_idx != to_idx:
                            self.reorder_requested.emit(from_idx, to_idx)
                            self.selected_index = to_idx
                    event.acceptProposedAction()
                    return
                except ValueError:
                    pass
            elif text.isdigit():
                try:
                    from_idx = int(text)
                    total_dur = self.project.total_duration
                    if total_dur > 0:
                        global_sec = (x / self.width()) * total_dur
                        to_idx, _ = self.project.get_clip_at_global_time(global_sec)
                        if from_idx != to_idx:
                            self.reorder_requested.emit(from_idx, to_idx)
                            self.selected_index = to_idx
                    event.acceptProposedAction()
                    return
                except ValueError:
                    pass

        # 4. Dropping file directly from external desktop / explorer
        if mime.hasUrls():
            for url in mime.urls():
                p = url.toLocalFile()
                if p and os.path.exists(p):
                    insert_idx = self._get_drop_insert_index(x)
                    self.media_dropped.emit(p, insert_idx)
                    event.acceptProposedAction()
                    return

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#1a1a1a"))
        
        # Draw Ruler Zone Background
        painter.fillRect(QRect(0, 0, self.width(), 20), QColor("#2a2a2a"))
        
        total_dur = self.project.total_duration
        if total_dur <= 0:
            # Draw placeholder hint
            painter.setPen(QColor("#777777"))
            painter.drawText(self.rect().adjusted(0, 20, 0, 0), Qt.AlignCenter, "Drag clips from the Project Media tab here to build your timeline")
            painter.end()
            return

        pixels_per_sec = self.width() / total_dur
        current_x = 0

        for i, clip in enumerate(self.project.timeline):
            w = max(1, clip.timeline_duration * pixels_per_sec)
            
            # Clips draw below the 20px ruler
            rect = QRect(int(current_x), 20, int(w), self.height() - 20)
            
            bg_color = "#3a5a78" if i == self.selected_index else "#444444"
            painter.fillRect(rect, QColor(bg_color))
            painter.setPen(QPen(QColor("#222222"), 2))
            painter.drawRect(rect)
            
            if os.path.exists(clip.thumbnail_path):
                pix = QPixmap(clip.thumbnail_path)
                if not pix.isNull():
                    scaled_pix = pix.scaledToHeight(self.height() - 24, Qt.SmoothTransformation)
                    painter.drawPixmap(int(current_x) + 2, 22, scaled_pix)
            
            painter.setPen(QColor("white"))
            painter.drawText(int(current_x) + 5, 40, f"{clip.name[:15]} [{clip.timeline_duration:.1f}s]")
            
            current_x += w

        # Draw Playhead
        playhead_x = int(self.playhead_global_sec * pixels_per_sec)
        painter.setPen(QPen(QColor("red"), 2))
        painter.drawLine(playhead_x, 0, playhead_x, self.height())
        
        painter.end()


class TimelinePanel(QWidget):
    def __init__(self, project):
        super().__init__()
        self.project = project
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        toolbar = QHBoxLayout()
        title = QLabel("Timeline Track (Scrub top bar | Drag & drop media or reorder clips)")
        title.setStyleSheet("font-weight: bold; color: #aaaaaa;")
        
        self.delete_btn = QPushButton("Delete Selected")
        self.export_btn = QPushButton("Export Video")
        self.export_btn.setStyleSheet("background-color: #1b5e20; font-weight: bold;")
        
        toolbar.addWidget(title)
        toolbar.addStretch()
        toolbar.addWidget(self.delete_btn)
        toolbar.addWidget(self.export_btn)

        self.track = TimelineTrackWidget(self.project)

        layout.addLayout(toolbar)
        layout.addWidget(self.track)
