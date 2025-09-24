#!/usr/bin/env python3
"""
增强版SOOP平台处理器
用于改进title字段的解析
"""

import json
import re
import html
from typing import Optional
import streamget
import httpx
from .base import PlatformHandler, StreamData
from ...utils.logger import logger
from ...utils.utils import trace_error_decorator


class EnhancedSoopHandler(PlatformHandler):
    """增强版SOOP平台处理器，改进title解析"""
    platform = "soop"

    def __init__(
        self,
        proxy: str | None = None,
        cookies: str | None = None,
        record_quality: str | None = None,
        platform: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        super().__init__(proxy, cookies, record_quality, platform, username, password)
        self.live_stream: streamget.SoopLiveStream | None = None

    @trace_error_decorator
    async def get_stream_info(self, live_url: str) -> StreamData:
        """获取SOOP直播信息，增强title解析"""
        if not self.live_stream:
            self.live_stream = streamget.SoopLiveStream(
                proxy_addr=self.proxy, cookies=self.cookies, username=self.username, password=self.password
            )
        
        # 获取原始数据
        json_data = await self.live_stream.fetch_web_stream_data(url=live_url)
        
        # 使用基类的统一方法处理json_data为None的情况
        offline_result = self._handle_json_data_none(json_data, live_url)
        if offline_result is not None:
            return offline_result
        
        # 获取基础StreamData
        stream_data = await self.live_stream.fetch_stream_url(json_data, self.record_quality)
        
        # 如果title为空，尝试多种方法解析title
        if stream_data and (not stream_data.title or stream_data.title.strip() == ""):
            enhanced_title = None
            
            # 方法1: 从json_data中解析title
            enhanced_title = self._extract_title_from_json(json_data, live_url)
            
            # 方法2: 如果仍然没有title，尝试从网页抓取
            if not enhanced_title:
                enhanced_title = await self._extract_title_from_webpage(live_url)
            
            if enhanced_title:
                # 解码HTML实体编码
                decoded_title = self._decode_html_entities(enhanced_title)
                
                # 创建新的StreamData对象，包含解析出的title
                enhanced_stream_data = StreamData(
                    platform=stream_data.platform,
                    anchor_name=stream_data.anchor_name,
                    is_live=stream_data.is_live,
                    title=decoded_title,  # 使用解码后的title
                    quality=stream_data.quality,
                    m3u8_url=stream_data.m3u8_url,
                    flv_url=stream_data.flv_url,
                    record_url=stream_data.record_url,
                    new_cookies=stream_data.new_cookies,
                    new_token=stream_data.new_token,
                    extra=stream_data.extra
                )
                #logger.info(f"SOOP平台成功解析title: '{decoded_title}'")
                return enhanced_stream_data
            else:
                #logger.info(f"SOOP平台无法从数据中解析title: {live_url}")
                pass
        
        return stream_data

    def _extract_title_from_json(self, json_data, live_url: str) -> Optional[str]:
        """从JSON数据中提取title"""
        if not json_data:
            return None
        
        try:
            # 尝试多种可能的title字段路径
            title_candidates = []
            
            # 方法1: 直接查找title字段
            if isinstance(json_data, dict):
                title_candidates.extend(self._search_title_in_dict(json_data))
            elif isinstance(json_data, str):
                try:
                    parsed_data = json.loads(json_data)
                    if isinstance(parsed_data, dict):
                        title_candidates.extend(self._search_title_in_dict(parsed_data))
                except json.JSONDecodeError:
                    pass
            
            # 方法2: 使用正则表达式搜索可能的title
            json_str = str(json_data)
            title_candidates.extend(self._search_title_with_regex(json_str))
            
            # 选择最合适的title
            best_title = self._select_best_title(title_candidates)
            
            if best_title:
                logger.debug(f"从SOOP数据中提取到title候选: {title_candidates}")
                logger.debug(f"选择的最佳title: '{best_title}'")
            
            return best_title
            
        except json.JSONDecodeError as e:
            logger.debug(f"JSON解析错误: {e}")
            return None
        except (AttributeError, TypeError) as e:
            logger.debug(f"数据类型错误: {e}")
            return None
        except Exception as e:
            logger.warning(f"解析SOOP title时发生未知错误: {e}")
            return None

    async def _extract_title_from_webpage(self, live_url: str) -> Optional[str]:
        """从网页中提取title"""
        try:
            logger.debug(f"尝试从网页抓取SOOP title: {live_url}")
            
            # 设置请求头，模拟浏览器
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            # 如果有cookies，添加到请求头
            if self.cookies:
                headers['Cookie'] = self.cookies
            
            async with httpx.AsyncClient(timeout=10.0, proxy=self.proxy) as client:
                response = await client.get(live_url, headers=headers)
                response.raise_for_status()
                
                html_content = response.text
                
                # 使用多种方法提取title
                title_candidates = []
                
                # 方法1: 从HTML title标签提取
                title_match = re.search(r'<title[^>]*>([^<]+)</title>', html_content, re.IGNORECASE)
                if title_match:
                    title_candidates.append({
                        'title': title_match.group(1).strip(),
                        'method': 'html_title',
                        'priority': 1
                    })
                
                # 方法2: 从meta标签提取
                meta_patterns = [
                    r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']',
                    r'<meta[^>]*name=["\']title["\'][^>]*content=["\']([^"\']+)["\']',
                    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']',
                ]
                
                for pattern in meta_patterns:
                    matches = re.findall(pattern, html_content, re.IGNORECASE)
                    for match in matches:
                        if match.strip():
                            title_candidates.append({
                                'title': match.strip(),
                                'method': 'meta_tag',
                                'priority': 2
                            })
                
                # 方法3: 从JavaScript变量中提取
                js_patterns = [
                    r'["\']title["\']\s*:\s*["\']([^"\']+)["\']',
                    r'["\']roomTitle["\']\s*:\s*["\']([^"\']+)["\']',
                    r'["\']liveTitle["\']\s*:\s*["\']([^"\']+)["\']',
                    r'roomTitle\s*=\s*["\']([^"\']+)["\']',
                    r'liveTitle\s*=\s*["\']([^"\']+)["\']',
                ]
                
                for pattern in js_patterns:
                    matches = re.findall(pattern, html_content, re.IGNORECASE)
                    for match in matches:
                        if match.strip():
                            title_candidates.append({
                                'title': match.strip(),
                                'method': 'javascript',
                                'priority': 3
                            })
                
                # 选择最佳title
                if title_candidates:
                    # 按优先级排序
                    title_candidates.sort(key=lambda x: x['priority'])
                    
                    # 过滤掉明显不是title的内容
                    filtered_candidates = []
                    for candidate in title_candidates:
                        title = candidate['title']
                        # 使用统一的过滤条件
                        if self._is_valid_title(title):
                            filtered_candidates.append(candidate)
                    
                    if filtered_candidates:
                        best_candidate = filtered_candidates[0]
                        # 解码HTML实体编码
                        decoded_title = self._decode_html_entities(best_candidate['title'])
                        logger.debug(f"从网页提取到title: '{decoded_title}' (方法: {best_candidate['method']})")
                        return decoded_title
                
                logger.debug(f"未能从网页中提取到有效的title: {live_url}")
                return None
                
        except httpx.TimeoutException as e:
            logger.warning(f"网页抓取超时: {e}")
            return None
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP请求错误 {e.response.status_code}: {e}")
            return None
        except httpx.RequestError as e:
            logger.warning(f"网络请求错误: {e}")
            return None
        except Exception as e:
            logger.warning(f"从网页抓取title时发生未知错误: {e}")
            return None

    def _search_title_in_dict(self, data: dict, path: str = "") -> list:
        """在字典中递归搜索title相关字段"""
        title_candidates = []
        
        # 常见的title字段名
        title_fields = [
            'title', 'roomTitle', 'room_title', 'liveTitle', 'live_title',
            'streamTitle', 'stream_title', 'broadcastTitle', 'broadcast_title',
            'name', 'roomName', 'room_name', 'streamName', 'stream_name',
            'subject', 'topic', 'description', 'desc'
        ]
        
        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key
            
            # 检查是否是title字段
            if key.lower() in [field.lower() for field in title_fields]:
                if isinstance(value, str) and value.strip():
                    title_candidates.append({
                        'title': value.strip(),
                        'path': current_path,
                        'priority': self._get_title_priority(key)
                    })
            
            # 递归搜索嵌套字典
            if isinstance(value, dict):
                title_candidates.extend(self._search_title_in_dict(value, current_path))
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        title_candidates.extend(self._search_title_in_dict(item, f"{current_path}[{i}]"))
        
        return title_candidates

    def _search_title_with_regex(self, text: str) -> list:
        """使用正则表达式搜索title"""
        title_candidates = []
        
        # 合并所有模式为一个正则表达式，提高性能
        combined_pattern = r'"(?:title|roomTitle|room_title|liveTitle|live_title|streamTitle|stream_title|name|roomName|subject|topic|description)"\s*:\s*"([^"]+)"'
        
        try:
            matches = re.findall(combined_pattern, text, re.IGNORECASE)
            for match in matches:
                if match.strip() and len(match.strip()) > 1:
                    title_candidates.append({
                        'title': match.strip(),
                        'path': "regex:combined_pattern",
                        'priority': 5  # 正则表达式优先级较低
                    })
        except re.error as e:
            logger.debug(f"正则表达式错误: {e}")
        
        return title_candidates

    def _get_title_priority(self, field_name: str) -> int:
        """获取字段的优先级，数字越小优先级越高"""
        priority_map = {
            'title': 1,
            'roomTitle': 1,
            'room_title': 1,
            'liveTitle': 2,
            'live_title': 2,
            'streamTitle': 2,
            'stream_title': 2,
            'broadcastTitle': 2,
            'broadcast_title': 2,
            'name': 3,
            'roomName': 3,
            'room_name': 3,
            'streamName': 3,
            'stream_name': 3,
            'subject': 4,
            'topic': 4,
            'description': 5,
            'desc': 5,
        }
        return priority_map.get(field_name.lower(), 6)

    def _select_best_title(self, title_candidates: list) -> Optional[str]:
        """从候选title中选择最佳的"""
        if not title_candidates:
            return None
        
        # 按优先级排序
        title_candidates.sort(key=lambda x: x['priority'])
        
        # 过滤掉明显不是title的内容
        filtered_candidates = []
        for candidate in title_candidates:
            title = candidate['title']
            # 统一的过滤条件
            if self._is_valid_title(title):
                filtered_candidates.append(candidate)
        
        if filtered_candidates:
            best_candidate = filtered_candidates[0]
            logger.debug(f"选择最佳title: '{best_candidate['title']}' (路径: {best_candidate['path']}, 优先级: {best_candidate['priority']})")
            return best_candidate['title']
        
        return None

    def _is_valid_title(self, title: str) -> bool:
        """检查title是否有效"""
        if not title or not isinstance(title, str):
            return False
        
        title = title.strip()
        
        # 过滤掉太短、纯数字、或明显不是标题的内容
        return (len(title) >= 2 and 
                not title.isdigit() and 
                title.lower() not in ['null', 'none', 'undefined', ''] and
                not re.match(r'^[0-9\-_]+$', title) and
                'sooplive' not in title.lower() and  # 过滤掉网站名称
                'soop' not in title.lower())

    def _decode_html_entities(self, text: str) -> str:
        """解码HTML实体编码"""
        if not text or not isinstance(text, str):
            return text
        
        try:
            # 使用Python内置的html.unescape解码HTML实体
            decoded_text = html.unescape(text)
            
            # 记录解码前后的变化（仅在调试模式下）
            if decoded_text != text:
                logger.debug(f"HTML实体解码: '{text}' -> '{decoded_text}'")
            
            return decoded_text
        except Exception as e:
            logger.warning(f"HTML实体解码失败: {e}, 返回原始文本")
            return text
