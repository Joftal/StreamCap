import asyncio
import threading
from datetime import datetime, timedelta

from ..messages.message_pusher import MessagePusher
from ..models.recording_model import Recording
from ..models.recording_status_model import RecordingStatus
from ..utils import utils
from ..utils.logger import logger
from .platform_handlers import get_platform_info
from .stream_manager import LiveStreamRecorder


class GlobalRecordingState:
    recordings = []
    lock = threading.Lock()


class RecordingManager:
    def __init__(self, app):
        self.app = app
        self.settings = app.settings
        self.periodic_task_started = False
        self.loop_time_seconds = None
        self.app.language_manager.add_observer(self)
        self.load_recordings()
        self._ = {}
        self.load()
        self.initialize_dynamic_state()

    @property
    def recordings(self):
        return GlobalRecordingState.recordings

    @recordings.setter
    def recordings(self, value):
        raise AttributeError("Please use add_recording/update_recording methods to modify data")

    def load(self):
        language = self.app.language_manager.language
        for key in ("recording_manager", "video_quality"):
            self._.update(language.get(key, {}))

    def load_recordings(self):
        """Load recordings from a JSON file into objects."""
        recordings_data = self.app.config_manager.load_recordings_config()
        if not GlobalRecordingState.recordings:
            GlobalRecordingState.recordings = [Recording.from_dict(rec) for rec in recordings_data]
        logger.info(f"Live Recordings: Loaded {len(self.recordings)} items")

    def initialize_dynamic_state(self):
        """Initialize dynamic state for all recordings."""
        loop_time_seconds = self.settings.user_config.get("loop_time_seconds")
        self.loop_time_seconds = int(loop_time_seconds or 300)
        for recording in self.recordings:
            recording.loop_time_seconds = self.loop_time_seconds
            recording.update_title(self._[recording.quality])

    async def add_recording(self, recording):
        with GlobalRecordingState.lock:
            GlobalRecordingState.recordings.append(recording)
            await self.persist_recordings()

    async def remove_recording(self, recording: Recording):
        with GlobalRecordingState.lock:
            GlobalRecordingState.recordings.remove(recording)
            await self.persist_recordings()

    async def clear_all_recordings(self):
        with GlobalRecordingState.lock:
            GlobalRecordingState.recordings.clear()
            await self.persist_recordings()

    async def persist_recordings(self):
        """Persist recordings to a JSON file."""
        data_to_save = [rec.to_dict() for rec in self.recordings]
        await self.app.config_manager.save_recordings_config(data_to_save)

    async def update_recording_card(self, recording: Recording, updated_info: dict):
        """Update an existing recording object and persist changes to a JSON file."""
        if recording:
            recording.update(updated_info)
            self.app.page.run_task(self.persist_recordings)

    @staticmethod
    async def _update_recording(
        recording: Recording, monitor_status: bool, display_title: str, status_info: str, selected: bool
    ):
        attrs_update = {
            "monitor_status": monitor_status,
            "display_title": display_title,
            "status_info": status_info,
            "selected": selected,
        }
        for attr, value in attrs_update.items():
            setattr(recording, attr, value)

    async def start_monitor_recording(self, recording: Recording, auto_save: bool = True):
        """
        Start monitoring a single recording if it is not already being monitored.
        """
        if not recording.monitor_status:
            await self._update_recording(
                recording=recording,
                monitor_status=True,
                display_title=recording.title,
                status_info=RecordingStatus.MONITORING,
                selected=False,
            )
            self.app.page.run_task(self.check_if_live, recording)
            self.app.page.run_task(self.app.record_card_manager.update_card, recording)
            self.app.page.pubsub.send_others_on_topic("update", recording)
            if auto_save:
                self.app.page.run_task(self.persist_recordings)

    async def stop_monitor_recording(self, recording: Recording, auto_save: bool = True):
        """
        Stop monitoring a single recording if it is currently being monitored.
        """
        if recording.monitor_status:
            await self._update_recording(
                recording=recording,
                monitor_status=False,
                display_title=f"[{self._['monitor_stopped']}] {recording.title}",
                status_info=RecordingStatus.STOPPED_MONITORING,
                selected=False,
            )
            self.stop_recording(recording)
            
            # 手动停止监控时，重置通知状态和was_recording标志
            # 这样下次开始监控时可以再次发送通知
            recording.notification_sent = False
            if hasattr(recording, 'was_recording'):
                recording.was_recording = False
            logger.info(f"手动停止监控，重置通知状态: {recording.streamer_name}")
            
            self.app.page.run_task(self.app.record_card_manager.update_card, recording)
            self.app.page.pubsub.send_others_on_topic("update", recording)
            if auto_save:
                self.app.page.run_task(self.persist_recordings)

    async def start_monitor_recordings(self):
        """
        Start monitoring multiple recordings based on user selection or all recordings if none are selected.
        """
        selected_recordings = await self.get_selected_recordings()
        pre_start_monitor_recordings = selected_recordings if selected_recordings else self.recordings
        cards_obj = self.app.record_card_manager.cards_obj
        for recording in pre_start_monitor_recordings:
            if cards_obj[recording.rec_id]["card"].visible:
                self.app.page.run_task(self.start_monitor_recording, recording, auto_save=False)
        self.app.page.run_task(self.persist_recordings)
        logger.info(f"Batch Start Monitor Recordings: {[i.rec_id for i in pre_start_monitor_recordings]}")

    async def stop_monitor_recordings(self, selected_recordings: list[Recording | None] | None = None):
        """
        Stop monitoring multiple recordings based on user selection or all recordings if none are selected.
        """
        if not selected_recordings:
            selected_recordings = await self.get_selected_recordings()
        pre_stop_monitor_recordings = selected_recordings or self.recordings
        cards_obj = self.app.record_card_manager.cards_obj
        for recording in pre_stop_monitor_recordings:
            if cards_obj[recording.rec_id]["card"].visible:
                self.app.page.run_task(self.stop_monitor_recording, recording, auto_save=False)
        self.app.page.run_task(self.persist_recordings)
        logger.info(f"Batch Stop Monitor Recordings: {[i.rec_id for i in pre_stop_monitor_recordings]}")

    async def get_selected_recordings(self):
        return [recording for recording in self.recordings if recording.selected]

    async def remove_recordings(self, recordings: list[Recording]):
        """Remove a recording from the list and update the JSON file."""
        for recording in recordings:
            if recording in self.recordings:
                await self.remove_recording(recording)
                logger.info(f"Delete Items: {recording.rec_id}-{recording.streamer_name}")

    def find_recording_by_id(self, rec_id: str):
        """Find a recording by its ID (hash of dict representation)."""
        for rec in self.recordings:
            if rec.rec_id == rec_id:
                return rec
        return None

    async def check_all_live_status(self):
        """Check the live status of all recordings and update their display titles."""
        for recording in self.recordings:
            if recording.monitor_status and not recording.recording:
                is_exceeded = utils.is_time_interval_exceeded(recording.detection_time, recording.loop_time_seconds)
                if not recording.detection_time or is_exceeded:
                    self.app.page.run_task(self.check_if_live, recording)

    async def setup_periodic_live_check(self, interval: int = 180):
        """Set up a periodic task to check live status."""

        async def periodic_check():
            while True:
                await asyncio.sleep(interval)
                await self.check_free_space()
                if self.app.recording_enabled:
                    await self.check_all_live_status()

        if not self.periodic_task_started:
            self.periodic_task_started = True
            await periodic_check()

    async def check_if_live(self, recording: Recording):
        """Check if the live stream is available, fetch stream data and update is_live status."""

        if recording.recording:
            return

        if not recording.monitor_status:
            recording.display_title = f"[{self._['monitor_stopped']}] {recording.title}"
            recording.status_info = RecordingStatus.STOPPED_MONITORING

        elif not recording.is_checking:
            recording.status_info = RecordingStatus.STATUS_CHECKING
            recording.detection_time = datetime.now().time()
            if recording.scheduled_recording and recording.scheduled_start_time and recording.monitor_hours:
                scheduled_time_range = await self.get_scheduled_time_range(
                    recording.scheduled_start_time, recording.monitor_hours)
                recording.scheduled_time_range = scheduled_time_range
                in_scheduled = utils.is_current_time_within_range(scheduled_time_range)
                if not in_scheduled:
                    recording.status_info = RecordingStatus.NOT_IN_SCHEDULED_CHECK
                    logger.info(f"Skip Detection: {recording.url} not in scheduled check range {scheduled_time_range}")
                    return

            recording.is_checking = True
            platform, platform_key = get_platform_info(recording.url)

            if self.settings.user_config["language"] != "zh_CN":
                platform = platform_key

            output_dir = self.settings.get_video_save_path()
            await self.check_free_space(output_dir)
            if not self.app.recording_enabled:
                recording.is_checking = False
                recording.status_info = RecordingStatus.NOT_RECORDING_SPACE
                return

            recording_info = {
                "platform": platform,
                "platform_key": platform_key,
                "live_url": recording.url,
                "output_dir": output_dir,
                "segment_record": recording.segment_record,
                "segment_time": recording.segment_time,
                "save_format": recording.record_format,
                "quality": recording.quality,
            }

            recorder = LiveStreamRecorder(self.app, recording, recording_info)

            stream_info = await recorder.fetch_stream()
            logger.info(f"Stream Data: {stream_info}")
            if not stream_info or not stream_info.anchor_name:
                logger.error(f"Fetch stream data failed: {recording.url}")
                recording.is_checking = False
                recording.status_info = RecordingStatus.LIVE_STATUS_CHECK_ERROR
                return

            if self.settings.user_config.get("remove_emojis"):
                stream_info.anchor_name = utils.clean_name(stream_info.anchor_name, self._["live_room"])

            # 检查直播状态变化
            was_live = recording.is_live
            recording.is_live = stream_info.is_live
            
            # 如果直播状态从在线变为离线，重置通知状态
            if was_live and not recording.is_live:
                recording.notification_sent = False
                logger.info(f"直播已结束，重置通知状态: {recording.streamer_name}")
                
            is_record = True
            if recording.is_live and not recording.recording:
                recording.live_title = stream_info.title
                if not recording.streamer_name or recording.streamer_name.strip() == self._["live_room"]:
                    recording.streamer_name = stream_info.anchor_name
                recording.title = f"{recording.streamer_name} - {self._[recording.quality]}"
                recording.display_title = f"[{self._['is_live']}] {recording.title}"

                if getattr(recording, "record_mode", "auto") == "auto":
                    recording.status_info = RecordingStatus.PREPARING_RECORDING
                    if self.settings.user_config["stream_start_notification_enabled"] or recording.enabled_message_push:
                        # 检查是否有至少一个推送渠道被启用
                        user_config = self.settings.user_config
                        bark_enabled = user_config.get("bark_enabled", False)
                        wechat_enabled = user_config.get("wechat_enabled", False)
                        dingtalk_enabled = user_config.get("dingtalk_enabled", False)
                        ntfy_enabled = user_config.get("ntfy_enabled", False)
                        telegram_enabled = user_config.get("telegram_enabled", False)
                        email_enabled = user_config.get("email_enabled", False)
                        
                        any_channel_enabled = (
                            bark_enabled or wechat_enabled or dingtalk_enabled or 
                            ntfy_enabled or telegram_enabled or email_enabled
                        )
                        
                        logger.info(f"推送渠道状态: bark={bark_enabled}, wechat={wechat_enabled}, "
                                   f"dingtalk={dingtalk_enabled}, ntfy={ntfy_enabled}, "
                                   f"telegram={telegram_enabled}, email={email_enabled}")
                        
                        # 检查是否已经发送过通知，避免重复发送
                        if any_channel_enabled and not recording.notification_sent:
                            push_content = self._["push_content"]
                            begin_push_message_text = self.settings.user_config.get("custom_stream_start_content")
                            if begin_push_message_text:
                                push_content = begin_push_message_text

                            push_at = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
                            push_content = push_content.replace("[room_name]", recording.streamer_name).replace(
                                "[time]", push_at
                            )
                            msg_title = self.settings.user_config.get("custom_notification_title").strip()
                            msg_title = msg_title or self._["status_notify"]

                            logger.info(f"自动录制模式下触发消息推送: {msg_title} - {push_content}")
                            msg_manager = MessagePusher(self.settings)
                            self.app.page.run_task(msg_manager.push_messages, msg_title, push_content)
                            # 设置通知已发送标志
                            recording.notification_sent = True
                        elif recording.notification_sent:
                            logger.info(f"已经发送过开播通知，跳过重复发送: {recording.streamer_name}")
                        else:
                            logger.info("没有启用任何推送渠道，跳过消息推送")

                        if self.settings.user_config.get("only_notify_no_record"):
                            notify_loop_time = self.settings.user_config.get("notify_loop_time")
                            recording.loop_time_seconds = int(notify_loop_time or 3600)
                            is_record = False
                            # 设置状态为"直播中（未录制）"，确保UI显示正确
                            recording.status_info = RecordingStatus.NOT_RECORDING
                        else:
                            recording.loop_time_seconds = self.loop_time_seconds

                    if is_record:
                        self.start_update(recording)
                        self.app.page.run_task(recorder.start_recording, stream_info)

                    self.app.page.run_task(self.app.record_card_manager.update_card, recording)
                    self.app.page.pubsub.send_others_on_topic("update", recording)
                else:
                    # 手动录制模式下，设置状态为"直播中（未录制）"
                    recording.status_info = RecordingStatus.NOT_RECORDING
                    
                    # 在手动模式下，当直播间处于"直播中（未录制）"状态时也触发消息推送
                    # 但要避免从"录制中"状态变为"直播中（未录制）"状态时重复发送
                    was_recording = getattr(recording, "was_recording", False)
                    
                    if self.settings.user_config["stream_start_notification_enabled"] or recording.enabled_message_push:
                        # 检查是否有至少一个推送渠道被启用
                        user_config = self.settings.user_config
                        bark_enabled = user_config.get("bark_enabled", False)
                        wechat_enabled = user_config.get("wechat_enabled", False)
                        dingtalk_enabled = user_config.get("dingtalk_enabled", False)
                        ntfy_enabled = user_config.get("ntfy_enabled", False)
                        telegram_enabled = user_config.get("telegram_enabled", False)
                        email_enabled = user_config.get("email_enabled", False)
                        
                        any_channel_enabled = (
                            bark_enabled or wechat_enabled or dingtalk_enabled or 
                            ntfy_enabled or telegram_enabled or email_enabled
                        )
                        
                        logger.info(f"推送渠道状态: bark={bark_enabled}, wechat={wechat_enabled}, "
                                  f"dingtalk={dingtalk_enabled}, ntfy={ntfy_enabled}, "
                                  f"telegram={telegram_enabled}, email={email_enabled}")
                        
                        # 检查是否已经发送过通知，避免重复发送
                        # 如果是从"录制中"状态变为"直播中（未录制）"状态，则不发送通知
                        if any_channel_enabled and not recording.notification_sent and not was_recording:
                            push_content = self._["push_content"]
                            begin_push_message_text = self.settings.user_config.get("custom_stream_start_content")
                            if begin_push_message_text:
                                push_content = begin_push_message_text

                            push_at = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
                            push_content = push_content.replace("[room_name]", recording.streamer_name).replace(
                                "[time]", push_at
                            )
                            msg_title = self.settings.user_config.get("custom_notification_title").strip()
                            msg_title = msg_title or self._["status_notify"]

                            logger.info(f"手动录制模式下直播中（未录制）状态触发消息推送: {msg_title} - {push_content}")
                            msg_manager = MessagePusher(self.settings)
                            self.app.page.run_task(msg_manager.push_messages, msg_title, push_content)
                            # 设置通知已发送标志
                            recording.notification_sent = True
                        elif recording.notification_sent:
                            logger.info(f"已经发送过开播通知，跳过重复发送: {recording.streamer_name}")
                        elif was_recording:
                            logger.info(f"从录制中状态变为直播中（未录制）状态，跳过消息推送: {recording.streamer_name}")
                        else:
                            logger.info("没有启用任何推送渠道，跳过消息推送")
                    
                    # 重置was_recording标志
                    recording.was_recording = False
                    
                    self.app.page.run_task(self.app.record_card_manager.update_card, recording)
                    self.app.page.pubsub.send_others_on_topic("update", recording)

    @staticmethod
    def start_update(recording: Recording):
        """Start the recording process."""
        if recording.is_live and not recording.recording:
            # Reset cumulative and last durations for a fresh start
            recording.update(
                {
                    "cumulative_duration": timedelta(),
                    "last_duration": timedelta(),
                    "start_time": datetime.now(),
                    "recording": True,
                }
            )
            logger.info(f"Started recording for {recording.title}")

    @staticmethod
    def stop_recording(recording: Recording):
        """Stop the recording process."""
        if recording.recording:
            if recording.start_time is not None:
                elapsed = datetime.now() - recording.start_time
                # Add the elapsed time to the cumulative duration.
                recording.cumulative_duration += elapsed
                # Update the last recorded duration.
                recording.last_duration = recording.cumulative_duration
            recording.start_time = None
            recording.recording = False
            logger.info(f"Stopped recording for {recording.title}")
            
            # 当直播结束时（而不是仅仅停止录制时），重置notification_sent标志
            # 这样下次直播开始时可以再次发送通知
            if not recording.is_live:
                recording.notification_sent = False
                logger.info(f"直播已结束，重置通知状态: {recording.streamer_name}")
            else:
                # 如果直播仍在进行中，设置was_recording标志
                # 这样在下次检测到直播状态时知道这是从"录制中"状态变为"直播中（未录制）"状态
                recording.was_recording = True
                logger.info(f"直播仍在进行中，保持通知状态，避免重复推送: {recording.streamer_name}")

    def get_duration(self, recording: Recording):
        """Get the duration of the current recording session in a formatted string."""
        if recording.recording and recording.start_time is not None:
            elapsed = datetime.now() - recording.start_time
            # If recording, add the current session time.
            total_duration = recording.cumulative_duration + elapsed
            return self._["recorded"] + " " + str(total_duration).split(".")[0]
        else:
            # If stopped, show the last recorded total duration.
            total_duration = recording.last_duration
            return str(total_duration).split(".")[0]

    async def delete_recording_cards(self, recordings: list[Recording]):
        self.app.page.run_task(self.app.record_card_manager.remove_recording_card, recordings)
        self.app.page.pubsub.send_others_on_topic('delete', recordings)
        await self.remove_recordings(recordings)
        
        # 检查是否需要切换平台视图
        home_page = self.app.current_page
        if hasattr(home_page, "current_platform_filter") and home_page.current_platform_filter != "all":
            current_platform = home_page.current_platform_filter
            
            # 检查是否还有当前平台的录制项
            remaining_items = False
            for recording in self.recordings:
                _, platform_key = get_platform_info(recording.url)
                if platform_key == current_platform:
                    remaining_items = True
                    break
            
            # 如果当前平台没有剩余录制项，自动切换到全部平台视图
            if not remaining_items:
                logger.info(f"批量删除后平台 {current_platform} 下没有剩余直播间，自动切换到全部平台视图")
                home_page.current_platform_filter = "all"
        
        # 删除后更新主页筛选区域
        if hasattr(self.app.current_page, "create_filter_area") and hasattr(self.app.current_page, "content_area"):
            self.app.current_page.content_area.controls[1] = self.app.current_page.create_filter_area()
            self.app.current_page.content_area.update()
            
            # 应用筛选
            if hasattr(self.app.current_page, "apply_filter"):
                self.app.page.run_task(self.app.current_page.apply_filter)

    async def check_free_space(self, output_dir: str | None = None):
        disk_space_limit = float(self.settings.user_config.get("recording_space_threshold"))
        output_dir = output_dir or self.settings.get_video_save_path()
        if utils.check_disk_capacity(output_dir) < disk_space_limit:
            self.app.recording_enabled = False
            logger.error(
                f"Disk space remaining is below {disk_space_limit} GB. Recording function disabled"
            )
            self.app.page.run_task(
                self.app.snack_bar.show_snack_bar,
                self._["not_disk_space_tip"],
                duration=86400,
                show_close_icon=True
            )

        else:
            self.app.recording_enabled = True

    @staticmethod
    async def get_scheduled_time_range(scheduled_start_time, monitor_hours) -> str | None:
        monitor_hours = float(monitor_hours or 5)
        if scheduled_start_time and monitor_hours:
            end_time = utils.add_hours_to_time(scheduled_start_time, monitor_hours)
            scheduled_time_range = f"{scheduled_start_time}~{end_time}"
            return scheduled_time_range

    async def get_stream_url(self, recording: Recording):
        """
        获取直播源地址，仅在已开始监控状态下可用。
        返回record_url（如m3u8/flv），如未获取到则返回None。
        """
        if not recording.monitor_status:
            return None, "未开始监控，无法获取直播源地址"
        platform, platform_key = get_platform_info(recording.url)
        output_dir = self.settings.get_video_save_path()
        recording_info = {
            "platform": platform,
            "platform_key": platform_key,
            "live_url": recording.url,
            "output_dir": output_dir,
            "segment_record": recording.segment_record,
            "segment_time": recording.segment_time,
            "save_format": recording.record_format,
            "quality": recording.quality,
        }
        recorder = LiveStreamRecorder(self.app, recording, recording_info)
        stream_info = await recorder.fetch_stream()
        if not stream_info or not getattr(stream_info, "record_url", None):
            return None, "未获取到直播源地址，可能未开播或平台暂不支持"
        return stream_info.record_url, None
