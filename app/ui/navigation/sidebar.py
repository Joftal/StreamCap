import asyncio
import flet as ft

from ..themes import PopupColorItem, ThemeManager
from ...utils.logger import logger


class ControlGroup:
    def __init__(self, icon, label, index, name, selected_icon):
        self.icon = icon
        self.label = label
        self.index = index
        self.name = name
        self.selected_icon = selected_icon


class NavigationItem(ft.Container):
    def __init__(self, destination, item_clicked):
        super().__init__()
        self.ink = True
        self.padding = 10
        self.border_radius = 5
        self.destination = destination
        self.icon = destination.icon
        self.text = destination.label
        self.content = ft.Row([ft.Icon(self.icon), ft.Text(self.text)])
        self.on_click = lambda e: item_clicked(e)


class NavigationColumn(ft.Column):
    def __init__(self, sidebar, page, app):
        super().__init__()
        self.expand = 4
        self.spacing = 0
        self.scroll = ft.ScrollMode.ALWAYS
        self.sidebar = sidebar
        self.selected_index = 0
        self.page = page
        self.app = app
        self.controls = self.get_navigation_items()

    def get_navigation_items(self):
        return [
            NavigationItem(destination, item_clicked=self.item_clicked) for destination in self.sidebar.control_groups
        ]

    def item_clicked(self, e):
        # 获取目标页面名称
        destination_name = e.control.destination.name
        destination_index = e.control.destination.index
        
        # 记录点击的导航项
        logger.debug(f"导航项被点击: {destination_name}, index={destination_index}")
        
        # 检查是否已经在该页面
        current_page = self.app.current_page
        current_page_name = getattr(current_page, 'page_name', None) if current_page else None
        
        if current_page_name == destination_name:
            logger.debug(f"已经在 {destination_name} 页面，忽略导航请求")
            return
        
        # 检查应用是否正在加载页面
        if getattr(self.app, '_loading_page', False):
            logger.debug(f"应用正在加载页面，将请求排队: {destination_name}")
            # 记录请求但不立即执行
            setattr(self.app, '_pending_page_request', destination_name)
            # 更新选中状态，提供视觉反馈
            self.selected_index = destination_index
            self.update_selected_item()
            return
        
        # 更新选中状态
        self.selected_index = destination_index
        self.update_selected_item()
        
        # 使用app_manager来切换页面，而不是直接调用page.go
        logger.debug(f"请求切换到页面: {destination_name}")
        try:
            self.page.run_task(self.app.switch_page, destination_name)
        except Exception as e:
            logger.error(f"请求切换到页面 {destination_name} 时出错: {e}")
            # 如果出错，尝试使用page.go作为备选方案
            try:
                logger.debug(f"尝试使用备选方式切换到页面: {destination_name}")
                self.page.go(f"/{destination_name}")
            except Exception as backup_error:
                logger.error(f"备选页面切换方式也失败: {backup_error}")

    def update_selected_item(self):
        for item in self.controls:
            item.bgcolor = None
            item.content.controls[0].icon = item.destination.icon
        if 0 <= self.selected_index < len(self.controls):
            self.controls[self.selected_index].bgcolor = ft.Colors.SECONDARY_CONTAINER
            self.controls[self.selected_index].content.controls[0].icon = self.controls[
                self.selected_index
            ].destination.selected_icon


