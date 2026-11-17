from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtCore import Qt, QUrl, Signal

class PreviewPanel(QWidget):
    set_in_point = Signal()
    set_out_point = Signal()
    split_clip = Signal()
    step_back = Signal()
    step_forward = Signal()
    toggle_play = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #000000;")
        
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)

        controls_layout = QHBoxLayout()
        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self.toggle_play.emit)
        
        self.prev_btn = QPushButton("-1f")
        self.prev_btn.clicked.connect(self.step_back.emit)
        self.next_btn = QPushButton("+1f")
        self.next_btn.clicked.connect(self.step_forward.emit)

        self.in_btn = QPushButton("[ Set In")
        self.in_btn.clicked.connect(self.set_in_point.emit)
        self.out_btn = QPushButton("Set Out ]")
        self.out_btn.clicked.connect(self.set_out_point.emit)
        self.split_btn = QPushButton("Split ✂")
        self.split_btn.clicked.connect(self.split_clip.emit)
        
        controls_layout.addWidget(self.play_btn)
        controls_layout.addWidget(self.prev_btn)
        controls_layout.addWidget(self.next_btn)
        controls_layout.addWidget(self.in_btn)
        controls_layout.addWidget(self.out_btn)
        controls_layout.addWidget(self.split_btn)

        layout.addWidget(self.video_widget, stretch=1)
        layout.addLayout(controls_layout)

    def load_video(self, file_path):
        if self.player.source().toLocalFile() != file_path:
            self.player.setSource(QUrl.fromLocalFile(file_path))