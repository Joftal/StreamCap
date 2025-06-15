from datetime import timedelta
from .video_format_model import VideoFormat
from .audio_format_model import AudioFormat


class Recording:
    def __init__(
        self,
        rec_id: str,
        url: str,
        streamer_name: str,
        quality: str,
        segment_record: bool,
        monitor_status: bool,
        segment_time,
        scheduled_recording,
        scheduled_start_time,
        monitor_hours,
        recording_dir,
        enabled_message_push,
        media_type: str = "video",
        record_format: str = None,
        record_mode="auto",
        remark: str = None  # 新增备注参数
    ):
        """
        Initialize a recording object.

        :param rec_id: Unique identifier for the recording task.
        :param url: URL address of the live stream.
        :param streamer_name: Name of the streamer.
        :param quality: Quality of the recorded video, e.g., 'OD', 'UHD', 'HD'.
        :param segment_record: Whether to enable segmented recording.
        :param monitor_status: Monitoring status, whether the live room is being monitored.
        :param media_type: Type of the recorded file, e.g., 'video', 'audio'.
        :param record_format: Format of the recorded file, e.g., 'mp4', 'ts', 'mkv'.
        :param segment_time: Time interval (in seconds) for segmented recording if enabled.
        :param scheduled_recording: Whether to enable scheduled recording.
        :param scheduled_start_time: Scheduled start time for recording (string format like '18:30:00').
        :param monitor_hours: Number of hours to monitor from the scheduled recording start time, e.g., 3.
        :param recording_dir: Directory path where the recorded files will be saved.
        :param enabled_message_push: Whether to enable message push.
        :param record_mode: Recording mode, either 'auto' or 'manual'.
        :param remark: Remark for the recording task, limited to 20 Chinese characters.
        """

        self.rec_id = rec_id
        self.url = url
        self.streamer_name = streamer_name
        self.quality = quality
        self.monitor_status = monitor_status
        self.segment_record = segment_record
        self._media_type = media_type
        self._record_format = None  # 先初始化为None
        self.segment_time = segment_time
        self.scheduled_recording = scheduled_recording
        self.scheduled_start_time = scheduled_start_time
        self.monitor_hours = monitor_hours
        self.recording_dir = recording_dir
        self.enabled_message_push = enabled_message_push
        self.scheduled_time_range = None
        self.title = f"{streamer_name} - {self.quality}"
        self.speed = "0 KB/s"
        self.is_live = False
        self.recording = False  # Record status
        self.start_time = None
        self.record_mode = record_mode
        self.manually_stopped = False

        self.cumulative_duration = timedelta()  # Accumulated recording time
        self.last_duration = timedelta()  # Save the total time of the last recording
        self.display_title = self.title
        self.selected = False
        self.is_checking = False
        self.status_info = None
        self.live_title = None
        self.detection_time = None
        self.loop_time_seconds = None
        self.use_proxy = None
        self.record_url = None
        # 用于跟踪是否已经发送过直播状态通知
        self.notification_sent = False
        
        # 设置媒体类型和录制格式
        self.media_type = media_type
        self.record_format = record_format
        self.remark = remark if remark and len(remark) <= 20 else None

    def to_dict(self):
        """Convert the Recording instance to a dictionary for saving."""
        return {
            "rec_id": self.rec_id,
            "media_type": self.media_type,
            "url": self.url,
            "streamer_name": self.streamer_name,
            "record_format": self.record_format,
            "quality": self.quality,
            "segment_record": self.segment_record,
            "segment_time": self.segment_time,
            "monitor_status": self.monitor_status,
            "scheduled_recording": self.scheduled_recording,
            "scheduled_start_time": self.scheduled_start_time,
            "monitor_hours": self.monitor_hours,
            "recording_dir": self.recording_dir,
            "enabled_message_push": self.enabled_message_push,
            "record_mode": self.record_mode,
            "remark": self.remark,  # 添加备注到保存数据中
        }

    @classmethod
    def from_dict(cls, data):
        """Create a Recording instance from a dictionary."""
        recording = cls(
            data.get("rec_id"),
            data.get("url"),
            data.get("streamer_name"),
            data.get("quality"),
            data.get("segment_record"),
            data.get("monitor_status"),
            data.get("segment_time"),
            data.get("scheduled_recording"),
            data.get("scheduled_start_time"),
            data.get("monitor_hours"),
            data.get("recording_dir"),
            data.get("enabled_message_push"),
            data.get("media_type"),
            data.get("record_format"),
            data.get("record_mode", "auto"),
            data.get("remark"),  # 从数据中读取备注
        )
        recording.title = data.get("title", recording.title)
        recording.display_title = data.get("display_title", recording.title)
        recording.last_duration_str = data.get("last_duration")
        if recording.last_duration_str is not None:
            recording.last_duration = timedelta(seconds=float(recording.last_duration_str))
        return recording

    def update_title(self, quality_info, prefix=None):
        """Helper method to update the title."""
        self.title = f"{self.streamer_name} - {quality_info}"
        self.display_title = f"{prefix or ''}{self.title}"

    def update(self, updated_info: dict):
        """Update the recording object with new information."""
        for attr, value in updated_info.items():
            if hasattr(self, attr):
                setattr(self, attr, value)
        if "record_mode" in updated_info:
            self.record_mode = updated_info["record_mode"]

    @property
    def media_type(self) -> str:
        """获取媒体类型"""
        return self._media_type

    @media_type.setter
    def media_type(self, value: str):
        """设置媒体类型，并在切换时更新格式"""
        if not value:
            self._media_type = "video"  # 默认为视频类型
        else:
            # 转换为小写进行比较
            value = value.lower()
            if value not in ["video", "audio"]:
                self._media_type = "video"
            else:
                self._media_type = value
                
        # 当媒体类型改变时，根据新的媒体类型设置默认格式
        if self._media_type == "video":
            if not self._record_format or self._record_format not in VideoFormat.get_formats():
                self._record_format = VideoFormat.TS
        else:  # audio
            if not self._record_format or self._record_format not in AudioFormat.get_formats():
                self._record_format = AudioFormat.MP3

    @property
    def record_format(self) -> str:
        """获取录制格式"""
        return self._record_format

    @record_format.setter
    def record_format(self, value: str):
        """设置录制格式"""
        if not value:
            self._record_format = VideoFormat.TS if self.media_type == "video" else AudioFormat.MP3
        else:
            # 转换为大写进行比较
            value = value.upper()
            if self.media_type == "video":
                if value not in VideoFormat.get_formats():
                    self._record_format = VideoFormat.TS
                else:
                    self._record_format = value
            else:  # audio
                if value not in AudioFormat.get_formats():
                    self._record_format = AudioFormat.MP3
                else:
                    self._record_format = value