class LeftNavigationMenu(ft.Column):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.sidebar = app.sidebar
        self.page = app.page
        self.rail = None
        self.dark_light_text = None
        self.dark_light_icon = None
        self.speed_display_text = None
        self.speed_display_icon = None
        self.bottom_controls = None
        self.first_run = True
        self.theme_manager = ThemeManager(self.app)
        self.app.language_manager.add_observer(self)
        self._ = {}
        self.load()

    def load(self):
        logger.debug("正在重新加载左侧导航菜单...")
        self._ = self.app.language_manager.language.get("sidebar")
        
        # 重新创建导航列
        old_rail = self.rail
        self.rail = NavigationColumn(sidebar=self.sidebar, page=self.page, app=self.app)
        
        # 深色/浅色主题切换按钮
        if self.page.theme_mode == ft.ThemeMode.DARK:
            self.dark_light_text = ft.Text(self._["dark_theme"])
            self.dark_light_icon = ft.IconButton(
                icon=ft.Icons.BRIGHTNESS_HIGH_OUTLINED,
                tooltip=self._["toggle_day_theme"],
                on_click=self.theme_changed,
            )
        else:
            self.dark_light_text = ft.Text(self._["light_theme"])
            self.dark_light_icon = ft.IconButton(
                icon=ft.Icons.BRIGHTNESS_2_OUTLINED,
                tooltip=self._["toggle_night_theme"],
                on_click=self.theme_changed,
            )
            
        # 速度显示控制按钮
        show_recording_speed = self.app.settings.user_config.get("show_recording_speed", True)
        if show_recording_speed:
            self.speed_display_text = ft.Text(self._["show_speed"])
            self.speed_display_icon = ft.IconButton(
                icon=ft.Icons.SPEED,
                tooltip=self._["toggle_hide_speed"],
                on_click=self.speed_display_changed,
            )
        else:
            self.speed_display_text = ft.Text(self._["hide_speed"])
            self.speed_display_icon = ft.IconButton(
                icon=ft.Icons.VISIBILITY_OFF,
                tooltip=self._["toggle_show_speed"],
                on_click=self.speed_display_changed,
            )

        # 添加直播间缩略图控制按钮
        show_live_thumbnail = self.app.settings.user_config.get("show_live_thumbnail", False)
        if show_live_thumbnail:
            self.thumbnail_display_text = ft.Text(self._["show_thumbnail"])
            self.thumbnail_display_icon = ft.IconButton(
                icon=ft.Icons.PHOTO_LIBRARY,
                tooltip=self._["toggle_hide_thumbnail"],
                on_click=self.thumbnail_display_changed,
            )
        else:
            self.thumbnail_display_text = ft.Text(self._["hide_thumbnail"])
            self.thumbnail_display_icon = ft.IconButton(
                icon=ft.Icons.PHOTO_LIBRARY_OUTLINED,
                tooltip=self._["toggle_show_thumbnail"],
                on_click=self.thumbnail_display_changed,
            )

        # 主题颜色选择
        color_names = {
            "deeppurple": {"zh": "深紫色", "en": "Deep purple"},
            "purple": {"zh": "紫色", "en": "Purple"},
            "indigo": {"zh": "靛蓝", "en": "Indigo"},
            "blue": {"zh": "蓝色", "en": "Blue"},
            "teal": {"zh": "蓝绿色", "en": "Teal"},
            "deeporange": {"zh": "深橙色", "en": "Deep orange"},
            "orange": {"zh": "橙色", "en": "Orange"},
            "pink": {"zh": "粉色", "en": "Pink"},
            "brown": {"zh": "棕色", "en": "Brown"},
            "bluegrey": {"zh": "蓝灰色", "en": "Blue Grey"},
            "green": {"zh": "绿色", "en": "Green"},
            "cyan": {"zh": "青色", "en": "Cyan"},
            "lightblue": {"zh": "浅蓝色", "en": "Light Blue"},
            "": {"zh": "默认", "en": "Default"},
        }
        lang = self.app.language_code if hasattr(self.app, 'language_code') else 'zh_CN'
        if lang.startswith('zh'):
            lang_key = 'zh'
        else:
            lang_key = 'en'
        colors_list = [(color, color_names[color].get(lang_key, color_names[color]["en"])) for color in color_names]

        # 重建底部控制组
        self.bottom_controls = ft.Column(
            controls=[
                # 添加速度显示控制行
                ft.Row(
                    controls=[
                        self.speed_display_icon,
                        self.speed_display_text,
                    ],
                    alignment=ft.MainAxisAlignment.START,
                ),
                # 添加直播间缩略图控制行
                ft.Row(
                    controls=[
                        self.thumbnail_display_icon,
                        self.thumbnail_display_text,
                    ],
                    alignment=ft.MainAxisAlignment.START,
                ),
                # 原有的深色/浅色主题切换行
                ft.Row(
                    controls=[
                        self.dark_light_icon,
                        self.dark_light_text,
                    ],
                    alignment=ft.MainAxisAlignment.START,
                ),
                ft.Row(
                    controls=[
                        ft.PopupMenuButton(
                            icon=ft.Icons.COLOR_LENS_OUTLINED,
                            tooltip=self._["colors"],
                            items=[PopupColorItem(color=color, name=name) for color, name in colors_list],
                        ),
                        ft.Text(self._["theme_color"]),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                ),
            ],
            alignment=ft.MainAxisAlignment.END,
        )

        # 更新整体控件列表
        self.controls = [
            self.rail,
            ft.Container(expand=True),
            self.bottom_controls,
        ]

        # 设置布局属性
        self.width = 160
        self.spacing = 0
        self.alignment = ft.MainAxisAlignment.START

        # 如果已经添加到页面，则进行更新
        if self in self.page.controls or (hasattr(self.app, 'complete_page') and self in self.app.complete_page.controls):
            self.update()
        
        # 确保导航栏已选中正确的项
        if hasattr(self.rail, 'update_selected_item'):
            self.rail.update_selected_item()
        
        logger.debug("左侧导航菜单重新加载完成")

    async def theme_changed(self, _):
        page = self.app.page
        self._ = self.app.language_manager.language.get("sidebar")
        if page.theme_mode == ft.ThemeMode.LIGHT:
            page.theme_mode = ft.ThemeMode.DARK
            self.dark_light_text.value = self._["dark_theme"]
            self.dark_light_icon.icon = ft.Icons.BRIGHTNESS_HIGH_OUTLINED
            self.dark_light_icon.tooltip = self._["toggle_day_theme"]
            self.app.settings.user_config["theme_mode"] = "dark"
        else:
            page.theme_mode = ft.ThemeMode.LIGHT
            self.dark_light_text.value = self._["light_theme"]
            self.dark_light_icon.icon = ft.Icons.BRIGHTNESS_2_OUTLINED
            self.dark_light_icon.tooltip = self._["toggle_night_theme"]
            self.app.settings.user_config["theme_mode"] = "light"
        self.page.run_task(self.app.config_manager.save_user_config, self.app.settings.user_config)
        await self.on_theme_change()
        page.update()

    async def speed_display_changed(self, _):
        page = self.app.page
        self._ = self.app.language_manager.language.get("sidebar")
        # 获取当前设置状态并切换
        show_recording_speed = not self.app.settings.user_config.get("show_recording_speed", True)
        self.app.settings.user_config["show_recording_speed"] = show_recording_speed
        
        # 更新UI元素
        if show_recording_speed:
            self.speed_display_text.value = self._["show_speed"]
            self.speed_display_icon.icon = ft.Icons.SPEED
            self.speed_display_icon.tooltip = self._["toggle_hide_speed"]
            # 添加开启速度监控的提示，使用国际化文本
            self.app.page.run_task(self.app.snack_bar.show_snack_bar, self._["speed_monitor_enabled"], ft.Colors.GREEN)
        else:
            self.speed_display_text.value = self._["hide_speed"]
            self.speed_display_icon.icon = ft.Icons.VISIBILITY_OFF
            self.speed_display_icon.tooltip = self._["toggle_show_speed"]
            # 添加关闭速度监控的提示，使用国际化文本
            self.app.page.run_task(self.app.snack_bar.show_snack_bar, self._["speed_monitor_disabled"], ft.Colors.BLUE)
            
        # 保存配置并更新UI
        self.page.run_task(self.app.config_manager.save_user_config, self.app.settings.user_config)
        
        # 确保所有现有卡片都立即更新以反映速度监控状态的变化
        if hasattr(self.app, 'record_card_manager') and hasattr(self.app, 'record_manager'):
            # 使用分批更新卡片的方式，避免UI卡顿
            recordings = self.app.record_manager.recordings
            if recordings:
                # 批量更新卡片，每批最多更新15个
                batch_size = 15
                total_recordings = len(recordings)
                total_batches = (total_recordings + batch_size - 1) // batch_size
                
                logger.info(f"开始批量更新录制卡片速度显示状态，共 {total_recordings} 个，分 {total_batches} 批处理")
                
                for batch_index in range(total_batches):
                    start_idx = batch_index * batch_size
                    end_idx = min(start_idx + batch_size, total_recordings)
                    batch_recordings = recordings[start_idx:end_idx]
                    
                    logger.debug(f"更新第 {batch_index+1}/{total_batches} 批卡片，{len(batch_recordings)} 个")
                    
                    # 并行更新当前批次的卡片
                    update_tasks = []
                    for recording in batch_recordings:
                        if recording.rec_id in self.app.record_card_manager.cards_obj:
                            update_tasks.append(self.app.record_card_manager.update_card(recording))
                    
                    if update_tasks:
                        await asyncio.gather(*update_tasks)
                        # 每批次更新后短暂停顿，避免UI卡顿
                        await asyncio.sleep(0.05)
        
        page.update()
        
    async def thumbnail_display_changed(self, _):
        page = self.app.page
        self._ = self.app.language_manager.language.get("sidebar")
        # 获取当前设置状态并切换
        show_live_thumbnail = not self.app.settings.user_config.get("show_live_thumbnail", False)
        self.app.settings.user_config["show_live_thumbnail"] = show_live_thumbnail
        
        # 更新UI元素
        if show_live_thumbnail:
            self.thumbnail_display_text.value = self._["show_thumbnail"]
            self.thumbnail_display_icon.icon = ft.Icons.PHOTO_LIBRARY
            self.thumbnail_display_icon.tooltip = self._["toggle_hide_thumbnail"]
            # 添加开启缩略图的提示，使用国际化文本
            self.app.page.run_task(self.app.snack_bar.show_snack_bar, self._["thumbnail_enabled"], ft.Colors.GREEN)
            
            # 为所有正在直播或录制的项目启动缩略图捕获任务
            if hasattr(self.app, 'record_manager') and hasattr(self.app, 'thumbnail_manager'):
                logger.info("开启缩略图功能，为所有直播中或录制中的直播间启动缩略图捕获任务")
                active_recordings = [r for r in self.app.record_manager.recordings 
                                    if (r.is_live or r.recording) and r.monitor_status]
                
                if active_recordings:
                    logger.info(f"找到 {len(active_recordings)} 个直播中或录制中的直播间，开始启动缩略图捕获")
                    for recording in active_recordings:
                        logger.info(f"为直播间 {recording.streamer_name} (ID: {recording.rec_id}) 启动缩略图捕获")
                        self.app.page.run_task(self.app.thumbnail_manager.start_thumbnail_capture, recording)
                else:
                    logger.info("未找到直播中或录制中的直播间，无需启动缩略图捕获任务")
        else:
            self.thumbnail_display_text.value = self._["hide_thumbnail"]
            self.thumbnail_display_icon.icon = ft.Icons.PHOTO_LIBRARY_OUTLINED
            self.thumbnail_display_icon.tooltip = self._["toggle_show_thumbnail"]
            # 添加关闭缩略图的提示，使用国际化文本
            self.app.page.run_task(self.app.snack_bar.show_snack_bar, self._["thumbnail_disabled"], ft.Colors.BLUE)
            
            # 停止所有缩略图捕获任务
            if hasattr(self.app, 'thumbnail_manager'):
                logger.info("关闭缩略图功能，停止所有缩略图捕获任务")
                self.app.page.run_task(self.app.thumbnail_manager.stop_all_thumbnail_captures)
            
        # 保存配置并更新UI
        self.page.run_task(self.app.config_manager.save_user_config, self.app.settings.user_config)
        
        # 确保所有现有卡片都立即更新以反映缩略图状态的变化
        if hasattr(self.app, 'record_card_manager') and hasattr(self.app, 'record_manager'):
            # 使用分批更新卡片的方式，避免UI卡顿
            recordings = self.app.record_manager.recordings
            if recordings:
                # 批量更新卡片，每批最多更新15个
                batch_size = 15
                total_recordings = len(recordings)
                total_batches = (total_recordings + batch_size - 1) // batch_size
                
                logger.info(f"开始批量更新录制卡片缩略图显示状态，共 {total_recordings} 个，分 {total_batches} 批处理")
                
                for batch_index in range(total_batches):
                    start_idx = batch_index * batch_size
                    end_idx = min(start_idx + batch_size, total_recordings)
                    batch_recordings = recordings[start_idx:end_idx]
                    
                    logger.debug(f"更新第 {batch_index+1}/{total_batches} 批卡片，{len(batch_recordings)} 个")
                    
                    # 并行更新当前批次的卡片
                    update_tasks = []
                    for recording in batch_recordings:
                        if recording.rec_id in self.app.record_card_manager.cards_obj:
                            update_tasks.append(self.app.record_card_manager.update_card(recording))
                    
                    if update_tasks:
                        await asyncio.gather(*update_tasks)
                        # 每批次更新后短暂停顿，避免UI卡顿
                        await asyncio.sleep(0.05)
        
        page.update()

    async def on_theme_change(self):
        """When the theme changes, recreate the content and update the page"""
        if self.app.current_page.page_name == "about":
            await self.app.current_page.load()


class NavigationSidebar:
    def __init__(self, app):
        self.app = app
        self.control_groups = []
        self.selected_control_group = None
        self.app.language_manager.add_observer(self)
        self._ = {}
        self.load()

    def load(self):
        self._ = self.app.language_manager.language.get("sidebar")
        # 保存当前选中的控制组索引
        selected_index = getattr(self.selected_control_group, 'index', 0) if self.selected_control_group else 0
        
        # 创建新的控制组
        self.control_groups = [
            ControlGroup(icon=ft.Icons.HOME, label=self._["home"], index=0, name="home", selected_icon=ft.Icons.HOME),
            ControlGroup(
                icon=ft.Icons.SETTINGS,
                label=self._["settings"],
                index=1,
                name="settings",
                selected_icon=ft.Icons.SETTINGS,
            ),
            ControlGroup(
                icon=ft.Icons.DRIVE_FILE_MOVE,
                label=self._["storage"],
                index=2,
                name="storage",
                selected_icon=ft.Icons.DRIVE_FILE_MOVE_OUTLINE
            ),
            ControlGroup(icon=ft.Icons.INFO, label=self._["about"], index=3, name="about", selected_icon=ft.Icons.INFO),
        ]
        
        # 恢复选中状态
        self.selected_control_group = self.control_groups[selected_index]
        
        # 通知任何观察者更新
        if hasattr(self.app, 'left_navigation_menu') and self.app.left_navigation_menu:
            self.app.left_navigation_menu.load()
