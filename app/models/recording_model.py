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
        remark: str = None,  # 新增备注参数
        thumbnail_enabled: bool = None,  # 新增单个房间缩略图开关
        translation_enabled: bool = None  # 新增单个房间翻译开关
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
        :param thumbnail_enabled: Whether to enable thumbnail for this specific room (None means use global setting).
        :param translation_enabled: Whether to enable translation for this specific room (None means use global setting).
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
        self.translated_title = None  # 翻译后的标题（当前语言）
        self.last_live_title = None  # 上次的直播标题，用于检测标题变化
        self.cached_translated_title = None  # 缓存的翻译标题，用于翻译开关重启时恢复
        self.multi_language_titles = {}  # 多语言标题缓存，格式：{"zh": "中文标题", "en": "English Title"}
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
        
        # 单个房间缩略图开关（None表示使用全局设置）
        self.thumbnail_enabled = thumbnail_enabled
        
        # 单个房间翻译开关（None表示使用全局设置）
        self.translation_enabled = translation_enabled

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
            "thumbnail_enabled": self.thumbnail_enabled,  # 添加单个房间缩略图开关到保存数据中
            "translation_enabled": self.translation_enabled,  # 添加单个房间翻译开关到保存数据中
            "live_title": self.live_title,  # 添加直播标题到保存数据中
            "translated_title": self.translated_title,  # 添加翻译标题到保存数据中
            "last_live_title": self.last_live_title,  # 添加上次直播标题缓存到保存数据中
            "cached_translated_title": self.cached_translated_title,  # 添加缓存的翻译标题到保存数据中
            "multi_language_titles": self.multi_language_titles,  # 添加多语言标题缓存到保存数据中
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
            data.get("thumbnail_enabled"),  # 从数据中读取单个房间缩略图开关
            data.get("translation_enabled"),  # 从数据中读取单个房间翻译开关
        )
        recording.title = data.get("title", recording.title)
        recording.display_title = data.get("display_title", recording.title)
        recording.last_duration_str = data.get("last_duration")
        if recording.last_duration_str is not None:
            recording.last_duration = timedelta(seconds=float(recording.last_duration_str))
        
        # 从保存的数据中恢复标题相关字段
        recording.live_title = data.get("live_title")
        recording.translated_title = data.get("translated_title")
        recording.last_live_title = data.get("last_live_title")
        recording.cached_translated_title = data.get("cached_translated_title")
        recording.multi_language_titles = data.get("multi_language_titles", {})
        
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

    def is_thumbnail_enabled(self, global_thumbnail_enabled: bool) -> bool:
        """
        判断是否应该显示缩略图
        
        Args:
            global_thumbnail_enabled: 全局缩略图开关状态
            
        Returns:
            bool: 是否应该显示缩略图
        """
        # 如果单个房间有明确设置，使用单个房间设置
        if self.thumbnail_enabled is not None:
            return self.thumbnail_enabled
        # 否则使用全局设置
        return global_thumbnail_enabled
    
    def is_translation_enabled(self, global_translation_enabled: bool) -> bool:
        """
        判断是否应该启用翻译
        
        Args:
            global_translation_enabled: 全局翻译开关状态
            
        Returns:
            bool: 是否应该启用翻译
        """
        # 如果单个房间有明确设置，使用单个房间设置
        if self.translation_enabled is not None:
            return self.translation_enabled
        # 否则使用全局设置
        return global_translation_enabled
    
    def get_translated_title_for_language(self, language_code: str) -> str:
        """
        获取指定语言的翻译标题
        
        Args:
            language_code: 语言代码，如 'zh', 'en'
            
        Returns:
            str: 指定语言的翻译标题，如果没有则返回None
        """
        return self.multi_language_titles.get(language_code)
    
    def set_translated_title_for_language(self, language_code: str, translated_title: str):
        """
        设置指定语言的翻译标题
        
        Args:
            language_code: 语言代码，如 'zh', 'en'
            translated_title: 翻译后的标题
        """
        if translated_title and translated_title.strip():
            self.multi_language_titles[language_code] = translated_title.strip()
    
    def clear_translated_titles(self):
        """清除所有翻译标题缓存"""
        self.multi_language_titles.clear()
        self.translated_title = None
        self.cached_translated_title = None
