import json
import os
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
        base_path = Path(__file__).parent.parent.parent
        
        # 默认缓存文件路径，改为保存在StreamCap\config目录下
        self.cache_dir = cache_dir or os.path.join(base_path, "config")
        self.cache_file = os.path.join(self.cache_dir, "platform_logo_cache.json")
        self.cache_data = {}
        
        # 确保缓存目录存在
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # 加载缓存
        self.load_cache()
    
    def load_cache(self):
        """加载缓存文件"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache_data = json.load(f)
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
            return self.cache_data[rec_id]
        
        # 如果没有，则根据平台key获取默认logo路径
        default_logo_path = self.get_platform_logo_path(platform_key)
        
        # 将路径保存到缓存
        self.cache_data[rec_id] = default_logo_path
        self.save_cache()
        
        return default_logo_path
    
    def update_logo_path(self, rec_id, logo_path):
        """
        更新指定直播间的平台logo路径
        
        :param rec_id: 直播间ID
        :param logo_path: logo图片路径
        """
        self.cache_data[rec_id] = logo_path
        self.save_cache()
    
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
    
    @staticmethod
    def get_platform_logo_path(platform_key):
        """
        根据平台key获取对应的logo图片路径
        
        :param platform_key: 平台标识
        :return: logo图片路径
        """
        # 获取项目根目录下的平台logo路径
        base_path = Path(__file__).parent.parent.parent
        platform_logo_dir = os.path.join(base_path, "assets", "icons", "platforms")
        
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