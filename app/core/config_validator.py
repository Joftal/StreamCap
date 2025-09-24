import asyncio
from typing import Dict, Any, List, Tuple

from ..models.video_format_model import VideoFormat
from ..utils.logger import logger


class ConfigValidator:
    """配置验证器类，用于检查和修复配置项"""
    
    # 有效的视频格式列表
    VALID_VIDEO_FORMATS = ["ts", "flv", "mkv", "mov", "mp4"]
    # 有效的音频格式列表
    VALID_AUDIO_FORMATS = ["mp3", "m4a", "wav", "wma", "aac"]
    # 所有有效格式列表
    VALID_SAVE_FORMATS = VALID_VIDEO_FORMATS + VALID_AUDIO_FORMATS
    # 默认视频格式
    DEFAULT_VIDEO_FORMAT = "ts"
    # 默认音频格式
    DEFAULT_AUDIO_FORMAT = "mp3"
    # 默认分段时间
    DEFAULT_SEGMENT_TIME = "1800"
    
    def __init__(self, app):
        """
        初始化配置验证器
        
        Args:
            app: 应用程序实例
        """
        self.app = app
        self.config_manager = app.config_manager
        self.user_config = app.settings.user_config
        
    async def validate_all_configs(self) -> List[Tuple[str, str, str]]:
        """
        验证所有配置项，并修复无效的配置
        
        Returns:
            List[Tuple[str, str, str]]: 修复的配置项列表，每项包含 (配置键, 原始值, 修复后的值)
        """
        #logger.info("开始验证配置项...")
        fixed_items = []
        
        # 验证所有配置项
        validators = [
            self.validate_video_format,
            self.validate_audio_format,
            self.validate_segment_time
        ]
        
        for validator in validators:
            if fixed := await validator():
                fixed_items.append(fixed)
            
        if fixed_items:
            logger.info(f"配置验证完成，已修复 {len(fixed_items)} 个配置项")
        else:
            logger.info("配置验证完成，所有配置项均有效")
            
        return fixed_items
        
    async def _validate_format(self, key: str, valid_formats: List[str], default_format: str) -> Tuple[str, str, str] | None:
        """
        通用的格式验证方法
        
        Args:
            key: 配置键名
            valid_formats: 有效格式列表
            default_format: 默认格式
            
        Returns:
            Tuple[str, str, str] | None: 如果修复了配置，返回 (配置键, 原始值, 修复后的值)，否则返回 None
        """
        original_value = self.user_config.get(key, "")
        
        if not original_value:
            logger.warning(f"配置验证 - 未设置{key}，使用默认值: {default_format.upper()}")
            self.user_config[key] = default_format.upper()
            await self.config_manager.save_user_config(self.user_config)
            return key, "", default_format.upper()
            
        # 检查格式是否有效（不区分大小写）
        if original_value.lower() not in valid_formats:
            logger.warning(f"配置验证 - 无效的{key}: {original_value}，使用默认值: {default_format.upper()}")
            self.user_config[key] = default_format.upper()
            await self.config_manager.save_user_config(self.user_config)
            return key, original_value, default_format.upper()
            
        return None
        
    async def validate_video_format(self) -> Tuple[str, str, str] | None:
        """验证视频格式配置"""
        return await self._validate_format("video_format", self.VALID_VIDEO_FORMATS, self.DEFAULT_VIDEO_FORMAT)

    async def validate_audio_format(self) -> Tuple[str, str, str] | None:
        """验证音频格式配置"""
        return await self._validate_format("audio_format", self.VALID_AUDIO_FORMATS, self.DEFAULT_AUDIO_FORMAT)
        
    async def validate_segment_time(self) -> Tuple[str, str, str] | None:
        """
        验证分段时间配置，如果无效则修复
        
        Returns:
            Tuple[str, str, str] | None: 如果修复了配置，返回 (配置键, 原始值, 修复后的值)，否则返回 None
        """
        key = "video_segment_time"
        original_value = self.user_config.get(key, "")
        
        if not original_value:
            logger.warning(f"配置验证 - 未设置分段时间，使用默认值: {self.DEFAULT_SEGMENT_TIME}")
            self.user_config[key] = self.DEFAULT_SEGMENT_TIME
            await self.config_manager.save_user_config(self.user_config)
            return key, "", self.DEFAULT_SEGMENT_TIME
            
        try:
            time_value = int(original_value)
            if time_value <= 0:
                logger.warning(f"配置验证 - 分段时间必须为正数，输入值: {time_value}，使用默认值: {self.DEFAULT_SEGMENT_TIME}")
                self.user_config[key] = self.DEFAULT_SEGMENT_TIME
                await self.config_manager.save_user_config(self.user_config)
                return key, original_value, self.DEFAULT_SEGMENT_TIME
        except (ValueError, TypeError):
            logger.warning(f"配置验证 - 无效的分段时间格式: {original_value}，使用默认值: {self.DEFAULT_SEGMENT_TIME}")
            self.user_config[key] = self.DEFAULT_SEGMENT_TIME
            await self.config_manager.save_user_config(self.user_config)
            return key, original_value, self.DEFAULT_SEGMENT_TIME
            
        return None
        
    async def update_recordings_with_valid_config(self, fixed_items: List[Tuple[str, str, str]]) -> None:
        """
        根据修复后的配置更新所有录制项
        
        Args:
            fixed_items: 修复的配置项列表，每项包含 (配置键, 原始值, 修复后的值)
        """
        if not fixed_items or not hasattr(self.app, "record_manager") or not self.app.record_manager.recordings:
            return
            
        #logger.info("正在更新录制项以使用有效配置...")
        recordings = self.app.record_manager.recordings
        updated = False
        
        for key, _, new_value in fixed_items:
            if key in ("video_format", "audio_format"):
                media_type = "video" if key == "video_format" else "audio"
                valid_formats = self.VALID_VIDEO_FORMATS if key == "video_format" else self.VALID_AUDIO_FORMATS
                
                for recording in recordings:
                    if (recording.media_type == media_type and 
                        (not recording.record_format or recording.record_format.lower() not in valid_formats)):
                        recording.record_format = new_value
                        updated = True
                        
            elif key == "video_segment_time":
                for recording in recordings:
                    try:
                        time_value = int(recording.segment_time)
                        if time_value <= 0:
                            recording.segment_time = new_value
                            updated = True
                    except (ValueError, TypeError):
                        recording.segment_time = new_value
                        updated = True
        
        if updated:
            # 保存更新后的录制项
            self.app.page.run_task(self.app.record_manager.persist_recordings)
            #logger.info("已更新录制项以使用有效配置")
            
    async def update_recording_cards(self) -> None:
        """
        更新所有录制卡片的显示
        """
        if not hasattr(self.app, "record_card_manager") or not self.app.record_manager.recordings:
            return
            
        #logger.info("正在更新所有录制卡片显示...")
        
        for recording in self.app.record_manager.recordings:
            await self.app.record_card_manager.update_card(recording)
            
        #logger.info("录制卡片显示更新完成") 