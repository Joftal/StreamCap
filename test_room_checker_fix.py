#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import asyncio
import time
import unittest
from unittest.mock import Mock, patch, AsyncMock
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.utils.room_checker import RoomChecker
from app.models.recording_model import Recording


class TestRoomChecker(unittest.TestCase):
    """房间去重逻辑测试类 - 支持所有平台"""
    
    def setUp(self):
        """测试前准备"""
        # 清除缓存
        RoomChecker.clear_cache()
        
        # 创建模拟的录制列表
        self.existing_recordings = [
            Recording(
                rec_id="test1",
                url="https://live.douyin.com/123456",
                streamer_name="测试主播1",
                quality="OD",
                segment_record=False,
                monitor_status=True,
                segment_time="1800",
                scheduled_recording=False,
                scheduled_start_time=None,
                monitor_hours=None,
                recording_dir="test_output",
                enabled_message_push=True
            ),
            Recording(
                rec_id="test2",
                url="https://live.bilibili.com/789",
                streamer_name="测试主播2",
                quality="OD",
                segment_record=False,
                monitor_status=True,
                segment_time="1800",
                scheduled_recording=False,
                scheduled_start_time=None,
                monitor_hours=None,
                recording_dir="test_output",
                enabled_message_push=True
            ),
            Recording(
                rec_id="test3",
                url="https://live.kuaishou.com/u/user123",
                streamer_name="快手主播",
                quality="OD",
                segment_record=False,
                monitor_status=True,
                segment_time="1800",
                scheduled_recording=False,
                scheduled_start_time=None,
                monitor_hours=None,
                recording_dir="test_output",
                enabled_message_push=True
            )
        ]
        
        # 创建模拟的app对象
        self.mock_app = self.create_mock_app()
    
    def create_mock_app(self):
        """创建模拟的app对象"""
        existing_recordings = self.existing_recordings  # 获取外部类的属性
        
        class MockApp:
            def __init__(self):
                self.record_manager = MockRecordManager()
        
        class MockRecordManager:
            def __init__(self):
                self.recordings = existing_recordings  # 使用闭包中的变量
                self.settings = MockSettings()
        
        class MockSettings:
            def get_video_save_path(self):
                return "test_output"
        
        return MockApp()
    
    def test_all_platforms_room_id_extraction(self):
        """测试所有平台的房间ID提取功能"""
        print("\n=== 测试所有平台的房间ID提取功能 ===")
        
        # 完整的平台测试用例
        test_cases = [
            # 抖音
            ("https://live.douyin.com/123456", "123456"),
            ("https://live.douyin.com/123456/", "123456"),
            ("https://live.douyin.com/123456?param=value", "123456"),
            ("https://v.douyin.com/abc123", None),  # 短链接
            
            # TikTok
            ("https://www.tiktok.com/@pearlgaga88/live", "pearlgaga88"),
            ("https://www.tiktok.com/@user123/live?param=value", "user123"),
            
            # 快手
            ("https://live.kuaishou.com/u/user123", "user123"),
            ("https://live.kuaishou.com/room456", "room456"),
            ("https://v.kuaishou.com/def456", None),  # 短链接
            
            # 虎牙
            ("https://www.huya.com/52333", "52333"),
            ("https://www.huya.com/123456?param=value", "123456"),
            
            # 斗鱼
            ("https://www.douyu.com/3637778", "3637778"),
            ("https://www.douyu.com/topic/wzDBLS6?rid=4921614", "4921614"),
            ("https://www.douyu.com/room/123456", "123456"),
            
            # YY
            ("https://www.yy.com/22490906/22490906", "22490906"),
            ("https://live.yy.com/123456", "123456"),
            
            # B站
            ("https://live.bilibili.com/320", "320"),
            ("https://live.bilibili.com/h5/123", "123"),
            ("https://live.bilibili.com/789/", "789"),
            
            # 小红书
            ("https://www.xiaohongshu.com/user/profile/user456", "user456"),
            ("https://www.xiaohongshu.com/live/room789", "room789"),
            ("https://www.xiaohongshu.com/explore/123", None),  # 探索页面
            ("http://xhslink.com/xyz789", None),  # 短链接
            
            # Bigo
            ("https://www.bigo.tv/cn/716418802", "716418802"),
            ("https://www.bigo.tv/123456", "123456"),
            
            # Blued
            ("https://app.blued.cn/live?id=Mp6G2R", "Mp6G2R"),
            
            # SOOP
            ("https://play.sooplive.co.kr/sw7love", "sw7love"),
            
            # 网易CC
            ("https://cc.163.com/583946984", "583946984"),
            
            # 千度热播
            ("https://qiandurebo.com/web/video.php?roomnumber=33333", "33333"),
            
            # PandaTV
            ("https://www.pandalive.co.kr/live/play/bara0109", "bara0109"),
            ("https://www.pandalive.co.kr/123456", "123456"),
            
            # 猫耳FM
            ("https://fm.missevan.com/live/868895007", "868895007"),
            
            # Look直播
            ("https://look.163.com/live?id=65108820", "65108820"),
            
            # WinkTV
            ("https://www.winktv.co.kr/live/play/anjer1004", "anjer1004"),
            ("https://www.winktv.co.kr/123456", "123456"),
            
            # TtingLive
            ("https://www.ttinglive.com/channels/52406/live", "52406"),
            ("https://www.ttinglive.com/123456", "123456"),
            
            # PopkonTV
            ("https://www.popkontv.com/live/view?castId=wjfal007", "wjfal007"),
            ("https://www.popkontv.com/channel/notices?mcid=wjfal007", "wjfal007"),
            
            # TwitCasting
            ("https://twitcasting.tv/c:uonq", "uonq"),
            ("https://twitcasting.tv/123456", "123456"),
            
            # 百度直播
            ("https://live.baidu.com/m/media/pclive/pchome/live.html?room_id=9175031377", "9175031377"),
            
            # 微博直播
            ("https://weibo.com/l/wblive/p/show/1022:2321325026370190442592", "2321325026370190442592"),
            ("https://weibo.com/show/123456", "123456"),
            
            # 酷狗直播
            ("https://fanxing2.kugou.com/50428671", "50428671"),
            
            # Twitch
            ("https://www.twitch.tv/gamerbee", "gamerbee"),
            
            # LiveMe
            ("https://www.liveme.com/zh/v/17141543493018047815", "17141543493018047815"),
            ("https://www.liveme.com/zh/v/17141543493018047815/index.html", "17141543493018047815"),
            
            # 花椒直播
            ("https://www.huajiao.com/l/345096174", "345096174"),
            ("https://www.huajiao.com/123456", "123456"),
            
            # ShowRoom
            ("https://www.showroom-live.com/room/profile?room_id=480206", "480206"),
            
            # Acfun
            ("https://live.acfun.cn/live/179922", "179922"),
            
            # 映客直播
            ("https://www.inke.cn/liveroom/index.html?uid=22954469&id=1720860391070904", "1720860391070904"),
            
            # 音播直播
            ("https://live.ybw1666.com/800002949", "800002949"),
            
            # 知乎直播
            ("https://www.zhihu.com/people/ac3a467005c5d20381a82230101308e9", "ac3a467005c5d20381a82230101308e9"),
            
            # CHZZK
            ("https://chzzk.naver.com/live/458f6ec20b034f49e0fc6d03921646d2", "458f6ec20b034f49e0fc6d03921646d2"),
            
            # 嗨秀直播
            ("https://www.haixiutv.com/123456", "123456"),
            
            # VV秀
            ("https://www.vvxqiu.com/live?roomId=123456", "123456"),
            
            # 17Live
            ("https://17.live/live/123456", "123456"),
            ("https://17.live/123456", "123456"),
            
            # LangLive
            ("https://lang.live/room/123456", "123456"),
            ("https://lang.live/123456", "123456"),
            
            # TLC直播
            ("https://www.tlclw.com/123456", "123456"),
            
            # 微米直播
            ("https://www.weimipopo.com/live?anchorUid=123456", "123456"),
            
            # 6间房
            ("https://www.6.cn/123456", "123456"),
            
            # 乐嗨直播
            ("https://www.lehaitv.com/123456", "123456"),
            
            # 猫秀168
            ("https://www.catshow168.com/live?anchorUid=123456", "123456"),
            
            # Shopee
            ("https://www.shp.ee/live?uid=123456", "123456"),
            
            # YouTube
            ("https://www.youtube.com/watch?v=123456", "123456"),
            
            # 淘宝
            ("https://tb.cn/abc123", None),  # 短链接
            
            # 京东
            ("https://3.cn/def456", None),  # 短链接
            
            # Faceit
            ("https://faceit.com/players/user123/stream", "user123"),
            ("https://faceit.com/players/user123/stream?param=value", "user123"),
            
            # 无效URL
            ("https://example.com", None),
            ("", None),
            ("not_a_url", None),
        ]
        
        success_count = 0
        total_count = len(test_cases)
        failed_cases = []
        
        for url, expected in test_cases:
            result = RoomChecker.extract_room_id(url)
            is_success = result == expected
            if is_success:
                success_count += 1
                print(f"✅ {url} -> {result}")
            else:
                failed_cases.append((url, expected, result))
                print(f"❌ {url} -> {result} (期望: {expected})")
        
        print(f"\n房间ID提取测试结果: {success_count}/{total_count} 通过")
        print(f"通过率: {(success_count/total_count)*100:.2f}%")
        
        if failed_cases:
            print(f"\n❌ 失败的测试用例 ({len(failed_cases)} 个):")
            for url, expected, actual in failed_cases:
                print(f"  {url} -> {actual} (期望: {expected})")
        
        self.assertGreaterEqual(success_count / total_count, 0.85, "房间ID提取测试通过率应大于85%")
    
    def test_platform_coverage(self):
        """测试平台覆盖率"""
        print("\n=== 测试平台覆盖率 ===")
        
        # 获取所有支持的平台
        supported_platforms = set(RoomChecker.PLATFORM_RULES.keys())
        print(f"支持的平台数量: {len(supported_platforms)}")
        print(f"支持的平台: {', '.join(sorted(supported_platforms))}")
        
        # 测试每个平台至少有一个URL能正确识别
        platform_test_urls = {
            "douyin": "https://live.douyin.com/123456",
            "tiktok": "https://www.tiktok.com/@user123/live",
            "kuaishou": "https://live.kuaishou.com/u/user123",
            "huya": "https://www.huya.com/123456",
            "douyu": "https://www.douyu.com/123456",
            "yy": "https://www.yy.com/123456/123456",
            "bilibili": "https://live.bilibili.com/123456",
            "xiaohongshu": "https://www.xiaohongshu.com/user/profile/user123",
            "bigo": "https://www.bigo.tv/123456",
            "blued": "https://app.blued.cn/live?id=123456",
            "sooplive": "https://play.sooplive.co.kr/123456",
            "netease": "https://cc.163.com/123456",
            "qiandurebo": "https://qiandurebo.com/web/video.php?roomnumber=123456",
            "pandalive": "https://www.pandalive.co.kr/123456",
            "maoerfm": "https://fm.missevan.com/live/123456",
            "look": "https://look.163.com/live?id=123456",
            "winktv": "https://www.winktv.co.kr/123456",
            "ttinglive": "https://www.ttinglive.com/123456",
            "popkontv": "https://www.popkontv.com/live/view?castId=123456",
            "twitcasting": "https://twitcasting.tv/123456",
            "baidu": "https://live.baidu.com/m/media/pclive/pchome/live.html?room_id=123456",
            "weibo": "https://weibo.com/show/123456",
            "kugou": "https://fanxing2.kugou.com/123456",
            "twitch": "https://www.twitch.tv/123456",
            "liveme": "https://www.liveme.com/zh/v/123456",
            "huajiao": "https://www.huajiao.com/123456",
            "showroom": "https://www.showroom-live.com/room/profile?room_id=123456",
            "acfun": "https://live.acfun.cn/live/123456",
            "inke": "https://www.inke.cn/liveroom/index.html?uid=123456&id=123456",
            "ybw1666": "https://live.ybw1666.com/123456",
            "zhihu": "https://www.zhihu.com/people/123456",
            "chzzk": "https://chzzk.naver.com/123456",
            "haixiutv": "https://www.haixiutv.com/123456",
            "vvxqiu": "https://www.vvxqiu.com/live?roomId=123456",
            "17live": "https://17.live/123456",
            "langlive": "https://lang.live/123456",
            "tlclw": "https://www.tlclw.com/123456",
            "weimipopo": "https://www.weimipopo.com/live?anchorUid=123456",
            "6cn": "https://www.6.cn/123456",
            "lehaitv": "https://www.lehaitv.com/123456",
            "catshow168": "https://www.catshow168.com/live?anchorUid=123456",
            "shopee": "https://www.shp.ee/live?uid=123456",
            "youtube": "https://www.youtube.com/watch?v=123456",
            "taobao": "https://tb.cn/abc123",  # 短链接格式
            "jd": "https://3.cn/def456",  # 短链接格式
            "faceit": "https://faceit.com/players/user123/stream",  # 去掉www和zh前缀
        }
        
        # 短链接平台列表（这些平台在房间ID提取阶段返回None是正常的）
        short_url_platforms = {"taobao", "jd"}
        
        covered_platforms = set()
        for platform, url in platform_test_urls.items():
            if platform in supported_platforms:
                room_id = RoomChecker.extract_room_id(url)
                
                # 对于短链接平台，返回None是正常行为
                if platform in short_url_platforms:
                    if room_id is None:
                        covered_platforms.add(platform)
                        print(f"✅ {platform}: {url} -> None (短链接平台，正常行为)")
                    else:
                        print(f"❌ {platform}: {url} -> {room_id} (短链接平台，应该返回None)")
                else:
                    # 对于普通平台，应该能提取到房间ID
                    if room_id is not None:
                        covered_platforms.add(platform)
                        print(f"✅ {platform}: {url} -> {room_id}")
                    else:
                        print(f"❌ {platform}: {url} -> None")
        
        coverage_rate = len(covered_platforms) / len(supported_platforms) * 100
        print(f"\n平台覆盖率: {len(covered_platforms)}/{len(supported_platforms)} ({coverage_rate:.2f}%)")
        
        uncovered_platforms = supported_platforms - covered_platforms
        if uncovered_platforms:
            print(f"未覆盖的平台: {', '.join(sorted(uncovered_platforms))}")
        
        self.assertGreaterEqual(coverage_rate, 95, "平台覆盖率应大于95%")
    
    def test_cache_mechanism(self):
        """测试缓存机制"""
        print("\n=== 测试缓存机制 ===")
        
        # 测试平台信息缓存
        url = "https://live.douyin.com/123456"
        
        # 第一次调用
        start_time = time.time()
        platform1, key1 = RoomChecker._get_cached_platform_info(url)
        first_call_time = time.time() - start_time
        
        # 第二次调用相同URL
        start_time = time.time()
        platform2, key2 = RoomChecker._get_cached_platform_info(url)
        second_call_time = time.time() - start_time
        
        # 检查缓存是否工作
        self.assertEqual(platform1, platform2, "缓存应该返回相同的结果")
        self.assertEqual(key1, key2, "缓存应该返回相同的平台键")
        self.assertLess(second_call_time, first_call_time, "缓存调用应该更快")
        
        # 获取缓存统计
        stats = RoomChecker.get_cache_stats()
        print(f"平台缓存统计: {stats}")
        
        # 测试短链接缓存
        short_url = "https://v.douyin.com/abc123"
        RoomChecker._set_cached_short_url_result(short_url, "123456")
        cached_result = RoomChecker._get_cached_short_url_result(short_url)
        
        self.assertEqual(cached_result, "123456", "短链接缓存应该正确存储和获取")
        print(f"短链接缓存测试: {cached_result}")
        
        # 测试缓存大小限制
        for i in range(1100):  # 超过MAX_CACHE_SIZE
            RoomChecker._get_cached_platform_info(f"https://test{i}.com")
        
        stats_after = RoomChecker.get_cache_stats()
        self.assertLessEqual(stats_after["cache_size"], RoomChecker.MAX_CACHE_SIZE, "缓存大小应该被限制")
        print(f"缓存大小限制测试: {stats_after['cache_size']} <= {RoomChecker.MAX_CACHE_SIZE}")
        
        print("✅ 缓存机制测试完成")
    
    @patch('app.core.stream_manager.LiveStreamRecorder')
    def test_duplicate_check_basic(self, mock_recorder_class):
        """测试基本去重检查功能"""
        print("\n=== 测试基本去重检查功能 ===")
        
        # 模拟录制器
        mock_recorder = Mock()
        mock_recorder_class.return_value = mock_recorder
        
        test_cases = [
            {
                "url": "https://live.douyin.com/123456",
                "expected_duplicate": True,
                "expected_reason": "URL完全相同"
            },
            {
                "url": "https://live.douyin.com/123456?param=value",
                "expected_duplicate": True,
                "expected_reason": "同平台房间ID相同"
            },
            {
                "url": "https://live.douyin.com/789012",
                "expected_duplicate": True,
                "expected_reason": "同平台同名主播"
            },
            {
                "url": "https://live.bilibili.com/123456",
                "expected_duplicate": False,
                "expected_reason": None
            }
        ]
        
        def run_async_test_in_thread():
            import threading
            
            def worker():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                async def async_test():
                    for case in test_cases:
                        url = case["url"]
                        expected_duplicate = case["expected_duplicate"]
                        expected_reason = case["expected_reason"]
                        
                        # 模拟获取主播信息
                        mock_stream_info = Mock()
                        mock_stream_info.anchor_name = "测试主播1"
                        mock_recorder.fetch_stream = AsyncMock(return_value=mock_stream_info)
                        mock_recorder.get_room_id_from_short_url = AsyncMock(return_value=None)
                        
                        is_duplicate, reason = await RoomChecker.check_duplicate_room(
                            self.mock_app, url
                        )
                        
                        if is_duplicate == expected_duplicate:
                            print(f"✅ {url} -> 重复: {is_duplicate}, 原因: {reason}")
                        else:
                            print(f"❌ {url} -> 重复: {is_duplicate}, 原因: {reason} (期望: {expected_duplicate}, {expected_reason})")
                        
                        self.assertEqual(is_duplicate, expected_duplicate, f"去重检查结果不匹配: {url}")
                        if expected_reason:
                            self.assertEqual(reason, expected_reason, f"去重原因不匹配: {url}")
                
                try:
                    loop.run_until_complete(async_test())
                finally:
                    loop.close()
            
            thread = threading.Thread(target=worker)
            thread.start()
            thread.join()
        
        run_async_test_in_thread()
        print("✅ 基本去重检查功能测试完成")
    
    @patch('app.core.stream_manager.LiveStreamRecorder')
    def test_short_url_handling(self, mock_recorder_class):
        """测试短链接处理功能"""
        print("\n=== 测试短链接处理功能 ===")
        
        # 模拟录制器
        mock_recorder = Mock()
        mock_recorder_class.return_value = mock_recorder
        
        def run_async_test_in_thread():
            import threading
            
            def worker():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                async def async_test():
                    # 第一次调用（应该进行网络请求）
                    mock_recorder.get_room_id_from_short_url = AsyncMock(return_value="123456")
                    mock_stream_info = Mock()
                    mock_stream_info.anchor_name = "测试主播"
                    mock_recorder.fetch_stream = AsyncMock(return_value=mock_stream_info)
                    
                    is_duplicate, reason = await RoomChecker.check_duplicate_room(
                        self.mock_app, "https://v.douyin.com/abc123"
                    )
                    
                    print(f"短链接测试结果: 重复: {is_duplicate}, 原因: {reason}")
                    
                    # 第二次调用相同短链接（应该使用缓存）
                    is_duplicate2, reason2 = await RoomChecker.check_duplicate_room(
                        self.mock_app, "https://v.douyin.com/abc123"
                    )
                    
                    print(f"短链接缓存测试结果: 重复: {is_duplicate2}, 原因: {reason2}")
                    
                    # 验证缓存是否工作
                    cached_result = RoomChecker._get_cached_short_url_result("https://v.douyin.com/abc123")
                    self.assertEqual(cached_result, "123456", "短链接缓存应该正确存储")
                    
                    print("✅ 短链接处理功能测试完成")
                
                try:
                    loop.run_until_complete(async_test())
                finally:
                    loop.close()
            
            thread = threading.Thread(target=worker)
            thread.start()
            thread.join()
        
        run_async_test_in_thread()
    
    def test_fallback_duplicate_check(self):
        """测试降级去重检查功能"""
        print("\n=== 测试降级去重检查功能 ===")
        
        # 由于_fallback_duplicate_check方法已被优化移除，改为测试基本的去重逻辑
        # 测试空录制列表的情况
        def run_async_test_in_thread():
            import threading
            
            def worker():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                async def async_test():
                    # 测试空录制列表 - 传入空列表而不是None
                    is_duplicate, reason = await RoomChecker.check_duplicate_room(
                        self.mock_app, "https://live.douyin.com/123456", 
                        existing_recordings=[]
                    )
                    self.assertFalse(is_duplicate, "空录制列表应该返回False")
                    self.assertIsNone(reason, "空录制列表应该返回None原因")
                    print("✅ 空录制列表测试通过")
                    
                    # 测试URL完全相同
                    is_duplicate, reason = await RoomChecker.check_duplicate_room(
                        self.mock_app, "https://live.douyin.com/123456"
                    )
                    self.assertTrue(is_duplicate, "URL完全相同应该返回True")
                    self.assertEqual(reason, "URL完全相同", "URL完全相同应该返回正确原因")
                    print("✅ URL完全相同测试通过")
                    
                    # 测试房间ID相同
                    is_duplicate, reason = await RoomChecker.check_duplicate_room(
                        self.mock_app, "https://live.douyin.com/123456?param=value"
                    )
                    self.assertTrue(is_duplicate, "房间ID相同应该返回True")
                    self.assertEqual(reason, "同平台房间ID相同", "房间ID相同应该返回正确原因")
                    print("✅ 房间ID相同测试通过")
                
                try:
                    loop.run_until_complete(async_test())
                finally:
                    loop.close()
            
            thread = threading.Thread(target=worker)
            thread.start()
            thread.join()
        
        run_async_test_in_thread()
        print("✅ 降级去重检查功能测试完成")
    
    def test_cache_performance(self):
        """测试缓存性能"""
        print("\n=== 测试缓存性能 ===")
        
        # 测试缓存命中率
        test_urls = [
            "https://live.douyin.com/123456",
            "https://live.bilibili.com/789",
            "https://live.kuaishou.com/u/user123"
        ]
        
        # 多次调用相同URL
        for _ in range(10):
            for url in test_urls:
                RoomChecker._get_cached_platform_info(url)
        
        stats = RoomChecker.get_cache_stats()
        hit_rate = stats["hit_rate"]
        
        print(f"缓存命中率: {hit_rate:.2%}")
        self.assertGreater(hit_rate, 0.5, "缓存命中率应该大于50%")
        
        # 测试缓存大小限制
        for i in range(2000):  # 超过缓存限制
            RoomChecker._get_cached_platform_info(f"https://test{i}.com")
        
        final_stats = RoomChecker.get_cache_stats()
        self.assertLessEqual(final_stats["cache_size"], RoomChecker.MAX_CACHE_SIZE, "缓存大小应该被限制")
        
        print(f"最终缓存大小: {final_stats['cache_size']}")
        print("✅ 缓存性能测试完成")
    
    def test_error_handling(self):
        """测试错误处理"""
        print("\n=== 测试错误处理 ===")
        
        # 测试无效URL
        result = RoomChecker.extract_room_id("")
        self.assertIsNone(result, "空URL应该返回None")
        
        result = RoomChecker.extract_room_id(None)
        self.assertIsNone(result, "None URL应该返回None")
        
        result = RoomChecker.extract_room_id("not_a_url")
        self.assertIsNone(result, "无效URL应该返回None")
        
        # 测试缓存错误处理
        platform, key = RoomChecker._get_cached_platform_info("")
        self.assertIsNone(platform, "空URL的平台信息应该返回None")
        self.assertIsNone(key, "空URL的平台键应该返回None")
        
        print("✅ 错误处理测试完成")
    
    def test_thread_safety(self):
        """测试线程安全性"""
        print("\n=== 测试线程安全性 ===")
        
        import threading
        
        def worker():
            for i in range(100):
                url = f"https://test{i}.com"
                RoomChecker._get_cached_platform_info(url)
                RoomChecker.extract_room_id(url)
        
        # 创建多个线程
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        # 检查缓存是否正常工作
        stats = RoomChecker.get_cache_stats()
        self.assertGreater(stats["cache_size"], 0, "多线程后缓存应该有内容")
        
        print(f"多线程测试完成，缓存大小: {stats['cache_size']}")
        print("✅ 线程安全性测试完成")


