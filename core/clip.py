import uuid
import os
import subprocess

class Clip:
    def __init__(self, file_path: str):
        self.id = str(uuid.uuid4())
        self.file_path = file_path
        self.name = os.path.basename(file_path)
        
        # Get true duration using ffprobe
        self.total_duration = self._get_duration()
        self.source_start = 0.0
        self.source_end = self.total_duration
        
        self.thumbnail_path = f"assets/thumb_{self.id}.jpg"
        self._generate_thumbnail()

    def _get_duration(self) -> float:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", 
            "format=duration", "-of", 
            "default=noprint_wrappers=1:nokey=1", self.file_path
        ]
        try:
            # CREATE_NO_WINDOW prevents cmd boxes from flashing on Windows
            output = subprocess.check_output(cmd, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return float(output.strip())
        except Exception as e:
            print(f"Failed to get duration: {e}")
            return 10.0 # Fallback

    def _generate_thumbnail(self):
        os.makedirs("assets", exist_ok=True)
        if not os.path.exists(self.thumbnail_path):
            cmd = [
                "ffmpeg", "-y", "-i", self.file_path, 
                "-ss", "00:00:00", "-vframes", "1", 
                "-vf", "scale=160:-1", self.thumbnail_path
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)

    @property
    def timeline_duration(self) -> float:
        return self.source_end - self.source_start