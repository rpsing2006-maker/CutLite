import sys
import os
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QSplitter, QMessageBox, QFileDialog
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtCore import Qt

from core.project import Project
from core.clip import Clip
from core.renderer import Renderer
from ui.media_panel import MediaPanel
from ui.timeline import TimelinePanel
from ui.preview_panel import PreviewPanel

class CutLiteWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CutLite - Local Video Editor")
        self.resize(1280, 720)
        
        self.project = Project()
        self.current_global_sec = 0.0
        self.active_clip_index = -1
        
        self.pending_position = -1 
        self.was_playing = False 
        
        self._setup_ui()
        self._apply_dark_theme()

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        top_splitter = QSplitter(Qt.Horizontal)
        
        # 1. Project Media Library Panel
        self.media_panel = MediaPanel()
        self.media_panel.setMinimumWidth(300)
        self.media_panel.files_imported.connect(self.handle_imports)
        self.media_panel.media_list.itemClicked.connect(self.on_media_item_clicked)
        
        # 2. Preview Panel (Monitor)
        self.preview_panel = PreviewPanel()
        self.preview_panel.toggle_play.connect(self.toggle_playback)
        self.preview_panel.step_back.connect(self.step_backward_frame)
        self.preview_panel.step_forward.connect(lambda: self.seek_global(self.current_global_sec + 0.033, pause_playback=True))
        self.preview_panel.set_in_point.connect(self.handle_set_in)
        self.preview_panel.set_out_point.connect(self.handle_set_out)
        self.preview_panel.split_clip.connect(self.handle_split)
        
        self.preview_panel.player.positionChanged.connect(self.on_player_position_changed)
        self.preview_panel.player.mediaStatusChanged.connect(self.on_media_status_changed)
        
        top_splitter.addWidget(self.media_panel)
        top_splitter.addWidget(self.preview_panel)
        top_splitter.setStretchFactor(1, 1)

        # 3. Timeline Panel
        self.timeline_panel = TimelinePanel(self.project)
        self.timeline_panel.track.seek_requested.connect(self.handle_scrub_seek)
        self.timeline_panel.track.reorder_requested.connect(self.handle_reorder)
        self.timeline_panel.track.media_dropped.connect(self.handle_media_dropped_to_timeline)
        self.timeline_panel.delete_btn.clicked.connect(self.delete_selected_clip)
        self.timeline_panel.export_btn.clicked.connect(self.export_project)

        main_layout.addWidget(top_splitter, stretch=2)
        main_layout.addWidget(self.timeline_panel, stretch=1)

    def handle_imports(self, file_paths):
        """
        Imports videos into the Project Media library only.
        Does NOT automatically add them to the timeline.
        """
        for path in file_paths:
            clip = Clip(path)
            self.project.media_library.append(clip)
            self.media_panel.add_media_item(clip)

    def handle_media_dropped_to_timeline(self, file_path: str, insert_idx: int):
        """
        Called when a media item is dragged from the Project Media tab
        (or an external video file is dragged) and dropped into the timeline track.
        """
        # Check if already in media_library or create new clip
        existing = next((c for c in self.project.media_library if c.file_path == file_path), None)
        if existing:
            # Create a new clip instance for the timeline
            clip = Clip(existing.file_path)
        else:
            clip = Clip(file_path)
            self.project.media_library.append(clip)
            self.media_panel.add_media_item(clip)

        # Insert at drop location
        if insert_idx < 0 or insert_idx > len(self.project.timeline):
            insert_idx = len(self.project.timeline)
            
        self.project.timeline.insert(insert_idx, clip)
        self.timeline_panel.track.selected_index = insert_idx
        self.timeline_panel.track.update()

        # If this was the first clip added to timeline, load it for preview
        if len(self.project.timeline) == 1 or self.active_clip_index == -1:
            self.seek_global(0.0)

    def on_media_item_clicked(self, item):
        """Clicking an item in the Media Library previews it in the monitor."""
        file_path = item.data(Qt.UserRole)
        if file_path and os.path.exists(file_path):
            self.preview_panel.load_video(file_path)
            self.preview_panel.player.pause()
            self.preview_panel.play_btn.setText("Play")

    def toggle_playback(self):
        player = self.preview_panel.player
        if player.playbackState() == QMediaPlayer.PlayingState:
            player.pause()
            self.preview_panel.play_btn.setText("Play")
        else:
            player.play()
            self.preview_panel.play_btn.setText("Pause")

    def seek_global(self, global_sec, pause_playback: bool = False):
        if not self.project.timeline: return
        
        if pause_playback:
            self.was_playing = False
            self.preview_panel.player.pause()
            self.preview_panel.play_btn.setText("Play")
        
        self.current_global_sec = min(max(0.0, global_sec), self.project.total_duration)
        self.timeline_panel.track.set_playhead(self.current_global_sec)
        
        clip_idx, local_sec = self.project.get_clip_at_global_time(self.current_global_sec)
        clip = self.project.timeline[clip_idx]
        
        target_pos_ms = int(local_sec * 1000)
        
        if clip_idx != self.active_clip_index:
            if not pause_playback:
                self.was_playing = (self.preview_panel.player.playbackState() == QMediaPlayer.PlayingState)
            self.active_clip_index = clip_idx
            self.pending_position = target_pos_ms 
            self.preview_panel.load_video(clip.file_path)
        else:
            self.preview_panel.player.setPosition(target_pos_ms)

    def handle_scrub_seek(self, global_sec):
        """Called when user scrubs or drags the playhead line: stops preview and seeks."""
        self.seek_global(global_sec, pause_playback=True)

    def step_backward_frame(self):
        """Fixes -1f behavior across clip boundaries"""
        if not self.project.timeline: return
        
        # Step backward stops playback
        self.was_playing = False
        self.preview_panel.player.pause()
        self.preview_panel.play_btn.setText("Play")

        target_global = max(0.0, self.current_global_sec - 0.033)
        self.seek_global(target_global, pause_playback=True)

    def on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            if getattr(self, 'pending_position', -1) >= 0:
                self.preview_panel.player.setPosition(self.pending_position)
                self.pending_position = -1
                
                # Force continuous playback to resume seamlessly across clips
                if self.was_playing:
                    self.preview_panel.player.play()
                    self.preview_panel.play_btn.setText("Pause")
                    self.was_playing = False
                else:
                    self.preview_panel.player.play()
                    self.preview_panel.player.pause()
                    self.preview_panel.play_btn.setText("Play")

    def on_player_position_changed(self, pos_ms):
        if self.active_clip_index < 0 or not self.project.timeline: return
        if pos_ms == 0 and getattr(self, 'pending_position', -1) >= 0: return 
            
        clip = self.project.timeline[self.active_clip_index]
        local_sec = pos_ms / 1000.0
        
        accumulated = sum(c.timeline_duration for c in self.project.timeline[:self.active_clip_index])
        self.current_global_sec = accumulated + (local_sec - clip.source_start)
        self.timeline_panel.track.set_playhead(self.current_global_sec)
        
        # Seamless transition when hitting the out-point of the current clip
        if local_sec >= clip.source_end - 0.04:
            if self.active_clip_index < len(self.project.timeline) - 1:
                if self.preview_panel.player.playbackState() == QMediaPlayer.PlayingState:
                    self.was_playing = True 
                self.seek_global(accumulated + clip.timeline_duration + 0.001)
            else:
                self.preview_panel.player.pause()
                self.preview_panel.play_btn.setText("Play")

    def handle_reorder(self, from_idx, to_idx):
        if 0 <= from_idx < len(self.project.timeline) and 0 <= to_idx < len(self.project.timeline):
            clip = self.project.timeline.pop(from_idx)
            self.project.timeline.insert(to_idx, clip)
            self.timeline_panel.track.update()
            
            self.active_clip_index = -1 
            self.seek_global(self.current_global_sec)

    def handle_set_in(self):
        if self.active_clip_index >= 0:
            local_sec = self.preview_panel.player.position() / 1000.0
            self.project.timeline[self.active_clip_index].source_start = local_sec
            self.timeline_panel.track.update()

    def handle_set_out(self):
        if self.active_clip_index >= 0:
            local_sec = self.preview_panel.player.position() / 1000.0
            self.project.timeline[self.active_clip_index].source_end = local_sec
            self.timeline_panel.track.update()

    def handle_split(self):
        if self.active_clip_index >= 0:
            local_sec = self.preview_panel.player.position() / 1000.0
            self.project.split_clip(self.active_clip_index, local_sec)
            self.timeline_panel.track.update()

    def delete_selected_clip(self):
        idx = self.timeline_panel.track.selected_index
        if 0 <= idx < len(self.project.timeline):
            self.project.timeline.pop(idx)
            self.timeline_panel.track.selected_index = -1
            self.timeline_panel.track.update()
            self.active_clip_index = -1
            if self.project.timeline:
                self.seek_global(0.0)
            else:
                self.preview_panel.player.stop()

    def export_project(self):
        if not self.project.timeline: return
        out_path, _ = QFileDialog.getSaveFileName(self, "Export", "output.mp4", "Video Files (*.mp4)")
        if out_path:
            self.timeline_panel.export_btn.setText("Exporting...")
            QApplication.processEvents()
            try:
                Renderer(self.project).export(out_path)
                QMessageBox.information(self, "Success", f"Exported:\n{out_path}")
            except Exception as e:
                QMessageBox.critical(self, "Failed", str(e))
            finally:
                self.timeline_panel.export_btn.setText("Export Video")

    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #202020; color: #ffffff; }
            QWidget { color: #ffffff; }
            QPushButton { background-color: #333333; color: white; border: 1px solid #555; padding: 5px; }
            QPushButton:hover { background-color: #444444; }
        """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CutLiteWindow()
    window.show()
    sys.exit(app.exec())
