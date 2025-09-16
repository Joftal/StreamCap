import asyncio
import httpx
import re
from typing import Optional
from ..utils.logger import logger


class TranslationService:
    """谷歌翻译服务类"""
    
    def __init__(self):
        self.session = None
        self.base_url = "https://translate.googleapis.com/translate_a/single"
        
        # 支持的语言映射
        self.language_map = {
            'zh_CN': 'zh',  # 中文
            'en': 'en',     # 英文
            'zh': 'zh',     # 中文（简化）
            'en_US': 'en',  # 美式英文
            'en_GB': 'en',  # 英式英文
        }
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = httpx.AsyncClient(timeout=10.0)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.aclose()
    
    def is_chinese(self, text: str) -> bool:
        """判断文本是否为中文"""
        if not text:
            return False
        
        # 检查是否包含中文字符
        chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
        return bool(chinese_pattern.search(text))
    
    def is_english(self, text: str) -> bool:
        """判断文本是否为英文"""
        if not text:
            return False
        
        # 检查是否主要包含英文字符
        english_pattern = re.compile(r'^[a-zA-Z\s\.,!?;:\'\"\-\(\)]+$')
        return bool(english_pattern.search(text.strip()))
    
    def detect_language(self, text: str) -> str:
        """检测文本语言"""
        if not text:
            return 'unknown'
        
        if self.is_chinese(text):
            return 'zh'
        elif self.is_english(text):
            return 'en'
        else:
            return 'unknown'
    
    def get_target_language(self, app_language_code: str) -> str:
        """根据程序语言获取翻译目标语言"""
        return self.language_map.get(app_language_code, 'zh')  # 默认翻译为中文
    
    async def translate_text(self, text: str, target_language: str) -> Optional[str]:
        """
        将文本翻译为指定语言
        
        Args:
            text: 要翻译的文本
            target_language: 目标语言代码 (zh, en)
            
        Returns:
            翻译后的文本，如果翻译失败则返回None
        """
        if not text:
            return text
            
        # 检测源语言
        source_language = self.detect_language(text)
        
        # 如果源语言与目标语言相同，不需要翻译
        if source_language == target_language:
            return text
            
        try:
            if not self.session:
                self.session = httpx.AsyncClient(timeout=10.0)
            
            # 构建请求参数
            params = {
                'client': 'gtx',
                'sl': 'auto',  # 自动检测源语言
                'tl': target_language,  # 目标语言
                'dt': 't',
                'q': text
            }
            
            # 发送请求
            response = await self.session.get(self.base_url, params=params)
            response.raise_for_status()
            
            # 解析响应
            result = response.json()
            if result and len(result) > 0 and result[0]:
                # 提取翻译结果
                translated_parts = []
                for item in result[0]:
                    if item and len(item) > 0:
                        translated_parts.append(item[0])
                
                translated_text = ''.join(translated_parts)
                
                # 验证翻译结果
                if translated_text and translated_text.strip():
                    logger.debug(f"翻译成功: '{text}' -> '{translated_text}' ({source_language} -> {target_language})")
                    return translated_text.strip()
                else:
                    logger.warning(f"翻译结果为空: '{text}'")
                    return None
            else:
                logger.warning(f"翻译API返回空结果: '{text}'")
                return None
                
        except httpx.TimeoutException:
            logger.error(f"翻译请求超时: '{text}'")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"翻译请求HTTP错误: {e.status_code} - '{text}'")
            return None
        except Exception as e:
            logger.error(f"翻译请求异常: {e} - '{text}'")
            return None
    
    async def translate_to_chinese(self, text: str) -> Optional[str]:
        """
        将文本翻译为中文（保持向后兼容）
        
        Args:
            text: 要翻译的文本
            
        Returns:
            翻译后的中文文本，如果翻译失败则返回None
        """
        return await self.translate_text(text, 'zh')
    
    async def translate_live_title(self, live_title: str, app_language_code: str = 'zh_CN') -> Optional[str]:
        """
        翻译直播标题（支持国际化）
        
        Args:
            live_title: 直播标题
            app_language_code: 程序语言代码
            
        Returns:
            翻译后的标题，如果翻译失败或不需要翻译则返回原标题
        """
        if not live_title:
            return live_title
            
        # 获取目标语言
        target_language = self.get_target_language(app_language_code)
        
        # 检测源语言
        source_language = self.detect_language(live_title)
        
        # 如果源语言与目标语言相同，不需要翻译
        if source_language == target_language:
            return live_title
            
        # 翻译为目标语言
        translated = await self.translate_text(live_title, target_language)
        return translated if translated else live_title


# 全局翻译服务实例
_translation_service = None


async def get_translation_service() -> TranslationService:
    """获取翻译服务实例"""
    global _translation_service
    if _translation_service is None:
        _translation_service = TranslationService()
    return _translation_service


async def translate_live_title(live_title: str, app_language_code: str = 'zh_CN') -> str:
    """
    翻译直播标题的便捷函数（支持国际化）
    
    Args:
        live_title: 直播标题
        app_language_code: 程序语言代码
        
    Returns:
        翻译后的标题
    """
    if not live_title:
        return live_title
        
    try:
        async with TranslationService() as service:
            result = await service.translate_live_title(live_title, app_language_code)
            return result if result else live_title
    except Exception as e:
        logger.error(f"翻译直播标题失败: {e}")
        return live_title
