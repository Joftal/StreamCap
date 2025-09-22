import asyncio
import uuid

import flet as ft

from ...core.platform_handlers import get_platform_info
from ...models.recording_model import Recording
from ...models.recording_status_model import RecordingStatus
from ...utils.logger import logger
from ..base_page import PageBase
from ..components.help_dialog import HelpDialog
from ..components.recording_dialog import RecordingDialog
from ..components.search_dialog import SearchDialog
from app.core.platform_handlers.platform_map import get_platform_display_name


class HomePage(PageBase):
    def __init__(self, app):
        super().__init__(app)
        self.page_name = "home"
        self.recording_card_area = None
        self.add_recording_dialog = None
        self.is_grid_view = app.settings.user_config.get("is_grid_view", True)
        self.loading_indicator = None
        self.app.language_manager.add_observer(self)
        self.load_language()
        self.current_filter = "all"
        self.current_platform_filter = "all"
        self.platform_dropdown = None
        
        # 分页相关属性
        self.current_page = 1
        self.items_per_page = app.settings.user_config.get("items_per_page", 12)
        self.total_pages = 1
        self.pagination_controls = None
        self.page_info_text = None
        self.visible_cards = []
        
        self.init()

    def load_language(self):
        language = self.app.language_manager.language
        for key in ("home_page", "video_quality", "base", "recording_manager"):
            self._.update(language.get(key, {}))
        
        # 添加默认分页相关的语言项，如果语言文件中没有定义
        if "pagination" not in self._:
            self._["pagination"] = {
                "page_info": "第 {current_page}/{total_pages} 页，共 {total_items} 项",
                "prev_page": "上一页",
                "next_page": "下一页",
                "first_page": "首页",
                "last_page": "末页",
                "items_per_page": "每页显示",
            }
            
        # 如果分页控件已经创建，且当前页面是活跃的，尝试更新其文本
        if (hasattr(self, 'pagination_controls') and 
            self.pagination_controls and 
            self.app.current_page == self):
            try:
                self.update_pagination_texts()
            except Exception as e:
                logger.error(f"加载语言时更新分页控件文本出错: {e}")
            
    def update_pagination_texts(self):
        """更新分页控件的文本以反映当前语言"""
        if not hasattr(self, 'pagination_controls') or not self.pagination_controls:
            return
            
        # 更新页码信息文本
        if hasattr(self, 'page_info_text') and self.page_info_text:
            self.page_info_text.value = self._["pagination"]["page_info"].format(
                current_page=self.current_page, 
                total_pages=self.total_pages,
                total_items=len(self.visible_cards) if hasattr(self, 'visible_cards') else 0
            )
            
        try:
            # 确保分页控件已经添加到页面并且内容结构完整
            if (not self.pagination_controls.content or 
                not self.pagination_controls.content.content or 
                not hasattr(self.pagination_controls.content.content, 'content')):
                return
                
            # 更新按钮提示文本
            pagination_row = self.pagination_controls.content.content.content
            pagination_row.controls[0].tooltip = self._["pagination"]["first_page"]
            pagination_row.controls[1].tooltip = self._["pagination"]["prev_page"]
            pagination_row.controls[3].tooltip = self._["pagination"]["next_page"]
            pagination_row.controls[4].tooltip = self._["pagination"]["last_page"]
            
            # 更新每页显示数量下拉框标签
            pagination_row.controls[5].label = self._["pagination"]["items_per_page"]
            
            # 更新控件
            self.pagination_controls.update()
        except Exception as e:
            logger.error(f"更新分页控件文本时出错: {e}")
        
    def on_language_changed(self):
        """语言变更时的回调函数"""
        self.load_language()
        
        # 如果当前页面是活跃的，更新UI
        if self.app.current_page == self:
            # 检查分页控件是否已添加到页面
            pagination_exists = False
            pagination_container = None
            
            for overlay_item in self.page.overlay:
                if hasattr(overlay_item, 'key') and overlay_item.key == 'home_pagination_container':
                    pagination_exists = True
                    pagination_container = overlay_item
                    break
            
            # 确保分页控件已创建并正确初始化
            if not hasattr(self, 'pagination_controls') or not self.pagination_controls or not pagination_exists:
                # 创建新的分页控件
                self.create_pagination_controls()
                
                # 如果已存在容器，更新其内容
                if pagination_exists and pagination_container:
                    pagination_container.content = self.pagination_controls
                    pagination_container.update()
                    logger.debug("语言变更：更新了已存在分页控件的内容")
                else:
                    # 否则添加新的容器
                    self.pagination_controls.key = 'home_pagination'
                    self.page.overlay.append(
                        ft.Container(
                            key='home_pagination_container',
                            content=self.pagination_controls,
                            alignment=ft.alignment.bottom_center,
                            left=170,  # 从左侧边栏右侧开始
                            right=0,
                            bottom=0,
                            padding=ft.padding.only(bottom=10),  # 只保留底部间距
                        )
                    )
                    logger.debug("语言变更：创建并添加了新的分页控件")
            
            # 更新分页控件文本
            self.update_pagination_texts()
            self.content_area.update()
            self.page.update()

    def init(self):
        self.loading_indicator = ft.ProgressRing(
            width=40, 
            height=40, 
            stroke_width=3,
            visible=False
        )
        
        if self.is_grid_view:
            initial_content = ft.GridView(
                expand=True,
                runs_count=3,
                spacing=10,
                run_spacing=10,
                child_aspect_ratio=2.3,
                controls=[]
            )
        else:
            initial_content = ft.Column(
                controls=[], 
                spacing=5, 
                expand=True
            )
        
        self.recording_card_area = ft.Container(
            content=initial_content,
            expand=True
        )
        
        # 不在初始化时创建分页控件，而是在load方法中创建
        self.pagination_controls = None
        
        self.add_recording_dialog = RecordingDialog(self.app, self.add_recording)
        self.pubsub_subscribe()

    def create_pagination_controls(self):
        """创建分页控制组件"""
        self.page_info_text = ft.Text(
            value=self._["pagination"]["page_info"].format(
                current_page=self.current_page, 
                total_pages=self.total_pages,
                total_items=0
            ),
            size=14
        )
        
        # 每页显示数量下拉框
        items_per_page_dropdown = ft.Dropdown(
            value=str(self.items_per_page),
            options=[
                ft.dropdown.Option(key="6", text="6"),
                ft.dropdown.Option(key="8", text="8"),
                ft.dropdown.Option(key="10", text="10"),
                ft.dropdown.Option(key="12", text="12"),
            ],
            on_change=self.on_items_per_page_change,
            width=80,
            label=self._["pagination"]["items_per_page"]
        )
        
        # 获取安全的背景色和文本颜色
        is_dark = hasattr(self.page, 'theme_mode') and self.page.theme_mode == ft.ThemeMode.DARK
        bg_color = ft.colors.with_opacity(0.9, ft.colors.SURFACE_TINT if is_dark else ft.colors.WHITE)
        border_color = ft.colors.OUTLINE_VARIANT
        
        # 创建分页按钮
        pagination_row = ft.Row(
            [
                ft.IconButton(
                    icon=ft.icons.FIRST_PAGE,
                    tooltip=self._["pagination"]["first_page"],
                    on_click=self.go_to_first_page,
                    disabled=True,
                    icon_size=20,
                ),
                ft.IconButton(
                    icon=ft.icons.NAVIGATE_BEFORE,
                    tooltip=self._["pagination"]["prev_page"],
                    on_click=self.go_to_prev_page,
                    disabled=True,
                    icon_size=20,
                ),
                self.page_info_text,
                ft.IconButton(
                    icon=ft.icons.NAVIGATE_NEXT,
                    tooltip=self._["pagination"]["next_page"],
                    on_click=self.go_to_next_page,
                    disabled=True,
                    icon_size=20,
                ),
                ft.IconButton(
                    icon=ft.icons.LAST_PAGE,
                    tooltip=self._["pagination"]["last_page"],
                    on_click=self.go_to_last_page,
                    disabled=True,
                    icon_size=20,
                ),
                items_per_page_dropdown
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=5,
            tight=True,
        )
        
        # 创建一个居中的容器
        self.pagination_controls = ft.Container(
            content=ft.Card(
                content=ft.Container(
                    content=pagination_row,
                    padding=ft.padding.symmetric(horizontal=15, vertical=8),
                ),
                elevation=4,
            ),
            alignment=ft.alignment.center,
            width=None,  # 自适应宽度
            margin=ft.margin.only(bottom=10),
        )

    async def on_items_per_page_change(self, e):
        """处理每页显示数量变化"""
        self.items_per_page = int(e.control.value)
        self.current_page = 1  # 重置到第一页
        
        # 保存到用户配置
        self.app.settings.user_config["items_per_page"] = self.items_per_page
        self.page.run_task(self.app.config_manager.save_user_config, self.app.settings.user_config)
        
        # 重新应用过滤和分页
        await self.apply_filter()

    async def go_to_first_page(self, _):
        """跳转到第一页"""
        if self.current_page != 1:
            self.current_page = 1
            await self.update_page_display()

    async def go_to_prev_page(self, _):
        """跳转到上一页"""
        if self.current_page > 1:
            self.current_page -= 1
            await self.update_page_display()

    async def go_to_next_page(self, _):
        """跳转到下一页"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            await self.update_page_display()

    async def go_to_last_page(self, _):
        """跳转到最后一页"""
        if self.current_page != self.total_pages:
            self.current_page = self.total_pages
            await self.update_page_display()

    async def update_page_display(self):
        """更新页面显示，根据当前页码显示对应的卡片"""
        # 确保分页控件已创建
        if not self.pagination_controls:
            return
            
        # 更新页码信息文本
        self.page_info_text.value = self._["pagination"]["page_info"].format(
            current_page=self.current_page, 
            total_pages=self.total_pages,
            total_items=len(self.visible_cards)
        )
        
        # 更新翻页按钮状态
        pagination_row = self.pagination_controls.content.content.content
        pagination_row.controls[0].disabled = self.current_page == 1  # 首页按钮
        pagination_row.controls[1].disabled = self.current_page == 1  # 上一页按钮
        pagination_row.controls[3].disabled = self.current_page == self.total_pages  # 下一页按钮
        pagination_row.controls[4].disabled = self.current_page == self.total_pages  # 末页按钮
        
        self.pagination_controls.update()
        
        # 计算当前页应显示的卡片
        start_idx = (self.current_page - 1) * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.visible_cards))
        
        # 检查当前页是否为空页（除非没有任何匹配项）
        if start_idx >= len(self.visible_cards) and len(self.visible_cards) > 0:
            # 当前页为空但有匹配项，自动调整到最后一页
            self.current_page = self.total_pages
            # 重新计算索引范围
            start_idx = (self.current_page - 1) * self.items_per_page
            end_idx = min(start_idx + self.items_per_page, len(self.visible_cards))
            
            # 更新页码信息文本
            self.page_info_text.value = self._["pagination"]["page_info"].format(
                current_page=self.current_page, 
                total_pages=self.total_pages,
                total_items=len(self.visible_cards)
            )
            
            # 更新翻页按钮状态
            pagination_row.controls[0].disabled = self.current_page == 1  # 首页按钮
            pagination_row.controls[1].disabled = self.current_page == 1  # 上一页按钮
            pagination_row.controls[3].disabled = self.current_page == self.total_pages  # 下一页按钮
            pagination_row.controls[4].disabled = self.current_page == self.total_pages  # 末页按钮
            
            self.pagination_controls.update()
        
        # 隐藏所有卡片
        cards_obj = self.app.record_card_manager.cards_obj
        for card_info in cards_obj.values():
            card_info["card"].visible = False
        
        # 只显示当前页的卡片
        for i in range(start_idx, end_idx):
            if i < len(self.visible_cards):
                card_id = self.visible_cards[i]
                if card_id in cards_obj:
                    cards_obj[card_id]["card"].visible = True
        
        # 更新卡片区域
        self.recording_card_area.content.update()

    async def load(self):
        """Load the home page content."""
        try:
            # 第一阶段：加载基本UI框架
            self.content_area.controls.extend(
                [
                    self.create_home_title_area(),
                    self.create_filter_area(),
                    self.create_home_content_area()
                ]
            )
            
            # 检查页面overlay中是否已存在分页控件，只是被隐藏了
            pagination_exists = False
            for overlay_item in self.page.overlay:
                if hasattr(overlay_item, 'key') and overlay_item.key == 'home_pagination_container':
                    pagination_exists = True
                    # 重新显示已存在的分页控件
                    overlay_item.visible = True
                    overlay_item.update()
                    logger.debug("已显示现有分页控件")
                    break
                    
            # 如果不存在分页控件，则创建新的
            if not pagination_exists:
                # 重新创建分页控件，确保使用最新的语言设置
                self.create_pagination_controls()
                
                # 将分页控件添加到页面底部固定位置
                # 给分页控件添加key，方便识别
                self.pagination_controls.key = 'home_pagination'
                self.page.overlay.append(
                    ft.Container(
                        key='home_pagination_container',
                        content=self.pagination_controls,
                        alignment=ft.alignment.bottom_center,
                        left=170,  # 从左侧边栏右侧开始
                        right=0,
                        bottom=0,
                        padding=ft.padding.only(bottom=10),  # 只保留底部间距
                    )
                )
                logger.debug("已创建并添加新的分页控件")
            
            self.content_area.update()
            self.page.update()
            
            # 短暂暂停，让UI有时间渲染
            await asyncio.sleep(0.05)
            
            # 第二阶段：清空卡片区域，准备加载卡片
            self.recording_card_area.content.controls.clear()
            self.recording_card_area.update()
            
            # 显示加载指示器
            if hasattr(self, 'loading_indicator'):
                self.loading_indicator.visible = True
                self.content_area.update()
            
            # 第三阶段：加载录制卡片
            await self.add_record_cards()
            
            # 隐藏加载指示器
            if hasattr(self, 'loading_indicator'):
                self.loading_indicator.visible = False
                self.content_area.update()
            
            # 第四阶段：调整网格布局（如果是网格视图）
            if self.is_grid_view:
                await self.recalculate_grid_columns()
            
            # 设置键盘和窗口大小调整事件处理
            self.page.on_keyboard_event = self.on_keyboard
            self.page.on_resized = self.update_grid_layout
            
            # 确保录制卡片显示正确的格式和分段时间
            if hasattr(self.app, "config_validator"):
                self.page.run_task(self.app.config_validator.update_recording_cards)
                
        except Exception as e:
            logger.error(f"加载主页面时出错: {e}")
            # 确保即使出错也能显示基本UI
            if not self.content_area.controls:
                self.content_area.controls.append(
                    ft.Text("加载页面时出错，请尝试刷新", color=ft.colors.RED)
                )
                self.content_area.update()

    def pubsub_subscribe(self):
        self.app.page.pubsub.subscribe_topic('add', self.subscribe_add_cards)
        self.app.page.pubsub.subscribe_topic('delete_all', self.subscribe_del_all_cards)

    async def toggle_view_mode(self, _):
        self.is_grid_view = not self.is_grid_view
        current_content = self.recording_card_area.content
        current_controls = current_content.controls if hasattr(current_content, 'controls') else []

        column_width = 350
        runs_count = max(1, int(self.page.width / column_width))

        if self.is_grid_view:
            new_content = ft.GridView(
                expand=True,
                runs_count=runs_count,
                spacing=10,
                run_spacing=10,
                child_aspect_ratio=2.3,
                controls=current_controls
            )
        else:
            new_content = ft.Column(
                controls=current_controls,
                spacing=5,
                expand=True
            )

        self.recording_card_area.content = new_content
        self.content_area.clean()
        self.content_area.controls.extend(
            [
                self.create_home_title_area(),
                self.create_filter_area(),
                self.create_home_content_area()
            ]
        )
        self.content_area.update()
        
        self.app.settings.user_config["is_grid_view"] = self.is_grid_view
        self.page.run_task(self.app.config_manager.save_user_config, self.app.settings.user_config)

    def create_home_title_area(self):
        return ft.Row(
            [
                ft.Text(self._["recording_list"], theme_style=ft.TextThemeStyle.TITLE_MEDIUM),
                ft.Container(expand=True),
                # ft.IconButton(
                #     icon=ft.Icons.GRID_VIEW if self.is_grid_view else ft.Icons.LIST,
                #     tooltip=self._["toggle_view"],
                #     on_click=self.toggle_view_mode
                # ),
                ft.IconButton(icon=ft.Icons.SEARCH, tooltip=self._["search"], on_click=self.search_on_click),
                ft.IconButton(icon=ft.Icons.ADD, tooltip=self._["add_record"], on_click=self.add_recording_on_click),
                ft.IconButton(icon=ft.Icons.REFRESH, tooltip=self._["refresh"], on_click=self.refresh_cards_on_click),
                ft.IconButton(
                    icon=ft.Icons.PLAY_ARROW,
                    tooltip=self._["batch_start"],
                    on_click=self.start_monitor_recordings_on_click,
                ),
                ft.IconButton(
                    icon=ft.Icons.STOP, tooltip=self._["batch_stop"], on_click=self.stop_monitor_recordings_on_click
                ),
                ft.IconButton(
                    icon=ft.Icons.DELETE_SWEEP,
                    tooltip=self._["batch_delete"],
                    on_click=self.delete_monitor_recordings_on_click,
                ),
            ],
            alignment=ft.MainAxisAlignment.START,
        )
    
    def create_filter_area(self):
        """Create the filter area"""
        platforms = self.get_available_platforms()
        style = self.app.settings.user_config.get("platform_filter_style", "tile")
        lang = getattr(self.app, 'language_code', 'zh_CN')
        def get_display_name(key):
            return get_platform_display_name(key, lang)

        if style == "dropdown":
            # 下拉框风格
            platform_dropdown = ft.Dropdown(
            value=self.current_platform_filter,
            options=[
                ft.dropdown.Option(key="all", text=self._["filter_all_platforms"]),
                    *[ft.dropdown.Option(key=platform[1], text=get_display_name(platform[1])) for platform in platforms]
            ],
            on_change=self.on_platform_filter_change,
                width=200,
            )
            platform_filter_control = platform_dropdown
        else:
            # 平铺按钮组风格
            platform_buttons = [
                ft.ElevatedButton(
                    self._["filter_all_platforms"],
                    on_click=lambda e: self.page.run_task(self.filter_all_platforms_on_click, e),
                    bgcolor=ft.Colors.BLUE if self.current_platform_filter == "all" else None,
                    color=ft.Colors.WHITE if self.current_platform_filter == "all" else None,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                )
            ]
            for name, key in platforms:
                selected = self.current_platform_filter == key
                platform_buttons.append(
                    ft.ElevatedButton(
                        get_display_name(key),
                        on_click=lambda e, k=key: self.page.run_task(self.on_platform_button_click, k),
                        bgcolor=ft.Colors.BLUE if selected else None,
                        color=ft.Colors.WHITE if selected else None,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                    )
                )
            platform_filter_control = ft.Container(
                content=ft.Row(
                    platform_buttons,
                    alignment=ft.MainAxisAlignment.START,
                    spacing=5,
                    scroll=ft.ScrollMode.HIDDEN,  # 隐藏滑动条
                    wrap=True  # 启用自动换行
                ),
                expand=True,
        )
        
        return ft.Column(
            controls=[
                ft.Row(
                    [
                        ft.Text(self._["filter"] + ":", size=14),
                        ft.ElevatedButton(
                            self._["filter_all"],
                            on_click=self.filter_all_on_click,
                            bgcolor=ft.Colors.BLUE if self.current_filter == "all" else None,
                            color=ft.Colors.WHITE if self.current_filter == "all" else None,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                        ),
                        ft.ElevatedButton(
                            self._["filter_recording"],
                            on_click=self.filter_recording_on_click,
                            bgcolor=ft.Colors.GREEN if self.current_filter == "recording" else None,
                            color=ft.Colors.WHITE if self.current_filter == "recording" else None,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                            ),
                        ft.ElevatedButton(
                            self._["filter_live_monitoring_not_recording"],
                            on_click=self.filter_live_monitoring_not_recording_on_click,
                            bgcolor=ft.Colors.CYAN if self.current_filter == "live_monitoring_not_recording" else None,
                            color=ft.Colors.WHITE if self.current_filter == "live_monitoring_not_recording" else None,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                        ),
                        ft.ElevatedButton(
                            self._["filter_offline"],
                            on_click=self.filter_offline_on_click,
                            bgcolor=ft.Colors.AMBER if self.current_filter == "offline" else None,
                            color=ft.Colors.WHITE if self.current_filter == "offline" else None,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                        ),
                        ft.ElevatedButton(
                            self._["filter_error"],
                            on_click=self.filter_error_on_click,
                            bgcolor=ft.Colors.RED if self.current_filter == "error" else None,
                            color=ft.Colors.WHITE if self.current_filter == "error" else None,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                        ),
                        ft.ElevatedButton(
                            self._["filter_stopped"],
                            on_click=self.filter_stopped_on_click,
                            bgcolor=ft.Colors.GREY if self.current_filter == "stopped" else None,
                            color=ft.Colors.WHITE if self.current_filter == "stopped" else None,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    spacing=5,
                ),
                ft.Row(
                    [
                        ft.Text(self._["platform_filter"] + ":", size=14),
                        platform_filter_control
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    spacing=5,
                ),
            ],
            spacing=5,
        )
    
    def get_available_platforms(self):
        platforms = set()
        recordings = self.app.record_manager.recordings
        
        for recording in recordings:
            if hasattr(recording, 'url') and recording.url:
                platform_name, platform_key = get_platform_info(recording.url)
                if platform_name and platform_key:
                    platforms.add((platform_name, platform_key))
        
        return sorted(list(platforms), key=lambda x: x[0])
    
    async def on_platform_filter_change(self, e):
        self.current_platform_filter = e.control.value
        await self.apply_filter()

    async def filter_all_on_click(self, _):
        self.current_filter = "all"
        await self.apply_filter()
    
    async def filter_recording_on_click(self, _):
        self.current_filter = "recording"
        await self.apply_filter()
    
    async def filter_error_on_click(self, _):
        self.current_filter = "error"
        await self.apply_filter()
    
    async def filter_offline_on_click(self, _):
        self.current_filter = "offline"
        await self.apply_filter()
    
    async def filter_stopped_on_click(self, _):
        self.current_filter = "stopped"
        await self.apply_filter()
    
    async def filter_live_monitoring_not_recording_on_click(self, _):
        self.current_filter = "live_monitoring_not_recording"
        await self.apply_filter()
    
    async def handle_empty_results(self, query=""):
        """处理空结果的通用方法，显示适当的提示信息
        
        参数:
            query: 搜索关键词，如果有的话
        """
        search_message = f"搜索 \"{query}\"" if query else ""
        
        # 检查是否已经有提示信息
        has_empty_tip = False
        for control in self.recording_card_area.content.controls:
            if hasattr(control, 'key') and control.key == 'empty_filter_tip':
                # 更新现有提示
                if hasattr(control, 'content') and hasattr(control.content, 'controls'):
                    for text_control in control.content.controls:
                        if isinstance(text_control, ft.Text):
                            if query:
                                text_control.value = self._.get("no_search_results", "没有找到匹配的结果") + f": {search_message}"
                            else:
                                text_control.value = self._.get("no_matching_items", "没有匹配的项目")
                has_empty_tip = True
                control.visible = True
                control.update()
                break
        
        # 如果没有提示信息，添加一个
        if not has_empty_tip:
            message = self._.get("no_search_results", "没有找到匹配的结果") + f": {search_message}" if query else self._.get("no_matching_items", "没有匹配的项目")
            empty_tip = ft.Container(
                key='empty_filter_tip',
                content=ft.Column(
                    [
                        ft.Icon(ft.icons.SEARCH_OFF, size=40, color=ft.colors.OUTLINE),
                        ft.Text(message, size=16)
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=10
                ),
                alignment=ft.alignment.center,
                expand=True,
                visible=True
            )
            self.recording_card_area.content.controls.append(empty_tip)
            self.recording_card_area.content.update()
        return True

    async def hide_empty_results_tip(self):
        """隐藏空结果提示"""
        for control in self.recording_card_area.content.controls:
            if hasattr(control, 'key') and control.key == 'empty_filter_tip':
                control.visible = False
                control.update()
                return True
        return False

    async def reset_cards_visibility(self):
        cards_obj = self.app.record_card_manager.cards_obj
        for card_info in cards_obj.values():
            if not card_info["card"].visible:
                card_info["card"].visible = True
                card_info["card"].update()

    @staticmethod
    def should_show_recording(filter_type, recording, platform_filter="all"):
        """检查录制项是否应该显示在当前筛选条件下"""
        # 先检查平台筛选
        if platform_filter != "all":
            _, platform_key = get_platform_info(recording.url)
            if platform_key != platform_filter:
                return False
        
        if filter_type == "all":
            return True
        elif filter_type == "recording":
            return recording.recording
        elif filter_type == "live_monitoring_not_recording":
            return recording.is_live and recording.monitor_status and not recording.recording
        elif filter_type == "error":
            return recording.status_info == RecordingStatus.RECORDING_ERROR
        elif filter_type == "offline":
            return not recording.is_live and recording.monitor_status
        elif filter_type == "stopped":
            return not recording.monitor_status
        return True

    async def apply_filter(self):
        self.content_area.controls[1] = self.create_filter_area()
        
        cards_obj = self.app.record_card_manager.cards_obj
        recordings = self.app.record_manager.recordings
        
        # 重置可见卡片列表
        self.visible_cards = []
        
        for recording in recordings:
            card_info = cards_obj.get(recording.rec_id)
            if not card_info:
                continue
                
            visible = self.should_show_recording(self.current_filter, recording, self.current_platform_filter)
            card_info["card"].visible = False  # 先设置所有卡片为不可见
            
            if visible:
                self.visible_cards.append(recording.rec_id)
        
        # 计算总页数
        self.total_pages = max(1, (len(self.visible_cards) + self.items_per_page - 1) // self.items_per_page)
        
        # 确保当前页码有效
        if self.current_page > self.total_pages:
            self.current_page = min(self.current_page, self.total_pages)
            if self.current_page < 1:
                self.current_page = 1
        
        # 更新页面显示
        await self.update_page_display()
        
        # 处理空结果
        if len(self.visible_cards) == 0:
            await self.handle_empty_results()
        else:
            await self.hide_empty_results_tip()
        
        self.content_area.update()

    async def filter_recordings(self, query="", use_current_filter=True):
        """
        过滤录制卡片显示
        
        参数:
            query: 搜索关键词
            use_current_filter: 是否使用当前筛选条件。如果为False，将忽略当前筛选，在所有直播间中搜索
        """
        cards_obj = self.app.record_card_manager.cards_obj
        recordings = self.app.record_manager.recordings
        
        # 重置可见卡片列表
        self.visible_cards = []
        
        # 首先重置所有卡片可见性
        if not use_current_filter:
            await self.reset_cards_visibility()
        
        for recording in recordings:
            card_info = cards_obj.get(recording.rec_id)
            if not card_info:
                continue
                
            # 搜索匹配
            match_query = True
            if query:
                query_lower = query.lower()
                match_query = (
                    query_lower in recording.streamer_name.lower()
                    or query_lower in recording.url.lower()
                    or (recording.live_title and query_lower in recording.live_title.lower())
                )
                
                # 添加平台名称搜索支持
                try:
                    from app.core.platform_handlers import get_platform_info
                    from app.core.platform_handlers.platform_map import get_platform_display_name
                    _, platform_key = get_platform_info(recording.url)
                    lang = getattr(self.app, 'language_code', 'zh_CN')
                    platform_name = get_platform_display_name(platform_key, lang)
                    # 支持中英文平台名称匹配，忽略大小写
                    if platform_name and query_lower in platform_name.lower():
                        match_query = True
                except:
                    pass
                
            # 筛选条件匹配
            match_filter = True
            if use_current_filter:
                match_platform = True
                if self.current_platform_filter != "all":
                    _, platform_key = get_platform_info(recording.url)
                    match_platform = (platform_key == self.current_platform_filter)
                    
                match_status = self.should_show_recording(self.current_filter, recording)
                match_filter = match_platform and match_status
                
            # 确定最终可见性
            visible = match_query and (not use_current_filter or match_filter)
            card_info["card"].visible = False  # 先设置所有卡片为不可见
            
            if visible:
                self.visible_cards.append(recording.rec_id)
        
        # 计算总页数
        self.total_pages = max(1, (len(self.visible_cards) + self.items_per_page - 1) // self.items_per_page)
        
        # 确保当前页码有效
        if self.current_page > self.total_pages:
            self.current_page = min(self.current_page, self.total_pages)
            if self.current_page < 1:
                self.current_page = 1
            
        # 更新页面显示
        await self.update_page_display()
        
        # 处理空结果
        if len(self.visible_cards) == 0:
            await self.handle_empty_results(query)
        else:
            await self.hide_empty_results_tip()

    def create_home_content_area(self):
        return ft.Column(
            expand=True,
            controls=[
                ft.Divider(height=1),
                ft.Container(
                    content=self.loading_indicator,
                    alignment=ft.alignment.center
                ),
                self.recording_card_area,
                # 添加底部空间，避免内容被固定在底部的分页控件遮挡
                ft.Container(height=60)
            ],
            scroll=ft.ScrollMode.AUTO,
        )

    async def add_record_cards(self):
        
        self.loading_indicator.visible = True
        self.loading_indicator.update()

        cards_to_create = []
        existing_cards = []
        
        for recording in self.app.record_manager.recordings:
            if recording.rec_id not in self.app.record_card_manager.cards_obj:
                cards_to_create.append(recording)
            else:
                existing_card = self.app.record_card_manager.cards_obj[recording.rec_id]["card"]
                existing_card.visible = False  # 初始设置为不可见，由分页控制显示
                existing_cards.append(existing_card)
        
        async def create_card_with_time_range(_recording: Recording):
            _card = await self.app.record_card_manager.create_card(_recording)
            _recording.scheduled_time_range = await self.app.record_manager.get_scheduled_time_range(
                _recording.scheduled_start_time, _recording.monitor_hours
            )
            return _card, _recording
        
        if cards_to_create:
            # 批量加载卡片，每批最多加载10个
            batch_size = 10
            total_batches = (len(cards_to_create) + batch_size - 1) // batch_size
            
            logger.info(f"开始批量加载录制卡片，共 {len(cards_to_create)} 个，分 {total_batches} 批处理")
            
            for batch_index in range(total_batches):
                start_idx = batch_index * batch_size
                end_idx = min(start_idx + batch_size, len(cards_to_create))
                batch_recordings = cards_to_create[start_idx:end_idx]
                
                logger.debug(f"加载第 {batch_index+1}/{total_batches} 批卡片，{len(batch_recordings)} 个")
                
                # 处理当前批次
                results = await asyncio.gather(*[
                    create_card_with_time_range(recording)
                    for recording in batch_recordings
                ])
                
                for card, recording in results:
                    card.visible = False  # 初始设置为不可见，由分页控制显示
                    self.recording_card_area.content.controls.append(card)
                    self.app.record_card_manager.cards_obj[recording.rec_id]["card"] = card
                
                # 更新UI，显示当前批次的卡片
                self.recording_card_area.update()
                
                # 如果不是最后一批，添加短暂延迟让UI有时间响应
                if batch_index < total_batches - 1:
                    await asyncio.sleep(0.05)
        
        if existing_cards:
            # 批量添加现有卡片，每批最多添加20个
            batch_size = 20
            total_batches = (len(existing_cards) + batch_size - 1) // batch_size
            
            for batch_index in range(total_batches):
                start_idx = batch_index * batch_size
                end_idx = min(start_idx + batch_size, len(existing_cards))
                batch_cards = existing_cards[start_idx:end_idx]
                
                self.recording_card_area.content.controls.extend(batch_cards)
                
                # 更新UI，显示当前批次的卡片
                if batch_index < total_batches - 1:
                    self.recording_card_area.update()
                    await asyncio.sleep(0.02)

        self.loading_indicator.visible = False
        self.loading_indicator.update()
        
        if not self.app.record_manager.periodic_task_started:
            self.page.run_task(
                self.app.record_manager.setup_periodic_live_check,
                self.app.record_manager.loop_time_seconds
            )
        
        # 应用过滤和分页
        await self.apply_filter()

    async def show_all_cards(self):
        cards_obj = self.app.record_card_manager.cards_obj
        for card in cards_obj.values():
            card["card"].visible = True
        self.recording_card_area.update()
        
        await self.apply_filter()

    async def add_recording(self, recordings_info):
        user_config = self.app.settings.user_config
        logger.info(f"Add items: {len(recordings_info)}")
        
        new_recordings = []
        for recording_info in recordings_info:
            streamer_name = recording_info.get("streamer_name")
            live_title = recording_info.get("live_title")
            title = recording_info.get("title")
            display_title = recording_info.get("display_title")
            if recording_info.get("record_format"):
                recording = Recording(
                    rec_id=str(uuid.uuid4()),
                    url=recording_info["url"],
                    streamer_name=streamer_name,
                    quality=recording_info["quality"],
                    record_format=recording_info["record_format"],
                    segment_record=recording_info["segment_record"],
                    segment_time=recording_info["segment_time"],
                    monitor_status=recording_info["monitor_status"],
                    scheduled_recording=recording_info["scheduled_recording"],
                    scheduled_start_time=recording_info["scheduled_start_time"],
                    monitor_hours=recording_info["monitor_hours"],
                    recording_dir=recording_info["recording_dir"],
                    enabled_message_push=recording_info["enabled_message_push"],
                    record_mode=recording_info.get("record_mode", "auto"),
                    remark=recording_info.get("remark"),
                    translation_enabled=recording_info.get("translation_enabled")
                )
            else:
                recording = Recording(
                    rec_id=str(uuid.uuid4()),
                    url=recording_info["url"],
                    streamer_name=streamer_name,
                    quality=recording_info["quality"],
                    record_format=user_config.get("video_format", "TS"),
                    segment_record=user_config.get("segmented_recording_enabled", False),
                    segment_time=user_config.get("video_segment_time", "1800"),
                    monitor_status=True,
                    scheduled_recording=user_config.get("scheduled_recording", False),
                    scheduled_start_time=user_config.get("scheduled_start_time"),
                    monitor_hours=user_config.get("monitor_hours"),
                    recording_dir=None,
                    enabled_message_push=True,
                    record_mode=recording_info.get("record_mode", user_config.get("record_mode", "auto")),
                    remark=recording_info.get("remark"),
                    translation_enabled=recording_info.get("translation_enabled")
                )
            recording.live_title = live_title
            if title:
                recording.title = title
            if display_title:
                recording.display_title = display_title
            recording.loop_time_seconds = int(user_config.get("loop_time_seconds", 300))
            
            # 处理翻译逻辑
            if live_title:
                await self.app.record_manager._handle_title_translation(recording)
            
            await self.app.record_manager.add_recording(recording)
            new_recordings.append(recording)

        if new_recordings:
            async def create_card_with_time_range(rec):
                _card = await self.app.record_card_manager.create_card(rec)
                rec.scheduled_time_range = await self.app.record_manager.get_scheduled_time_range(
                    rec.scheduled_start_time, rec.monitor_hours
                )
                return _card, rec

            results = await asyncio.gather(*[
                create_card_with_time_range(rec)
                for rec in new_recordings
            ])

            for card, recording in results:
                card.visible = False  # 初始设置为不可见，由分页控制显示
                self.recording_card_area.content.controls.append(card)
                self.app.record_card_manager.cards_obj[recording.rec_id]["card"] = card
                self.app.page.pubsub.send_others_on_topic("add", recording)
                
                # 将新添加的卡片添加到可见卡片列表
                if self.should_show_recording(self.current_filter, recording, self.current_platform_filter):
                    self.visible_cards.append(recording.rec_id)
                
                # 如果监控状态已开启，立即检查直播状态
                if recording.monitor_status:
                    self.app.page.run_task(self.app.record_manager.check_if_live, recording)

            # 重新计算总页数
            self.total_pages = max(1, (len(self.visible_cards) + self.items_per_page - 1) // self.items_per_page)
            
            # 如果添加了新卡片，自动跳转到最后一页以显示新卡片
            if self.visible_cards:
                self.current_page = self.total_pages
                await self.update_page_display()
                # 隐藏空结果提示
                await self.hide_empty_results_tip()
            else:
                self.recording_card_area.update()

        await self.app.snack_bar.show_snack_bar(self._["add_recording_success_tip"], bgcolor=ft.Colors.GREEN)
        self.content_area.controls[1] = self.create_filter_area()
        self.content_area.update()

    async def search_on_click(self, _e):
        """Open the search dialog when the search button is clicked."""
        search_dialog = SearchDialog(home_page=self)
        search_dialog.open = True
        self.app.dialog_area.content = search_dialog
        self.app.dialog_area.update()

    async def add_recording_on_click(self, _e):
        await self.add_recording_dialog.show_dialog()

    async def refresh_cards_on_click(self, _e):
        self.loading_indicator.visible = True
        self.loading_indicator.update()

        self.app.record_card_manager.load()

        cards_obj = self.app.record_card_manager.cards_obj
        recordings = self.app.record_manager.recordings
        selected_cards = self.app.record_card_manager.selected_cards
        new_ids = {rec.rec_id for rec in recordings}
        to_remove = []
        for card_id, card in cards_obj.items():
            if card_id not in new_ids:
                to_remove.append(card)
                continue
            if card_id in selected_cards:
                selected_cards[card_id].selected = False
                card["card"].content.bgcolor = None
                card["card"].update()

        for card in to_remove:
            card_key = card["card"].key
            cards_obj.pop(card_key, None)
            self.recording_card_area.controls.remove(card["card"])
            
            # 从可见卡片列表中移除
            if card_key in self.visible_cards:
                self.visible_cards.remove(card_key)

        # 批量更新卡片，每批最多更新15个
        batch_size = 15
        total_recordings = len(recordings)
        total_batches = (total_recordings + batch_size - 1) // batch_size
        
        logger.info(f"开始批量刷新录制卡片，共 {total_recordings} 个，分 {total_batches} 批处理")
        
        for batch_index in range(total_batches):
            start_idx = batch_index * batch_size
            end_idx = min(start_idx + batch_size, total_recordings)
            batch_recordings = recordings[start_idx:end_idx]
            
            logger.debug(f"刷新第 {batch_index+1}/{total_batches} 批卡片，{len(batch_recordings)} 个")
            
            # 并行更新当前批次的卡片
            update_tasks = []
            for recording in batch_recordings:
                update_tasks.append(self.app.record_card_manager.update_card(recording))
            
            if update_tasks:
                await asyncio.gather(*update_tasks)
                
                # 如果不是最后一批，添加短暂延迟让UI有时间响应
                if batch_index < total_batches - 1:
                    await asyncio.sleep(0.05)

        self.loading_indicator.visible = False
        self.loading_indicator.update()

        # 重新应用过滤和分页
        await self.apply_filter()

        await self.app.snack_bar.show_snack_bar(self._["refresh_success_tip"], bgcolor=ft.Colors.GREEN)

    async def start_monitor_recordings_on_click(self, _):
        # 直接尝试开始监控，start_monitor_recordings方法内部会检查磁盘空间
        # 无论是否已经显示过警告，每次点击按钮都会重新检查磁盘空间并可能显示警告
        result = await self.app.record_manager.start_monitor_recordings()
        
        # 只有在成功启动监控时才显示成功提示
        if result:
            await self.app.snack_bar.show_snack_bar(self._["start_recording_success_tip"], bgcolor=ft.Colors.GREEN)

    async def stop_monitor_recordings_on_click(self, _):
        await self.app.record_manager.stop_monitor_recordings()
        await self.app.snack_bar.show_snack_bar(self._["stop_recording_success_tip"])

    async def delete_monitor_recordings_on_click(self, _):
        selected_recordings = await self.app.record_manager.get_selected_recordings()
        
        # 检查是否有正在录制的项
        has_recording_items = False
        if selected_recordings:
            for recording in selected_recordings:
                if recording.recording:
                    has_recording_items = True
                    break
        else:
            # 如果没有选中项，则检查所有录制项
            for recording in self.app.record_manager.recordings:
                if recording.recording:
                    has_recording_items = True
                    break
        
        # 如果有正在录制的项，则提示无法删除
        if has_recording_items:
            await self.app.snack_bar.show_snack_bar(
                self._["recording_in_progress_tip"], bgcolor=ft.Colors.RED
            )
            return
        
        tips = self._["batch_delete_confirm_tip"] if selected_recordings else self._["clear_all_confirm_tip"]

        async def confirm_dlg(_):

            if selected_recordings:
                await self.app.record_manager.stop_monitor_recordings(selected_recordings)
                await self.app.record_manager.delete_recording_cards(selected_recordings)
            else:
                await self.app.record_manager.stop_monitor_recordings(self.app.record_manager.recordings)
                await self.app.record_manager.clear_all_recordings()
                await self.delete_all_recording_cards()
                self.app.page.pubsub.send_others_on_topic("delete_all", None)

            self.recording_card_area.update()
            await self.app.snack_bar.show_snack_bar(
                self._["delete_recording_success_tip"], bgcolor=ft.Colors.GREEN, duration=2000
            )
            await close_dialog(None)

        async def close_dialog(_):
            batch_delete_alert_dialog.open = False
            batch_delete_alert_dialog.update()

        batch_delete_alert_dialog = ft.AlertDialog(
            title=ft.Text(self._["confirm"]),
            content=ft.Text(tips),
            actions=[
                ft.TextButton(text=self._["cancel"], on_click=close_dialog),
                ft.TextButton(text=self._["sure"], on_click=confirm_dlg),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            modal=False,
        )

        batch_delete_alert_dialog.open = True
        self.app.dialog_area.content = batch_delete_alert_dialog
        self.page.update()

    async def delete_all_recording_cards(self):
        self.recording_card_area.content.controls.clear()
        self.recording_card_area.update()
        self.app.record_card_manager.cards_obj = {}
        
        # 重置分页相关状态
        self.visible_cards = []
        self.current_page = 1
        self.total_pages = 1
        
        # 确保分页控件已创建
        if self.pagination_controls:
            # 更新分页信息
            self.page_info_text.value = self._["pagination"]["page_info"].format(
                current_page=self.current_page, 
                total_pages=self.total_pages,
                total_items=0
            )
            
            # 更新分页控件状态
            pagination_row = self.pagination_controls.content.content.content
            pagination_row.controls[0].disabled = True  # 首页按钮
            pagination_row.controls[1].disabled = True  # 上一页按钮
            pagination_row.controls[3].disabled = True  # 下一页按钮
            pagination_row.controls[4].disabled = True  # 末页按钮
            self.pagination_controls.update()
        
        # 显示空结果提示
        await self.handle_empty_results()
        
        self.content_area.controls[1] = self.create_filter_area()
        self.content_area.update()

    async def subscribe_del_all_cards(self, *_):
        await self.delete_all_recording_cards()
        self.content_area.controls[1] = self.create_filter_area()
        self.content_area.update()

    async def subscribe_add_cards(self, _, recording: Recording):
        """Handle the subscription of adding cards from other clients"""
        
        self.loading_indicator.visible = True
        self.loading_indicator.update()
        
        if recording.rec_id not in self.app.record_card_manager.cards_obj:
            card = await self.app.record_card_manager.create_card(recording)
            recording.scheduled_time_range = await self.app.record_manager.get_scheduled_time_range(
                recording.scheduled_start_time, recording.monitor_hours
            )
            
            card.visible = False  # 初始设置为不可见，由分页控制显示
            self.recording_card_area.content.controls.append(card)
            self.app.record_card_manager.cards_obj[recording.rec_id]["card"] = card
            
            # 将新添加的卡片添加到可见卡片列表
            if self.should_show_recording(self.current_filter, recording, self.current_platform_filter):
                self.visible_cards.append(recording.rec_id)
                
                # 重新计算总页数
                self.total_pages = max(1, (len(self.visible_cards) + self.items_per_page - 1) // self.items_per_page)
                
                # 如果添加了新卡片，自动跳转到最后一页以显示新卡片
                self.current_page = self.total_pages
                await self.update_page_display()
            
            self.loading_indicator.visible = False
            self.loading_indicator.update()
            
            self.content_area.controls[1] = self.create_filter_area()
            self.content_area.update()

    async def update_grid_layout(self, _):
        self.page.run_task(self.recalculate_grid_columns)

    async def recalculate_grid_columns(self):
        if not self.is_grid_view:
            return

        column_width = 350
        runs_count = max(1, int(self.page.width / column_width))

        if isinstance(self.recording_card_area.content, ft.GridView):
            grid_view = self.recording_card_area.content
            grid_view.runs_count = runs_count
            grid_view.update()

    async def on_keyboard(self, e: ft.KeyboardEvent):
        if e.alt and e.key == "H":
            self.app.dialog_area.content = HelpDialog(self.app)
            self.app.dialog_area.content.open = True
            self.app.dialog_area.update()
        if self.app.current_page == self:
            if e.ctrl and e.key == "F":
                self.page.run_task(self.search_on_click, e)
            elif e.ctrl and e.key == "R":
                self.page.run_task(self.refresh_cards_on_click, e)
            elif e.alt and e.key == "N":
                self.page.run_task(self.add_recording_on_click, e)
            elif e.alt and e.key == "B":
                self.page.run_task(self.start_monitor_recordings_on_click, e)
            elif e.alt and e.key == "P":
                self.page.run_task(self.stop_monitor_recordings_on_click, e)
            elif e.alt and e.key == "D":
                self.page.run_task(self.delete_monitor_recordings_on_click, e)
            # 添加翻页快捷键
            elif e.ctrl and e.shift and e.key == "LEFT":  # Ctrl+Shift+左箭头：首页
                self.page.run_task(self.go_to_first_page, e)
            elif e.ctrl and e.key == "LEFT":  # Ctrl+左箭头：上一页
                self.page.run_task(self.go_to_prev_page, e)
            elif e.ctrl and e.key == "RIGHT":  # Ctrl+右箭头：下一页
                self.page.run_task(self.go_to_next_page, e)
            elif e.ctrl and e.shift and e.key == "RIGHT":  # Ctrl+Shift+右箭头：末页
                self.page.run_task(self.go_to_last_page, e)

    async def filter_all_platforms_on_click(self, _):
        self.current_platform_filter = "all"
        await self.apply_filter()

    async def on_platform_button_click(self, key):
        self.current_platform_filter = key
        await self.apply_filter()

    async def unload(self):
        """页面卸载时清理资源"""
        logger.debug("主页面开始卸载...")
        
        # 不做任何可能阻止或延迟页面切换的操作
        # 仅隐藏分页控件，保留其状态
        for overlay_item in self.page.overlay:
            if hasattr(overlay_item, 'key') and overlay_item.key == 'home_pagination_container':
                overlay_item.visible = False
                overlay_item.update()
                logger.debug("分页控件已隐藏")
        
        # 移除事件处理器
        self.page.on_keyboard_event = None
        self.page.on_resized = None
        
        logger.debug("主页面卸载完成")
