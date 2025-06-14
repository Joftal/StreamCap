import re
import threading
import time
from typing import Optional, Tuple, Dict, List, Any
from app.core.platform_handlers import get_platform_info
from app.models.recording_model import Recording
from app.utils.logger import logger


class RoomChecker:
    """直播间检测工具类"""
    
    # 缓存平台信息，避免重复调用get_platform_info
    _platform_cache: Dict[str, Tuple[str, str]] = {}
    _cache_lock = threading.Lock()
    _cache_hits = 0
    _cache_misses = 0
    
    # 缓存大小限制
    MAX_CACHE_SIZE = 1000
    
    # 短链接解析结果缓存
    _short_url_cache: Dict[str, Optional[str]] = {}
    _short_url_cache_lock = threading.Lock()
    _short_url_cache_hits = 0
    _short_url_cache_misses = 0
    
    # 短链接缓存大小限制
    MAX_SHORT_URL_CACHE_SIZE = 500
    
    # 短链接平台配置
    SHORT_URL_PLATFORMS = {
        "v.douyin.com": "douyin",
        "v.kuaishou.com": "kuaishou", 
        "xhslink.com": "xiaohongshu",
        "tb.cn": "taobao",
        "3.cn": "jd"
    }
    
    # 平台规则配置
    PLATFORM_RULES = {
        "douyin": {
            "patterns": [
                {"url": "live.douyin.com", "extract": "path_last", "exclude": ["live.douyin.com"]},
                {"url": "v.douyin.com", "extract": "short_url"}
            ]
        },
        "tiktok": {
            "patterns": [
                {"url": "tiktok.com", "extract": "custom", "custom_func": "extract_tiktok_room_id"}
            ]
        },
        "kuaishou": {
            "patterns": [
                {"url": "live.kuaishou.com/u/", "extract": "split", "split_by": "/u/", "exclude": []},
                {"url": "live.kuaishou.com", "extract": "path_last", "exclude": []},
                {"url": "v.kuaishou.com", "extract": "short_url"}
            ]
        },
        "huya": {
            "patterns": [
                {"url": "huya.com", "extract": "path_last", "exclude": []}
            ]
        },
        "douyu": {
            "patterns": [
                {"url": "douyu.com", "extract": "custom", "custom_func": "extract_douyu_room_id"}
            ]
        },
        "yy": {
            "patterns": [
                {"url": "live.yy.com", "extract": "path_last", "exclude": []},
                {"url": "yy.com", "extract": "path_second_last", "exclude": []}
            ]
        },
        "bilibili": {
            "patterns": [
                {"url": "bilibili.com/h5/", "extract": "split", "split_by": "/h5/", "exclude": ["live.bilibili.com"]},
                {"url": "bilibili.com", "extract": "path_last", "exclude": ["live.bilibili.com"]}
            ]
        },
        "xiaohongshu": {
            "patterns": [
                {"url": "xiaohongshu.com/user/profile/", "extract": "split", "split_by": "/user/profile/", "exclude": []},
                {"url": "xiaohongshu.com/explore/", "extract": "custom", "custom_func": "extract_xiaohongshu_explore_room_id"},
                {"url": "xiaohongshu.com", "extract": "path_last", "exclude": []},
                {"url": "xhslink.com", "extract": "short_url"}
            ]
        },
        "bigo": {
            "patterns": [
                {"url": "bigo.tv", "extract": "path_last", "exclude": ["cn", "live"]}
            ]
        },
        "blued": {
            "patterns": [
                {"url": "blued.cn", "extract": "param", "param_name": "id"}
            ]
        },
        "sooplive": {
            "patterns": [
                {"url": "sooplive.co.kr/", "extract": "custom", "custom_func": "extract_sooplive_room_id"},
                {"url": "sooplive.co.kr", "extract": "path_last", "exclude": []}
            ]
        },
        "netease": {
            "patterns": [
                {"url": "cc.163.com", "extract": "path_last", "exclude": []}
            ]
        },
        "qiandurebo": {
            "patterns": [
                {"url": "qiandurebo.com", "extract": "param", "param_name": "roomnumber"}
            ]
        },
        "pandalive": {
            "patterns": [
                {"url": "pandalive.co.kr/play/", "extract": "split", "split_by": "/play/", "exclude": []},
                {"url": "pandalive.co.kr", "extract": "path_last", "exclude": []}
            ]
        },
        "maoerfm": {
            "patterns": [
                {"url": "missevan.com", "extract": "path_last", "exclude": ["live", "cn"]}
            ]
        },
        "look": {
            "patterns": [
                {"url": "look.163.com", "extract": "param", "param_name": "id"}
            ]
        },
        "winktv": {
            "patterns": [
                {"url": "winktv.co.kr/play/", "extract": "split", "split_by": "/play/", "exclude": []},
                {"url": "winktv.co.kr", "extract": "path_last", "exclude": []}
            ]
        },
        "flextv": {
            "patterns": [
                {"url": "flextv.co.kr/channels/", "extract": "split", "split_by": "/channels/", "split_index": 0},
                {"url": "flextv.co.kr", "extract": "path_last", "exclude": []}
            ]
        },
        "popkontv": {
            "patterns": [
                {"url": "popkontv.com", "extract": "custom", "custom_func": "extract_popkontv_room_id"}
            ]
        },
        "twitcasting": {
            "patterns": [
                {"url": "twitcasting.tv/c:", "extract": "split", "split_by": "/c:", "exclude": []},
                {"url": "twitcasting.tv", "extract": "path_last", "exclude": []}
            ]
        },
        "baidu": {
            "patterns": [
                {"url": "baidu.com", "extract": "param", "param_name": "room_id"}
            ]
        },
        "weibo": {
            "patterns": [
                {"url": "weibo.com/l/wblive/p/show/", "extract": "custom", "custom_func": "extract_weibo_room_id"},
                {"url": "weibo.com/show/", "extract": "custom", "custom_func": "extract_weibo_room_id"},
                {"url": "weibo.com", "extract": "path_last", "exclude": []}
            ]
        },
        "kugou": {
            "patterns": [
                {"url": "kugou.com", "extract": "path_last", "exclude": []}
            ]
        },
        "twitch": {
            "patterns": [
                {"url": "twitch.tv", "extract": "path_last", "exclude": []}
            ]
        },
        "liveme": {
            "patterns": [
                {"url": "liveme.com/zh/v/", "extract": "custom", "custom_func": "extract_liveme_room_id"},
                {"url": "liveme.com/v/", "extract": "custom", "custom_func": "extract_liveme_room_id"},
                {"url": "liveme.com", "extract": "path_last", "exclude": []}
            ]
        },
        "huajiao": {
            "patterns": [
                {"url": "huajiao.com/l/", "extract": "split", "split_by": "/l/", "exclude": []},
                {"url": "huajiao.com", "extract": "path_last", "exclude": []}
            ]
        },
        "showroom": {
            "patterns": [
                {"url": "showroom-live.com", "extract": "param", "param_name": "room_id"}
            ]
        },
        "acfun": {
            "patterns": [
                {"url": "acfun.cn", "extract": "path_last", "exclude": ["live", "cn"]}
            ]
        },
        "inke": {
            "patterns": [
                {"url": "inke.cn", "extract": "custom", "custom_func": "extract_inke_room_id"}
            ]
        },
        "ybw1666": {
            "patterns": [
                {"url": "ybw1666.com", "extract": "path_last", "exclude": []}
            ]
        },
        "zhihu": {
            "patterns": [
                {"url": "zhihu.com/people/", "extract": "split", "split_by": "/people/", "exclude": []},
                {"url": "zhihu.com", "extract": "path_last", "exclude": []}
            ]
        },
        "chzzk": {
            "patterns": [
                {"url": "chzzk.naver.com/live/", "extract": "split", "split_by": "/live/", "exclude": []},
                {"url": "chzzk.naver.com", "extract": "path_last", "exclude": []}
            ]
        },
        "haixiutv": {
            "patterns": [
                {"url": "haixiutv.com", "extract": "path_last", "exclude": []}
            ]
        },
        "vvxqiu": {
            "patterns": [
                {"url": "vvxqiu.com", "extract": "param", "param_name": "roomId"}
            ]
        },
        "17live": {
            "patterns": [
                {"url": "17.live/live/", "extract": "split", "split_by": "/live/", "exclude": []},
                {"url": "17.live", "extract": "path_last", "exclude": []}
            ]
        },
        "langlive": {
            "patterns": [
                {"url": "lang.live/room/", "extract": "split", "split_by": "/room/", "exclude": []},
                {"url": "lang.live", "extract": "path_last", "exclude": []}
            ]
        },
        "tlclw": {
            "patterns": [
                {"url": "tlclw.com", "extract": "path_last", "exclude": []}
            ]
        },
        "weimipopo": {
            "patterns": [
                {"url": "weimipopo.com", "extract": "param", "param_name": "anchorUid"}
            ]
        },
        "6cn": {
            "patterns": [
                {"url": "6.cn", "extract": "path_last", "exclude": []}
            ]
        },
        "lehaitv": {
            "patterns": [
                {"url": "lehaitv.com", "extract": "path_last", "exclude": []}
            ]
        },
        "catshow168": {
            "patterns": [
                {"url": "catshow168.com", "extract": "param", "param_name": "anchorUid"}
            ]
        },
        "shopee": {
            "patterns": [
                {"url": "shp.ee", "extract": "param", "param_name": "uid"}
            ]
        },
        "youtube": {
            "patterns": [
                {"url": "youtube.com", "extract": "param", "param_name": "v"}
            ]
        },
        "taobao": {
            "patterns": [
                {"url": "tb.cn", "extract": "short_url"}
            ]
        },
        "jd": {
            "patterns": [
                {"url": "3.cn", "extract": "short_url"}
            ]
        },
        "faceit": {
            "patterns": [
                {"url": "faceit.com/players/", "extract": "custom", "custom_func": "extract_faceit_room_id"},
                {"url": "faceit.com", "extract": "path_last", "exclude": ["stream", "profile", "stats", "players"]}
            ]
        }
    }
    
    @staticmethod
    def _get_cached_platform_info(url: str) -> Tuple[Optional[str], Optional[str]]:
        if not url or not isinstance(url, str):
            return None, None
        with RoomChecker._cache_lock:
            if url in RoomChecker._platform_cache:
                RoomChecker._cache_hits += 1
                return RoomChecker._platform_cache[url]
            RoomChecker._cache_misses += 1
            if len(RoomChecker._platform_cache) >= RoomChecker.MAX_CACHE_SIZE:
                oldest_key = next(iter(RoomChecker._platform_cache))
                del RoomChecker._platform_cache[oldest_key]
            platform_info = get_platform_info(url)
            RoomChecker._platform_cache[url] = platform_info
            return platform_info
    
    @staticmethod
    def clear_cache():
        """清除平台信息缓存（线程安全）"""
        with RoomChecker._cache_lock:
            RoomChecker._platform_cache.clear()
            RoomChecker._cache_hits = 0
            RoomChecker._cache_misses = 0
            logger.info("平台信息缓存已清除")
        
        # 同时清除短链接缓存
        RoomChecker.clear_short_url_cache()
    
    @staticmethod
    def get_cache_stats() -> Dict[str, int]:
        """获取缓存统计信息"""
        with RoomChecker._cache_lock:
            platform_stats = {
                "cache_size": len(RoomChecker._platform_cache),
                "cache_hits": RoomChecker._cache_hits,
                "cache_misses": RoomChecker._cache_misses,
                "hit_rate": RoomChecker._cache_hits / (RoomChecker._cache_hits + RoomChecker._cache_misses) if (RoomChecker._cache_hits + RoomChecker._cache_misses) > 0 else 0
            }
        
        # 获取短链接缓存统计
        short_url_stats = RoomChecker.get_short_url_cache_stats()
        
        # 合并统计信息
        stats = platform_stats.copy()
        stats.update(short_url_stats)
        return stats
    
    @staticmethod
    def _get_cached_short_url_result(short_url: str) -> Optional[str]:
        """获取缓存的短链接解析结果（线程安全）"""
        with RoomChecker._short_url_cache_lock:
            if short_url in RoomChecker._short_url_cache:
                RoomChecker._short_url_cache_hits += 1
                return RoomChecker._short_url_cache[short_url]
            
            RoomChecker._short_url_cache_misses += 1
            return None
    
    @staticmethod
    def _set_cached_short_url_result(short_url: str, room_id: Optional[str]):
        """设置短链接解析结果缓存（线程安全）"""
        with RoomChecker._short_url_cache_lock:
            # 限制缓存大小
            if len(RoomChecker._short_url_cache) >= RoomChecker.MAX_SHORT_URL_CACHE_SIZE:
                # 清除最旧的缓存项
                oldest_key = next(iter(RoomChecker._short_url_cache))
                del RoomChecker._short_url_cache[oldest_key]
            
            RoomChecker._short_url_cache[short_url] = room_id
    
    @staticmethod
    def get_short_url_cache_stats() -> Dict[str, int]:
        """获取短链接缓存统计信息"""
        with RoomChecker._short_url_cache_lock:
            return {
                "short_url_cache_size": len(RoomChecker._short_url_cache),
                "short_url_cache_hits": RoomChecker._short_url_cache_hits,
                "short_url_cache_misses": RoomChecker._short_url_cache_misses,
                "short_url_hit_rate": RoomChecker._short_url_cache_hits / (RoomChecker._short_url_cache_hits + RoomChecker._short_url_cache_misses) if (RoomChecker._short_url_cache_hits + RoomChecker._short_url_cache_misses) > 0 else 0
            }
    
    @staticmethod
    def clear_short_url_cache():
        """清除短链接缓存（线程安全）"""
        with RoomChecker._short_url_cache_lock:
            RoomChecker._short_url_cache.clear()
            RoomChecker._short_url_cache_hits = 0
            RoomChecker._short_url_cache_misses = 0
            logger.info("短链接缓存已清除")
    
    @staticmethod
    def _extract_room_id_from_path(url: str, exclude_domains: List[str] = None) -> Optional[str]:
        """通用的路径提取房间ID方法"""
        try:
            room_id = url.split("/")[-1].split("?")[0]
            if exclude_domains and room_id in exclude_domains:
                return None
            # 检查是否是路径名而不是房间ID
            if room_id in ["profile", "play", "channels", "live", "room", "people", "players", "show", "u", "v", "l"]:
                return None
            return room_id if room_id else None
        except (IndexError, AttributeError):
            return None
    
    @staticmethod
    def _extract_room_id_from_param(url: str, param_name: str) -> Optional[str]:
        """从URL参数中提取房间ID"""
        try:
            if f"{param_name}=" in url:
                return url.split(f"{param_name}=")[1].split("&")[0]
            return None
        except (IndexError, AttributeError):
            return None
    
    @staticmethod
    def _extract_room_id_from_split(url: str, split_by: str, exclude: List[str] = None, split_index: int = -1) -> Optional[str]:
        """从分割后的URL中提取房间ID"""
        try:
            if split_by in url:
                parts = url.split(split_by)[1].split("?")[0]
                if split_index == -1:
                    room_id = parts.split("/")[-1] if "/" in parts else parts
                else:
                    room_id = parts.split("/")[split_index]
                
                # 检查是否是路径名而不是房间ID
                if room_id in ["profile", "play", "channels", "live", "room", "people", "players", "show", "u", "v", "l"]:
                    return None
                
                if exclude and room_id in exclude:
                    return None
                return room_id if room_id else None
            return None
        except (IndexError, AttributeError):
            return None
    
    @staticmethod
    def _extract_tiktok_room_id(url: str) -> Optional[str]:
        """提取TikTok房间ID"""
        try:
            if "/@" in url and "/live" in url:
                return url.split("/@")[1].split("/live")[0]
            return None
        except (IndexError, AttributeError):
            return None
    
    @staticmethod
    def _extract_douyu_room_id(url: str) -> Optional[str]:
        """提取斗鱼房间ID"""
        try:
            if "rid=" in url:
                return url.split("rid=")[1].split("&")[0]
            elif "room" in url:
                return url.split("room/")[1].split("?")[0]
            return url.split("/")[-1].split("?")[0]
        except (IndexError, AttributeError):
            return None
    
    @staticmethod
    def _extract_popkontv_room_id(url: str) -> Optional[str]:
        """提取PopkonTV房间ID"""
        try:
            if "castId=" in url:
                return url.split("castId=")[1].split("&")[0]
            elif "mcid=" in url:
                return url.split("mcid=")[1].split("&")[0]
            return None
        except (IndexError, AttributeError):
            return None
    
    @staticmethod
    def _extract_weibo_room_id(url: str) -> Optional[str]:
        """提取微博房间ID"""
        try:
            if "/show/" in url:
                parts = url.split("/show/")[1].split("?")[0]
                if ":" in parts:
                    # 提取冒号后面的部分作为房间ID
                    room_id = parts.split(":")[1]
                    return room_id if room_id else None
                return parts
            return None
        except (IndexError, AttributeError):
            return None
    
    @staticmethod
    def _extract_inke_room_id(url: str) -> Optional[str]:
        """提取映客房间ID"""
        try:
            # 使用正则表达式提取id参数
            id_match = re.search(r'[?&]id=(\d+)', url)
            if id_match:
                return id_match.group(1)
            # 如果没有id参数，则使用uid参数
            uid_match = re.search(r'[?&]uid=(\d+)', url)
            if uid_match:
                return uid_match.group(1)
            return None
        except (IndexError, AttributeError):
            return None
    
    @staticmethod
    def _extract_faceit_room_id(url: str) -> Optional[str]:
        """提取Faceit房间ID"""
        try:
            if "/players/" in url:
                # 提取玩家名，去掉可能的后续路径
                player_part = url.split("/players/")[1].split("?")[0]
                player_name = player_part.split("/")[0]
                # 确保不是路径名且不为空
                if player_name and player_name not in ["stream", "profile", "stats", "players"]:
                    return player_name
            return None
        except (IndexError, AttributeError):
            return None
    
    @staticmethod
    def _extract_xiaohongshu_explore_room_id(url: str) -> Optional[str]:
        """提取小红书探索页面的房间ID"""
        try:
            # 探索页面不是直播间，应该返回None
            return None
        except (IndexError, AttributeError):
            return None
    
    @staticmethod
    def _extract_liveme_room_id(url: str) -> Optional[str]:
        """提取LiveMe房间ID"""
        try:
            if "/v/" in url:
                # 提取/v/后面的部分
                parts = url.split("/v/")[1].split("?")[0]
                # 取第一个路径段作为房间ID
                room_id = parts.split("/")[0]
                return room_id if room_id else None
            return None
        except (IndexError, AttributeError):
            return None
    
    @staticmethod
    def _extract_sooplive_room_id(url: str) -> Optional[str]:
        """提取SOOP直播间房间ID（主播用户名）"""
        try:
            # SOOP URL格式: https://play.sooplive.co.kr/主播用户名/直播间ID
            # 或者: https://play.sooplive.co.kr/主播用户名
            if "sooplive.co.kr/" in url:
                parts = url.split("sooplive.co.kr/")[1].split("?")[0]
                # 取第一个路径段作为主播用户名（房间ID）
                room_id = parts.split("/")[0]
                return room_id if room_id else None
            return None
        except (IndexError, AttributeError):
            return None
    
    @staticmethod
    def _extract_by_platform_rules(url: str, rules: Dict[str, Any]) -> Optional[str]:
        """根据平台规则提取房间ID"""
        try:
            for pattern in rules["patterns"]:
                if pattern["url"] in url:
                    extract_type = pattern["extract"]
                    
                    if extract_type == "path_last":
                        exclude = pattern.get("exclude", [])
                        return RoomChecker._extract_room_id_from_path(url, exclude)
                    
                    elif extract_type == "path_second_last":
                        try:
                            room_id = url.split("/")[-2].split("?")[0]
                            return room_id if room_id else None
                        except (IndexError, AttributeError):
                            return None
                    
                    elif extract_type == "param":
                        param_name = pattern["param_name"]
                        return RoomChecker._extract_room_id_from_param(url, param_name)
                    
                    elif extract_type == "split":
                        split_by = pattern["split_by"]
                        exclude = pattern.get("exclude", [])
                        split_index = pattern.get("split_index", -1)
                        return RoomChecker._extract_room_id_from_split(url, split_by, exclude, split_index)
                    
                    elif extract_type == "custom":
                        custom_func = pattern["custom_func"]
                        if hasattr(RoomChecker, f"_{custom_func}"):
                            return getattr(RoomChecker, f"_{custom_func}")(url)
                    
                    elif extract_type == "short_url":
                        return None  # 短链接需要特殊处理
            
            return None
        except Exception as e:
            logger.warning(f"根据平台规则提取房间ID失败: {url}, 错误: {e}")
            return None
    
    @staticmethod
    def extract_room_id(url: str) -> Optional[str]:
        if not url or not isinstance(url, str):
            return None
        try:
            url = url.rstrip('/')
            if url.endswith(('.com', '.cn', '.tv', '.kr', '.live', '.co.kr')):
                return None
            for platform, rules in RoomChecker.PLATFORM_RULES.items():
                result = RoomChecker._extract_by_platform_rules(url, rules)
                if result is not None:
                    return result
            return None
        except (IndexError, AttributeError, ValueError) as e:
            logger.warning(f"URL格式错误，无法提取房间ID: {url}, 错误: {e}")
            return None
        except Exception as e:
            logger.error(f"提取直播间ID时发生未知错误: {url}, 错误: {e}")
            return None

    @staticmethod
    async def check_duplicate_room(
        app,
        live_url: str,
        streamer_name: Optional[str] = None,
        existing_recordings: list[Recording] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        检查直播间是否已存在（按优先级顺序检查）
        
        去重检查优先级顺序：
        1. 最高优先级：URL完全相同
        2. 次优先级：同平台主播名称相同（主播ID）
        3. 最低优先级：同平台房间ID相同
        
        Args:
            app: 应用实例
            live_url: 直播间URL
            streamer_name: 主播名称（可选）
            existing_recordings: 现有的录制列表（可选）
            
        Returns:
            Tuple[bool, Optional[str]]: (是否重复, 重复原因)
        """
        start_time = time.time()
        logger.info(f"开始检查直播间是否重复: {live_url}")
        
        try:
            # 早期退出：空URL检查
            if not live_url:
                logger.warning("URL为空，无法进行去重检查")
                return False, None
            
            # 处理录制列表参数
            if existing_recordings is None:
                # 只有当参数为None时才使用默认录制列表
                existing_recordings = app.record_manager.recordings
                logger.info(f"使用默认录制列表，当前共有 {len(existing_recordings)} 个录制项")
            
            # 早期退出：空录制列表检查
            if not existing_recordings:
                logger.info("录制列表为空，无需去重检查")
                return False, None

            # 1. 获取直播间的真实信息（只获取一次）
            platform, platform_key = RoomChecker._get_cached_platform_info(live_url)
            if not platform:
                logger.warning(f"无法识别平台: {live_url}")
                return False, None

            logger.info(f"识别到平台: {platform} ({platform_key})")

            # 2. 按优先级顺序检查重复
            # 2.1 最高优先级：检查URL是否完全相同（可以早期退出）
            for recording in existing_recordings:
                if recording.url == live_url:
                    logger.info("发现重复: URL完全相同")
                    return True, "URL完全相同"
            
            # 2.2 次优先级：检查主播ID（主播名称）
            real_anchor_name = await RoomChecker._get_real_anchor_name(
                app, live_url, platform, platform_key, streamer_name
            )
            
            # 只有在有主播名称时才进行主播名称检查
            if real_anchor_name:
                duplicate_found = RoomChecker._check_streamer_name_duplicate(
                    real_anchor_name, platform_key, existing_recordings
                )
                if duplicate_found:
                    return True, "同平台同名主播"
            
            # 2.3 最低优先级：检查房间号
            room_id = RoomChecker.extract_room_id(live_url)
            
            # 如果是短链接且没有提取到房间ID，尝试从缓存或网络获取
            if not room_id and any(short_url in live_url for short_url in RoomChecker.SHORT_URL_PLATFORMS.keys()):
                room_id = await RoomChecker._resolve_short_url_room_id(app, live_url, platform, platform_key)
            
            # 检查房间ID（最低优先级，仅限同平台）
            if room_id:
                duplicate_found = RoomChecker._check_room_id_duplicate(
                    room_id, platform_key, existing_recordings
                )
                if duplicate_found:
                    return True, "同平台房间ID相同"

            logger.info("未发现重复直播间")
            return False, None

        except Exception as e:
            logger.error(f"检查重复直播间失败: {e}")
            return False, None
        finally:
            duration = time.time() - start_time
            logger.info(f"去重检查耗时: {duration:.3f}秒")

    @staticmethod
    async def _resolve_short_url_room_id(
        app, live_url: str, platform: str, platform_key: str
    ) -> Optional[str]:
        """解析短链接获取房间ID"""
        # 首先检查缓存
        cached_room_id = RoomChecker._get_cached_short_url_result(live_url)
        if cached_room_id is not None:
            logger.info(f"从缓存获取到短链接房间ID: {cached_room_id}")
            return cached_room_id
        
        # 缓存中没有，尝试网络解析
        try:
            from app.core.stream_manager import LiveStreamRecorder
            recording_info_dict = RoomChecker._create_recording_info_dict(
                app, platform, platform_key, live_url
            )
            recorder = LiveStreamRecorder(app, None, recording_info_dict)
            room_id = await recorder.get_room_id_from_short_url(live_url)
            if room_id:
                logger.info(f"从短链接获取到真实房间ID: {room_id}")
                # 缓存结果
                RoomChecker._set_cached_short_url_result(live_url, room_id)
                return room_id
        except Exception as e:
            logger.error(f"获取短链接真实ID失败: {e}")
            # 缓存失败结果，避免重复尝试
            RoomChecker._set_cached_short_url_result(live_url, None)
        
        return None

    @staticmethod
    async def _get_real_anchor_name(
        app, live_url: str, platform: str, platform_key: str, streamer_name: Optional[str]
    ) -> Optional[str]:
        """获取真实主播名称"""
        if streamer_name:
            # 如果提供了主播名称，直接使用
            return streamer_name
        
        # 尝试获取真实主播名称
        try:
            from app.core.stream_manager import LiveStreamRecorder
            recording_info_dict = RoomChecker._create_recording_info_dict(
                app, platform, platform_key, live_url
            )
            recorder = LiveStreamRecorder(app, None, recording_info_dict)
            stream_info = await recorder.fetch_stream()
            
            if stream_info and stream_info.anchor_name:
                real_anchor_name = stream_info.anchor_name
                logger.info(f"获取到主播名称: {real_anchor_name}")
                return real_anchor_name
            else:
                logger.warning(f"无法获取主播名称: {live_url}")
                return None
        except Exception as e:
            logger.error(f"获取直播间信息失败: {e}")
            return None

    @staticmethod
    def _check_room_id_duplicate(
        room_id: str, platform_key: str, existing_recordings: list[Recording]
    ) -> bool:
        """检查房间ID是否重复（最低优先级检查）"""
        for recording in existing_recordings:
            # 获取现有录制项的平台信息
            existing_platform, existing_platform_key = RoomChecker._get_cached_platform_info(recording.url)
            if not existing_platform:
                logger.warning(f"无法识别现有录制项的平台: {recording.url}")
                continue
            
            # 只检查同平台的房间ID
            if platform_key == existing_platform_key:
                existing_room_id = RoomChecker.extract_room_id(recording.url)
                if existing_room_id and existing_room_id == room_id:
                    logger.info(f"现有录制项房间ID: {existing_room_id}")
                    logger.info(f"发现重复: 同平台房间ID相同 ({room_id})")
                    return True
        
        return False

    @staticmethod
    def _check_streamer_name_duplicate(
        real_anchor_name: str, platform_key: str, existing_recordings: list[Recording]
    ) -> bool:
        """检查主播名称是否重复（次优先级检查）"""
        for recording in existing_recordings:
            # 获取现有录制项的平台信息
            existing_platform, existing_platform_key = RoomChecker._get_cached_platform_info(recording.url)
            if not existing_platform:
                logger.warning(f"无法识别现有录制项的平台: {recording.url}")
                continue
            
            # 只检查同平台的主播名称
            if platform_key == existing_platform_key and recording.streamer_name == real_anchor_name:
                logger.info(f"主播名称匹配: {real_anchor_name}")
                logger.info(f"平台匹配: {platform_key}")
                logger.info(f"发现重复: 同平台同名主播 ({real_anchor_name})")
                return True
        
        return False

    @staticmethod
    def _create_recording_info_dict(app, platform: str, platform_key: str, live_url: str) -> dict:
        """创建录制信息字典（避免重复代码）"""
        return {
            "platform": platform,
            "platform_key": platform_key,
            "live_url": live_url,
            "output_dir": app.record_manager.settings.get_video_save_path(),
            "segment_record": False,
            "segment_time": "1800",
            "save_format": "ts",
            "quality": "OD",
        } 