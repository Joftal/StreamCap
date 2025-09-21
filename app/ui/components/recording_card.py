import asyncio
import os.path
from datetime import datetime, timedelta
from functools import partial
import sys
import os

import flet as ft

from ...core.platform_handlers import get_platform_info
from ...core.stream_manager import LiveStreamRecorder
from ...messages.message_pusher import MessagePusher
from ...models.recording_model import Recording
from ...models.recording_status_model import RecordingStatus
from ...utils import utils
from ...utils.logger import logger
from ..views.storage_view import StoragePage
from .card_dialog import CardDialog
from .recording_dialog import RecordingDialog
from .video_player import VideoPlayer


class RecordingCardManager:
    def __init__(self, app):
        self.app = app
        self.cards_obj = {}
        self.update_duration_tasks = {}
        self.selected_cards = {}
        self.app.language_manager.add_observer(self)
        self._ = {}
        self.load()
        self.pubsub_subscribe()

    def load(self):
        language = self.app.language_manager.language
        for key in ("recording_card", "recording_manager", "base", "home_page", "video_quality", "storage_page"):
            self._.update(language.get(key, {}))

    def pubsub_subscribe(self):
        self.app.page.pubsub.subscribe_topic("update", self.subscribe_update_card)
        self.app.page.pubsub.subscribe_topic("delete", self.subscribe_remove_cards)

    async def create_card(self, recording: Recording):
        """Create a card for a given recording."""
        rec_id = recording.rec_id
        if not self.cards_obj.get(rec_id):
            if self.app.recording_enabled:
                self.app.page.run_task(self.app.record_manager.check_if_live, recording)
            else:
                recording.status_info = RecordingStatus.NOT_RECORDING_SPACE
        card_data = self._create_card_components(recording)
        self.cards_obj[rec_id] = card_data
        self.start_update_task(recording)
        return card_data["card"]

    def _create_card_components(self, recording: Recording):
        """create card components."""
        duration_text_label = ft.Text(self.app.record_manager.get_duration(recording), size=12)

        # 获取速度监控设置
        show_recording_speed = self.app.settings.user_config.get("show_recording_speed", True)

        # 修改：判断是否禁用录制按钮的条件，包括手动模式和自动模式
        is_record_button_disabled = not recording.monitor_status or (recording.monitor_status and not recording.is_live)
        
        record_button = ft.IconButton(
            icon=self.get_icon_for_recording_state(recording),
            tooltip=self.get_tip_for_recording_state(recording),
            on_click=partial(self.recording_button_on_click, recording=recording),
            disabled=is_record_button_disabled,  # 未监控或未开播时禁用录制按钮
        )

        edit_button = ft.IconButton(
            icon=ft.Icons.EDIT,
            tooltip=self._["edit_record_config"],
            on_click=partial(self.edit_recording_button_click, recording=recording),
        )

        preview_button = ft.IconButton(
            icon=ft.Icons.VIDEO_LIBRARY,
            tooltip=self._["preview_video"],
            on_click=partial(self.preview_video_button_on_click, recording=recording),
        )

        monitor_button = ft.IconButton(
            icon=self.get_icon_for_monitor_state(recording),
            tooltip=self.get_tip_for_monitor_state(recording),
            on_click=partial(self.monitor_button_on_click, recording=recording),
        )

        delete_button = ft.IconButton(
            icon=ft.Icons.DELETE,
            tooltip=self._["delete_monitor"],
            on_click=partial(self.recording_delete_button_click, recording=recording),
        )

        # 判断当前语言环境
        get_stream_button = ft.IconButton(
            icon=ft.Icons.LINK,
            tooltip=(self._["copy_stream_url"] if (recording.monitor_status and (recording.is_live or recording.recording)) else self._["no_stream_source"]),
            on_click=partial(self.get_stream_url_on_click, recording=recording),
            disabled=not (recording.monitor_status and (recording.is_live or recording.recording)),
        )

        play_button = ft.IconButton(
            icon=ft.Icons.PLAY_ARROW,
            tooltip=(self._["play_stream"] if (recording.monitor_status and (recording.is_live or recording.recording)) else self._["no_stream_source"]),
            on_click=partial(self.play_stream_on_click, recording=recording),
            disabled=not (recording.monitor_status and (recording.is_live or recording.recording)),
        )

        # 创建缩略图开关按钮
        # 不在直播状态时禁用缩略图按钮
        is_thumbnail_button_disabled = not (recording.monitor_status and (recording.is_live or recording.recording))
        global_thumbnail_enabled = self.app.settings.user_config.get("show_live_thumbnail", False)
        
        # 根据全局设置和房间设置确定初始状态
        if is_thumbnail_button_disabled:
            thumbnail_tooltip = self._["thumbnail_switch_tip_disabled"]
            thumbnail_icon = ft.Icons.PHOTO_LIBRARY_OUTLINED
        else:
            thumbnail_enabled = recording.is_thumbnail_enabled(global_thumbnail_enabled)
            if thumbnail_enabled:
                thumbnail_tooltip = self._["thumbnail_switch_tip_on"]
                thumbnail_icon = ft.Icons.PHOTO_LIBRARY
            else:
                thumbnail_tooltip = self._["thumbnail_switch_tip_off"]
                thumbnail_icon = ft.Icons.PHOTO_LIBRARY_OUTLINED
        
        thumbnail_switch_button = ft.IconButton(
            icon=thumbnail_icon,
            tooltip=thumbnail_tooltip,
            on_click=partial(self.thumbnail_switch_button_on_click, recording=recording),
            disabled=is_thumbnail_button_disabled,
        )

        # 创建翻译开关按钮
        # 不在直播状态时禁用翻译按钮
        is_translation_button_disabled = not (recording.monitor_status and (recording.is_live or recording.recording))
        global_translation_enabled = self.app.settings.user_config.get("enable_title_translation", False)
        
        # 根据全局设置和房间设置确定初始状态
        if is_translation_button_disabled:
            translation_tooltip = self._["translation_switch_tip_disabled"]
            translation_icon = ft.Icons.TRANSLATE_OUTLINED
            translation_style = ft.ButtonStyle(
                color=ft.Colors.GREY_600,
                overlay_color=ft.Colors.TRANSPARENT,
            )
        else:
            translation_enabled = recording.is_translation_enabled(global_translation_enabled)
            if translation_enabled:
                translation_tooltip = self._["translation_switch_tip_on"]
                translation_icon = ft.Icons.TRANSLATE
                translation_style = ft.ButtonStyle(
                    color=ft.Colors.GREEN_600,
                    overlay_color=ft.Colors.GREEN_50,
                )
            else:
                translation_tooltip = self._["translation_switch_tip_off"]
                translation_icon = ft.Icons.TRANSLATE_OUTLINED
                translation_style = ft.ButtonStyle(
                    color=ft.Colors.GREY_600,
                    overlay_color=ft.Colors.TRANSPARENT,
                )
        
        translation_switch_button = ft.IconButton(
            icon=translation_icon,
            tooltip=translation_tooltip,
            on_click=partial(self.translation_switch_button_on_click, recording=recording),
            disabled=is_translation_button_disabled,
            style=translation_style,
        )

        display_title = recording.title
        display_title_label = ft.Text(
            display_title, 
            size=14, 
            selectable=True, 
            max_lines=1, 
            no_wrap=True,
            overflow=ft.TextOverflow.ELLIPSIS,
            expand=True,
            weight=ft.FontWeight.BOLD if recording.recording or recording.is_live else None,
        )

        # 新增：备注显示（无备注时隐藏）
        remark_label = None
        if recording.remark:
            remark_label = ft.Container(
                content=ft.Text(
                    f"备注：{recording.remark}",
                    size=12,
                    color=ft.colors.WHITE,
                    max_lines=1,
                    no_wrap=True,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                bgcolor=ft.colors.BLUE_700,
                border_radius=5,
                padding=ft.padding.only(left=8, right=8, top=2, bottom=2),
                visible=True,
            )

        open_folder_button = ft.IconButton(
            icon=ft.Icons.FOLDER,
            tooltip=self._["open_folder"],
            on_click=partial(self.recording_dir_button_on_click, recording=recording),
        )
        recording_info_button = ft.IconButton(
            icon=ft.Icons.INFO,
            tooltip=self._["recording_info"],
            on_click=partial(self.recording_info_button_on_click, recording=recording),
        )
        
        # 创建速度文本标签，始终可见，但内容根据监控设置变化
        speed_text = f"{self._['speed']} {recording.speed}" if show_recording_speed else f"{self._['speed']} {self._['speed_disabled']}"
        speed_text_label = ft.Text(
            speed_text, 
            size=12,
            color=ft.colors.GREY if not show_recording_speed else None  # 禁用时显示灰色
        )

        status_label = self.create_status_label(recording)

        title_row = ft.Row(
            [display_title_label, status_label] if status_label else [display_title_label],
            alignment=ft.MainAxisAlignment.START,
            spacing=5,
            tight=True,
        )
        
        # 获取平台logo路径
        _, platform_key = get_platform_info(recording.url)
        logo_path = self.app.platform_logo_cache.get_logo_path(recording.rec_id, platform_key)
        
        # 获取缩略图设置并设置初始可见状态
        show_live_thumbnail = self.app.settings.user_config.get("show_live_thumbnail", False)
        
        # 检查单个房间的缩略图设置
        should_show_thumbnail = recording.is_thumbnail_enabled(show_live_thumbnail)
        
        # 固定缩略图容器高度，避免动态调整导致logo位置问题
        thumbnail_container_height = 140  # 固定高度
        
        # 如果开启了缩略图并且正在直播/录制，初始化为不可见（等待缩略图加载）
        platform_logo_visible = not (should_show_thumbnail and (recording.is_live or recording.recording))
        
        # 创建平台logo图片组件（当不显示缩略图时使用）
        platform_logo = ft.Container(
            content=ft.Image(
            src=logo_path if logo_path else None,
            width=50,
            height=50,
            fit=ft.ImageFit.CONTAIN,
            border_radius=ft.border_radius.all(5),
            ),
            alignment=ft.alignment.center,
            expand=True,  # 使其可以填充整个Stack空间
            visible=platform_logo_visible,  # 根据缩略图设置设置初始可见状态
        )
        
        # 创建缩略图组件（初始不显示）
        thumbnail_image = ft.Image(
            src=None,
            width=230,
            height=thumbnail_container_height,
            fit=ft.ImageFit.CONTAIN,
            visible=False,
        )
        
        # 创建叠加在缩略图上的小logo（当缩略图显示时使用）
        overlay_logo = ft.Container(
            content=ft.Image(
                src=logo_path if logo_path else None,
                width=30,
                height=30,
                fit=ft.ImageFit.CONTAIN,
            ),
            top=8,  # 距离顶部5px
            left=0,  # 直接贴左边
            visible=False,
        )
        
        # 创建左侧logo/缩略图容器
        logo_container_content = ft.Stack(
            [
                thumbnail_image,  # 缩略图（底层）
                platform_logo,    # 主logo（当无缩略图时显示）
                overlay_logo,     # 叠加logo（当有缩略图时显示）
            ],
            width=230,
            height=thumbnail_container_height,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,  # 添加剪裁行为，避免溢出
        )
        
        logo_container = ft.Container(
            content=logo_container_content,
            width=230,
            height=thumbnail_container_height,
            alignment=ft.alignment.center,
            padding=ft.padding.all(5),
            border_radius=ft.border_radius.all(5),
        )
        
        # 创建直播标题显示标签
        live_title_label = None
        translated_title_label = None
        
        if recording.live_title:
            live_title_label = ft.Container(
                content=ft.Text(
                    f"{self._['live_title_label']}{recording.live_title}",
                    size=12,
                    color=ft.colors.WHITE,
                    max_lines=1,
                    no_wrap=True,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                bgcolor=ft.colors.BLUE_700,
                border_radius=5,
                padding=ft.padding.only(left=8, right=8, top=2, bottom=2),
                visible=True,
            )
            
            # 检查是否需要显示翻译标题
            global_translation_enabled = self.app.settings.user_config.get("enable_title_translation", False)
            should_show_translation = recording.is_translation_enabled(global_translation_enabled)
            
            if should_show_translation and recording.translated_title:
                translated_title_label = ft.Container(
                    content=ft.Text(
                        f"{self._['translated_title_label']}{recording.translated_title}",
                        size=12,
                        color=ft.colors.WHITE,
                        max_lines=1,
                        no_wrap=True,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    bgcolor=ft.colors.GREEN_700,
                    border_radius=5,
                    padding=ft.padding.only(left=8, right=8, top=2, bottom=2),
                    visible=True,
                )

        # 创建右侧内容容器
        content_column_children = [
            title_row,
            duration_text_label,
            speed_text_label,
        ]
        if live_title_label:
            content_column_children.append(live_title_label)
        if translated_title_label:
            content_column_children.append(translated_title_label)
        if remark_label:
            content_column_children.append(remark_label)
        content_column_children.append(
            ft.Row(
                [
                    record_button,
                    open_folder_button,
                    recording_info_button,
                    preview_button,
                    get_stream_button,
                    play_button,
                    thumbnail_switch_button,
                    translation_switch_button,
                    edit_button,
                    delete_button,
                    monitor_button
                ],
                spacing=3,
                alignment=ft.MainAxisAlignment.START
            )
        )
        content_container = ft.Container(
            content=ft.Column(
                content_column_children,
                spacing=3,
                tight=True
            ),
            expand=True,
        )
        
        # 创建卡片内容行，包含左侧logo和右侧内容
        card_content_row = ft.Row(
            [logo_container, content_container],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
        )

        card_container = ft.Container(
            content=card_content_row,
            padding=8,
            on_click=partial(self.recording_card_on_click, recording=recording),
            bgcolor=self.get_card_background_color(recording),
            border_radius=5,
            border=ft.border.all(2, self.get_card_border_color(recording)),
        )
        card = ft.Card(key=str(recording.rec_id), content=card_container)

        return {
            "card": card,
            "display_title_label": display_title_label,
            "live_title_label": live_title_label,
            "translated_title_label": translated_title_label,
            "duration_label": duration_text_label,
            "speed_label": speed_text_label,
            "record_button": record_button,
            "open_folder_button": open_folder_button,
            "recording_info_button": recording_info_button,
            "edit_button": edit_button,
            "monitor_button": monitor_button,
            "status_label": status_label,
            "get_stream_button": get_stream_button,
            "play_button": play_button,
            "preview_button": preview_button,
            "delete_button": delete_button,
            "thumbnail_switch_button": thumbnail_switch_button,
            "translation_switch_button": translation_switch_button,
            "platform_logo": platform_logo,
            "thumbnail_image": thumbnail_image,
            "overlay_logo": overlay_logo,
        }
        
    def get_card_background_color(self, recording: Recording):
        is_dark_mode = self.app.page.theme_mode == ft.ThemeMode.DARK
        if recording.selected:
            return ft.colors.GREY_800 if is_dark_mode else ft.colors.GREY_400
        return None

    @staticmethod
    def get_card_border_color(recording: Recording):
        """Get the border color of the card."""
        if recording.recording:
            return ft.colors.GREEN
        elif recording.status_info == RecordingStatus.RECORDING_ERROR:
            return ft.colors.RED
        elif recording.is_live and recording.monitor_status and not recording.recording:
            # 为"直播中（未录制）"状态添加青色边框
            return ft.colors.CYAN
        elif not recording.is_live and recording.monitor_status:
            return ft.colors.AMBER
        elif not recording.monitor_status:
            return ft.colors.GREY
        return ft.colors.TRANSPARENT

    def create_status_label(self, recording: Recording):
        if recording.recording:
            return ft.Container(
                content=ft.Text(self._["recording"], color=ft.colors.WHITE, size=12, weight=ft.FontWeight.BOLD),
                bgcolor=ft.colors.GREEN,
                border_radius=5,
                padding=5,
                width=60,
                height=26,
                alignment=ft.alignment.center,
            )
        elif recording.status_info == RecordingStatus.RECORDING_ERROR:
            return ft.Container(
                content=ft.Text(self._["recording_error"], color=ft.colors.WHITE, size=12, weight=ft.FontWeight.BOLD),
                bgcolor=ft.colors.RED,
                border_radius=5,
                padding=5,
                width=60,
                height=26,
                alignment=ft.alignment.center,
            )
        elif not recording.is_live and recording.monitor_status:
            return ft.Container(
                content=ft.Text(self._["offline"], color=ft.colors.BLACK, size=12, weight=ft.FontWeight.BOLD),
                bgcolor=ft.colors.AMBER,
                border_radius=5,
                padding=5,
                width=60,
                height=26,
                alignment=ft.alignment.center,
            )
        elif not recording.monitor_status:
            return ft.Container(
                content=ft.Text(self._["no_monitor"], color=ft.colors.WHITE, size=12, weight=ft.FontWeight.BOLD),
                bgcolor=ft.colors.GREY,
                border_radius=5,
                padding=5,
                width=60,
                height=26,
                alignment=ft.alignment.center,
            )
        elif recording.is_live and recording.monitor_status and not recording.recording:
            # 显示"直播中（未录制）"状态标签
            return ft.Container(
                content=ft.Text(self._["live_monitoring_not_recording"], color=ft.colors.WHITE, size=12, weight=ft.FontWeight.BOLD),
                bgcolor=ft.colors.CYAN,
                border_radius=5,
                padding=5,
                width=160,
                height=26,
                alignment=ft.alignment.center,
            )
        return None

    async def update_card(self, recording):
        """Update the card display based on the recording's state."""
        try:
            recording_card = self.cards_obj.get(recording.rec_id)
            if not recording_card:
                return

            # 获取速度监控设置
            show_recording_speed = self.app.settings.user_config.get("show_recording_speed", True)
            
            # 获取缩略图设置
            show_live_thumbnail = self.app.settings.user_config.get("show_live_thumbnail", False)

            new_status_label = self.create_status_label(recording)
            
            if recording_card["card"] and recording_card["card"].content and recording_card["card"].content.content:
                # 获取卡片内容行（包含logo和内容的Row）
                card_content_row = recording_card["card"].content.content
                # 获取右侧内容区域（第二个控件）
                content_container = card_content_row.controls[1]
                # 获取内容区域的Column
                content_column = content_container.content
                
                # 更新直播标题显示
                live_title_index = 3  # 直播标题在第4个位置（0-based索引为3）
                if recording.live_title:
                    new_live_title_container = ft.Container(
                        content=ft.Text(
                            f"{self._['live_title_label']}{recording.live_title}",
                            size=12,
                            color=ft.colors.WHITE,
                            max_lines=1,
                            no_wrap=True,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        bgcolor=ft.colors.BLUE_700,
                        border_radius=5,
                        padding=ft.padding.only(left=8, right=8, top=2, bottom=2),
                        visible=True,
                    )
                    # 如果已经有直播标题控件，更新它；否则添加新的直播标题控件
                    if len(content_column.controls) > live_title_index and isinstance(content_column.controls[live_title_index], ft.Container):
                        content_column.controls[live_title_index] = new_live_title_container
                    else:
                        content_column.controls.insert(live_title_index, new_live_title_container)
                else:
                    # 如果没有直播标题，移除直播标题控件（如果存在）
                    if (len(content_column.controls) > live_title_index and 
                        isinstance(content_column.controls[live_title_index], ft.Container) and
                        hasattr(content_column.controls[live_title_index], 'content') and
                        hasattr(content_column.controls[live_title_index].content, 'value') and
                        content_column.controls[live_title_index].content.value and
                        content_column.controls[live_title_index].content.value.startswith(self._['live_title_label'])):
                        content_column.controls.pop(live_title_index)

                # 更新翻译标题显示
                translated_title_index = 4 if recording.live_title else 3
                global_translation_enabled = self.app.settings.user_config.get("enable_title_translation", False)
                should_show_translation = recording.is_translation_enabled(global_translation_enabled)
                
                if should_show_translation and recording.translated_title:
                    new_translated_title_container = ft.Container(
                        content=ft.Text(
                            f"{self._['translated_title_label']}{recording.translated_title}",
                            size=12,
                            color=ft.colors.WHITE,
                            max_lines=1,
                            no_wrap=True,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        bgcolor=ft.colors.GREEN_700,
                        border_radius=5,
                        padding=ft.padding.only(left=8, right=8, top=2, bottom=2),
                        visible=True,
                    )
                    # 如果已经有翻译标题控件，更新它；否则添加新的翻译标题控件
                    if len(content_column.controls) > translated_title_index and isinstance(content_column.controls[translated_title_index], ft.Container):
                        content_column.controls[translated_title_index] = new_translated_title_container
                    else:
                        content_column.controls.insert(translated_title_index, new_translated_title_container)
                else:
                    # 如果不显示翻译标题，移除翻译标题控件（如果存在）
                    if (len(content_column.controls) > translated_title_index and 
                        isinstance(content_column.controls[translated_title_index], ft.Container) and
                        hasattr(content_column.controls[translated_title_index], 'content') and
                        hasattr(content_column.controls[translated_title_index].content, 'value') and
                        content_column.controls[translated_title_index].content.value and
                        content_column.controls[translated_title_index].content.value.startswith(self._['translated_title_label'])):
                        content_column.controls.pop(translated_title_index)

                # 更新备注显示（需要重新计算索引，因为可能插入了直播标题和翻译标题）
                remark_index = 4 if recording.live_title else 3
                if recording.live_title and should_show_translation and recording.translated_title:
                    remark_index = 5
                if recording.remark:
                    remark_container = ft.Container(
                        content=ft.Text(
                            f"备注：{recording.remark}",
                            size=12,
                            color=ft.colors.WHITE,
                            max_lines=1,
                            no_wrap=True,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        bgcolor=ft.colors.BLUE_700,
                        border_radius=5,
                        padding=ft.padding.only(left=8, right=8, top=2, bottom=2),
                        visible=True,
                    )
                    # 如果已经有备注控件，更新它；否则添加新的备注控件
                    if len(content_column.controls) > remark_index and isinstance(content_column.controls[remark_index], ft.Container):
                        content_column.controls[remark_index] = remark_container
                    else:
                        content_column.controls.insert(remark_index, remark_container)
                else:
                    # 如果没有备注，移除备注控件（如果存在）
                    if len(content_column.controls) > remark_index and isinstance(content_column.controls[remark_index], ft.Container):
                        content_column.controls.pop(remark_index)
                
                # 获取标题行（Column的第一个控件）
                title_row = content_column.controls[0]
                
                title_row.alignment = ft.MainAxisAlignment.START
                title_row.spacing = 5
                title_row.tight = True
                
                title_row_controls = title_row.controls
                if len(title_row_controls) > 1:
                    if new_status_label:
                        title_row_controls[1] = new_status_label
                    else:
                        title_row_controls.pop(1)
                elif new_status_label:
                    title_row_controls.append(new_status_label)
                
                # 更新平台logo和缩略图状态
                if recording_card.get("platform_logo") and recording_card.get("thumbnail_image") and recording_card.get("overlay_logo"):
                    # 检查是否应该显示缩略图（考虑单个房间设置）
                    should_show_thumbnail = recording.is_thumbnail_enabled(show_live_thumbnail)
                    if should_show_thumbnail and (recording.is_live or recording.recording):
                        # 尝试获取最新的缩略图
                        if hasattr(self.app, 'thumbnail_manager'):
                            thumbnail_path = self.app.thumbnail_manager.get_latest_thumbnail(recording)
                            if thumbnail_path and os.path.exists(thumbnail_path):
                                recording_card["thumbnail_image"].src = thumbnail_path
                                recording_card["thumbnail_image"].visible = True
                                recording_card["platform_logo"].visible = False
                                recording_card["overlay_logo"].visible = True
                            else:
                                # 没有缩略图时显示普通logo
                                recording_card["thumbnail_image"].visible = False
                                recording_card["platform_logo"].visible = True
                                recording_card["overlay_logo"].visible = False
                    else:
                        # 不显示缩略图时只显示普通logo
                        recording_card["thumbnail_image"].visible = False
                        recording_card["platform_logo"].visible = True
                        recording_card["overlay_logo"].visible = False
            
            recording_card["status_label"] = new_status_label
            
            if recording_card.get("display_title_label"):
                display_title = recording.title
                recording_card["display_title_label"].value = display_title
                title_label_weight = ft.FontWeight.BOLD if recording.recording or recording.is_live else None
                recording_card["display_title_label"].weight = title_label_weight
            
            if recording_card.get("duration_label"):
                recording_card["duration_label"].value = self.app.record_manager.get_duration(recording)
            
            if recording_card.get("speed_label"):
                # 更新速度文本，始终可见但根据监控设置显示不同内容
                speed_text = f"{self._['speed']} {recording.speed}" if show_recording_speed else f"{self._['speed']} {self._['speed_disabled']}"
                recording_card["speed_label"].value = speed_text
                recording_card["speed_label"].color = ft.colors.GREY if not show_recording_speed else None
            
            # 全面刷新所有按钮和文本的国际化内容
            if recording_card.get("record_button"):
                recording_card["record_button"].icon = self.get_icon_for_recording_state(recording)
                recording_card["record_button"].tooltip = self.get_tip_for_recording_state(recording)
                # 更新录制按钮的禁用状态：未监控或未开播时禁用
                is_record_button_disabled = not recording.monitor_status or (recording.monitor_status and not recording.is_live)
                recording_card["record_button"].disabled = is_record_button_disabled
            if recording_card.get("edit_button"):
                recording_card["edit_button"].tooltip = self._["edit_record_config"]
            if recording_card.get("preview_button"):
                recording_card["preview_button"].tooltip = self._["preview_video"]
            if recording_card.get("monitor_button"):
                recording_card["monitor_button"].icon = self.get_icon_for_monitor_state(recording)
                recording_card["monitor_button"].tooltip = self.get_tip_for_monitor_state(recording)
            if recording_card.get("delete_button"):
                recording_card["delete_button"].tooltip = self._["delete_monitor"]
            if recording_card.get("get_stream_button"):
                recording_card["get_stream_button"].disabled = not (recording.monitor_status and (recording.is_live or recording.recording))
                recording_card["get_stream_button"].tooltip = (
                    self._["copy_stream_url"] if (recording.monitor_status and (recording.is_live or recording.recording)) else self._["no_stream_source"]
                )
            if recording_card.get("play_button"):
                recording_card["play_button"].disabled = not (recording.monitor_status and (recording.is_live or recording.recording))
                recording_card["play_button"].tooltip = (
                    self._["play_stream"] if (recording.monitor_status and (recording.is_live or recording.recording)) else self._["no_stream_source"]
                )
            if recording_card.get("open_folder_button"):
                recording_card["open_folder_button"].tooltip = self._["open_folder"]
            if recording_card.get("recording_info_button"):
                recording_card["recording_info_button"].tooltip = self._["recording_info"]

            # 更新缩略图开关按钮状态
            if recording_card.get("thumbnail_switch_button"):
                await self._update_thumbnail_switch_button(recording, recording.is_thumbnail_enabled(show_live_thumbnail))

            # 更新翻译开关按钮状态
            if recording_card.get("translation_switch_button"):
                global_translation_enabled = self.app.settings.user_config.get("enable_title_translation", False)
                await self._update_translation_switch_button(recording, recording.is_translation_enabled(global_translation_enabled))

            if recording_card["card"] and recording_card["card"].content:
                recording_card["card"].content.bgcolor = self.get_card_background_color(recording)
                recording_card["card"].content.border = ft.border.all(2, self.get_card_border_color(recording))
                recording_card["card"].update()
        except Exception as e:
            logger.error(f"Error updating card: {str(e)}", exc_info=True)

    async def update_monitor_state(self, recording: Recording):
        """Update the monitor button state based on the current monitoring status."""
        if recording.monitor_status:
            recording.update(
                {
                    "recording": False,
                    "monitor_status": not recording.monitor_status,
                    "status_info": RecordingStatus.STOPPED_MONITORING,
                    "display_title": f"{recording.title}",
                }
            )
            self.app.record_manager.stop_recording(recording, manually_stopped=True)
            
            # 手动停止监控时，重置通知状态和was_recording标志
            # 这样下次开始监控时可以再次发送通知
            recording.notification_sent = False
            recording.end_notification_sent = False
            if hasattr(recording, 'was_recording'):
                recording.was_recording = False
            logger.info(f"手动停止监控，重置通知状态: {recording.streamer_name}")
            
            self.app.page.run_task(self.app.snack_bar.show_snack_bar, self._["stop_monitor_tip"])
        else:
            # 开始监控前检查磁盘空间是否足够
            # 每次点击开始监控按钮都会检查空间并可能显示警告
            if not await self.app.record_manager.check_free_space():
                # 如果磁盘空间不足，不执行开始监控的操作，并返回
                logger.error("磁盘空间不足，无法开始监控")
                return
                
            # 磁盘空间足够，执行正常的开始监控操作
            recording.update(
                {
                    "monitor_status": not recording.monitor_status,
                    "status_info": RecordingStatus.MONITORING,
                    "display_title": f"{recording.title}",
                }
            )
            self.app.page.run_task(self.app.record_manager.check_if_live, recording)
            self.app.page.run_task(self.app.snack_bar.show_snack_bar, self._["start_monitor_tip"], ft.Colors.GREEN)

        await self.update_card(recording)
        self.app.page.pubsub.send_others_on_topic("update", recording)
        self.app.page.run_task(self.app.record_manager.persist_recordings)
        
        # 重新应用筛选条件，确保卡片在状态变更后显示在正确的分类中
        if hasattr(self.app, 'current_page') and hasattr(self.app.current_page, 'apply_filter'):
            await self.app.current_page.apply_filter()

        # 无论是哪种录制模式，都更新录制按钮的状态
        recording_card = self.cards_obj.get(recording.rec_id)
        if recording_card and recording_card.get("record_button"):
            # 修复：根据监控状态和直播状态综合判断是否禁用录制按钮
            is_record_button_disabled = not recording.monitor_status or (recording.monitor_status and not recording.is_live)
            recording_card["record_button"].disabled = is_record_button_disabled
            recording_card["record_button"].update()

    async def show_recording_info_dialog(self, recording: Recording):
        """Display a dialog with detailed information about the recording."""
        # 修复：同时判断开播和关播推送
        global_push_enabled = self.app.settings.user_config.get("stream_start_notification_enabled", False)
        global_end_push_enabled = self.app.settings.user_config.get("stream_end_notification_enabled", False)
        final_push_enabled = global_push_enabled or global_end_push_enabled or recording.enabled_message_push
        dialog = CardDialog(self.app, recording, final_push_enabled=final_push_enabled)
        dialog.open = True
        self.app.dialog_area.content = dialog
        self.app.page.update()

    async def edit_recording_callback(self, recording_list: list[dict]):
        recording_dict = recording_list[0]
        rec_id = recording_dict["rec_id"]
        recording = self.app.record_manager.find_recording_by_id(rec_id)

        await self.app.record_manager.update_recording_card(recording, updated_info=recording_dict)
        if not recording_dict["monitor_status"]:
            recording.display_title = recording.title

        recording.scheduled_time_range = await self.app.record_manager.get_scheduled_time_range(
            recording.scheduled_start_time, recording.monitor_hours)

        await self.update_card(recording)
        self.app.page.pubsub.send_others_on_topic("update", recording_dict)
        
        # 重新应用筛选条件，确保卡片在状态变更后显示在正确的分类中
        if hasattr(self.app, 'current_page') and hasattr(self.app.current_page, 'apply_filter'):
            await self.app.current_page.apply_filter()

    async def on_toggle_recording(self, recording: Recording):
        """Toggle recording state."""
        if recording:
            # 如果已经在录制，则停止录制
            if recording.recording:
                self.app.record_manager.stop_recording(recording, manually_stopped=True)
                await self.app.snack_bar.show_snack_bar(self._["stop_record_tip"])
            else:
                # 每次点击开始录制按钮都检查磁盘空间并可能显示警告
                if not await self.app.record_manager.check_free_space():
                    # 如果磁盘空间不足，不执行开始录制的操作，并返回
                    logger.error("磁盘空间不足，无法开始录制")
                    return
                
                # 复用自动录制参数构建方式，保证平台识别一致
                platform, platform_key = get_platform_info(recording.url)
                if not platform or not platform_key:
                    await self.app.snack_bar.show_snack_bar(
                        self._["platform_not_supported_tip"], bgcolor=ft.Colors.RED
                    )
                    return
                    
                output_dir = self.app.record_manager.settings.get_video_save_path()
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
                recording.is_live = getattr(stream_info, "is_live", False)
                if stream_info and getattr(stream_info, "record_url", None) and recording.is_live:
                    # 新增：手动模式下也赋值主播id、标题等
                    recording.live_title = getattr(stream_info, "title", None)
                    recording.streamer_name = getattr(stream_info, "anchor_name", recording.streamer_name)
                    recording.title = f"{recording.streamer_name} - {self._[recording.quality]}"
                    recording.display_title = f"[{self._['is_live']}] {recording.title}"
                    
                    # 处理翻译逻辑
                    await self._translate_live_title(recording)
                    
                    # 修复手动录制模式下的消息推送逻辑
                    if recording.record_mode == "manual":
                        try:
                            # 手动模式下，检查全局推送设置和单独的消息推送设置
                            user_config = self.app.settings.user_config
                            
                            # 检查是否启用了全局直播状态推送开关
                            global_push_enabled = user_config.get("stream_start_notification_enabled", False)
                            # 检查是否启用了该录制项的消息推送
                            item_push_enabled = recording.enabled_message_push
                            
                            logger.info(f"全局推送设置: {global_push_enabled}, 单独推送设置: {item_push_enabled}")
                            
                            # 修改：只有当全局直播状态推送开关打开AND该录制项启用了消息推送时，才进行推送
                            # 从OR条件改为AND条件，与自动模式保持一致
                            if global_push_enabled and item_push_enabled:
                                # 检查是否有至少一个推送渠道被启用
                                bark_enabled = user_config.get("bark_enabled", False)
                                wechat_enabled = user_config.get("wechat_enabled", False)
                                dingtalk_enabled = user_config.get("dingtalk_enabled", False)
                                ntfy_enabled = user_config.get("ntfy_enabled", False)
                                telegram_enabled = user_config.get("telegram_enabled", False)
                                email_enabled = user_config.get("email_enabled", False)
                                serverchan_enabled = user_config.get("serverchan_enabled", False)
                                windows_notify_enabled = user_config.get("windows_notify_enabled", False)
                                
                                any_channel_enabled = (
                                    bark_enabled or wechat_enabled or dingtalk_enabled or 
                                    ntfy_enabled or telegram_enabled or email_enabled or
                                    serverchan_enabled or windows_notify_enabled
                                )
                                
                                logger.info(f"推送渠道状态: bark={bark_enabled}, wechat={wechat_enabled}, "
                                           f"dingtalk={dingtalk_enabled}, ntfy={ntfy_enabled}, "
                                           f"telegram={telegram_enabled}, email={email_enabled}, "
                                           f"serverchan={serverchan_enabled}, windows={windows_notify_enabled}")
                                
                                # 检查是否已经发送过通知，避免重复发送
                                if any_channel_enabled and not recording.notification_sent:
                                    # 准备推送内容
                                    push_content = self._["push_content"]
                                    custom_content = user_config.get("custom_stream_start_content")
                                    if custom_content:
                                        push_content = custom_content
                                    
                                    push_at = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
                                    push_content = push_content.replace("[room_name]", recording.streamer_name).replace(
                                        "[time]", push_at
                                    )
                                    
                                    msg_title = user_config.get("custom_notification_title", "").strip()
                                    msg_title = msg_title or self._["status_notify"]
                                    
                                    # 记录推送信息
                                    logger.info(f"手动录制模式下触发消息推送: {msg_title} - {push_content}")
                                    
                                    # 创建消息推送器并发送消息
                                    msg_manager = MessagePusher(self.app.settings)
                                    
                                    # 优化: 只在Windows系统且启用Windows通知时才获取平台代码
                                    if self.app.settings.user_config.get("windows_notify_enabled") and sys.platform == "win32":
                                        # 获取平台代码用于显示对应图标
                                        _, platform_code = get_platform_info(recording.url)
                                        # 直接在当前任务中执行推送
                                        self.app.page.run_task(msg_manager.push_messages, msg_title, push_content, platform_code)
                                    else:
                                        # 其他情况不传递平台代码
                                        self.app.page.run_task(msg_manager.push_messages, msg_title, push_content)
                                    
                                    logger.info("已创建消息推送任务")
                                    # 设置通知已发送标志
                                    recording.notification_sent = True
                                elif recording.notification_sent:
                                    logger.info(f"已经发送过开播通知，跳过重复发送: {recording.streamer_name}")
                                else:
                                    logger.info("没有启用任何推送渠道，跳过消息推送")
                            else:
                                logger.info("全局推送开关和单独推送设置必须同时启用，跳过消息推送")
                        except Exception as e:
                            logger.error(f"手动录制模式下消息推送失败: {str(e)}")
                    
                    self.app.record_manager.start_update(recording)
                    await recorder.start_recording(stream_info)
                    await self.app.snack_bar.show_snack_bar(self._["pre_record_tip"], bgcolor=ft.Colors.GREEN)
                    # 注意：此时不重置notification_sent标志，保持其状态
                    # 这样在停止录制返回"直播中（未录制）"状态时不会重复发送通知
                    logger.info(f"开始录制，保持通知状态: {recording.streamer_name}")
                else:
                    pass
            await self.update_card(recording)
            self.app.page.pubsub.send_others_on_topic("update", recording)
            
            # 重新应用筛选条件，确保卡片在状态变更后显示在正确的分类中
            if hasattr(self.app, 'current_page') and hasattr(self.app.current_page, 'apply_filter'):
                await self.app.current_page.apply_filter()

    async def on_delete_recording(self, recording: Recording):
        """Delete a recording from the list and update UI."""
        if recording:
            # 在删除前检查是否需要切换平台视图
            home_page = self.app.current_page
            need_switch_to_all = False
            
            if hasattr(home_page, "current_platform_filter") and home_page.current_platform_filter != "all":
                # 获取当前平台
                current_platform = home_page.current_platform_filter
                _, recording_platform = get_platform_info(recording.url)
                
                # 如果要删除的是当前筛选平台的录制项
                if recording_platform == current_platform:
                    # 检查是否还有其他相同平台的录制项
                    remaining_items = 0
                    for rec in self.app.record_manager.recordings:
                        if rec.rec_id != recording.rec_id:  # 排除当前要删除的项
                            _, platform_key = get_platform_info(rec.url)
                            if platform_key == current_platform:
                                remaining_items += 1
                    
                    # 如果没有剩余项，准备切换到全部平台视图
                    if remaining_items == 0:
                        need_switch_to_all = True
                        logger.info(f"删除后平台 {current_platform} 下没有剩余直播间，将切换到全部平台视图")
            
            # 删除平台logo缓存
            self.app.platform_logo_cache.remove_logo_cache(recording.rec_id)
            
            # 删除缩略图文件
            if hasattr(self.app, 'thumbnail_manager'):
                self.app.thumbnail_manager.delete_thumbnails_for_recording(recording.rec_id)
            
            # 执行删除操作
            await self.app.record_manager.delete_recording_cards([recording])
            
            # 如果需要切换到全部平台视图
            if need_switch_to_all and hasattr(home_page, "current_platform_filter"):
                home_page.current_platform_filter = "all"
                home_page.page.run_task(home_page.apply_filter)
            
            await self.app.snack_bar.show_snack_bar(
                self._["delete_recording_success_tip"], bgcolor=ft.Colors.GREEN, duration=2000
            )

    async def remove_recording_card(self, recordings: list[Recording]):
        home_page = self.app.current_page

        existing_ids = {rec.rec_id for rec in self.app.record_manager.recordings}
        remove_ids = {rec.rec_id for rec in recordings}
        keep_ids = existing_ids - remove_ids
        
        # 批量删除平台logo缓存
        self.app.platform_logo_cache.remove_multiple_logo_cache(list(remove_ids))
        
        # 批量删除缩略图文件
        if hasattr(self.app, 'thumbnail_manager'):
            self.app.thumbnail_manager.delete_thumbnails_for_recordings(list(remove_ids))

        cards_to_remove = [
            card_data["card"]
            for rec_id, card_data in self.cards_obj.items()
            if rec_id not in keep_ids
        ]

        home_page.recording_card_area.content.controls = [
            control
            for control in home_page.recording_card_area.content.controls
            if control not in cards_to_remove
        ]

        self.cards_obj = {
            k: v for k, v in self.cards_obj.items()
            if k in keep_ids
        }
        home_page.recording_card_area.update()
        
        # 删除卡片后更新筛选区域
        if hasattr(home_page, "create_filter_area") and hasattr(home_page, "content_area"):
            # 检查是否需要切换到全部平台视图
            if hasattr(home_page, "current_platform_filter") and home_page.current_platform_filter != "all":
                # 获取当前平台下的录制项
                current_platform = home_page.current_platform_filter
                remaining_items = False
                
                # 检查是否还有当前平台的录制项
                for recording in self.app.record_manager.recordings:
                    _, platform_key = get_platform_info(recording.url)
                    if platform_key == current_platform:
                        remaining_items = True
                        break
                
                # 如果当前平台没有剩余录制项，自动切换到全部平台视图
                if not remaining_items:
                    logger.info(f"平台 {current_platform} 下没有剩余直播间，自动切换到全部平台视图")
                    home_page.current_platform_filter = "all"
            
            # 更新筛选区域
            home_page.content_area.controls[1] = home_page.create_filter_area()
            home_page.content_area.update()
            
            # 应用筛选
            if hasattr(home_page, "apply_filter"):
                self.app.page.run_task(home_page.apply_filter)

    @staticmethod
    async def update_record_hover(recording: Recording):
        return ft.Colors.GREY_400 if recording.selected else None

    @staticmethod
    def get_icon_for_recording_state(recording: Recording):
        """Return the appropriate icon based on the recording's state."""
        return ft.Icons.PLAY_CIRCLE if not recording.recording else ft.Icons.STOP_CIRCLE

    def get_tip_for_recording_state(self, recording: Recording):
        # 修改：无论哪种模式，停止监控状态下都显示需要开启监控的提示
        if not recording.monitor_status:
            return self._["tip_start_monitor_first"]
        # 添加未开播状态的提示
        elif recording.monitor_status and not recording.is_live:
            return self._["tip_not_live"]
        elif recording.recording:
            return self._["tip_stop_recording"]
        return self._["tip_start_recording"]

    @staticmethod
    def get_icon_for_monitor_state(recording: Recording):
        """Return the appropriate icon based on the monitor's state."""
        return ft.Icons.VISIBILITY if recording.monitor_status else ft.Icons.VISIBILITY_OFF

    def get_tip_for_monitor_state(self, recording: Recording):
        return self._["stop_monitor"] if recording.monitor_status else self._["start_monitor"]

    async def update_duration(self, recording: Recording):
        """Update the duration text periodically."""
        while True:
            await asyncio.sleep(1)  # Update every second
            if not recording or recording.rec_id not in self.cards_obj:  # Stop task if card is removed
                break

            if recording.recording:
                duration_label = self.cards_obj[recording.rec_id]["duration_label"]
                duration_label.value = self.app.record_manager.get_duration(recording)
                duration_label.update()

    def start_update_task(self, recording: Recording):
        """Start a background task to update the duration text."""
        self.update_duration_tasks[recording.rec_id] = self.app.page.run_task(self.update_duration, recording)

    async def on_card_click(self, recording: Recording):
        """Handle card click events."""
        recording.selected = not recording.selected
        self.selected_cards[recording.rec_id] = recording
        self.cards_obj[recording.rec_id]["card"].content.bgcolor = await self.update_record_hover(recording)
        self.cards_obj[recording.rec_id]["card"].update()

    async def recording_dir_on_click(self, recording: Recording):
        if recording.recording_dir:
            if os.path.exists(recording.recording_dir):
                if not utils.open_folder(recording.recording_dir):
                    await self.app.snack_bar.show_snack_bar(self._['no_video_file'])
            else:
                await self.app.snack_bar.show_snack_bar(self._["no_recording_folder"])
        else:
            await self.app.snack_bar.show_snack_bar(self._["no_recording_started"])

    async def edit_recording_button_click(self, _, recording: Recording):
        """Handle edit button click by showing the edit dialog with existing recording info."""

        if recording.recording or recording.monitor_status:
            await self.app.snack_bar.show_snack_bar(self._["please_stop_monitor_tip"])
            return

        await RecordingDialog(
            self.app,
            on_confirm_callback=self.edit_recording_callback,
            recording=recording,
        ).show_dialog()

    async def recording_delete_button_click(self, _, recording: Recording):
        # 检查是否正在录制，如果是则直接提示
        if recording.recording:
            await self.app.snack_bar.show_snack_bar(
                self._["recording_in_progress_tip"], bgcolor=ft.Colors.RED
            )
            return

        async def confirm_dlg(_):
            self.app.page.run_task(self.on_delete_recording, recording)
            await close_dialog(None)

        async def close_dialog(_):
            delete_alert_dialog.open = False
            delete_alert_dialog.update()

        delete_alert_dialog = ft.AlertDialog(
            title=ft.Text(self._["confirm"]),
            content=ft.Text(self._["delete_confirm_tip"]),
            actions=[
                ft.TextButton(text=self._["cancel"], on_click=close_dialog),
                ft.TextButton(text=self._["sure"], on_click=confirm_dlg),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            modal=False,
        )
        delete_alert_dialog.open = True
        self.app.dialog_area.content = delete_alert_dialog
        self.app.page.update()

    async def preview_video_button_on_click(self, _, recording: Recording):
        if self.app.page.web and recording.record_url:
            video_player = VideoPlayer(self.app)
            await video_player.preview_video(recording.record_url, is_file_path=False, room_url=recording.url)
        elif recording.recording_dir and os.path.exists(recording.recording_dir):
            video_files = []
            for root, _, files in os.walk(recording.recording_dir):
                for file in files:
                    if utils.is_valid_video_file(file):
                        video_files.append(os.path.join(root, file))

            if video_files:
                video_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                latest_video = video_files[0]
                await StoragePage(self.app).preview_file(latest_video, recording.url)
            else:
                await self.app.snack_bar.show_snack_bar(self._["no_video_file"])
        elif not recording.recording_dir:
            await self.app.snack_bar.show_snack_bar(self._["no_recording_started"])
        else:
            await self.app.snack_bar.show_snack_bar(self._["no_recording_folder"])

    async def recording_button_on_click(self, _, recording: Recording):
        await self.on_toggle_recording(recording)

    async def recording_dir_button_on_click(self, _, recording: Recording):
        await self.recording_dir_on_click(recording)

    async def recording_info_button_on_click(self, _, recording: Recording):
        await self.show_recording_info_dialog(recording)

    async def monitor_button_on_click(self, _, recording: Recording):
        await self.update_monitor_state(recording)

    async def recording_card_on_click(self, _, recording: Recording):
        await self.on_card_click(recording)

    async def subscribe_update_card(self, _, recording: Recording):
        await self.update_card(recording)
        
        # 重新应用筛选条件，确保卡片在状态变更后显示在正确的分类中
        if hasattr(self.app, 'current_page') and hasattr(self.app.current_page, 'apply_filter'):
            await self.app.current_page.apply_filter()

    async def subscribe_remove_cards(self, _, recordings: list[Recording]):
        await self.remove_recording_card(recordings)

    async def get_stream_url_on_click(self, _, recording: Recording):
        if not recording.monitor_status:
            await self.app.snack_bar.show_snack_bar(self._["please_start_monitor"], bgcolor=ft.Colors.RED)
            return
        stream_url, err = await self.app.record_manager.get_stream_url(recording)
        if stream_url:
            self.app.page.set_clipboard(stream_url)
            await self.app.snack_bar.show_snack_bar(self._["stream_url_copied"], bgcolor=ft.Colors.GREEN)
        else:
            await self.app.snack_bar.show_snack_bar(err or self._["no_stream_url"], bgcolor=ft.Colors.RED)

    async def play_stream_on_click(self, _, recording: Recording):
        if not recording.monitor_status:
            await self.app.snack_bar.show_snack_bar(self._["please_start_monitor"], bgcolor=ft.Colors.RED)
            return
        
        # 获取用户选择的默认播放器
        default_player = self.app.settings.user_config.get("default_player", "potplayer")
        
        # 根据选择的播放器获取相应的路径和可执行文件名
        if default_player == "vlc":
            player_path = self.app.settings.user_config.get("vlc_path")
            exe_name = "vlc.exe"
            not_set_message = self._["vlc_not_set"]
        else:  # potplayer
            player_path = self.app.settings.user_config.get("potplayer_path")
            exe_name = "PotPlayerMini64.exe"
            not_set_message = self._["potplayer_not_set"]
        
        if not player_path:
            await self.app.snack_bar.show_snack_bar(not_set_message, bgcolor=ft.Colors.RED)
            return
        
        # 处理播放器路径：如果是目录路径，自动拼接可执行文件名
        if os.path.isdir(player_path):
            player_exe_path = os.path.join(player_path, exe_name)
            if os.path.exists(player_exe_path):
                player_path = player_exe_path
            else:
                await self.app.snack_bar.show_snack_bar(not_set_message, bgcolor=ft.Colors.RED)
                return
        elif not os.path.exists(player_path):
            await self.app.snack_bar.show_snack_bar(not_set_message, bgcolor=ft.Colors.RED)
            return
            
        stream_url, err = await self.app.record_manager.get_stream_url(recording)
        if stream_url:
            import subprocess
            try:
                subprocess.Popen([player_path, stream_url])
                await self.app.snack_bar.show_snack_bar(self._["play_stream"] + "...", bgcolor=ft.Colors.GREEN)
            except Exception as e:
                await self.app.snack_bar.show_snack_bar(self._["play_failed"] + f"\n{e}", bgcolor=ft.Colors.RED)
        else:
            await self.app.snack_bar.show_snack_bar(err or self._["play_failed"], bgcolor=ft.Colors.RED)

    async def update_thumbnail(self, recording: Recording, thumbnail_path: str):
        """更新卡片中的缩略图"""
        try:
            rec_id = recording.rec_id
            card_data = self.cards_obj.get(rec_id)
            
            if not card_data:
                logger.debug(f"无法更新缩略图: 未找到卡片数据 {rec_id}")
                return
            
            # 获取缩略图设置
            show_live_thumbnail = self.app.settings.user_config.get("show_live_thumbnail", False)
            
            # 检查单个房间的缩略图设置
            should_show_thumbnail = recording.is_thumbnail_enabled(show_live_thumbnail)
            
            # 获取缩略图和logo组件
            thumbnail_image = card_data.get("thumbnail_image")
            platform_logo = card_data.get("platform_logo")
            overlay_logo = card_data.get("overlay_logo")
            
            if not thumbnail_image or not platform_logo or not overlay_logo:
                logger.debug(f"无法更新缩略图: 缺少必要组件 {rec_id}")
                return
            
            # 更新UI组件
            if should_show_thumbnail and (recording.is_live or recording.recording):
                # 确保文件存在
                if not os.path.exists(thumbnail_path):
                    logger.error(f"缩略图文件不存在: {thumbnail_path}")
                    return
                
                # 更新缩略图
                thumbnail_image.src = thumbnail_path
                thumbnail_image.visible = True
                
                # 隐藏主logo，显示小logo
                platform_logo.visible = False
                overlay_logo.visible = True
            else:
                # 显示主logo，隐藏缩略图和小logo
                thumbnail_image.visible = False
                platform_logo.visible = True
                overlay_logo.visible = False
            
            # 更新UI
            self.app.page.update()
            
        except Exception as e:
            logger.error(f"更新缩略图时发生错误: {e}")

    async def thumbnail_switch_button_on_click(self, _, recording: Recording):
        """处理缩略图开关按钮点击事件"""
        try:
            # 检查是否在直播状态，如果不在直播状态则直接返回
            if not (recording.monitor_status and (recording.is_live or recording.recording)):
                return
            
            # 获取全局缩略图设置
            global_thumbnail_enabled = self.app.settings.user_config.get("show_live_thumbnail", False)
            
            # 获取当前房间的缩略图状态
            current_thumbnail_enabled = recording.is_thumbnail_enabled(global_thumbnail_enabled)
            
            # 切换房间的缩略图设置
            if recording.thumbnail_enabled is None:
                # 如果当前使用全局设置，则设置为与全局设置相反
                recording.thumbnail_enabled = not global_thumbnail_enabled
            else:
                # 如果当前有独立设置，则切换该设置
                recording.thumbnail_enabled = not recording.thumbnail_enabled
            
            # 获取新的缩略图状态
            new_thumbnail_enabled = recording.is_thumbnail_enabled(global_thumbnail_enabled)
            
            # 更新按钮状态和提示
            await self._update_thumbnail_switch_button(recording, new_thumbnail_enabled)
            
            # 根据新的设置启动或停止缩略图捕获
            if hasattr(self.app, 'thumbnail_manager'):
                if new_thumbnail_enabled and (recording.is_live or recording.recording):
                    # 开启缩略图捕获
                    self.app.page.run_task(self.app.thumbnail_manager.start_thumbnail_capture, recording)
                    await self.app.snack_bar.show_snack_bar(self._["thumbnail_enabled_for_room"], ft.Colors.GREEN)
                else:
                    # 停止缩略图捕获
                    self.app.page.run_task(self.app.thumbnail_manager.stop_thumbnail_capture, recording)
                    await self.app.snack_bar.show_snack_bar(self._["thumbnail_disabled_for_room"], ft.Colors.BLUE)
            
            # 更新卡片显示
            await self.update_card(recording)
            
            # 保存录制配置
            self.app.page.run_task(self.app.record_manager.persist_recordings)
            
        except Exception as e:
            logger.error(f"切换房间缩略图设置时发生错误: {e}")
            await self.app.snack_bar.show_snack_bar(f"切换缩略图设置失败: {e}", ft.Colors.RED)
    
    async def _update_thumbnail_switch_button(self, recording: Recording, thumbnail_enabled: bool):
        """更新缩略图开关按钮的状态"""
        try:
            rec_id = recording.rec_id
            card_data = self.cards_obj.get(rec_id)
            
            if not card_data:
                return
            
            thumbnail_switch_button = card_data.get("thumbnail_switch_button")
            if not thumbnail_switch_button:
                return
            
            # 获取全局缩略图设置
            global_thumbnail_enabled = self.app.settings.user_config.get("show_live_thumbnail", False)
            
            # 设置按钮禁用状态：不在直播状态时禁用
            is_thumbnail_button_disabled = not (recording.monitor_status and (recording.is_live or recording.recording))
            thumbnail_switch_button.disabled = is_thumbnail_button_disabled
            
            # 更新按钮图标和提示
            if is_thumbnail_button_disabled:
                # 按钮被禁用时，显示禁用提示
                thumbnail_switch_button.tooltip = self._["thumbnail_switch_tip_disabled"]
            elif recording.thumbnail_enabled is None:
                # 使用全局设置
                if global_thumbnail_enabled:
                    thumbnail_switch_button.icon = ft.Icons.PHOTO_LIBRARY
                    thumbnail_switch_button.tooltip = self._["thumbnail_switch_tip_on"]
                else:
                    thumbnail_switch_button.icon = ft.Icons.PHOTO_LIBRARY_OUTLINED
                    thumbnail_switch_button.tooltip = self._["thumbnail_switch_tip_off"]
            else:
                # 使用独立设置
                if recording.thumbnail_enabled:
                    thumbnail_switch_button.icon = ft.Icons.PHOTO_LIBRARY
                    thumbnail_switch_button.tooltip = self._["thumbnail_switch_tip_on"]
                else:
                    thumbnail_switch_button.icon = ft.Icons.PHOTO_LIBRARY_OUTLINED
                    thumbnail_switch_button.tooltip = self._["thumbnail_switch_tip_off"]
            
            # 更新UI
            thumbnail_switch_button.update()
            
        except Exception as e:
            logger.error(f"更新缩略图开关按钮状态时发生错误: {e}")

    async def translation_switch_button_on_click(self, _, recording: Recording):
        """处理翻译开关按钮点击事件"""
        try:
            # 检查是否在直播状态，如果不在直播状态则直接返回
            if not (recording.monitor_status and (recording.is_live or recording.recording)):
                return
            
            # 获取全局翻译设置
            global_translation_enabled = self.app.settings.user_config.get("enable_title_translation", False)
            
            # 获取当前房间的翻译状态
            current_translation_enabled = recording.is_translation_enabled(global_translation_enabled)
            
            # 切换房间的翻译设置
            if recording.translation_enabled is None:
                # 如果当前使用全局设置，则设置为与当前状态相反
                recording.translation_enabled = not current_translation_enabled
            else:
                # 如果当前有独立设置，则切换该设置
                recording.translation_enabled = not recording.translation_enabled
            
            # 获取新的翻译状态
            new_translation_enabled = recording.is_translation_enabled(global_translation_enabled)
            
            # 更新按钮状态和提示
            await self._update_translation_switch_button(recording, new_translation_enabled)
            
            # 根据新的设置处理翻译
            if new_translation_enabled and recording.live_title:
                # 如果开启翻译且有直播标题，检查是否有缓存的翻译结果
                if recording.cached_translated_title and recording.live_title == recording.last_live_title:
                    # 如果有缓存且标题没有变化，直接使用缓存的翻译结果
                    recording.translated_title = recording.cached_translated_title
                else:
                    # 如果没有缓存或标题有变化，进行新的翻译
                    await self._translate_live_title(recording, force_translate=True)
            else:
                # 关闭翻译时，清除翻译标题但保留缓存
                recording.translated_title = None
            
            # 更新卡片显示
            await self.update_card(recording)
            
            # 保存录制配置
            self.app.page.run_task(self.app.record_manager.persist_recordings)
            
            # 显示提示信息
            if new_translation_enabled:
                await self.app.snack_bar.show_snack_bar(self._["translation_enabled_for_room"], ft.Colors.GREEN)
            else:
                await self.app.snack_bar.show_snack_bar(self._["translation_disabled_for_room"], ft.Colors.BLUE)
            
        except Exception as e:
            logger.error(f"切换房间翻译设置时发生错误: {e}")
            await self.app.snack_bar.show_snack_bar(f"切换翻译设置失败: {e}", ft.Colors.RED)
    
    async def _update_translation_switch_button(self, recording: Recording, translation_enabled: bool):
        """更新翻译开关按钮的状态"""
        try:
            rec_id = recording.rec_id
            card_data = self.cards_obj.get(rec_id)
            
            if not card_data:
                return
            
            translation_switch_button = card_data.get("translation_switch_button")
            if not translation_switch_button:
                return
            
            # 获取全局翻译设置
            global_translation_enabled = self.app.settings.user_config.get("enable_title_translation", False)
            
            # 设置按钮禁用状态：不在直播状态时禁用
            is_translation_button_disabled = not (recording.monitor_status and (recording.is_live or recording.recording))
            translation_switch_button.disabled = is_translation_button_disabled
            
            # 更新按钮图标、颜色和提示
            if is_translation_button_disabled:
                # 按钮被禁用时，显示禁用提示
                translation_switch_button.tooltip = self._["translation_switch_tip_disabled"]
            elif recording.translation_enabled is None:
                # 使用全局设置
                if global_translation_enabled:
                    translation_switch_button.icon = ft.Icons.TRANSLATE
                    translation_switch_button.tooltip = self._["translation_switch_tip_on"]
                    translation_switch_button.style = ft.ButtonStyle(
                        color=ft.Colors.GREEN_600,
                        overlay_color=ft.Colors.GREEN_50,
                    )
                else:
                    translation_switch_button.icon = ft.Icons.TRANSLATE_OUTLINED
                    translation_switch_button.tooltip = self._["translation_switch_tip_off"]
                    translation_switch_button.style = ft.ButtonStyle(
                        color=ft.Colors.GREY_600,
                        overlay_color=ft.Colors.TRANSPARENT,
                    )
            else:
                # 使用独立设置
                if recording.translation_enabled:
                    translation_switch_button.icon = ft.Icons.TRANSLATE
                    translation_switch_button.tooltip = self._["translation_switch_tip_on"]
                    translation_switch_button.style = ft.ButtonStyle(
                        color=ft.Colors.GREEN_600,
                        overlay_color=ft.Colors.GREEN_50,
                    )
                else:
                    translation_switch_button.icon = ft.Icons.TRANSLATE_OUTLINED
                    translation_switch_button.tooltip = self._["translation_switch_tip_off"]
                    translation_switch_button.style = ft.ButtonStyle(
                        color=ft.Colors.GREY_600,
                        overlay_color=ft.Colors.TRANSPARENT,
                    )
            
            # 更新UI
            translation_switch_button.update()
            
        except Exception as e:
            logger.error(f"更新翻译开关按钮状态时发生错误: {e}")

    async def _translate_live_title(self, recording: Recording, force_translate: bool = False):
        """翻译直播标题（支持国际化）"""
        try:
            if not recording.live_title:
                return
            
            # 检查标题是否有变化，如果没有变化则不需要重新翻译（除非强制翻译）
            if not force_translate and recording.live_title == recording.last_live_title:
                # 标题没有变化，不需要重新翻译
                return
                
            # 获取全局翻译设置
            global_translation_enabled = self.app.settings.user_config.get("enable_title_translation", False)
            
            # 检查是否应该翻译
            should_translate = recording.is_translation_enabled(global_translation_enabled)
            
            if should_translate:
                # 导入翻译服务
                from ...utils.translation_service import translate_live_title
                
                # 获取当前程序语言代码
                app_language_code = self.app.settings.language_code
                
                # 翻译标题（根据程序语言选择目标语言）
                translated = await translate_live_title(recording.live_title, app_language_code, self.app.config_manager)
                if translated and translated != recording.live_title:
                    recording.translated_title = translated
                    recording.cached_translated_title = translated  # 保存到缓存
                    #logger.info(f"翻译成功: '{recording.live_title}' -> '{translated}' (目标语言: {app_language_code})")
                else:
                    recording.translated_title = None
                    #logger.debug(f"翻译失败或不需要翻译: '{recording.live_title}' (目标语言: {app_language_code})")
            else:
                # 如果不需要翻译，清除翻译标题
                recording.translated_title = None
            
            # 更新上次的直播标题缓存
            recording.last_live_title = recording.live_title
                
        except Exception as e:
            logger.error(f"翻译直播标题时发生错误: {e}")
            recording.translated_title = None
