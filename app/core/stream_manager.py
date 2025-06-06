import asyncio
import os
import re
import shutil
import subprocess
import time
from datetime import datetime
from typing import Any

from ..models.recording_status_model import RecordingStatus
from ..models.video_quality_model import VideoQuality
from ..process_manager import BackgroundService
from ..utils import utils
from ..utils.logger import logger
from . import ffmpeg_builders, platform_handlers
from .platform_handlers import StreamData


class LiveStreamRecorder:
    DEFAULT_SEGMENT_TIME = "1800"  #默认分段时间
    DEFAULT_SAVE_FORMAT = "ts"  #默认保存格式
    DEFAULT_QUALITY = VideoQuality.OD  #默认录制质量
    VALID_SAVE_FORMATS = ["ts", "flv", "mkv", "mov", "mp4", "mp3", "m4a"]   #有效录制格式列表

    def __init__(self, app, recording, recording_info):
        self.app = app
        self.settings = app.settings
        self.recording = recording
        self.recording_info = recording_info
        self.subprocess_start_info = app.subprocess_start_up_info

        self.user_config = self.settings.user_config
        self.account_config = self.settings.accounts_config
        self.platform_key = self._get_info("platform_key")
        self.cookies = self.settings.cookies_config.get(self.platform_key)

        self.platform = self._get_info("platform")
        self.live_url = self._get_info("live_url")
        self.output_dir = self._get_info("output_dir")
        self.segment_record = self._get_info("segment_record", default=False)
        
        # 验证并设置分段时间
        segment_time = self._get_info("segment_time")
        self.segment_time = self.validate_segment_time(segment_time)
        
        self.quality = self._get_info("quality", default=self.DEFAULT_QUALITY)
        
        # 验证并设置保存格式
        save_format = self._get_info("save_format", default=self.DEFAULT_SAVE_FORMAT)
        self.save_format = self.validate_save_format(save_format)
        
        # 配置代理
        self.proxy = self.configure_proxy()
        
        os.makedirs(self.output_dir, exist_ok=True)
        self.app.language_manager.add_observer(self)
        self._ = {}
        self.load()

    def load(self):
        language = self.app.language_manager.language
        for key in ("recording_manager", "stream_manager"):
            self._.update(language.get(key, {}))

    def _get_info(self, key: str, default: Any = None):
        return self.recording_info.get(key, default) or default

    def should_use_proxy(self) -> bool:
        """
        判断是否应该使用代理
        """
        default_proxy_platform = self.user_config.get("default_platform_with_proxy", "")
        proxy_list = default_proxy_platform.replace("，", ",").replace(" ", "").split(",")
        
        should_use = self.user_config.get("enable_proxy") and self.platform_key in proxy_list
        logger.info(f"代理检查 - 平台: {self.platform_key}, 是否启用代理: {should_use}")
        logger.info(f"代理检查 - 代理平台列表: {proxy_list}")
        return should_use

    def configure_proxy(self) -> str | None:
        """
        配置并返回代理地址，如果不应该使用代理则返回None
        """
        if not self.should_use_proxy():
            logger.info(f"代理配置 - 平台 {self.platform_key} 不需要使用代理")
            return None
            
        proxy_address = self.user_config.get("proxy_address")
        logger.info(f"代理配置 - 尝试使用代理地址: {proxy_address}")
        
        if not self.validate_proxy_address(proxy_address):
            logger.warning(f"代理配置 - 无效的代理地址: {proxy_address}，将不使用代理")
            return None
            
        logger.info(f"代理配置 - 成功配置代理: {proxy_address}")
        return proxy_address
    
    def validate_proxy_address(self, proxy_address: str | None) -> bool:
        """
        验证代理地址是否有效
        """
        if not proxy_address:
            logger.warning("代理验证 - 代理地址为空")
            return False
            
        # 简单验证代理地址格式
        proxy_pattern = re.compile(r'^(http|https|socks5)://[\w\-\.]+(\:\d+)?$')
        is_valid = bool(proxy_pattern.match(proxy_address))
        logger.info(f"代理验证 - 地址: {proxy_address}, 格式是否有效: {is_valid}")
        
        return is_valid
        
    def validate_save_format(self, format_name: str | None) -> str:
        """
        验证并返回有效的保存格式
        """
        logger.info(f"格式验证 - 输入格式: {format_name}")
        
        if not format_name:
            logger.warning(f"格式验证 - 未指定保存格式，使用默认格式: {self.DEFAULT_SAVE_FORMAT}")
            return self.DEFAULT_SAVE_FORMAT
            
        format_name = format_name.lower()
        if format_name not in self.VALID_SAVE_FORMATS:
            logger.warning(f"格式验证 - 无效的保存格式: {format_name}，使用默认格式: {self.DEFAULT_SAVE_FORMAT}")
            
            # 如果是从录制信息中获取的格式无效，则更新录制信息
            if self.recording and hasattr(self.recording, "record_format"):
                logger.info(f"格式验证 - 更新录制项 {self.recording.rec_id} 的保存格式为: {self.DEFAULT_SAVE_FORMAT}")
                self.recording.record_format = self.DEFAULT_SAVE_FORMAT
                self.app.page.run_task(self.app.record_manager.persist_recordings)
            
            # 如果是从用户配置中获取的格式无效，则更新用户配置
            recording_info_format = self.recording_info.get("save_format")
            if recording_info_format == format_name:
                logger.info(f"格式验证 - 更新录制信息中的保存格式为: {self.DEFAULT_SAVE_FORMAT}")
                self.recording_info["save_format"] = self.DEFAULT_SAVE_FORMAT
            
            # 检查是否是从用户配置文件中读取的无效格式
            if self.user_config.get("video_format", "").lower() == format_name:
                logger.info(f"格式验证 - 更新用户配置中的视频格式为: {self.DEFAULT_SAVE_FORMAT.upper()}")
                self.user_config["video_format"] = self.DEFAULT_SAVE_FORMAT.upper()
                # 异步保存用户配置
                self.app.page.run_task(self.app.config_manager.save_user_config, self.user_config)
                
                # 更新所有录制卡片的格式显示
                self.app.page.run_task(self.update_all_recording_formats)
            
            return self.DEFAULT_SAVE_FORMAT
            
        logger.info(f"格式验证 - 使用有效格式: {format_name}")
        return format_name
        
    def validate_segment_time(self, segment_time: str | None) -> str:
        """
        验证并返回有效的分段时间
        """
        logger.info(f"分段时间验证 - 输入时间: {segment_time}")
        
        if not segment_time:
            logger.info(f"分段时间验证 - 未指定分段时间，使用默认值: {self.DEFAULT_SEGMENT_TIME}")
            return self.DEFAULT_SEGMENT_TIME
            
        try:
            time_value = int(segment_time)
            if time_value <= 0:
                logger.warning(f"分段时间验证 - 分段时间必须为正数，输入值: {time_value}，使用默认值: {self.DEFAULT_SEGMENT_TIME}")
                
                # 如果是从录制信息中获取的分段时间无效，则更新录制信息
                if self.recording and hasattr(self.recording, "segment_time"):
                    logger.info(f"分段时间验证 - 更新录制项 {self.recording.rec_id} 的分段时间为: {self.DEFAULT_SEGMENT_TIME}")
                    self.recording.segment_time = self.DEFAULT_SEGMENT_TIME
                    self.app.page.run_task(self.app.record_manager.persist_recordings)
                
                # 如果是从用户配置中获取的分段时间无效，则更新用户配置
                recording_info_segment_time = self.recording_info.get("segment_time")
                if recording_info_segment_time == segment_time:
                    logger.info(f"分段时间验证 - 更新录制信息中的分段时间为: {self.DEFAULT_SEGMENT_TIME}")
                    self.recording_info["segment_time"] = self.DEFAULT_SEGMENT_TIME
                
                # 检查是否是从用户配置文件中读取的无效分段时间
                if self.user_config.get("video_segment_time") == segment_time:
                    logger.info(f"分段时间验证 - 更新用户配置中的分段时间为: {self.DEFAULT_SEGMENT_TIME}")
                    self.user_config["video_segment_time"] = self.DEFAULT_SEGMENT_TIME
                    # 异步保存用户配置
                    self.app.page.run_task(self.app.config_manager.save_user_config, self.user_config)
                    
                    # 更新所有录制卡片的分段时间显示
                    self.app.page.run_task(self.update_all_segment_times)
                
                return self.DEFAULT_SEGMENT_TIME
                
            logger.info(f"分段时间验证 - 使用有效值: {time_value}")
            return str(time_value)
        except (ValueError, TypeError):
            logger.warning(f"分段时间验证 - 无效的分段时间格式: {segment_time}，使用默认值: {self.DEFAULT_SEGMENT_TIME}")
            
            # 如果是从录制信息中获取的分段时间无效，则更新录制信息
            if self.recording and hasattr(self.recording, "segment_time"):
                logger.info(f"分段时间验证 - 更新录制项 {self.recording.rec_id} 的分段时间为: {self.DEFAULT_SEGMENT_TIME}")
                self.recording.segment_time = self.DEFAULT_SEGMENT_TIME
                self.app.page.run_task(self.app.record_manager.persist_recordings)
            
            # 如果是从用户配置中获取的分段时间无效，则更新用户配置
            recording_info_segment_time = self.recording_info.get("segment_time")
            if recording_info_segment_time == segment_time:
                logger.info(f"分段时间验证 - 更新录制信息中的分段时间为: {self.DEFAULT_SEGMENT_TIME}")
                self.recording_info["segment_time"] = self.DEFAULT_SEGMENT_TIME
            
            # 检查是否是从用户配置文件中读取的无效分段时间
            if self.user_config.get("video_segment_time") == segment_time:
                logger.info(f"分段时间验证 - 更新用户配置中的分段时间为: {self.DEFAULT_SEGMENT_TIME}")
                self.user_config["video_segment_time"] = self.DEFAULT_SEGMENT_TIME
                # 异步保存用户配置
                self.app.page.run_task(self.app.config_manager.save_user_config, self.user_config)
                
                # 更新所有录制卡片的分段时间显示
                self.app.page.run_task(self.update_all_segment_times)
            
            return self.DEFAULT_SEGMENT_TIME

    def _get_filename(self, stream_info: StreamData) -> str:
        live_title = None
        stream_info.title = utils.clean_name(stream_info.title, None)
        if self.user_config.get("filename_includes_title") and stream_info.title:
            stream_info.title = self._clean_and_truncate_title(stream_info.title)
            live_title = stream_info.title

        if self.recording.streamer_name and self.recording.streamer_name != self._["live_room"]:
            stream_info.anchor_name = self.recording.streamer_name
        else:
            stream_info.anchor_name = utils.clean_name(stream_info.anchor_name, self._["live_room"])

        now = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
        full_filename = "_".join([i for i in (stream_info.anchor_name, live_title, now) if i])
        return full_filename

    def _get_output_dir(self, stream_info: StreamData) -> str:
        if self.recording.recording_dir and self.user_config.get("folder_name_time"):
            current_date = datetime.today().strftime("%Y-%m-%d")
            if current_date not in self.recording.recording_dir:
                self.recording.recording_dir = None
                
        if self.recording.recording_dir:
            return self.recording.recording_dir

        now = datetime.today().strftime("%Y-%m-%d_%H-%M-%S")
        output_dir = self.output_dir.rstrip("/").rstrip("\\")
        if self.user_config.get("folder_name_platform"):
            output_dir = os.path.join(output_dir, stream_info.platform)
        if self.user_config.get("folder_name_author"):
            output_dir = os.path.join(output_dir, stream_info.anchor_name)
        if self.user_config.get("folder_name_time"):
            output_dir = os.path.join(output_dir, now[:10])
        if self.user_config.get("folder_name_title") and stream_info.title:
            live_title = self._clean_and_truncate_title(stream_info.title)
            if self.user_config.get("folder_name_time"):
                output_dir = os.path.join(output_dir, f"{live_title}_{stream_info.anchor_name}")
            else:
                output_dir = os.path.join(output_dir, f"{now[:10]}_{live_title}")
        os.makedirs(output_dir, exist_ok=True)
        self.recording.recording_dir = output_dir
        self.app.page.run_task(self.app.record_manager.persist_recordings)
        return output_dir

    def _get_save_path(self, filename: str) -> str:
        suffix = self.save_format
        suffix = "_%03d." + suffix if self.segment_record and self.save_format != "flv" else "." + suffix
        save_file_path = os.path.join(self.output_dir, filename + suffix).replace(" ", "_")
        return save_file_path.replace("\\", "/")

    @staticmethod
    def _clean_and_truncate_title(title: str) -> str | None:
        if not title:
            return None
        cleaned_title = title[:30].replace("，", ",").replace(" ", "")
        return cleaned_title

    def _get_record_url(self, url: str):
        http_record_list = ["shopee"]
        if self.platform_key in http_record_list:
            url = url.replace("https://", "http://")
        if self.user_config.get("force_https_recording") and url.startswith("http://"):
            url = url.replace("http://", "https://")
        return url

    async def fetch_stream(self) -> StreamData:
        logger.info(f"Live URL: {self.live_url}")
        logger.info(f"Use Proxy: {self.proxy or None}")
        
        if self.recording is not None:
            self.recording.use_proxy = bool(self.proxy)
            
        handler = platform_handlers.get_platform_handler(
            live_url=self.live_url,
            proxy=self.proxy,
            cookies=self.cookies,
            record_quality=self.quality,
            platform=self.platform,
            username=self.account_config.get(self.platform_key, {}).get("username"),
            password=self.account_config.get(self.platform_key, {}).get("password"),
            account_type=self.account_config.get(self.platform_key, {}).get("account_type")
        )
        if handler is None:
            lang_code = getattr(self.app, "language_code", "zh_CN").lower()
            logger.info(f"当前语言环境: {lang_code}")
            if not lang_code or "zh" in lang_code:
                msg = f"未找到适配的直播平台处理器: live_url={self.live_url}, platform={self.platform}, platform_key={self.platform_key}"
            else:
                msg = f"No suitable live platform handler found: live_url={self.live_url}, platform={self.platform}, platform_key={self.platform_key}"
            logger.debug(msg)
            
            if self.recording is not None:
                self.recording.is_checking = False
                
            return None
        stream_info = await handler.get_stream_info(self.live_url)
        
        if self.recording is not None:
            self.recording.is_checking = False
            
        return stream_info

    async def start_recording(self, stream_info: StreamData):
        """
        Construct ffmpeg recording parameters and start recording
        """

        filename = self._get_filename(stream_info)
        self.output_dir = self._get_output_dir(stream_info)
        save_path = self._get_save_path(filename)
        logger.info(f"Save Path: {save_path}")
        self.recording.recording_dir = os.path.dirname(save_path)
        os.makedirs(self.recording.recording_dir, exist_ok=True)
        record_url = self._get_record_url(stream_info.record_url)

        ffmpeg_builder = ffmpeg_builders.create_builder(
            self.save_format,
            record_url=record_url,
            proxy=self.proxy,
            segment_record=self.segment_record,
            segment_time=self.segment_time,
            full_path=save_path,
            headers=self.get_headers_params(record_url, self.platform_key)
        )
        ffmpeg_command = ffmpeg_builder.build_command()
        self.app.page.run_task(
            self.start_ffmpeg,
            stream_info.anchor_name,
            self.live_url,
            stream_info.record_url,
            ffmpeg_command,
            self.save_format,
            self.user_config.get("custom_script_command")
        )

    async def start_ffmpeg(
        self,
        record_name: str,
        live_url: str,
        record_url: str,
        ffmpeg_command: list,
        save_type: str,
        script_command: str | None = None
    ) -> bool:
        """
        The child process executes ffmpeg for recording
        """

        try:
            save_file_path = ffmpeg_command[-1]

            process = await asyncio.create_subprocess_exec(
                *ffmpeg_command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                startupinfo=self.subprocess_start_info
            )

            self.app.add_ffmpeg_process(process)
            self.recording.status_info = RecordingStatus.RECORDING
            self.recording.record_url = record_url
            logger.info(f"Recording in Progress: {live_url}")
            logger.log("STREAM", f"Recording Stream URL: {record_url}")
            while True:
                if not self.recording.recording or not self.app.recording_enabled:
                    logger.info(f"Preparing to End Recording: {live_url}")

                    if os.name == "nt":
                        if process.stdin:
                            process.stdin.write(b"q")
                            await process.stdin.drain()
                    else:
                        # import signal
                        # process.send_signal(signal.SIGINT)
                        process.terminate()

                    if process.stdin:
                        process.stdin.close()

                    try:
                        await asyncio.wait_for(process.wait(), timeout=10.0)
                    except asyncio.TimeoutError:
                        process.kill()
                        await process.wait()

                if process.returncode is not None:
                    logger.info(f"Exit loop recording (normal 0 | abnormal 1): code={process.returncode}, {live_url}")
                    break

                await asyncio.sleep(1)

            return_code = process.returncode
            safe_return_code = [0, 255]
            stdout, stderr = await process.communicate()
            if return_code not in safe_return_code and stderr:
                logger.error(f"FFmpeg Stderr Output: {str(stderr.decode()).splitlines()[0]}")
                self.recording.status_info = RecordingStatus.RECORDING_ERROR

                try:
                    self.app.record_manager.stop_recording(self.recording)
                    await self.app.record_card_manager.update_card(self.recording)
                    self.app.page.pubsub.send_others_on_topic("update", self.recording)
                    await self.app.snack_bar.show_snack_bar(
                        record_name + " " + self._["record_stream_error"], duration=2000
                    )
                except Exception as e:
                    logger.debug(f"Failed to update UI: {e}")

            if return_code in safe_return_code:
                if self.recording.monitor_status:
                    self.recording.status_info = RecordingStatus.MONITORING
                    display_title = self.recording.title
                else:
                    self.recording.status_info = RecordingStatus.STOPPED_MONITORING
                    display_title = self.recording.display_title

                self.recording.live_title = None
                if not self.recording.recording:
                    logger.success(f"Live recording has stopped: {record_name}")
                else:
                    self.recording.recording = False
                    logger.success(f"Live recording completed: {record_name}")

                try:
                    self.recording.update({"display_title": display_title})
                    await self.app.record_card_manager.update_card(self.recording)
                    self.app.page.pubsub.send_others_on_topic("update", self.recording)
                    if self.app.recording_enabled and process in self.app.process_manager.ffmpeg_processes:
                        self.app.page.run_task(self.app.record_manager.check_if_live, self.recording)
                    else:
                        self.recording.status_info = RecordingStatus.NOT_RECORDING_SPACE
                except Exception as e:
                    logger.debug(f"Failed to update UI: {e}")

                if self.user_config.get("convert_to_mp4") and self.save_format == "ts":
                    if self.segment_record:
                        file_paths = utils.get_file_paths(os.path.dirname(save_file_path))
                        prefix = os.path.basename(save_file_path).rsplit("_", maxsplit=1)[0]
                        for path in file_paths:
                            if prefix in path:
                                try:
                                    self.app.page.run_task(
                                        self.converts_mp4, path, self.user_config["delete_original"]
                                    )
                                except Exception as e:
                                    logger.error(f"Failed to convert video: {e}")
                                    await self.converts_mp4(path, self.user_config["delete_original"])
                    else:
                        try:
                            self.app.page.run_task(
                                self.converts_mp4, save_file_path, self.user_config["delete_original"]
                            )
                        except Exception as e:
                            logger.error(f"Failed to convert video: {e}")
                            await self.converts_mp4(save_file_path, self.user_config["delete_original"])

                if self.user_config.get("execute_custom_script") and script_command:
                    logger.info("Prepare a direct script in the background")
                    try:
                        self.app.page.run_task(
                            self.custom_script_execute,
                            script_command,
                            record_name,
                            save_file_path,
                            save_type,
                            self.segment_record,
                            self.user_config.get("convert_to_mp4")
                        )
                        logger.success("Successfully added script execution")
                    except Exception as e:
                        logger.error(f"Failed to execute custom script: {e}")
                        await self.custom_script_execute(
                            script_command,
                            record_name,
                            save_file_path,
                            save_type,
                            self.segment_record,
                            self.user_config.get("convert_to_mp4")
                        )

        except Exception as e:
            logger.error(f"An error occurred during the subprocess execution: {e}")
            return False
        finally:
            self.recording.record_url = None

        return True

    async def converts_mp4(self, converts_file_path: str, is_original_delete: bool = True) -> None:
        """Asynchronous transcoding method, can be added to the background service to continue execution"""
        if not self.app.recording_enabled:
            logger.info(f"Application is closing, adding transcoding task to background service: {converts_file_path}")
            BackgroundService.get_instance().add_task(
                self.converts_mp4_sync, converts_file_path, is_original_delete
            )
            return
            
        # Otherwise, execute transcoding normally
        await self._do_converts_mp4(converts_file_path, is_original_delete)
    
    def converts_mp4_sync(self, converts_file_path: str, is_original_delete: bool = True) -> None:
        """Synchronous version of the transcoding method, used for background service"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._do_converts_mp4(converts_file_path, is_original_delete))
        finally:
            loop.close()
    
    async def _do_converts_mp4(self, converts_file_path: str, is_original_delete: bool = True) -> None:
        """Actual execution method for transcoding"""
        converts_success = False
        save_path = None
        try:
            converts_file_path = converts_file_path.replace("\\", "/")
            if os.path.exists(converts_file_path) and os.path.getsize(converts_file_path) > 0:
                save_path = converts_file_path.rsplit(".", maxsplit=1)[0] + ".mp4"
                _output = subprocess.check_output(
                    [
                        "ffmpeg",
                        "-i", converts_file_path,
                        "-c:v", "copy",
                        "-c:a", "copy",
                        "-f", "mp4",
                        save_path
                    ],
                    stderr=subprocess.STDOUT,
                    startupinfo=self.subprocess_start_info,
                )

                converts_success = True
                logger.info(f"Video transcoding completed: {save_path}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Video transcoding failed! Error message: {e.output.decode()}")

        try:
            if converts_success:
                if is_original_delete:
                    time.sleep(1)
                    if os.path.exists(converts_file_path):
                        os.remove(converts_file_path)
                    logger.info(f"Delete Original File: {converts_file_path}")
                else:
                    converts_dir = f"{os.path.dirname(save_path)}/original"
                    os.makedirs(converts_dir, exist_ok=True)
                    shutil.move(converts_file_path, converts_dir)
                    logger.info(f"Move Transcoding Files: {converts_file_path}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Error occurred during conversion: {e}")
        except Exception as e:
            logger.error(f"An unknown error occurred: {e}")

    async def custom_script_execute(
        self,
        script_command: str,
        record_name: str,
        save_file_path: str,
        save_type: str,
        split_video_by_time: bool,
        converts_to_mp4: bool
    ):
        from ..process_manager import BackgroundService
        
        if "python" in script_command:
            params = [
                f'--record_name "{record_name}"',
                f'--save_file_path "{save_file_path}"',
                f"--save_type {save_type}--split_video_by_time {split_video_by_time}",
                f"--converts_to_mp4 {converts_to_mp4}"
            ]
        else:
            params = [
                f'"{record_name.split(" ", maxsplit=1)[-1]}"',
                f'"{save_file_path}"',
                save_type,
                f"split_video_by_time: {split_video_by_time}",
                f"converts_to_mp4: {converts_to_mp4}"
            ]
        script_command = script_command.strip() + " " + " ".join(params)
        
        if not self.app.recording_enabled:
            logger.info("Application is closing, adding script execution task to background service")
            BackgroundService.get_instance().add_task(self.run_script_sync, script_command)
        else:
            self.app.page.run_task(self.run_script_async, script_command)
            
        logger.success("Script command execution initiated!")
        
    def run_script_sync(self, command: str) -> None:
        """Synchronous version of the script execution method, used for background service"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.run_script_async(command))
        finally:
            loop.close()

    async def run_script_async(self, command: str) -> None:
        try:
            process = await asyncio.create_subprocess_exec(
                *command.split(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                startupinfo=self.subprocess_start_info,
                text=True
            )

            stdout, stderr = await process.communicate()

            if stdout:
                logger.info(stdout.splitlines()[0])
            if stderr:
                logger.error(stderr.splitlines()[0])

            if process.returncode != 0:
                logger.info(f"Custom Script process exited with return code {process.returncode}")

        except PermissionError:
            logger.error(
                "Script has no execution permission!, If it is a Linux environment, "
                "please first execute: chmod+x your_script.sh to grant script executable permission"
            )
        except OSError:
            logger.error("Please add `#!/bin/bash` at the beginning of your bash script file.")
        except Exception as e:
            logger.error(f"An error occurred: {e}")

    @staticmethod
    def get_headers_params(live_url, platform_key):
        live_domain = "/".join(live_url.split("/")[0:3])
        record_headers = {
            "pandalive": "origin:https://www.pandalive.co.kr",
            "winktv": "origin:https://www.winktv.co.kr",
            "popkontv": "origin:https://www.popkontv.com",
            "flextv": "origin:https://www.flextv.co.kr",
            "qiandurebo": "referer:https://qiandurebo.com",
            "17live": "referer:https://17.live/en/live/6302408",
            "lang": "referer:https://www.lang.live",
            "shopee": "origin:" + live_domain
        }
        return record_headers.get(platform_key)

    async def update_all_recording_formats(self):
        """
        当用户配置中的默认录制格式被修改时，更新所有录制卡片的显示
        """
        logger.info("正在更新所有录制卡片的格式显示...")
        
        # 等待一小段时间确保配置已保存
        await asyncio.sleep(0.5)
        
        # 获取当前页面和录制卡片管理器
        home_page = self.app.current_page
        if not home_page or not hasattr(self.app, "record_card_manager"):
            logger.warning("无法更新录制卡片：主页或录制卡片管理器不可用")
            return
            
        # 更新所有录制项的格式
        default_format = self.user_config.get("video_format", self.DEFAULT_SAVE_FORMAT).upper()
        for recording in self.app.record_manager.recordings:
            # 只更新那些使用默认格式的录制项
            if not recording.record_format or recording.record_format.lower() not in self.VALID_SAVE_FORMATS:
                recording.record_format = default_format
                # 更新卡片显示
                await self.app.record_card_manager.update_card(recording)
                
        # 保存更新后的录制项
        self.app.page.run_task(self.app.record_manager.persist_recordings)
        
        # 如果有刷新按钮功能，触发一次刷新
        if hasattr(home_page, "refresh_cards_on_click"):
            self.app.page.run_task(home_page.refresh_cards_on_click, None)
            
        logger.info(f"已更新所有录制卡片的默认格式为: {default_format}")

    async def update_all_segment_times(self):
        """
        当用户配置中的默认分段时间被修改时，更新所有录制卡片的显示
        """
        logger.info("正在更新所有录制卡片的分段时间显示...")
        
        # 等待一小段时间确保配置已保存
        await asyncio.sleep(0.5)
        
        # 获取当前页面和录制卡片管理器
        home_page = self.app.current_page
        if not home_page or not hasattr(self.app, "record_card_manager"):
            logger.warning("无法更新录制卡片：主页或录制卡片管理器不可用")
            return
            
        # 更新所有录制项的分段时间
        default_segment_time = self.user_config.get("video_segment_time", self.DEFAULT_SEGMENT_TIME)
        for recording in self.app.record_manager.recordings:
            # 只更新那些使用默认分段时间或无效分段时间的录制项
            try:
                time_value = int(recording.segment_time)
                if time_value <= 0:
                    recording.segment_time = default_segment_time
                    # 更新卡片显示
                    await self.app.record_card_manager.update_card(recording)
            except (ValueError, TypeError):
                recording.segment_time = default_segment_time
                # 更新卡片显示
                await self.app.record_card_manager.update_card(recording)
                
        # 保存更新后的录制项
        self.app.page.run_task(self.app.record_manager.persist_recordings)
        
        # 如果有刷新按钮功能，触发一次刷新
        if hasattr(home_page, "refresh_cards_on_click"):
            self.app.page.run_task(home_page.refresh_cards_on_click, None)
            
        logger.info(f"已更新所有录制卡片的默认分段时间为: {default_segment_time}")
