import asyncio
import httpx
import re
import hashlib
import random
import time
from typing import Optional, Dict, Any
from ..utils.logger import logger


class TranslationService:
    """翻译服务类，支持多种翻译提供商"""
    
    def __init__(self, provider: str = "google", baidu_app_id: str = "", baidu_secret_key: str = ""):
        self.session = None
        self.provider = provider
        self.baidu_app_id = baidu_app_id
        self.baidu_secret_key = baidu_secret_key
        
        # Google翻译API配置
        self.google_base_url = "https://translate.googleapis.com/translate_a/single"
        
        # 百度翻译API配置
        self.baidu_base_url = "https://fanyi-api.baidu.com/api/trans/vip/translate"
        
        # 支持的语言映射
        self.language_map = {
            'zh_CN': 'zh',  # 中文
            'en': 'en',     # 英文
            'zh': 'zh',     # 中文（简化）
            'en_US': 'en',  # 美式英文
            'en_GB': 'en',  # 英式英文
        }
        
        # 百度翻译语言代码映射
        self.baidu_language_map = {
            'zh': 'zh',     # 中文
            'en': 'en',     # 英文
            'zh_CN': 'zh',  # 中文
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
    
    def _generate_baidu_sign(self, query: str, salt: str) -> str:
        """生成百度翻译API的签名"""
        sign_str = self.baidu_app_id + query + salt + self.baidu_secret_key
        return hashlib.md5(sign_str.encode('utf-8')).hexdigest()
    
    async def _translate_with_google(self, text: str, target_language: str) -> Optional[str]:
        """使用Google翻译API进行翻译"""
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
            response = await self.session.get(self.google_base_url, params=params)
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
                    return translated_text.strip()
                else:
                    logger.warning(f"Google翻译结果为空: '{text}'")
                    return None
            else:
                logger.warning(f"Google翻译API返回空结果: '{text}'")
                return None
                
        except httpx.TimeoutException:
            logger.error(f"Google翻译请求超时: '{text}'")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"Google翻译请求HTTP错误: {e.status_code} - '{text}'")
            return None
        except Exception as e:
            logger.error(f"Google翻译请求异常: {e} - '{text}'")
            return None
    
    async def _translate_with_baidu(self, text: str, target_language: str) -> Optional[str]:
        """使用百度翻译API进行翻译"""
        try:
            if not self.baidu_app_id or not self.baidu_secret_key:
                logger.error("百度翻译API配置不完整，缺少App ID或Secret Key")
                return None
                
            if not self.session:
                self.session = httpx.AsyncClient(timeout=10.0)
            
            # 生成随机数和签名
            salt = str(int(time.time() * 1000))
            sign = self._generate_baidu_sign(text, salt)
            
            # 构建请求参数
            params = {
                'q': text,
                'from': 'auto',  # 自动检测源语言
                'to': self.baidu_language_map.get(target_language, target_language),
                'appid': self.baidu_app_id,
                'salt': salt,
                'sign': sign
            }
            
            # 发送请求
            response = await self.session.get(self.baidu_base_url, params=params)
            response.raise_for_status()
            
            # 解析响应
            result = response.json()
            if result.get('error_code'):
                logger.error(f"百度翻译API错误: {result.get('error_msg', '未知错误')}")
                return None
                
            if result.get('trans_result'):
                translated_text = result['trans_result'][0]['dst']
                if translated_text and translated_text.strip():
                    return translated_text.strip()
                else:
                    logger.warning(f"百度翻译结果为空: '{text}'")
                    return None
            else:
                logger.warning(f"百度翻译API返回空结果: '{text}'")
                return None
                
        except httpx.TimeoutException:
            logger.error(f"百度翻译请求超时: '{text}'")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"百度翻译请求HTTP错误: {e.status_code} - '{text}'")
            return None
        except Exception as e:
            logger.error(f"百度翻译请求异常: {e} - '{text}'")
            return None

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
            
        # 根据配置的翻译提供商进行翻译
        if self.provider == "baidu":
            translated_text = await self._translate_with_baidu(text, target_language)
        else:  # 默认使用Google翻译
            translated_text = await self._translate_with_google(text, target_language)
        
        if translated_text:
            #logger.debug(f"翻译成功 ({self.provider}): '{text}' -> '{translated_text}' ({source_language} -> {target_language})")
            return translated_text
        else:
            logger.warning(f"翻译失败 ({self.provider}): '{text}'")
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
    
    async def translate_live_title_to_multiple_languages(self, live_title: str, target_languages: list) -> dict:
        """
        将直播标题翻译为多种语言
        
        Args:
            live_title: 直播标题
            target_languages: 目标语言列表，如 ['zh', 'en']
            
        Returns:
            dict: 语言代码到翻译结果的映射，如 {'zh': '中文标题', 'en': 'English Title'}
        """
        if not live_title:
            return {}
            
        results = {}
        
        # 检测源语言
        source_language = self.detect_language(live_title)
        
        # 为每种目标语言进行翻译
        for target_lang in target_languages:
            # 如果源语言与目标语言相同，不需要翻译
            if source_language == target_lang:
                results[target_lang] = live_title
                continue
                
            # 翻译为目标语言
            translated = await self.translate_text(live_title, target_lang)
            if translated and translated != live_title:
                results[target_lang] = translated
            else:
                # 翻译失败，使用原标题
                results[target_lang] = live_title
                
        return results


