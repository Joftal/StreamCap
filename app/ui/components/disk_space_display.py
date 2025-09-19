import flet as ft
import asyncio
import os
import shutil
from pathlib import Path
from ...utils.logger import logger
from ...utils import utils


class DiskSpaceDisplay(ft.Container):
    """磁盘空间显示组件 - Windows任务管理器风格
    显示录制保存路径所在磁盘的空间使用情况
    仅支持手动刷新，不会自动更新以避免性能损耗
    """
    
    def __init__(self, app):
        self.app = app
        self._ = {}
        self.last_save_path = None  # 记录上次的保存路径
        self.load_language()
        
        super().__init__(
            content=self._create_content(),
            padding=ft.padding.only(left=16, right=16, top=8, bottom=8),
            margin=ft.margin.only(bottom=5),
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLUE_GREY),
            border=ft.border.only(
                top=ft.border.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.BLUE_GREY)),
                left=ft.border.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.BLUE_GREY)),
                right=ft.border.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.BLUE_GREY)),
                bottom=ft.border.BorderSide(2, ft.Colors.with_opacity(0.2, ft.Colors.BLUE_GREY))
            ),
        )
        
        # 记录初始保存路径
        self.last_save_path = self.app.settings.get_video_save_path()
    
    def load_language(self):
        """加载语言配置"""
        language = self.app.language_manager.language
        self._ = language.get("disk_space_display", {})
    
    def _create_content(self):
        """创建组件内容 - Windows任务管理器风格"""
        # 获取磁盘信息
        disk_info = self._get_disk_space_info()
        
        # 磁盘图标
        disk_icon = ft.Icon(
            ft.icons.STORAGE,
            color=ft.Colors.BLUE_600,
            size=20
        )
        
        # 刷新按钮
        refresh_button = ft.TextButton(
            text=self._["refresh_tooltip"],
            on_click=self._on_refresh_click,
            style=ft.ButtonStyle(
                color=ft.Colors.BLUE_600,
                overlay_color=ft.Colors.with_opacity(0.1, ft.Colors.BLUE_600)
            )
        )
        
        # 进度条
        self.progress_bar = ft.ProgressBar(
            value=disk_info["usage_ratio"],
            width=100,
            height=12,
            color=self._get_progress_color(disk_info["usage_ratio"]),
            bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.BLUE_600),
            border_radius=6
        )
        
        # 检查录制状态
        recording_enabled = getattr(self.app, 'recording_enabled', True)
        status_color = ft.Colors.RED_600 if not recording_enabled else ft.Colors.BLUE_700
        status_text = f" ({self._['recording_disabled']})" if not recording_enabled else ""
        
        # 创建磁盘标识行
        disk_label_row = ft.Row(
            controls=[
                disk_icon,
                ft.Text(
                    f"{self._['disk_label']} ({disk_info['drive_letter']}){status_text}",
                    size=14,
                    weight=ft.FontWeight.BOLD,
                    color=status_color
                ),
                ft.Container(expand=True),  # 占位符
                refresh_button
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8
        )
        
        # 创建容量信息行（紧凑布局）
        capacity_row = ft.Column(
            controls=[
                # 第一行：容量信息 + 进度条 + 百分比
                ft.Row(
                    controls=[
                        ft.Text(
                            f"{disk_info['free_text']} {self._['free_of']} {disk_info['total_text']}",
                            size=13,
                            color=ft.Colors.GREY_700,
                            weight=ft.FontWeight.NORMAL
                        ),
                        ft.Container(width=12),  # 间距
                        self.progress_bar,
                        ft.Container(width=8),  # 间距
                        ft.Text(
                            disk_info["percentage_text"],
                            size=12,
                            color=ft.Colors.BLUE_700,
                            weight=ft.FontWeight.BOLD
                        )
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=0
                ),
                # 第二行：已用空间信息
                ft.Text(
                    f"{self._['used_label']}: {disk_info['used_text']}",
                    size=12,
                    color=ft.Colors.GREY_600,
                    weight=ft.FontWeight.NORMAL
                )
            ],
            spacing=4,
            alignment=ft.MainAxisAlignment.START
        )
        
        # 组合所有元素
        return ft.Column(
            controls=[disk_label_row, capacity_row],
            spacing=6,
            alignment=ft.MainAxisAlignment.START
        )
    
    def _get_disk_space_info(self):
        """获取完整的磁盘空间信息 - 与录制管理器保持一致"""
        try:
            # 使用与录制管理器相同的路径获取方法
            save_path = self.app.settings.get_video_save_path()
            
            # 使用与录制管理器相同的磁盘检查方法
            free_space_gb = utils.check_disk_capacity(save_path)
            
            # 获取完整的磁盘使用信息（用于显示总容量和已用空间）
            absolute_path = os.path.abspath(save_path)
            directory = os.path.dirname(absolute_path)
            disk_usage = shutil.disk_usage(directory)
            
            # 获取驱动器盘符
            drive_letter = Path(directory).anchor.rstrip('\\/')
            
            # 转换为GB
            total_gb = disk_usage.total / (1024**3)
            used_gb = disk_usage.used / (1024**3)
            
            # 使用录制管理器检查的剩余空间（更准确）
            free_gb = free_space_gb
            
            # 计算使用比例
            usage_ratio = used_gb / total_gb if total_gb > 0 else 0
            
            # 格式化显示函数
            def format_size(size_gb):
                if size_gb >= 1024:  # 大于1TB
                    return f"{size_gb / 1024:.1f} TB"
                else:
                    return f"{size_gb:.1f} GB"
            
            return {
                "drive_letter": drive_letter,
                "free_text": format_size(free_gb),
                "total_text": format_size(total_gb),
                "used_text": format_size(used_gb),
                "percentage_text": f"{usage_ratio * 100:.1f}%",
                "usage_ratio": usage_ratio,
                "free_gb": free_gb,
                "total_gb": total_gb,
                "used_gb": used_gb
            }
        except Exception as e:
            logger.error(f"获取磁盘空间信息失败: {e}")
            return {
                "drive_letter": "C:",
                "free_text": self._["unknown"],
                "total_text": self._["unknown"],
                "used_text": self._["unknown"],
                "percentage_text": "0%",
                "usage_ratio": 0,
                "free_gb": 0,
                "total_gb": 0,
                "used_gb": 0
            }
    
    def _get_progress_color(self, usage_ratio):
        """根据使用率获取进度条颜色"""
        if usage_ratio > 0.9:  # 超过90%使用率
            return ft.Colors.RED_600
        elif usage_ratio > 0.8:  # 超过80%使用率
            return ft.Colors.ORANGE_600
        else:
            return ft.Colors.BLUE_600
    
    def update_disk_space(self):
        """更新磁盘空间显示"""
        try:
            # 检查保存路径是否发生变化
            current_save_path = self.app.settings.get_video_save_path()
            if self.last_save_path != current_save_path:
                logger.debug(f"录制保存路径发生变化: {self.last_save_path} -> {current_save_path}")
                self.last_save_path = current_save_path
            
            # 重新创建内容以更新所有信息（包括录制状态）
            self.content = self._create_content()
            self.update()
        except Exception as e:
            logger.error(f"更新磁盘空间显示失败: {e}")
    
    def update_recording_status(self):
        """更新录制状态显示（当录制状态改变时调用）"""
        try:
            # 只更新录制状态相关的显示，不重新获取磁盘空间信息
            self.content = self._create_content()
            self.update()
        except Exception as e:
            logger.error(f"更新录制状态显示失败: {e}")
    
    def _on_refresh_click(self, e):
        """刷新按钮点击事件"""
        self.update_disk_space()
    
    
    def on_language_changed(self):
        """语言变更时调用"""
        self.load_language()
        # 重新创建内容
        self.content = self._create_content()
        self.update()