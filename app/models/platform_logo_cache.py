import json
import os
import sys
from pathlib import Path

from ..utils.logger import logger


class PlatformLogoCache:
    """
    平台logo缓存管理类
    用于管理直播间卡片左侧显示的平台logo缓存
    """
    def __init__(self, cache_dir=None):
        """
        初始化平台logo缓存
        
        :param cache_dir: 缓存目录，如果为None则使用默认缓存目录
        """
        # 获取项目根目录
        self.base_path = self._get_base_path()
        
        # 默认缓存文件路径，改为保存在StreamCap\config目录下
        self.cache_dir = cache_dir or os.path.join(self.base_path, "config")
        self.cache_file = os.path.join(self.cache_dir, "platform_logo_cache.json")
        self.cache_data = {}
        
        # 确保缓存目录存在
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # 加载缓存
        self.load_cache()
    
    def _get_base_path(self):
        """获取应用程序基础路径，考虑打包和开发环境"""
        if getattr(sys, 'frozen', False):
            # 如果是打包后的可执行文件，使用可执行文件所在目录
            base_path = os.path.dirname(sys.executable)
            logger.info(f"运行在打包环境中，基础路径: {base_path}")
        else:
            # 开发环境，使用项目根目录
            base_path = Path(__file__).parent.parent.parent
            logger.info(f"运行在开发环境中，基础路径: {base_path}")
        return base_path
    
    def _convert_to_relative_path(self, absolute_path):
        """将绝对路径转换为相对于基础路径的相对路径"""
        if not absolute_path:
            return None
        
        try:
            # 尝试从绝对路径中提取文件名
            file_name = os.path.basename(absolute_path)
            # 查找该文件在assets/icons/platforms目录中
            platform_logo_dir = os.path.join(self.base_path, "assets", "icons", "platforms")
            relative_path = os.path.join(platform_logo_dir, file_name)
            
            if os.path.exists(relative_path):
                return relative_path
            else:
                return None
        except:
            return None
    
    def load_cache(self):
        """加载缓存文件"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache_data = json.load(f)
                
                # 处理目录迁移情况：检查缓存中的路径是否存在，如果不存在则尝试修复
                fixed_items = 0
                platform_logo_dir = os.path.join(self.base_path, "assets", "icons", "platforms")
                
                # 创建一个新的缓存字典，用于存储修复后的数据
                fixed_cache = {}
                
                for rec_id, logo_path in self.cache_data.items():
                    # 检查路径是否存在
                    if logo_path and os.path.exists(logo_path):
                        # 路径存在，但转换为相对于当前基础路径的路径
                        fixed_cache[rec_id] = logo_path
                    else:
                        # 路径不存在，尝试从路径中提取平台标识
                        platform_key = None
                        try:
                            # 尝试从路径中提取文件名
                            file_name = os.path.basename(logo_path)
                            # 移除扩展名
                            platform_key = os.path.splitext(file_name)[0]
                        except Exception:
                            platform_key = None
                        
                        # 如果成功提取了平台标识，尝试在当前目录结构中找到对应的logo
                        if platform_key:  
                            new_path = os.path.join(platform_logo_dir, f"{platform_key}.png")
                            if os.path.exists(new_path):
                                fixed_cache[rec_id] = new_path
                                fixed_items += 1
                                logger.info(f"已修复平台logo路径: {platform_key} -> {new_path}")
                            else:
                                # 使用默认logo
                                default_logo = os.path.join(platform_logo_dir, "moren.png")
                                if os.path.exists(default_logo):
                                    fixed_cache[rec_id] = default_logo
                                    fixed_items += 1
                                    logger.info(f"未找到平台 {platform_key} 的logo，已使用默认logo")
                        else:
                            # 无法识别平台，使用默认logo
                            default_logo = os.path.join(platform_logo_dir, "moren.png")
                            if os.path.exists(default_logo):
                                fixed_cache[rec_id] = default_logo
                                fixed_items += 1
                                logger.info(f"无法识别平台logo路径，已使用默认logo")
                
                # 更新缓存数据
                self.cache_data = fixed_cache
                
                # 如果有修复的项，立即保存缓存
                if fixed_items > 0:
                    logger.info(f"已修复 {fixed_items} 个无效的平台logo路径")
                    self.save_cache()
                
                logger.info(f"已加载平台logo缓存，共{len(self.cache_data)}项")
            else:
                logger.info("平台logo缓存文件不存在，将创建新缓存")
                self.cache_data = {}
        except Exception as e:
            logger.error(f"加载平台logo缓存失败: {str(e)}")
            self.cache_data = {}
    
    def save_cache(self):
        """保存缓存到文件"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache_data, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存平台logo缓存，共{len(self.cache_data)}项")
        except Exception as e:
            logger.error(f"保存平台logo缓存失败: {str(e)}")
    
    def get_logo_path(self, rec_id, platform_key):
        """
        获取指定直播间的平台logo路径
        
        :param rec_id: 直播间ID
        :param platform_key: 平台标识
        :return: logo图片路径
        """
        # 首先检查缓存中是否有该直播间的logo信息
        if rec_id in self.cache_data:
            logo_path = self.cache_data[rec_id]
            # 验证路径是否存在且不为None
            if logo_path and os.path.exists(logo_path):
                return logo_path
            else:
                # 路径不存在或为None，从缓存中移除
                logger.warning(f"缓存的logo路径不存在或无效: {logo_path}，将重新获取")
                self.remove_logo_cache(rec_id)
        
        # 如果没有或路径无效，则根据平台key获取默认logo路径
        default_logo_path = self.get_platform_logo_path(platform_key)
        
        # 验证获取的路径是否有效
        if default_logo_path:
            # 将路径保存到缓存
            self.cache_data[rec_id] = default_logo_path
            self.save_cache()
            return default_logo_path
        else:
            # 如果获取失败，不保存到缓存
            logger.warning(f"无法为平台 {platform_key} 获取有效的logo路径")
            return None
    
    def update_logo_path(self, rec_id, logo_path):
        """
        更新指定直播间的平台logo路径
        
        :param rec_id: 直播间ID
        :param logo_path: logo图片路径
        """
        # 验证路径是否存在
        if logo_path and os.path.exists(logo_path):
            self.cache_data[rec_id] = logo_path
            self.save_cache()
        else:
            logger.warning(f"尝试更新的logo路径不存在: {logo_path}")
    
    def remove_logo_cache(self, rec_id):
        """
        删除指定直播间的平台logo缓存
        
        :param rec_id: 直播间ID
        """
        if rec_id in self.cache_data:
            del self.cache_data[rec_id]
            self.save_cache()
            logger.info(f"已删除直播间 {rec_id} 的平台logo缓存")
    
    def remove_multiple_logo_cache(self, rec_ids):
        """
        批量删除多个直播间的平台logo缓存
        
        :param rec_ids: 直播间ID列表
        """
        removed_count = 0
        for rec_id in rec_ids:
            if rec_id in self.cache_data:
                del self.cache_data[rec_id]
                removed_count += 1
        
        if removed_count > 0:
            self.save_cache()
            logger.info(f"已批量删除{removed_count}个直播间的平台logo缓存")
    
    def clear_cache(self):
        """清空所有缓存"""
        self.cache_data = {}
        self.save_cache()
        logger.info("已清空平台logo缓存")
    
    def get_platform_logo_path(self, platform_key):
        """
        根据平台key获取对应的logo图片路径
        
        :param platform_key: 平台标识
        :return: logo图片路径
        """
        # 获取项目根目录下的平台logo路径
        platform_logo_dir = os.path.join(self.base_path, "assets", "icons", "platforms")
        
        # 检查平台特定的logo是否存在
        platform_logo_path = os.path.join(platform_logo_dir, f"{platform_key}.png")
        if os.path.exists(platform_logo_path):
            return platform_logo_path
        
        # 如果不存在，返回默认logo
        default_logo_path = os.path.join(platform_logo_dir, "moren.png")
        if os.path.exists(default_logo_path):
            return default_logo_path
        
        # 如果默认logo也不存在，返回None
        logger.warning(f"未找到平台 {platform_key} 的logo，且默认logo也不存在")
        return None 