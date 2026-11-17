import os
import subprocess
from core.project import Project

class Renderer:
    def __init__(self, project: Project):
        self.project = project

    def export(self, output_path: str, quality_preset: str = "medium"):
        if not self.project.timeline:
            raise ValueError("Timeline is empty")

        # Create a temporary concat file
        concat_file = "exports/concat_list.txt"
        os.makedirs("exports", exist_ok=True)
        
        with open(concat_file, 'w') as f:
            for clip in self.project.timeline:
                # FFmpeg requires forward slashes for paths in concat files
                safe_path = clip.file_path.replace('\\', '/')
                f.write(f"file '{safe_path}'\n")
                f.write(f"inpoint {clip.source_start}\n")
                f.write(f"outpoint {clip.source_end}\n")

        # Base FFmpeg command using concat demuxer
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c:v", "libx264",
            "-preset", quality_preset,
            "-c:a", "aac",
            output_path
        ]

        # Run FFmpeg (synchronous for MVP, can be moved to QThread later)
        subprocess.run(cmd, check=True)
        os.remove(concat_file)