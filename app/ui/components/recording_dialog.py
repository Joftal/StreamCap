import flet as ft
import asyncio

from ...core.platform_handlers import get_platform_info
from ...models.audio_format_model import AudioFormat
from ...models.video_format_model import VideoFormat
from ...models.video_quality_model import VideoQuality
from ...utils import utils
from ...utils.logger import logger
from ...utils.room_checker import RoomChecker


class RecordingDialog:
    def __init__(self, app, on_confirm_callback=None, recording=None):
        self.app = app
        self.page = self.app.page
        self.on_confirm_callback = on_confirm_callback
        self.recording = recording
        self.app.language_manager.add_observer(self)
        self._ = {}
        self.load()

    def load(self):
        language = self.app.language_manager.language
        for key in ("recording_dialog", "home_page", "base", "video_quality", "settings_page"):
            self._.update(language.get(key, {}))

    async def show_dialog(self):
        """Show a dialog for adding or editing a recording."""
        initial_values = self.recording.to_dict() if self.recording else {}

        async def on_url_change(_):
            """Enable or disable the submit button based on whether the URL field is filled."""
            is_active = utils.is_valid_url(url_field.value.strip()) or utils.contains_url(batch_input.value.strip())
            dialog.actions[1].disabled = not is_active
            self.page.update()

        # 创建提示文本控件
        alert_text = ft.Text(
            "",
            color=ft.colors.RED_400,
            size=16,
            weight=ft.FontWeight.BOLD,
            visible=False
        )

        async def update_format_options(e):
            if e.control.value == "video":
                record_format_field.options = [ft.dropdown.Option(i) for i in VideoFormat.get_formats()]
                record_format_field.value = self.app.settings.user_config.get("video_format", VideoFormat.TS)
                quality_dropdown.visible = True
            else:
                record_format_field.options = [ft.dropdown.Option(i) for i in AudioFormat.get_formats()]
                record_format_field.value = self.app.settings.user_config.get("audio_format", AudioFormat.MP3)
                quality_dropdown.visible = False
            record_format_field.update()
            quality_dropdown.update()

        url_field = ft.TextField(
            label=self._["input_live_link"],
            hint_text=self._["example"] + "：https://www.example.com/xxxxxx",
            border_radius=5,
            filled=False,
            value=initial_values.get("url"),
            on_change=on_url_change,
        )
        user_config = self.app.settings.user_config
        quality_dropdown = ft.Dropdown(
            label=self._["select_resolution"],
            options=[ft.dropdown.Option(i, text=self._[i]) for i in VideoQuality.get_qualities()],
            border_radius=5,
            filled=False,
            value=initial_values.get("quality", user_config.get("record_quality", VideoQuality.OD)),
            width=500,
            visible=True
        )
        streamer_name_field = ft.TextField(
            label=self._["input_anchor_name"],
            hint_text=self._["default_input"],
            border_radius=5,
            filled=False,
            value=initial_values.get("streamer_name", ""),
        )
        media_type_dropdown = ft.Dropdown(
            label=self._["select_media_type"],
            options=[
                ft.dropdown.Option("video", text=self._["video"]),
                ft.dropdown.Option("audio", text=self._["audio"])
            ],
            width=245,
            value="video",
            on_change=update_format_options
        )
        user_config = self.app.settings.user_config
        record_format_field = ft.Dropdown(
            label=self._["select_record_format"],
            options=[ft.dropdown.Option(i) for i in VideoFormat.get_formats()],
            border_radius=5,
            filled=False,
            value=initial_values.get("record_format", user_config.get("video_format", VideoFormat.TS)),
            width=245,
            menu_height=200
        )

        format_row = ft.Row([media_type_dropdown, record_format_field], expand=True)

        recording_dir_field = ft.TextField(
            label=self._["input_save_path"],
            hint_text=self._["default_input"],
            border_radius=5,
            filled=False,
            value=initial_values.get("recording_dir"),
        )

        user_config = self.app.settings.user_config
        segmented_recording_enabled = user_config.get('segmented_recording_enabled', False)
        video_segment_time = user_config.get('video_segment_time', 1800)
        segment_record = initial_values.get("segment_record", segmented_recording_enabled)
        segment_time = initial_values.get("segment_time", video_segment_time)

        async def on_segment_setting_change(e):
            selected_value = e.control.value
            segment_input.visible = selected_value == self._["yes"]
            self.page.update()

        segment_setting_dropdown = ft.Dropdown(
            label=self._["is_segment_enabled"],
            options=[
                ft.dropdown.Option(self._["yes"]),
                ft.dropdown.Option(self._["no"]),
            ],
            border_radius=5,
            filled=False,
            value=self._["yes"] if segment_record else self._["no"],
            on_change=on_segment_setting_change,
            width=500,
        )

        segment_input = ft.TextField(
            label=self._["segment_record_time"],
            hint_text=self._["input_segment_time"],
            border_radius=5,
            filled=False,
            value=segment_time,
            visible=segment_record,
        )

        scheduled_recording = initial_values.get("scheduled_recording", False)
        scheduled_start_time = initial_values.get("scheduled_start_time")
        monitor_hours = initial_values.get("monitor_hours", 5)
        message_push_enabled = initial_values.get('enabled_message_push', True)

        async def on_scheduled_setting_change(e):
            selected_value = e.control.value
            schedule_and_monitor_row.visible = selected_value == "true"
            monitor_hours_input.visible = selected_value == "true"
            self.page.update()

        async def pick_time(_):
            async def handle_change(_):
                scheduled_start_time_input.value = time_picker.value
                scheduled_start_time_input.update()

            time_picker = ft.TimePicker(
                confirm_text=self._['confirm'],
                cancel_text=self._['cancel'],
                error_invalid_text=self._['time_out_of_range'],
                help_text=self._['pick_time_slot'],
                hour_label_text=self._['hour_label_text'],
                minute_label_text=self._['minute_label_text'],
                on_change=handle_change
            )
            self.page.open(time_picker)

        scheduled_setting_dropdown = ft.Dropdown(
            label=self._["scheduled_recording"],
            options=[
                ft.dropdown.Option("true", self._["yes"]),
                ft.dropdown.Option("false", self._["no"]),
            ],
            border_radius=5,
            filled=False,
            value="true" if scheduled_recording else "false",
            on_change=on_scheduled_setting_change,
            width=500,
        )

        scheduled_start_time_input = ft.TextField(
            label=self._["scheduled_start_time"],
            hint_text=self._["example"] + "：18:30:00",
            border_radius=5,
            filled=False,
            value=scheduled_start_time,
        )

        time_picker_button = ft.ElevatedButton(
            self._['pick_time'],
            icon=ft.Icons.TIME_TO_LEAVE,
            on_click=pick_time,
            tooltip=self._['pick_time_tip']
        )

        schedule_and_monitor_row = ft.Row(
            [
                ft.Container(content=scheduled_start_time_input, expand=True),
                ft.Container(content=time_picker_button),
            ],
            spacing=10,
            visible=scheduled_recording,
        )

        monitor_hours_input = ft.TextField(
            label=self._["monitor_hours"],
            hint_text=self._["example"] + "：5",
            border_radius=5,
            filled=False,
            value=monitor_hours,
            keyboard_type=ft.KeyboardType.NUMBER,
            visible=scheduled_recording,
        )

        message_push_dropdown = ft.Dropdown(
            label=self._["enable_message_push"],
            options=[
                ft.dropdown.Option("true", self._["yes"]),
                ft.dropdown.Option("false", self._["no"]),
            ],
            border_radius=5,
            filled=False,
            value="true" if message_push_enabled else "false",
            width=500,
        )

        record_mode_dropdown = ft.Dropdown(
            label=self._["record_mode"],
            options=[
                ft.dropdown.Option("auto", self._["auto_record"]),
                ft.dropdown.Option("manual", self._["manual_record"])
            ],
            value=initial_values.get("record_mode", self.app.settings.user_config.get("record_mode", "auto")),
            width=500,
        )

        hint_text_dict = {
            "en": "Example:\n0，https://v.douyin.com/AbcdE，nickname1\n0，https://v.douyin.com/EfghI，nickname2\n\nFormat: [Quality],[URL],[StreamerName]\n"
            "Quality: 0=original image or Blu ray, 1=ultra clear, 2=high-definition, 3=standard definition, 4=smooth\n"
            "StreamerName: Optional, if provided will use custom name, otherwise auto-detect real name\n"
            "Settings: Will use global settings for recording format, segment recording, etc.",
            "zh_CN": "示例:\n0，https://v.douyin.com/AbcdE，主播名1\n0，https://v.douyin.com/EfghI，主播名2\n\n格式: [画质],[直播间链接],[主播名称]\n"
            "画质: 0=原画或蓝光，1=超清，2=高清，3=标清，4=流畅\n"
            "主播名称: 可选，填写则使用自定义名称，不填写则自动获取真实主播名称\n"
            "其他设置: 将使用全局设置（录制格式、分段录制、保存路径等）",
        }

        # Batch input field
        batch_input = ft.TextField(
            label=self._["batch_input_tip"],
            multiline=True,
            min_lines=15,
            max_lines=20,
            border_radius=5,
            filled=False,
            visible=True,
            hint_style=ft.TextStyle(
                size=14,
                color=ft.Colors.GREY_500,
                font_family="Arial",
            ),
            on_change=on_url_change,
            hint_text=hint_text_dict.get(self.app.language_code, hint_text_dict["zh_CN"]),
        )

        # 翻译控制开关
        global_translation_enabled = user_config.get("enable_title_translation", False)
        # 编辑现有房间时，使用房间的独立设置；新增房间时，使用全局设置
        translation_enabled = initial_values.get("translation_enabled", global_translation_enabled)
        
        translation_switch = ft.Switch(
            label=self._["enable_title_translation"],
            value=translation_enabled,
            tooltip=self._["enable_title_translation_tip"],
        )

        # 备注输入框
        remark_field = ft.TextField(
            label=self._["remark"],
            hint_text=self._["remark_hint"],
            border_radius=5,
            filled=False,
            value=initial_values.get("remark", ""),
            max_length=20,
        )

        tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            height=500,
            tabs=[
                ft.Tab(
                    text=self._["single_input"],
                    content=ft.Container(
                        content=ft.Column(
                            [
                                ft.Container(margin=ft.margin.only(top=10)),
                                url_field,
                                streamer_name_field,
                                format_row,
                                quality_dropdown,
                                record_mode_dropdown,
                                recording_dir_field,
                                segment_setting_dropdown,
                                segment_input,
                                scheduled_setting_dropdown,
                                schedule_and_monitor_row,
                                monitor_hours_input,
                                message_push_dropdown,
                                remark_field,  # 备注输入框
                                translation_switch  # 翻译控制开关移动到最下面
                            ],
                            tight=True,
                            spacing=10,
                            scroll=ft.ScrollMode.AUTO,
                        )
                    ),
                ),
                ft.Tab(
                    text=self._["batch_input"], content=ft.Container(content=batch_input, margin=ft.margin.only(top=15))
                ),
            ],
        )

        async def not_supported(url):
            lang_code = getattr(self.app, "language_code", "zh_CN").lower()
            if not lang_code or "zh" in lang_code:
                log_msg = f"⚠️ 暂不支持该平台录制: {url}"
            else:
                log_msg = f"⚠️ This platform does not support recording: {url}"
            logger.warning(log_msg)
            await self.app.snack_bar.show_snack_bar(self._["platform_not_supported_tip"], duration=3000)

        async def on_confirm(e):
            # 禁用确认按钮并显示加载状态
            confirm_button.disabled = True
            confirm_button.text = self._["creating"]
            self.page.update()
            
            try:
                if tabs.selected_index == 0:
                    quality_info = self._[quality_dropdown.value]

                    if not streamer_name_field.value:
                        anchor_name = self._["live_room"]
                        title = f"{anchor_name} - {quality_info}"
                    else:
                        anchor_name = streamer_name_field.value.strip()
                        title = f"{anchor_name} - {quality_info}"

                    display_title = title
                    rec_id = self.recording.rec_id if self.recording else None
                    live_url = url_field.value.strip()
                    platform, platform_key = get_platform_info(live_url)
                    if not platform:
                        await not_supported(url_field.value)
                        await close_dialog(e)
                        return

                    # 检查直播间是否已存在，但只在添加新房间时检查，编辑已有房间时跳过
                    if not self.recording:  # 只在添加新房间时检查
                        is_duplicate, reason = await RoomChecker.check_duplicate_room(
                            self.app,
                            live_url,
                            streamer_name_field.value.strip() if streamer_name_field.value else None
                        )
                        
                        if is_duplicate:
                            # 显示国际化的重复原因
                            reason_text = self._[reason] if reason in self._ else reason
                            alert_text.value = f"{self._['live_room_already_exists']} ({reason_text})"
                            alert_text.visible = True
                            self.page.update()
                            await asyncio.sleep(3)
                            alert_text.visible = False
                            self.page.update()
                            return

                    # 新增：直接获取直播间信息
                    real_anchor_name = anchor_name  # 优先使用用户输入的主播名称
                    real_title = title
                    
                    # 只有在用户没有输入主播名称时才获取真实主播名称
                    if not anchor_name or anchor_name.strip() == "":
                        try:
                            from ...core.stream_manager import LiveStreamRecorder
                            recording_info_dict = {
                                "platform": platform,
                                "platform_key": platform_key,
                                "live_url": live_url,
                                "output_dir": self.app.record_manager.settings.get_video_save_path(),
                                "segment_record": segment_input.visible,
                                "segment_time": segment_input.value,
                                "save_format": record_format_field.value,
                                "quality": quality_dropdown.value,
                            }
                            # 创建一个临时Recording对象传递给LiveStreamRecorder，避免使用None
                            from ...models.recording_model import Recording
                            temp_recording = Recording(
                                rec_id=None,
                                url=live_url,
                                streamer_name=anchor_name,
                                record_format=record_format_field.value,
                                quality=quality_dropdown.value,
                                segment_record=segment_input.visible,
                                segment_time=segment_input.value,
                                monitor_status=False,
                                scheduled_recording=False,
                                scheduled_start_time=None,
                                monitor_hours=None,
                                recording_dir=None,
                                enabled_message_push=False
                            )
                            
                            # 在编辑对话框中获取直播间信息时，不使用代理，避免可能的JSON解析错误
                            # 强制设置proxy为None，避免使用系统代理
                            user_config = self.app.settings.user_config
                            original_proxy_setting = user_config.get("enable_proxy", False)
                            original_proxy_platforms = user_config.get("default_platform_with_proxy", "")
                            
                            # 临时禁用代理
                            try:
                                # 创建不使用代理的LiveStreamRecorder实例
                                recorder = LiveStreamRecorder(self.app, temp_recording, recording_info_dict)
                                # 强制设置proxy为None
                                recorder.proxy = None
                                stream_info = await recorder.fetch_stream()
                                if stream_info:
                                    real_anchor_name = getattr(stream_info, "anchor_name", anchor_name)
                                    real_title = getattr(stream_info, "title", title)
                            except Exception as ex:
                                logger.error(f"[Dialog] 不使用代理获取直播间信息失败: {ex}")
                                # 如果不使用代理失败，尝试使用代理
                                logger.info("[Dialog] 尝试使用代理获取直播间信息")
                                try:
                                    recorder = LiveStreamRecorder(self.app, temp_recording, recording_info_dict)
                                    stream_info = await recorder.fetch_stream()
                                    if stream_info:
                                        real_anchor_name = getattr(stream_info, "anchor_name", anchor_name)
                                        real_title = getattr(stream_info, "title", title)
                                except Exception as ex2:
                                    logger.error(f"[Dialog] 使用代理获取直播间信息也失败: {ex2}")
                                    # 继续使用默认值
                        except Exception as ex:
                            logger.error(f"[Dialog] 获取直播间信息失败: {ex}")
                            # 继续使用默认值
                    else:
                        # 用户输入了主播名称，但仍需要获取直播间标题
                        try:
                            from ...core.stream_manager import LiveStreamRecorder
                            recording_info_dict = {
                                "platform": platform,
                                "platform_key": platform_key,
                                "live_url": live_url,
                                "output_dir": self.app.record_manager.settings.get_video_save_path(),
                                "segment_record": segment_input.visible,
                                "segment_time": segment_input.value,
                                "save_format": record_format_field.value,
                                "quality": quality_dropdown.value,
                            }
                            from ...models.recording_model import Recording
                            temp_recording = Recording(
                                rec_id=None,
                                url=live_url,
                                streamer_name=anchor_name,
                                record_format=record_format_field.value,
                                quality=quality_dropdown.value,
                                segment_record=segment_input.visible,
                                segment_time=segment_input.value,
                                monitor_status=False,
                                scheduled_recording=False,
                                scheduled_start_time=None,
                                monitor_hours=None,
                                recording_dir=None,
                                enabled_message_push=False
                            )
                            
                            # 只获取直播间标题，不覆盖主播名称
                            try:
                                recorder = LiveStreamRecorder(self.app, temp_recording, recording_info_dict)
                                recorder.proxy = None
                                stream_info = await recorder.fetch_stream()
                                if stream_info:
                                    real_title = getattr(stream_info, "title", title)
                            except Exception as ex:
                                logger.error(f"[Dialog] 获取直播间标题失败: {ex}")
                                try:
                                    recorder = LiveStreamRecorder(self.app, temp_recording, recording_info_dict)
                                    stream_info = await recorder.fetch_stream()
                                    if stream_info:
                                        real_title = getattr(stream_info, "title", title)
                                except Exception as ex2:
                                    logger.error(f"[Dialog] 获取直播间标题也失败: {ex2}")
                        except Exception as ex:
                            logger.error(f"[Dialog] 获取直播间标题失败: {ex}")

                    recordings_info = [
                        {
                            "rec_id": rec_id,
                            "url": live_url,
                            "streamer_name": real_anchor_name,
                            "record_format": record_format_field.value,
                            "quality": quality_dropdown.value,
                            "quality_info": quality_info,
                            "title": f"{real_anchor_name} - {quality_info}",
                            "speed": "0 KB/s",
                            "segment_record": segment_input.visible,
                            "segment_time": segment_input.value,
                            "monitor_status": initial_values.get("monitor_status", True),
                            "display_title": f"{real_anchor_name} - {quality_info}",
                            "scheduled_recording": schedule_and_monitor_row.visible,
                            "scheduled_start_time": str(scheduled_start_time_input.value),
                            "monitor_hours": monitor_hours_input.value,
                            "recording_dir": recording_dir_field.value,
                            "enabled_message_push": message_push_dropdown.value == "true",
                            "record_mode": record_mode_dropdown.value,
                            "live_title": real_title,
                            "translation_enabled": translation_switch.value,  # 新增翻译开关值
                            "remark": remark_field.value.strip() if remark_field.value and remark_field.value.strip() else None  # 修改备注处理逻辑
                        }
                    ]
                    await self.on_confirm_callback(recordings_info)

                elif tabs.selected_index == 1:  # Batch entry
                    lines = batch_input.value.splitlines()
                    recordings_info = []
                    filtered_urls = []
                    streamer_name = ""
                    quality = "OD"
                    quality_dict = {"0": "OD", "1": "UHD", "2": "HD", "3": "SD", "4": "LD"}
                    
                    # 收集所有URL和主播名称
                    urls = []
                    streamer_names = []
                    for line in lines:
                        if "http" not in line:
                            continue
                        res = [i for i in line.strip().replace("，", ",").split(",") if i]
                        if len(res) == 3:
                            quality, url, streamer_name = res
                        elif len(res) == 2:
                            if res[1].startswith("http"):
                                quality, url = res
                            else:
                                url, streamer_name = res
                        else:
                            url = res[0]
                        
                        urls.append(url.strip())
                        streamer_names.append(streamer_name.strip() if streamer_name else "")
                    
                    # 内部去重
                    unique_urls = []
                    unique_streamer_names = []
                    seen_urls = set()
                    
                    for i, url in enumerate(urls):
                        if url not in seen_urls:
                            seen_urls.add(url)
                            unique_urls.append(url)
                            unique_streamer_names.append(streamer_names[i])
                    
                    # 使用去重后的URL进行批量检查
                    valid_urls, filtered_urls = await RoomChecker.batch_check_duplicate_rooms(
                        self.app,
                        unique_urls,
                        unique_streamer_names
                    )
                    
                    # 处理有效的URL
                    for i, url in enumerate(unique_urls):
                        if url in valid_urls:
                            streamer_name = unique_streamer_names[i]
                            quality = "OD"  # 默认质量
                            
                            # 从原始输入中获取质量设置
                            for line in lines:
                                if url in line:
                                    res = [i for i in line.strip().replace("，", ",").split(",") if i]
                                    if len(res) >= 2 and res[0] in quality_dict:
                                        quality = quality_dict[res[0]]
                                    break
                            
                            platform, platform_key = get_platform_info(url)
                            if not platform:
                                await not_supported(url)
                                continue

                            # 获取真实的直播间信息（与单个输入保持一致）
                            real_anchor_name = streamer_name  # 优先使用用户输入的主播名称
                            real_title = ""
                            
                            # 只有在用户没有输入主播名称时才获取真实主播名称
                            if not streamer_name or streamer_name.strip() == "":
                                try:
                                    from ...core.stream_manager import LiveStreamRecorder
                                    recording_info_dict = {
                                        "platform": platform,
                                        "platform_key": platform_key,
                                        "live_url": url,
                                        "output_dir": self.app.record_manager.settings.get_video_save_path(),
                                        "segment_record": False,
                                        "segment_time": "1800",
                                        "save_format": "ts",
                                        "quality": quality,
                                    }
                                    # 创建一个临时Recording对象传递给LiveStreamRecorder
                                    from ...models.recording_model import Recording
                                    temp_recording = Recording(
                                        rec_id=None,
                                        url=url,
                                        streamer_name=streamer_name,
                                        record_format="ts",
                                        quality=quality,
                                        segment_record=False,
                                        segment_time="1800",
                                        monitor_status=False,
                                        scheduled_recording=False,
                                        scheduled_start_time=None,
                                        monitor_hours=None,
                                        recording_dir=None,
                                        enabled_message_push=False
                                    )
                                    
                                    # 获取直播间信息，优先不使用代理
                                    try:
                                        recorder = LiveStreamRecorder(self.app, temp_recording, recording_info_dict)
                                        recorder.proxy = None  # 强制不使用代理
                                        stream_info = await recorder.fetch_stream()
                                        if stream_info:
                                            real_anchor_name = getattr(stream_info, "anchor_name", streamer_name)
                                            real_title = getattr(stream_info, "title", "")
                                    except Exception as ex:
                                        logger.error(f"[Batch] 不使用代理获取直播间信息失败: {ex}")
                                        # 如果不使用代理失败，尝试使用代理
                                        try:
                                            recorder = LiveStreamRecorder(self.app, temp_recording, recording_info_dict)
                                            stream_info = await recorder.fetch_stream()
                                            if stream_info:
                                                real_anchor_name = getattr(stream_info, "anchor_name", streamer_name)
                                                real_title = getattr(stream_info, "title", "")
                                        except Exception as ex2:
                                            logger.error(f"[Batch] 使用代理获取直播间信息也失败: {ex2}")
                                            # 继续使用默认值
                                except Exception as ex:
                                    logger.error(f"[Batch] 获取直播间信息失败: {ex}")
                                    # 继续使用默认值
                            else:
                                # 用户输入了主播名称，但仍需要获取直播间标题
                                try:
                                    from ...core.stream_manager import LiveStreamRecorder
                                    recording_info_dict = {
                                        "platform": platform,
                                        "platform_key": platform_key,
                                        "live_url": url,
                                        "output_dir": self.app.record_manager.settings.get_video_save_path(),
                                        "segment_record": False,
                                        "segment_time": "1800",
                                        "save_format": "ts",
                                        "quality": quality,
                                    }
                                    from ...models.recording_model import Recording
                                    temp_recording = Recording(
                                        rec_id=None,
                                        url=url,
                                        streamer_name=streamer_name,
                                        record_format="ts",
                                        quality=quality,
                                        segment_record=False,
                                        segment_time="1800",
                                        monitor_status=False,
                                        scheduled_recording=False,
                                        scheduled_start_time=None,
                                        monitor_hours=None,
                                        recording_dir=None,
                                        enabled_message_push=False
                                    )
                                    
                                    # 只获取直播间标题，不覆盖主播名称
                                    try:
                                        recorder = LiveStreamRecorder(self.app, temp_recording, recording_info_dict)
                                        recorder.proxy = None
                                        stream_info = await recorder.fetch_stream()
                                        if stream_info:
                                            real_title = getattr(stream_info, "title", "")
                                    except Exception as ex:
                                        logger.error(f"[Batch] 获取直播间标题失败: {ex}")
                                        try:
                                            recorder = LiveStreamRecorder(self.app, temp_recording, recording_info_dict)
                                            stream_info = await recorder.fetch_stream()
                                            if stream_info:
                                                real_title = getattr(stream_info, "title", "")
                                        except Exception as ex2:
                                            logger.error(f"[Batch] 获取直播间标题也失败: {ex2}")
                                except Exception as ex:
                                    logger.error(f"[Batch] 获取直播间标题失败: {ex}")

                            # 使用获取到的信息构建标题
                            if not real_anchor_name:
                                real_anchor_name = self._["live_room"]
                            
                            title = f"{real_anchor_name} - {self._[quality]}"
                            display_title = title
                            if not streamer_name:  # 如果用户没有输入主播名称
                                display_title = real_anchor_name + url.split("?")[0] + "... - " + self._[quality]

                            recording_info = {
                                "url": url,
                                "streamer_name": real_anchor_name,  # 使用真实的主播名称
                                "quality": quality,
                                "quality_info": self._[VideoQuality.OD],
                                "title": title,
                                "display_title": display_title,
                                "record_format": self.app.settings.user_config.get("video_format", "ts").lower(),  # 使用全局录制格式设置
                                "segment_record": self.app.settings.user_config.get("segmented_recording_enabled", False),  # 使用全局分段录制设置
                                "segment_time": self.app.settings.user_config.get("video_segment_time", "1800"),  # 使用全局分段时间设置
                                "monitor_status": True,  # 批量新增默认开启监控
                                "scheduled_recording": False,  # 批量新增默认不开启定时录制
                                "scheduled_start_time": "00:00",  # 默认定时开始时间
                                "monitor_hours": 24,  # 默认监控时长
                                "recording_dir": self.app.record_manager.settings.get_video_save_path(),  # 使用全局保存路径设置
                                "enabled_message_push": False,  # 批量新增默认不开启消息推送
                                "record_mode": self.app.settings.user_config.get("record_mode", "auto"),  # 使用全局录制模式设置
                                "translation_enabled": self.app.settings.user_config.get("enable_title_translation", False),  # 使用全局翻译设置
                                "live_title": real_title,  # 添加真实的直播间标题
                                "remark": None  # 批量新增默认无备注
                            }
                            recordings_info.append(recording_info)

                    # 显示过滤统计信息
                    if filtered_urls:
                        # 统计不同原因的过滤数量
                        duplicate_count = sum(1 for _, reason in filtered_urls if reason != "platform_not_supported_tip")
                        unsupported_count = sum(1 for _, reason in filtered_urls if reason == "platform_not_supported_tip")
                        total_count = len(urls)
                        success_count = len(recordings_info)
                        
                        # 构建统计信息 - 精简显示格式
                        if unsupported_count > 0 and duplicate_count > 0:
                            # 同时存在不支持和重复的情况，使用统一提示
                            alert_text.value = f"{self._['url_filter_summary']} ({len(filtered_urls)}/{total_count})"
                        elif unsupported_count > 0:
                            alert_text.value = f"{self._['platform_not_supported_tip']}: {unsupported_count}/{total_count}"
                        else:
                            alert_text.value = f"{self._['live_room_already_exists']}: {duplicate_count}/{total_count}"
                        
                        alert_text.visible = True
                        self.page.update()
                        await asyncio.sleep(3)
                        alert_text.visible = False
                        self.page.update()
                        
                        # 只有当有成功添加的直播间时才显示成功提示
                        if success_count > 0:
                            await self.on_confirm_callback(recordings_info)
                            await close_dialog(e)
                            # 显示成功提示，如果同时有过滤URL，使用组合信息
                            if len(filtered_urls) > 0:
                                # 同时存在成功添加和被过滤的URL，使用精简提示
                                await self.app.snack_bar.show_snack_bar(
                                    f"{self._['success_add_rooms'].format(count=success_count)} ({self._['url_filter_summary_partial']})",
                                    duration=3000
                                )
                            else:
                                # 仅有成功添加的情况
                                await self.app.snack_bar.show_snack_bar(
                                    self._["success_add_rooms"].format(count=success_count),
                                    duration=3000
                                )
                            # 显示过滤文件路径提示
                            diff_file_result = await RoomChecker.get_diff_file_path()
                            diff_file_path, error_msg = diff_file_result
                            if diff_file_path:
                                await asyncio.sleep(3)  # 等待上一个提示消失
                                await self.app.snack_bar.show_snack_bar(
                                    self._["filtered_file_saved"].format(path=diff_file_path),
                                    duration=5000
                                )
                            elif error_msg:
                                await asyncio.sleep(3)  # 等待上一个提示消失
                                await self.app.snack_bar.show_snack_bar(
                                    self._["get_filtered_file_failed"].format(error=error_msg),
                                    duration=5000
                                )
                        else:
                            # 如果所有直播间都被过滤掉了，显示提示并关闭对话框
                            await close_dialog(e)
                            # 精简提示信息
                            if unsupported_count > 0 and duplicate_count > 0:
                                # 同时存在不支持和重复的情况
                                await self.app.snack_bar.show_snack_bar(
                                    self._["url_filter_summary"],
                                    duration=3000
                                )
                            elif unsupported_count > 0:
                                await self.app.snack_bar.show_snack_bar(
                                    f"{self._['platform_not_supported_tip']}: {unsupported_count}",
                                    duration=3000
                                )
                            else:
                                await self.app.snack_bar.show_snack_bar(
                                    self._["all_rooms_exist"],
                                    duration=3000
                                )
                            # 显示过滤文件路径提示
                            diff_file_result = await RoomChecker.get_diff_file_path()
                            diff_file_path, error_msg = diff_file_result
                            if diff_file_path:
                                await asyncio.sleep(3)  # 等待上一个提示消失
                                await self.app.snack_bar.show_snack_bar(
                                    self._["filtered_file_saved"].format(path=diff_file_path),
                                    duration=5000
                                )
                            elif error_msg:
                                await asyncio.sleep(3)  # 等待上一个提示消失
                                await self.app.snack_bar.show_snack_bar(
                                    self._["get_filtered_file_failed"].format(error=error_msg),
                                    duration=5000
                                )
                    else:
                        # 如果没有重复的直播间，直接添加
                        await self.on_confirm_callback(recordings_info)
                        await close_dialog(e)

                await close_dialog(e)
            finally:
                # 恢复确认按钮状态
                confirm_button.disabled = False
                confirm_button.text = self._["sure"]
                self.page.update()

        async def close_dialog(_):
            dialog.open = False
            self.page.update()

        close_button = ft.IconButton(icon=ft.Icons.CLOSE, tooltip=self._["close"], on_click=close_dialog)

        title_text = self._["edit_record"] if self.recording else self._["add_record"]
        dialog = ft.AlertDialog(
            open=True,
            modal=True,
            title=ft.Row(
                [
                    ft.Container(
                        content=ft.Text(title_text, size=16, theme_style=ft.TextThemeStyle.TITLE_LARGE),
                        width=120
                    ),
                    ft.Container(
                        content=alert_text,
                        expand=True,
                        alignment=ft.alignment.center,
                        margin=ft.margin.only(left=-60)  # 向左偏移以补偿左侧标题文本的宽度
                    ),
                    ft.Container(
                        content=close_button,
                        width=40
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                width=500
            ),
            content=tabs,
            actions=[
                ft.TextButton(text=self._["cancel"], on_click=close_dialog),
                ft.TextButton(text=self._["sure"], on_click=on_confirm, disabled=self.recording is None),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=10)
        )

        # 保存确认按钮的引用
        confirm_button = dialog.actions[1]

        self.page.overlay.append(dialog)
        self.page.update()
        