# 全局翻译服务实例
_translation_service = None


async def get_translation_service(config_manager=None) -> TranslationService:
    """获取翻译服务实例"""
    global _translation_service
    
    if config_manager:
        # 从配置中获取翻译设置
        user_config = config_manager.load_user_config()
        provider = user_config.get("translation_provider", "google")
        baidu_app_id = user_config.get("baidu_translation_app_id", "")
        baidu_secret_key = user_config.get("baidu_translation_secret_key", "")
        
        # 检查是否需要重新创建实例
        if (_translation_service is None or 
            _translation_service.provider != provider or
            _translation_service.baidu_app_id != baidu_app_id or
            _translation_service.baidu_secret_key != baidu_secret_key):
            
            _translation_service = TranslationService(
                provider=provider,
                baidu_app_id=baidu_app_id,
                baidu_secret_key=baidu_secret_key
            )
    elif _translation_service is None:
        # 默认使用Google翻译
        _translation_service = TranslationService()
    
    return _translation_service


async def translate_live_title(live_title: str, app_language_code: str = 'zh_CN', config_manager=None) -> str:
    """
    翻译直播标题的便捷函数（支持国际化）
    
    Args:
        live_title: 直播标题
        app_language_code: 程序语言代码
        config_manager: 配置管理器，用于获取翻译设置
        
    Returns:
        翻译后的标题
    """
    if not live_title:
        return live_title
        
    try:
        # 获取翻译服务实例
        service = await get_translation_service(config_manager)
        result = await service.translate_live_title(live_title, app_language_code)
        return result if result else live_title
    except Exception as e:
        logger.error(f"翻译直播标题失败: {e}")
        return live_title


async def translate_live_title_to_multiple_languages(live_title: str, target_languages: list, config_manager=None) -> dict:
    """
    将直播标题翻译为多种语言的便捷函数
    
    Args:
        live_title: 直播标题
        target_languages: 目标语言列表，如 ['zh', 'en']
        config_manager: 配置管理器，用于获取翻译设置
        
    Returns:
        dict: 语言代码到翻译结果的映射
    """
    if not live_title or not target_languages:
        return {}
        
    try:
        # 获取翻译服务实例
        service = await get_translation_service(config_manager)
        result = await service.translate_live_title_to_multiple_languages(live_title, target_languages)
        return result
    except Exception as e:
        logger.error(f"多语言翻译直播标题失败: {e}")
        return {}
