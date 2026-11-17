import json
from typing import List
from core.clip import Clip

class Project:
    def __init__(self):
        self.media_library: List[Clip] = []
        self.timeline: List[Clip] = []
        self.resolution = (1920, 1080)
        self.fps = 30

    def add_to_timeline(self, clip: Clip):
        self.timeline.append(clip)

    @property
    def total_duration(self) -> float:
        return sum(c.timeline_duration for c in self.timeline)

    def get_clip_at_global_time(self, global_sec: float):
        """Returns (clip_index, local_time_sec) for a given global timeline position"""
        if not self.timeline or global_sec <= 0:
            return 0, 0.0
            
        accumulated = 0.0
        for i, clip in enumerate(self.timeline):
            dur = clip.timeline_duration
            if global_sec < accumulated + dur or i == len(self.timeline) - 1:
                offset = max(0.0, min(dur, global_sec - accumulated))
                return i, clip.source_start + offset
            accumulated += dur
            
        last_idx = len(self.timeline) - 1
        return last_idx, self.timeline[last_idx].source_end

    def split_clip(self, clip_index: int, split_time: float):
        if clip_index < 0 or clip_index >= len(self.timeline): return
        original_clip = self.timeline[clip_index]
        if split_time <= original_clip.source_start or split_time >= original_clip.source_end: return

        # FIX: Clip no longer takes total_duration as an argument (ffprobe handles it)
        new_clip = Clip(original_clip.file_path) 
        
        # Apply the cut logic
        new_clip.source_start = split_time
        new_clip.source_end = original_clip.source_end
        original_clip.source_end = split_time
        
        self.timeline.insert(clip_index + 1, new_clip)