async def run_performance_test():
    """运行性能测试"""
    print("\n=== 性能测试 ===")
    
    # 创建大量测试数据
    test_urls = []
    for i in range(1000):
        test_urls.append(f"https://live.douyin.com/{i}")
        test_urls.append(f"https://live.bilibili.com/{i}")
        test_urls.append(f"https://live.kuaishou.com/u/user{i}")
    
    # 测试房间ID提取性能
    start_time = time.time()
    for url in test_urls:
        RoomChecker.extract_room_id(url)
    extract_time = time.time() - start_time
    
    print(f"房间ID提取性能: {len(test_urls)} 个URL, {extract_time:.3f} 秒")
    print(f"平均每个URL: {extract_time/len(test_urls)*1000:.3f} 毫秒")
    
    # 测试缓存性能
    start_time = time.time()
    for url in test_urls:
        RoomChecker._get_cached_platform_info(url)
    cache_time = time.time() - start_time
    
    print(f"缓存查询性能: {len(test_urls)} 个URL, {cache_time:.3f} 秒")
    print(f"平均每个URL: {cache_time/len(test_urls)*1000:.3f} 毫秒")
    
    # 获取最终统计
    stats = RoomChecker.get_cache_stats()
    print(f"最终缓存统计: {stats}")
    
    print("✅ 性能测试完成")


async def main():
    """主函数"""
    print("🚀 开始运行房间去重逻辑完整测试")
    
    # 运行单元测试
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # 运行性能测试
    await run_performance_test()
    
    print("\n🎉 所有测试完成！")


if __name__ == "__main__":
    asyncio.run(main()) 