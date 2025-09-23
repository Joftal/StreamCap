import json
import os
import shutil
from typing import Any

import aiofiles

from ..utils.logger import logger


class ConfigManager:
    def __init__(self, run_path):
        self.config_path = os.path.join(run_path, "config")
        self.language_config_path = os.path.join(self.config_path, "language.json")
        self.default_config_path = os.path.join(self.config_path, "default_settings.json")
        self.user_config_path = os.path.join(self.config_path, "user_settings.json")
        self.cookies_config_path = os.path.join(self.config_path, "cookies.json")
        self.about_config_path = os.path.join(self.config_path, "version.json")
        self.recordings_config_path = os.path.join(self.config_path, "recordings.json")
        self.accounts_config_path = os.path.join(self.config_path, "accounts.json")
        self.web_auth_config_path = os.path.join(self.config_path, "web_auth.json")

        os.makedirs(os.path.dirname(self.default_config_path), exist_ok=True)
        self.init()

    def init(self):
        self.init_default_config()
        self.init_user_config()
        self.init_cookies_config()
        self.init_accounts_config()
        self.init_recordings_config()
        self.init_web_auth_config()
        # 修复缺失或新增的JSON配置项
        self.fix_missing_config_keys()

    @staticmethod
    def _init_config(config_path, default_config=None):
        """Initialize a configuration file with default values if it does not exist."""
        if not os.path.exists(config_path):
            if default_config is None:
                default_config = {}
            try:
                with open(config_path, "w", encoding="utf-8") as file:
                    json.dump(default_config, file, ensure_ascii=False, indent=4)
                logger.info(f"Initialized configuration file: {config_path}")
            except Exception as e:
                logger.error(f"Failed to initialize configuration file {config_path}: {e}")

    def init_default_config(self):
        default_config = {}
        self._init_config(self.default_config_path, default_config)

    def init_user_config(self):
        if os.path.exists(self.user_config_path) and self.load_user_config():
            return
        shutil.copy(self.default_config_path, self.user_config_path)

    def init_cookies_config(self):
        cookies_config = {}
        self._init_config(self.cookies_config_path, cookies_config)

    def init_accounts_config(self):
        accounts_config = {}
        self._init_config(self.accounts_config_path, accounts_config)

    def init_recordings_config(self):
        recordings_config = []
        self._init_config(self.recordings_config_path, recordings_config)

    def init_web_auth_config(self):
        web_auth_config = {}
        self._init_config(self.web_auth_config_path, web_auth_config)

    @staticmethod
    def _load_config(config_path, error_message):
        """Load configuration from a JSON file."""
        try:
            with open(config_path, encoding="utf-8") as file:
                return json.load(file)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON format in file: {config_path}")
            return {}
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {config_path}")
            return {}
        except Exception as e:
            logger.error(f"{error_message}: {e}")
            return {}

    def load_default_config(self):
        return self._load_config(self.default_config_path, "An error occurred while loading default config")

    def load_user_config(self):
        return self._load_config(self.user_config_path, "An error occurred while loading user config")

    def load_recordings_config(self):
        return self._load_config(self.recordings_config_path, "An error occurred while loading recordings config")

    def load_accounts_config(self):
        return self._load_config(self.accounts_config_path, "An error occurred while loading accounts config")

    def load_cookies_config(self):
        return self._load_config(self.cookies_config_path, "An error occurred while loading cookies config")

    def load_about_config(self):
        return self._load_config(self.about_config_path, "An error occurred while loading about config")

    def load_language_config(self):
        return self._load_config(self.language_config_path, "An error occurred while loading language config")

    def load_i18n_config(self, path):
        """Load i18n configuration from a JSON file."""
        return self._load_config(path, "An error occurred while loading i18n config")

    def load_web_auth_config(self):
        return self._load_config(self.web_auth_config_path, "An error occurred while loading web auth config")

    @staticmethod
    async def _save_config(config_path, config, success_message, error_message):
        """Save configuration to a JSON file."""
        try:
            async with aiofiles.open(config_path, "w", encoding="utf-8") as file:
                await file.write(json.dumps(config, ensure_ascii=False, indent=4))
            logger.info(success_message)
        except Exception as e:
            logger.error(f"{error_message}: {e}")

    async def save_recordings_config(self, config):
        await self._save_config(
            self.recordings_config_path,
            config,
            success_message="Recordings configuration saved.",
            error_message="An error occurred while saving recordings config",
        )

    async def save_accounts_config(self, config):
        await self._save_config(
            self.accounts_config_path,
            config,
            success_message="Accounts configuration saved.",
            error_message="An error occurred while saving accounts config",
        )

    async def save_web_auth_config(self, config):
        await self._save_config(
            self.web_auth_config_path,
            config,
            success_message="Web auth configuration saved.",
            error_message="An error occurred while saving web auth config",
        )

    async def save_user_config(self, config):
        await self._save_config(
            self.user_config_path,
            config,
            success_message="User configuration saved.",
            error_message="An error occurred while saving user config",
        )

    async def save_cookies_config(self, config):
        await self._save_config(
            self.cookies_config_path,
            config,
            success_message="Cookies configuration saved.",
            error_message="An error occurred while saving cookies config",
        )

    def get_config_value(self, key: str, default: Any = None):
        user_config = self.load_user_config()
        default_config = self.load_default_config()
        return user_config.get(key, default_config.get(key, default))

    def fix_missing_config_keys(self):
        """修复缺失或新增的JSON配置项，保持原有顺序，新增项排在后面"""
        try:
            # 修复user_settings.json
            self._fix_user_settings_config()
            # 修复recordings.json
            self._fix_recordings_config()
            logger.info("配置项修复完成")
        except Exception as e:
            logger.error(f"修复配置项时发生错误: {e}")

    def _fix_user_settings_config(self):
        """修复user_settings.json中缺失的配置项"""
        try:
            default_config = self.load_default_config()
            user_config = self.load_user_config()
            
            if not default_config or not isinstance(default_config, dict):
                logger.warning("默认配置为空或格式错误，跳过user_settings修复")
                return
            
            if not user_config or not isinstance(user_config, dict):
                logger.warning("用户配置为空或格式错误，跳过user_settings修复")
                return
            
            # 检查是否有缺失的配置项
            missing_keys = []
            for key in default_config.keys():
                if key not in user_config:
                    missing_keys.append(key)
            
            if missing_keys:
                logger.info(f"发现user_settings.json中缺失的配置项: {missing_keys}")
                
                # 保持原有顺序，将缺失的配置项添加到末尾
                for key in missing_keys:
                    user_config[key] = default_config[key]
                
                # 保存修复后的配置
                with open(self.user_config_path, "w", encoding="utf-8") as file:
                    json.dump(user_config, file, ensure_ascii=False, indent=4)
                
                logger.info(f"已修复user_settings.json中{len(missing_keys)}个缺失的配置项")
            else:
                logger.debug("user_settings.json配置项完整，无需修复")
                
        except Exception as e:
            logger.error(f"修复user_settings.json时发生错误: {e}")

    def _fix_recordings_config(self):
        """修复recordings.json中缺失的配置项"""
        try:
            recordings_config = self.load_recordings_config()
            
            # 如果配置为空或不是列表，初始化为空列表
            if not isinstance(recordings_config, list):
                if recordings_config in ({}, []):
                    logger.debug("recordings.json为空，初始化为空列表")
                    recordings_config = []
                else:
                    logger.warning("recordings.json格式错误，跳过修复")
                    return
            
            # 定义recordings.json中每个录制项应该包含的字段
            required_fields = [
                "rec_id", "media_type", "url", "streamer_name", "record_format", 
                "quality", "segment_record", "segment_time", "monitor_status", 
                "scheduled_recording", "scheduled_start_time", "monitor_hours", 
                "recording_dir", "enabled_message_push", "record_mode", "remark",
                "thumbnail_enabled", "translation_enabled", "live_title", 
                "translated_title", "last_live_title", "cached_translated_title"
            ]
            
            # 定义默认值
            default_values = {
                "rec_id": "",
                "media_type": "video",
                "url": "",
                "streamer_name": "",
                "record_format": "MP4",
                "quality": "OD",
                "segment_record": True,
                "segment_time": "1800",
                "monitor_status": False,
                "scheduled_recording": False,
                "scheduled_start_time": "",
                "monitor_hours": 5,
                "recording_dir": "",
                "enabled_message_push": False,
                "record_mode": "manual",
                "remark": "",
                "thumbnail_enabled": None,
                "translation_enabled": False,
                "live_title": "",
                "translated_title": None,
                "last_live_title": "",
                "cached_translated_title": ""
            }
            
            fixed_count = 0
            for recording in recordings_config:
                if not isinstance(recording, dict):
                    continue
                    
                # 检查缺失的字段
                missing_fields = []
                for field in required_fields:
                    if field not in recording:
                        missing_fields.append(field)
                
                if missing_fields:
                    logger.info(f"发现录制项中缺失的字段: {missing_fields}")
                    
                    # 添加缺失的字段，保持原有顺序
                    for field in missing_fields:
                        recording[field] = default_values[field]
                    
                    fixed_count += len(missing_fields)
            
            # 如果配置被初始化为空列表，或者有修复的字段，则保存
            if recordings_config == [] and fixed_count == 0:
                # 保存空列表格式
                with open(self.recordings_config_path, "w", encoding="utf-8") as file:
                    json.dump(recordings_config, file, ensure_ascii=False, indent=4)
                logger.debug("recordings.json已初始化为空列表格式")
            elif fixed_count > 0:
                # 保存修复后的配置
                with open(self.recordings_config_path, "w", encoding="utf-8") as file:
                    json.dump(recordings_config, file, ensure_ascii=False, indent=4)
                logger.info(f"已修复recordings.json中{fixed_count}个缺失的字段")
            else:
                logger.debug("recordings.json字段完整，无需修复")
                
        except Exception as e:
            logger.error(f"修复recordings.json时发生错误: {e}")
