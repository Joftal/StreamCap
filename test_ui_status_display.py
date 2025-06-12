#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
主界面直播状态卡片演示脚本
用于展示不同直播状态下的卡片表现
"""

import asyncio
import os
import sys
import time
import uuid
from typing import List, Dict, Tuple

import flet as ft

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.recording_model import Recording
from app.models.recording_status_model import RecordingStatus
from app.core.platform_handlers.platform_map import get_platform_display_name, platform_map


class UIDemoApp:
    def __init__(self):
        self.page = None
        self.recordings = []
        self.platform_icons_path = "assets/icons/platforms"
        self.current_platform_filter = "all"
        self.current_filter = "all"  # 状态筛选：all, recording, live_monitoring_not_recording, offline, error, stopped
        self._ = self.load_language_dict()
        
    def load_language_dict(self) -> Dict:
        """加载语言字典（演示用）"""
        return {
            "recording": "录制中",
            "recording_error": "录制错误",
            "offline": "未开播",
            "no_monitor": "未监控",
            "live_monitoring_not_recording": "直播中(未录制)",
            "monitor_stopped": "停止监控中",
            "edit_record_config": "编辑录制配置",
            "preview_video": "预览视频",
            "delete_monitor": "删除监控",
            "copy_stream_url": "复制直播链接",
            "no_stream_source": "无直播源",
            "play_stream": "播放直播",
            "open_folder": "打开文件夹",
            "recording_info": "录制信息",
            "tip_start_monitor_first": "请先开启监控",
            "tip_not_live": "未开播",
            "tip_stop_recording": "停止录制",
            "tip_start_recording": "开始录制",
            "start_monitor": "开始监控",
            "stop_monitor": "停止监控",
            "filter": "筛选",
            "filter_all": "全部",
            "filter_recording": "录制中",
            "filter_live_monitoring_not_recording": "直播中(未录制)",
            "filter_offline": "未开播",
            "filter_error": "录制错误",
            "filter_stopped": "停止监控中",
            "platform_filter": "平台筛选",
            "filter_all_platforms": "全部平台",
            # 画质翻译
            "OD": "原画",
            "UHD": "超清",
            "HD": "高清",
            "SD": "标清",
            "LD": "流畅"
        }

    async def main(self, page: ft.Page):
        self.page = page
        self.page.title = "StreamCap主界面状态卡片演示"
        self.page.theme_mode = ft.ThemeMode.SYSTEM
        self.page.window_width = 1000
        self.page.window_height = 800
        self.page.padding = 20

        # 标题
        title = ft.Text("StreamCap主界面状态卡片演示", size=24, weight=ft.FontWeight.BOLD)
        subtitle = ft.Text("展示不同直播状态下卡片的表现", size=16, weight=ft.FontWeight.BOLD)
        
        # 创建不同状态的示例卡片
        await self.create_demo_recordings()
        
        # 创建筛选区域
        filter_area = self.create_filter_area()
        
        # 创建卡片容器
        cards_container = await self.create_cards_container()
        
        # 页面布局
        self.page.add(
            title,
            subtitle,
            ft.Divider(),
            ft.Text("筛选区域:", weight=ft.FontWeight.BOLD),
            filter_area,
            ft.Divider(),
            ft.Text("各状态卡片展示:", weight=ft.FontWeight.BOLD),
            cards_container
        )

    def create_filter_area(self):
        """创建筛选区域，包含状态筛选和平台筛选"""
        # 状态筛选行
        status_filter_row = ft.Row(
            [
                ft.Text(self._["filter"] + ":", size=14, weight=ft.FontWeight.BOLD),
                ft.ElevatedButton(
                    self._["filter_all"],
                    on_click=lambda e: self.page.run_task(self.filter_all_on_click),
                    bgcolor=ft.Colors.BLUE if self.current_filter == "all" else None,
                    color=ft.Colors.WHITE if self.current_filter == "all" else None,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                ),
                ft.ElevatedButton(
                    self._["filter_recording"],
                    on_click=lambda e: self.page.run_task(self.filter_recording_on_click),
                    bgcolor=ft.Colors.GREEN if self.current_filter == "recording" else None,
                    color=ft.Colors.WHITE if self.current_filter == "recording" else None,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                ),
                ft.ElevatedButton(
                    self._["filter_live_monitoring_not_recording"],
                    on_click=lambda e: self.page.run_task(self.filter_live_monitoring_not_recording_on_click),
                    bgcolor=ft.Colors.CYAN if self.current_filter == "live_monitoring_not_recording" else None,
                    color=ft.Colors.WHITE if self.current_filter == "live_monitoring_not_recording" else None,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                ),
                ft.ElevatedButton(
                    self._["filter_offline"],
                    on_click=lambda e: self.page.run_task(self.filter_offline_on_click),
                    bgcolor=ft.Colors.AMBER if self.current_filter == "offline" else None,
                    color=ft.Colors.WHITE if self.current_filter == "offline" else None,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                ),
                ft.ElevatedButton(
                    self._["filter_error"],
                    on_click=lambda e: self.page.run_task(self.filter_error_on_click),
                    bgcolor=ft.Colors.RED if self.current_filter == "error" else None,
                    color=ft.Colors.WHITE if self.current_filter == "error" else None,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                ),
                ft.ElevatedButton(
                    self._["filter_stopped"],
                    on_click=lambda e: self.page.run_task(self.filter_stopped_on_click),
                    bgcolor=ft.Colors.GREY if self.current_filter == "stopped" else None,
                    color=ft.Colors.WHITE if self.current_filter == "stopped" else None,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                ),
            ],
            alignment=ft.MainAxisAlignment.START,
            spacing=5,
            scroll=ft.ScrollMode.AUTO,
        )
        
        # 平台筛选行
        platforms = self.get_available_platforms()
        platform_buttons = [
            ft.ElevatedButton(
                self._["filter_all_platforms"],
                on_click=lambda e: self.page.run_task(self.filter_all_platforms_on_click),
                bgcolor=ft.Colors.BLUE if self.current_platform_filter == "all" else None,
                color=ft.Colors.WHITE if self.current_platform_filter == "all" else None,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
            )
        ]
        
        for platform_key in platforms:
            display_name = get_platform_display_name(platform_key, "zh")
            selected = self.current_platform_filter == platform_key
            platform_buttons.append(
                ft.ElevatedButton(
                    display_name,
                    on_click=lambda e, k=platform_key: self.page.run_task(self.on_platform_button_click, k),
                    bgcolor=ft.Colors.BLUE if selected else None,
                    color=ft.Colors.WHITE if selected else None,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                )
            )
        
        platform_filter_row = ft.Row(
            [
                ft.Text(self._["platform_filter"] + ":", size=14, weight=ft.FontWeight.BOLD),
                *platform_buttons
            ],
            alignment=ft.MainAxisAlignment.START,
            spacing=5,
            scroll=ft.ScrollMode.AUTO,
        )
        
        # 将两行组合到一个Column中
        return ft.Column(
            controls=[
                status_filter_row,
                platform_filter_row
            ],
            spacing=10,
        )

    def get_available_platforms(self):
        """获取所有可用平台"""
        platforms = set()
        
        for recording in self.recordings:
            if hasattr(recording, 'url') and recording.url:
                platform_type = self.get_platform_type(recording.url)
                if platform_type and platform_type != "moren":
                    platforms.add(platform_type)
        
        return sorted(list(platforms))
    
    async def filter_all_platforms_on_click(self):
        """所有平台按钮点击处理"""
        self.current_platform_filter = "all"
        await self.apply_filter()
    
    async def on_platform_button_click(self, platform_key):
        """平台按钮点击处理"""
        self.current_platform_filter = platform_key
        await self.apply_filter()

    async def apply_filter(self):
        """应用筛选"""
        # 更新筛选区域
        filter_area = self.create_filter_area()
        self.page.controls[4] = filter_area
        
        # 重新创建卡片列表
        await self.refresh_cards()
        
        self.page.update()
    
    async def refresh_cards(self):
        """刷新卡片显示"""
        # 清空卡片列表
        self.list_view.controls.clear()
        
        # 添加符合条件的卡片
        for recording in self.recordings:
            if self.should_show_recording(recording):
                card = await self.create_card(recording)
                self.list_view.controls.append(card)
                
        # 更新UI
        self.page.update()
    
    def should_show_recording(self, recording):
        """判断是否应该显示录制卡片"""
        # 如果不是全部平台且平台不匹配，则不显示
        if self.current_platform_filter != "all":
            platform_type = self.get_platform_type(recording.url)
            if platform_type != self.current_platform_filter:
                return False
        
        # 状态筛选
        if self.current_filter != "all":
            if self.current_filter == "recording" and not recording.recording:
                return False
            elif self.current_filter == "live_monitoring_not_recording":
                # 直播中（未录制）状态：主播开播、监控开启、未录制、且不是录制错误状态
                is_live_not_recording = (recording.is_live and 
                                         not recording.recording and 
                                         recording.monitor_status and 
                                         recording.status_info != RecordingStatus.RECORDING_ERROR)
                if not is_live_not_recording:
                    return False
            elif self.current_filter == "offline" and not (not recording.is_live and recording.monitor_status):
                return False
            elif self.current_filter == "error" and recording.status_info != RecordingStatus.RECORDING_ERROR:
                return False
            elif self.current_filter == "stopped" and recording.monitor_status:
                return False
            
        return True

    async def create_demo_recordings(self):
        """创建演示用的Recording对象，不同平台不同状态"""
        self.recordings = []
        
        # 创建不同平台的卡片
        platforms = ["bilibili", "douyu", "huya", "youtube", "twitch"]
        
        # 为每个平台创建不同状态的卡片
        for platform in platforms:
            # 获取平台信息
            platform_name = get_platform_display_name(platform, "zh")
            platform_url = self.get_platform_url(platform)
            
            # 录制中状态
            recording_id = str(uuid.uuid4())
            recording1 = Recording(
                rec_id=recording_id,
                url=platform_url,
                streamer_name=f"{platform_name}主播",
                record_format="mp4",
                quality="OD",
                segment_record=True,
                segment_time=3600,
                monitor_status=True,
                scheduled_recording=False,
                scheduled_start_time=None,
                monitor_hours=None,
                recording_dir=f"downloads/{platform}-录制中",
                enabled_message_push=True,
                record_mode="auto"
            )
            recording1.is_live = True
            recording1.recording = True
            recording1.speed = "1.2 MB/s"
            recording1.status_info = RecordingStatus.RECORDING
            recording1.title = f"{recording1.streamer_name} - {self._[recording1.quality]}"
            self.recordings.append(recording1)
            
            # 开播但未录制状态
            recording_id = str(uuid.uuid4())
            recording2 = Recording(
                rec_id=recording_id,
                url=platform_url,
                streamer_name=f"{platform_name}女神",
                record_format="mp4",
                quality="HD",
                segment_record=True,
                segment_time=3600,
                monitor_status=True,
                scheduled_recording=False,
                scheduled_start_time=None,
                monitor_hours=None,
                recording_dir=f"downloads/{platform}-开播未录制",
                enabled_message_push=True,
                record_mode="manual"
            )
            recording2.is_live = True
            recording2.recording = False
            recording2.speed = "0 KB/s"
            recording2.status_info = RecordingStatus.MONITORING
            recording2.title = f"{recording2.streamer_name} - {self._[recording2.quality]}"
            self.recordings.append(recording2)
            
            # 监控中但未开播状态
            recording_id = str(uuid.uuid4())
            recording3 = Recording(
                rec_id=recording_id,
                url=platform_url,
                streamer_name=f"{platform_name}小哥",
                record_format="ts",
                quality="HD",
                segment_record=False,
                segment_time=0,
                monitor_status=True,
                scheduled_recording=True,
                scheduled_start_time="20:00:00",
                monitor_hours=3,
                recording_dir=f"downloads/{platform}-未开播",
                enabled_message_push=True,
                record_mode="auto"
            )
            recording3.is_live = False
            recording3.recording = False
            recording3.speed = "0 KB/s"
            recording3.status_info = RecordingStatus.NOT_RECORDING
            recording3.title = f"{recording3.streamer_name} - {self._[recording3.quality]}"
            self.recordings.append(recording3)
            
            # 停止监控状态
            recording_id = str(uuid.uuid4())
            recording4 = Recording(
                rec_id=recording_id,
                url=platform_url,
                streamer_name=f"{platform_name}大神",
                record_format="mp4",
                quality="UHD",
                segment_record=True,
                segment_time=1800,
                monitor_status=False,
                scheduled_recording=False,
                scheduled_start_time=None,
                monitor_hours=None,
                recording_dir=f"downloads/{platform}-未监控",
                enabled_message_push=False,
                record_mode="auto"
            )
            recording4.is_live = False
            recording4.recording = False
            recording4.speed = "0 KB/s"
            recording4.status_info = RecordingStatus.STOPPED_MONITORING
            recording4.title = f"{recording4.streamer_name} - {self._[recording4.quality]}"
            self.recordings.append(recording4)
            
            # 录制错误状态
            recording_id = str(uuid.uuid4())
            recording5 = Recording(
                rec_id=recording_id,
                url=platform_url,
                streamer_name=f"{platform_name}老师",
                record_format="mp4",
                quality="HD",
                segment_record=True,
                segment_time=3600,
                monitor_status=True,
                scheduled_recording=False,
                scheduled_start_time=None,
                monitor_hours=None,
                recording_dir=f"downloads/{platform}-录制错误",
                enabled_message_push=True,
                record_mode="auto"
            )
            recording5.is_live = True
            recording5.recording = False
            recording5.speed = "0 KB/s"
            recording5.status_info = RecordingStatus.RECORDING_ERROR
            recording5.title = f"{recording5.streamer_name} - {self._[recording5.quality]}"
            self.recordings.append(recording5)
    
    def get_platform_url(self, platform):
        """获取平台示例URL"""
        platform_urls = {
            "bilibili": "https://live.bilibili.com/12345",
            "douyu": "https://www.douyu.com/67890",
            "huya": "https://www.huya.com/54321",
            "youtube": "https://www.youtube.com/watch?v=abcdef",
            "twitch": "https://www.twitch.tv/12345",
            "kuaishou": "https://www.kuaishou.com/98765",
            "douyin": "https://www.douyin.com/user/abcdef",
            "tiktok": "https://www.tiktok.com/@username",
            "xiaohongshu": "https://www.xiaohongshu.com/user/profile/123456",
        }
        return platform_urls.get(platform, f"https://www.{platform}.com/live/12345")
    
    async def create_cards_container(self):
        """创建卡片容器，只使用列表视图"""
        self.list_view = ft.Column(
            controls=[],
            spacing=5,
            expand=True,
            scroll=ft.ScrollMode.AUTO
        )
        
        # 创建所有卡片
        for recording in self.recordings:
            card = await self.create_card(recording)
            self.list_view.controls.append(card)
            
        return ft.Container(
            content=self.list_view,
            expand=True,
            border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=5,
            padding=10
        )
    
    def create_status_label(self, recording: Recording):
        """创建状态标签，与项目中的样式保持一致"""
        if recording.recording:
            return ft.Container(
                content=ft.Text(self._["recording"], color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.BOLD),
                bgcolor=ft.Colors.GREEN,
                border_radius=5,
                padding=5,
                width=60,
                height=26,
                alignment=ft.alignment.center,
            )
        elif recording.status_info == RecordingStatus.RECORDING_ERROR:
            return ft.Container(
                content=ft.Text(self._["recording_error"], color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.BOLD),
                bgcolor=ft.Colors.RED,
                border_radius=5,
                padding=5,
                width=60,
                height=26,
                alignment=ft.alignment.center,
            )
        elif not recording.is_live and recording.monitor_status:
            return ft.Container(
                content=ft.Text(self._["offline"], color=ft.Colors.BLACK, size=12, weight=ft.FontWeight.BOLD),
                bgcolor=ft.Colors.AMBER,
                border_radius=5,
                padding=5,
                width=60,
                height=26,
                alignment=ft.alignment.center,
            )
        elif not recording.monitor_status:
            return ft.Container(
                content=ft.Text(self._["monitor_stopped"], color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.BOLD),
                bgcolor=ft.Colors.GREY,
                border_radius=5,
                padding=5,
                width=80,
                height=26,
                alignment=ft.alignment.center,
            )
        elif recording.is_live and recording.monitor_status and not recording.recording:
            # 显示"直播中（未录制）"状态标签
            return ft.Container(
                content=ft.Text(self._["live_monitoring_not_recording"], color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.BOLD),
                bgcolor=ft.Colors.CYAN,
                border_radius=5,
                padding=5,
                width=160,
                height=26,
                alignment=ft.alignment.center,
            )
        return None
    
    @staticmethod
    def get_icon_for_recording_state(recording: Recording):
        """获取录制按钮图标，与项目中保持一致"""
        return ft.Icons.STOP_CIRCLE if recording.recording else ft.Icons.PLAY_CIRCLE
    
    def get_tip_for_recording_state(self, recording: Recording):
        """获取录制按钮提示文本，与项目中保持一致"""
        # 无论哪种模式，停止监控状态下都显示需要开启监控的提示
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
        """获取监控按钮图标，与项目中保持一致"""
        return ft.Icons.VISIBILITY if not recording.monitor_status else ft.Icons.VISIBILITY_OFF
    
    def get_tip_for_monitor_state(self, recording: Recording):
        """获取监控按钮提示文本，与项目中保持一致"""
        return self._["stop_monitor"] if recording.monitor_status else self._["start_monitor"]
    
    async def create_card(self, recording: Recording):
        """创建录制卡片，与项目中的样式保持一致"""
        # 状态标签
        status_label = self.create_status_label(recording)
        
        # 状态前缀
        status_prefix = ""
        if not recording.monitor_status:
            status_prefix = f"[{self._['monitor_stopped']}] "
        
        # 标题
        display_title = f"{status_prefix}{recording.title}"
        display_title_label = ft.Text(
            display_title, 
            size=14, 
            selectable=True, 
            max_lines=1, 
            no_wrap=True,
            overflow=ft.TextOverflow.ELLIPSIS,
            expand=True,
            weight=ft.FontWeight.BOLD,
        )
        
        # 标题行
        title_row = ft.Row(
            [display_title_label, status_label] if status_label else [display_title_label],
            alignment=ft.MainAxisAlignment.START,
            spacing=5,
            tight=True,
        )
        
        # 时长和速度信息
        duration_text_label = ft.Text("时长: 01:23:45", size=12, weight=ft.FontWeight.BOLD)
        speed_text_label = ft.Text(f"速度: {recording.speed}", size=12, weight=ft.FontWeight.BOLD)
        
        # 获取平台类型
        platform_type = self.get_platform_type(recording.url)
        
        # 平台图标路径
        logo_path = os.path.join(self.platform_icons_path, f"{platform_type}.png")
        if not os.path.exists(logo_path):
            # 如果找不到特定平台图标，使用默认图标
            logo_path = os.path.join(self.platform_icons_path, "moren.png")
            
        # 创建平台logo图片组件
        platform_logo = ft.Image(
            src=logo_path,
            width=50,
            height=50,
            fit=ft.ImageFit.CONTAIN,
            border_radius=ft.border_radius.all(5),
        )
        
        # 按钮状态设置
        # 录制按钮状态
        is_record_button_disabled = not recording.monitor_status or (recording.monitor_status and not recording.is_live)
        record_icon = self.get_icon_for_recording_state(recording)
        record_tooltip = self.get_tip_for_recording_state(recording)
        
        # 监控按钮状态
        monitor_icon = self.get_icon_for_monitor_state(recording)
        monitor_tooltip = self.get_tip_for_monitor_state(recording)
        
        # 按钮行
        button_row = ft.Row(
            [
                ft.IconButton(
                    icon=record_icon,
                    tooltip=record_tooltip,
                    disabled=is_record_button_disabled,
                ),
                ft.IconButton(
                    icon=ft.Icons.FOLDER,
                    tooltip=self._["open_folder"],
                ),
                ft.IconButton(
                    icon=ft.Icons.INFO,
                    tooltip=self._["recording_info"],
                ),
                ft.IconButton(
                    icon=ft.Icons.VIDEO_LIBRARY,
                    tooltip=self._["preview_video"],
                ),
                ft.IconButton(
                    icon=ft.Icons.LINK,
                    tooltip=(self._["copy_stream_url"] if (recording.monitor_status and (recording.is_live or recording.recording)) else self._["no_stream_source"]),
                    disabled=not (recording.monitor_status and (recording.is_live or recording.recording)),
                ),
                ft.IconButton(
                    icon=ft.Icons.PLAY_ARROW,
                    tooltip=(self._["play_stream"] if (recording.monitor_status and (recording.is_live or recording.recording)) else self._["no_stream_source"]),
                    disabled=not (recording.monitor_status and (recording.is_live or recording.recording)),
                ),
                ft.IconButton(
                    icon=ft.Icons.EDIT,
                    tooltip=self._["edit_record_config"],
                ),
                ft.IconButton(
                    icon=ft.Icons.DELETE,
                    tooltip=self._["delete_monitor"],
                ),
                ft.IconButton(
                    icon=monitor_icon,
                    tooltip=monitor_tooltip,
                ),
            ],
            spacing=3,
            alignment=ft.MainAxisAlignment.START
        )
        
        # 左侧logo容器
        logo_container = ft.Container(
            content=platform_logo,
            width=60,
            height=100,
            alignment=ft.alignment.center,
            padding=ft.padding.all(5),
        )
        
        # 右侧内容容器
        content_container = ft.Container(
            content=ft.Column(
                [
                    title_row,
                    duration_text_label,
                    speed_text_label,
                    button_row
                ],
                spacing=3,
                tight=True
            ),
            expand=True,
        )
        
        # 卡片内容行
        card_content_row = ft.Row(
            [logo_container, content_container],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.START,
            spacing=0,
        )
        
        # 卡片容器
        card_container = ft.Container(
            content=card_content_row,
            padding=8,
            bgcolor=None,
            border_radius=5,
            border=ft.border.all(2, self.get_card_border_color(recording)),
        )
        
        # 卡片
        card = ft.Card(
            content=card_container,
            key=recording.rec_id
        )
        
        return card
    
    def get_platform_type(self, url):
        """从URL中识别平台类型"""
        if "bilibili" in url:
            return "bilibili"
        elif "douyu" in url:
            return "douyu"
        elif "huya" in url:
            return "huya"
        elif "youtube" in url:
            return "youtube"
        elif "twitch" in url:
            return "twitch"
        elif "kuaishou" in url:
            return "kuaishou"
        elif "douyin" in url:
            return "douyin"
        elif "tiktok" in url:
            return "tiktok"
        elif "xiaohongshu" in url or "xhs" in url:
            return "xhs"
        else:
            return "moren"
    
    @staticmethod
    def get_card_border_color(recording: Recording):
        """获取卡片边框颜色"""
        if recording.recording:
            return ft.Colors.GREEN
        elif recording.status_info == RecordingStatus.RECORDING_ERROR:
            return ft.Colors.RED
        elif recording.is_live and recording.monitor_status and not recording.recording:
            # 为"直播中（未录制）"状态添加青色边框
            return ft.Colors.CYAN
        elif not recording.is_live and recording.monitor_status:
            return ft.Colors.AMBER
        elif not recording.monitor_status:
            return ft.Colors.GREY
        return ft.Colors.TRANSPARENT

    async def filter_all_on_click(self):
        """全部状态按钮点击处理"""
        self.current_filter = "all"
        await self.apply_filter()
    
    async def filter_recording_on_click(self):
        """录制中状态按钮点击处理"""
        self.current_filter = "recording"
        await self.apply_filter()
    
    async def filter_live_monitoring_not_recording_on_click(self):
        """直播中未录制状态按钮点击处理"""
        self.current_filter = "live_monitoring_not_recording"
        await self.apply_filter()
    
    async def filter_offline_on_click(self):
        """未开播状态按钮点击处理"""
        self.current_filter = "offline"
        await self.apply_filter()
    
    async def filter_error_on_click(self):
        """录制错误状态按钮点击处理"""
        self.current_filter = "error"
        await self.apply_filter()
    
    async def filter_stopped_on_click(self):
        """停止监控状态按钮点击处理"""
        self.current_filter = "stopped"
        await self.apply_filter()


def main():
    app = UIDemoApp()
    ft.app(target=app.main)


if __name__ == "__main__":
    main() 