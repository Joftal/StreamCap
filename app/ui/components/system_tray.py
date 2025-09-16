import os
import threading
from typing import Optional, Callable
import pystray
from PIL import Image
import flet as ft

from ...utils.logger import logger


class SystemTrayManager:
    """系统托盘管理器"""
    
    def __init__(self, app):
        self.app = app
        self.tray_icon: Optional[pystray.Icon] = None
        self.tray_thread: Optional[threading.Thread] = None
        self.is_minimized = False
        self._restore_callback: Optional[Callable] = None
        self._ = {}
        self.load_language()
        
        # 注册语言变更观察者
        if hasattr(self.app, 'language_manager'):
            self.app.language_manager.add_observer(self)
    
    def load_language(self):
        """加载语言配置"""
        if hasattr(self.app, 'language_manager'):
            language = self.app.language_manager.language
            self._ = language.get("system_tray", {})
    
    def load(self):
        """加载方法，用于语言管理器通知"""
        self.load_language()
    
    def on_language_changed(self):
        """语言变更时的回调函数"""
        self.load_language()
        # 如果托盘已经创建，重新创建以更新菜单文本
        if self.tray_icon and self.is_minimized:
            self.recreate_tray()
    
    def get_icon_image(self):
        """获取托盘图标图像"""
        try:
            # 使用项目中的图标文件
            icon_path = os.path.join(self.app.assets_dir, "icon.ico")
            if os.path.exists(icon_path):
                return Image.open(icon_path)
            else:
                # 如果找不到图标文件，使用备用图标
                icon_path = os.path.join(self.app.assets_dir, "icons", "app_icon.png")
                if os.path.exists(icon_path):
                    return Image.open(icon_path)
                else:
                    # 创建一个简单的默认图标
                    return self.create_default_icon()
        except Exception as e:
            logger.warning(f"加载托盘图标失败: {e}")
            return self.create_default_icon()
    
    def create_default_icon(self):
        """创建默认图标"""
        try:
            # 创建一个简单的32x32像素的蓝色图标
            img = Image.new('RGBA', (32, 32), (0, 120, 215, 255))
            return img
        except Exception as e:
            logger.error(f"创建默认图标失败: {e}")
            # 如果连默认图标都创建失败，返回None，pystray会使用系统默认图标
            return None
    
    def create_tray_menu(self):
        """创建托盘右键菜单"""
        return pystray.Menu(
            pystray.MenuItem(
                self._.get("show_window", "显示窗口"),
                self.on_restore_window,
                default=True  # 设置为默认项（双击时执行）
            ),
            pystray.Menu.SEPARATOR,
            # 注意：根据需求，这里不添加退出选项
            # pystray.MenuItem(
            #     self._.get("exit", "退出"),
            #     self.on_exit
            # )
        )
    
    def on_restore_window(self, icon=None, item=None):
        """恢复窗口显示（托盘菜单点击时调用）"""
        try:
            # 直接调用内部的恢复方法，避免循环调用
            self.restore_window()
        except Exception as e:
            logger.error(f"恢复窗口时出错: {e}")
    
    def minimize_to_tray(self, restore_callback: Optional[Callable] = None):
        """最小化到托盘"""
        try:
            if self.is_minimized:
                return
            
            # 如果提供了外部回调函数，则使用它，否则使用默认的恢复方法
            self._restore_callback = restore_callback if restore_callback else self.restore_window
            
            # 隐藏窗口
            self.app.page.window.visible = False
            self.app.page.update()
            
            # 创建托盘图标
            self.create_tray()
            
            self.is_minimized = True
            
        except Exception as e:
            logger.error(f"最小化到托盘时出错: {e}")
            # 如果出错，确保窗口仍然可见并重置状态
            self.app.page.window.visible = True
            self.app.page.update()
            self.is_minimized = False
    
    def create_tray(self):
        """创建系统托盘图标"""
        try:
            if self.tray_icon:
                return  # 已经存在
            
            icon_image = self.get_icon_image()
            menu = self.create_tray_menu()
            
            self.tray_icon = pystray.Icon(
                "StreamCap",
                icon_image,
                title="StreamCap",
                menu=menu
            )
            
            # 在单独的线程中运行托盘
            self.tray_thread = threading.Thread(
                target=self._run_tray,
                daemon=True
            )
            self.tray_thread.start()
            
        except Exception as e:
            logger.error(f"创建系统托盘时出错: {e}")
    
    def _run_tray(self):
        """在单独线程中运行托盘"""
        try:
            if self.tray_icon:
                self.tray_icon.run()
        except Exception as e:
            logger.error(f"运行系统托盘时出错: {e}")
    
    def recreate_tray(self):
        """重新创建托盘（用于更新菜单文本）"""
        try:
            if not self.is_minimized:
                return
            
            # 停止当前托盘
            old_callback = self._restore_callback
            self.stop_tray()
            
            # 重新创建
            self._restore_callback = old_callback
            self.create_tray()
            
        except Exception as e:
            logger.error(f"重新创建托盘时出错: {e}")
    
    def stop_tray(self):
        """停止托盘"""
        try:
            # 首先设置状态
            self.is_minimized = False
            
            if self.tray_icon:
                self.tray_icon.stop()
                self.tray_icon = None
            
            # 避免在当前线程中join自己
            if self.tray_thread and self.tray_thread.is_alive():
                current_thread = threading.current_thread()
                if self.tray_thread != current_thread:
                    self.tray_thread.join(timeout=1.0)
            
            self.tray_thread = None
            
        except Exception as e:
            logger.error(f"停止托盘时出错: {e}")
            # 确保状态被重置，即使出现错误
            self.is_minimized = False
    
    def restore_window(self):
        """恢复窗口显示"""
        try:
            # 首先检查是否真的需要恢复
            if not self.is_minimized:
                return
                
            # 显示窗口
            self.app.page.window.visible = True
            self.app.page.window.to_front()
            self.app.page.update()
            
            # 停止托盘
            self.stop_tray()
            
        except Exception as e:
            logger.error(f"恢复窗口时出错: {e}")
            # 即使出错也要确保状态重置
            self.is_minimized = False
    
    def cleanup(self):
        """清理资源"""
        try:
            self.stop_tray()
        except Exception as e:
            logger.error(f"清理托盘资源时出错: {e}")
