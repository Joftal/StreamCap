import pytest
import asyncio
import sys
from unittest.mock import Mock, patch, AsyncMock
from app.utils.room_checker import RoomChecker
from app.models.recording_model import Recording
from app.utils.logger import logger
import re


class MockStreamInfo:
    def __init__(self, anchor_name, title):
        self.anchor_name = anchor_name
        self.title = title


class MockApp:
    def __init__(self):
        self.record_manager = Mock()
        self.record_manager.recordings = []
        self.record_manager.settings = Mock()
        self.record_manager.settings.get_video_save_path = Mock(return_value="test_output")


@pytest.fixture
def mock_app():
    return MockApp()


@pytest.fixture
def mock_recorder():
    with patch('app.core.stream_manager.LiveStreamRecorder') as mock:
        recorder = mock.return_value
        recorder.fetch_stream = AsyncMock()
        recorder.get_room_id_from_short_url = AsyncMock()
        yield recorder


@pytest.fixture
def mock_platform_info():
    with patch('app.core.platform_handlers.get_platform_info') as mock:
        def get_platform_info(url):
            if "douyin.com" in url:
                return "抖音", "douyin"
            elif "tiktok.com" in url:
                return "TikTok", "tiktok"
            elif "kuaishou.com" in url:
                return "快手", "kuaishou"
            elif "huya.com" in url:
                return "虎牙", "huya"
            elif "douyu.com" in url:
                return "斗鱼", "douyu"
            elif "yy.com" in url:
                return "YY", "yy"
            elif "bilibili.com" in url:
                return "B站", "bilibili"
            elif "xiaohongshu.com" in url:
                return "小红书", "xiaohongshu"
            elif "bigo.tv" in url:
                return "Bigo", "bigo"
            elif "cc.163.com" in url:
                return "网易CC", "cc"
            elif "missevan.com" in url:
                return "猫耳FM", "missevan"
            elif "inke.cn" in url:
                return "映客直播", "inke"
            elif "weibo.com" in url:
                return "微博直播", "weibo"
            elif "kugou.com" in url:
                return "酷狗直播", "kugou"
            elif "twitch.tv" in url:
                return "Twitch", "twitch"
            return None, None
        mock.side_effect = get_platform_info
        yield mock


def print_test_result(test_name, result, expected=None, actual=None, details=None):
    """打印测试结果 - 简化版本"""
    # 只在失败时输出详细信息
    if not result:
        sys.stdout.write(f"\n❌ 失败: {test_name}\n")
        if expected is not None and actual is not None:
            sys.stdout.write(f"   期望: {expected}\n")
            sys.stdout.write(f"   实际: {actual}\n")
        if details:
            for key, value in details.items():
                sys.stdout.write(f"   {key}: {value}\n")
        sys.stdout.flush()


@pytest.mark.asyncio
async def test_extract_room_id():
    """测试从URL中提取房间ID"""
    sys.stdout.write("\n开始URL提取测试...\n")
    sys.stdout.flush()
    
    test_cases = [
        # 抖音
        ("https://live.douyin.com/745964462470", "745964462470"),
        ("https://v.douyin.com/iQFeBnt/", None),  # 短链接
        ("https://live.douyin.com/yall1102", "yall1102"),  # 链接+抖音号
        ("https://v.douyin.com/CeiU5cbX", None),  # 主播主页地址
        
        # TikTok
        ("https://www.tiktok.com/@pearlgaga88/live", "pearlgaga88"),
        
        # 快手
        ("https://live.kuaishou.com/u/yall1102", "yall1102"),
        
        # 虎牙
        ("https://www.huya.com/52333", "52333"),
        
        # 斗鱼
        ("https://www.douyu.com/3637778", "3637778"),
        ("https://www.douyu.com/topic/wzDBLS6?rid=4921614", "4921614"),
        
        # YY
        ("https://www.yy.com/22490906/22490906", "22490906"),
        
        # B站
        ("https://live.bilibili.com/320", "320"),
        
        # 小红书
        ("http://xhslink.com/xpJpfM", None),  # 短链接
        
        # Bigo
        ("https://www.bigo.tv/cn/716418802", "716418802"),
        
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
        
        # 猫耳FM
        ("https://fm.missevan.com/live/868895007", "868895007"),
        
        # Look直播
        ("https://look.163.com/live?id=65108820", "65108820"),
        
        # WinkTV
        ("https://www.winktv.co.kr/live/play/anjer1004", "anjer1004"),
        
        # TtingLive
        ("https://www.ttinglive.com/channels/52406/live", "52406"),
        
        # PopkonTV
        ("https://www.popkontv.com/live/view?castId=wjfal007", "wjfal007"),
        ("https://www.popkontv.com/channel/notices?mcid=wjfal007", "wjfal007"),
        
        # TwitCasting
        ("https://twitcasting.tv/c:uonq", "uonq"),
        
        # 百度直播
        ("https://live.baidu.com/m/media/pclive/pchome/live.html?room_id=9175031377", "9175031377"),
        
        # 微博直播
        ("https://weibo.com/l/wblive/p/show/1022:2321325026370190442592", "2321325026370190442592"),
        
        # 酷狗直播
        ("https://fanxing2.kugou.com/50428671", "50428671"),
        
        # Twitch
        ("https://www.twitch.tv/gamerbee", "gamerbee"),
        
        # LiveMe
        ("https://www.liveme.com/zh/v/17141543493018047815", "17141543493018047815"),
        
        # 花椒直播
        ("https://www.huajiao.com/l/345096174", "345096174"),
        
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
        ("https://www.haixiutv.com/6095106", "6095106"),
        
        # VV星球直播
        ("https://h5webcdn-pro.vvxqiu.com//activity/videoShare/videoShare.html?roomId=LP115924473", "LP115924473"),
        
        # 17Live
        ("https://17.live/en/live/6302408", "6302408"),
        
        # 浪Live
        ("https://www.lang.live/en-US/room/3349463", "3349463"),
        
        # 畅聊直播
        ("https://live.tlclw.com/106188", "106188"),
        
        # 飘飘直播
        ("https://m.pp.weimipopo.com/live/preview.html?uid=91648673&anchorUid=91625862", "91625862"),
        
        # 六间房直播
        ("https://v.6.cn/634435", "634435"),
        
        # 乐嗨直播
        ("https://www.lehaitv.com/8059096", "8059096"),
        
        # 花猫直播
        ("https://h.catshow168.com/live/preview.html?uid=19066357&anchorUid=18895331", "18895331"),
        
        # Shopee
        ("https://sg.shp.ee/GmpXeuf?uid=1006401066", "1006401066"),
        
        # Youtube
        ("https://www.youtube.com/watch?v=cS6zS5hi1w0", "cS6zS5hi1w0"),
        
        # 淘宝
        ("https://m.tb.cn/h.TWp0HTd", None),  # 短链接
        
        # 京东
        ("https://3.cn/28MLBy-E", None),  # 短链接
        
        # Faceit
        ("https://www.faceit.com/zh/players/Compl1/stream", "Compl1"),
    ]
    
    success_count = 0
    total_count = len(test_cases)
    failed_cases = []
    
    for url, expected in test_cases:
        result = RoomChecker.extract_room_id(url)
        is_success = result == expected
        if is_success:
            success_count += 1
        else:
            failed_cases.append((url, expected, result))
    
    # 输出总结
    sys.stdout.write(f"\nURL提取测试总结:\n")
    sys.stdout.write(f"总测试数: {total_count}\n")
    sys.stdout.write(f"通过数: {success_count}\n")
    sys.stdout.write(f"失败数: {total_count - success_count}\n")
    sys.stdout.write(f"通过率: {(success_count/total_count)*100:.2f}%\n")
    
    # 只输出失败的用例
    if failed_cases:
        sys.stdout.write(f"\n❌ 失败的测试用例 ({len(failed_cases)} 个):\n")
        for url, expected, actual in failed_cases:
            sys.stdout.write(f"  {url} -> {actual} (期望: {expected})\n")
    else:
        sys.stdout.write(f"\n✅ 所有测试通过！\n")
    
    sys.stdout.flush()
    
    assert success_count == total_count, f"URL提取测试失败: {total_count - success_count} 个测试未通过"


@pytest.mark.asyncio
async def test_check_duplicate_room_same_room_id(mock_app, mock_recorder):
    """测试相同房间ID的检测"""
    sys.stdout.write("\n开始测试相同房间ID检测...\n")
    sys.stdout.flush()
    
    # 设置模拟数据
    mock_recorder.fetch_stream.return_value = MockStreamInfo("测试主播", "测试标题")
    
    # 创建现有录制
    existing_recording = Recording(
        rec_id="test1",
        url="https://live.douyin.com/123456",
        streamer_name="测试主播",
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
    mock_app.record_manager.recordings = [existing_recording]
    
    # 测试相同房间ID（使用不同的URL）
    test_url = "https://live.douyin.com/123456?param=value"
    result, reason = await RoomChecker.check_duplicate_room(
        mock_app,
        test_url,
        "测试主播"
    )
    
    print_test_result(
        "相同房间ID检测",
        result is True and reason == "同平台房间ID相同",
        "同平台房间ID相同",
        reason,
        {
            "测试URL": test_url,
            "现有录制URL": existing_recording.url,
            "主播名称": "测试主播",
            "房间ID": "123456",
            "平台": "douyin"
        }
    )
    
    assert result is True
    assert reason == "同平台房间ID相同"


@pytest.mark.asyncio
async def test_check_duplicate_room_same_url(mock_app, mock_recorder):
    """测试相同URL的检测"""
    sys.stdout.write("\n开始测试相同URL检测...\n")
    sys.stdout.flush()
    
    # 设置模拟数据
    mock_recorder.fetch_stream.return_value = MockStreamInfo("测试主播", "测试标题")
    
    # 创建现有录制
    existing_recording = Recording(
        rec_id="test1",
        url="https://live.douyin.com/123456",
        streamer_name="测试主播",
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
    mock_app.record_manager.recordings = [existing_recording]
    
    # 测试相同URL
    test_url = "https://live.douyin.com/123456"
    result, reason = await RoomChecker.check_duplicate_room(
        mock_app,
        test_url,
        "测试主播"
    )
    
    print_test_result(
        "相同URL检测",
        result is True and reason == "URL完全相同",
        "URL完全相同",
        reason,
        {
            "测试URL": test_url,
            "现有录制URL": existing_recording.url,
            "主播名称": "测试主播",
            "房间ID": "123456",
            "平台": "douyin"
        }
    )
    
    assert result is True
    assert reason == "URL完全相同"


@pytest.mark.asyncio
async def test_check_duplicate_room_same_streamer(mock_app, mock_recorder):
    """测试相同主播的检测"""
    sys.stdout.write("\n开始测试相同主播检测...\n")
    sys.stdout.flush()
    
    # 设置模拟数据
    mock_recorder.fetch_stream.return_value = MockStreamInfo("测试主播", "测试标题")
    
    # 创建现有录制
    existing_recording = Recording(
        rec_id="test1",
        url="https://live.douyin.com/123456",
        streamer_name="测试主播",
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
    mock_app.record_manager.recordings = [existing_recording]
    
    # 测试相同主播
    test_url = "https://live.douyin.com/789012"
    result, reason = await RoomChecker.check_duplicate_room(
        mock_app,
        test_url,
        "测试主播"
    )
    
    print_test_result(
        "相同主播检测",
        result is True and reason == "同平台同名主播",
        "同平台同名主播",
        reason,
        {
            "测试URL": test_url,
            "现有录制URL": existing_recording.url,
            "主播名称": "测试主播",
            "房间ID": "789012",
            "平台": "douyin"
        }
    )
    
    assert result is True
    assert reason == "同平台同名主播"


@pytest.mark.asyncio
async def test_check_duplicate_room_short_url(mock_app, mock_recorder):
    """测试短链接的处理"""
    sys.stdout.write("\n开始测试短链接处理...\n")
    sys.stdout.flush()
    
    # 设置模拟数据
    mock_recorder.fetch_stream.return_value = MockStreamInfo("测试主播", "测试标题")
    mock_recorder.get_room_id_from_short_url.return_value = "123456"
    
    # 创建现有录制
    existing_recording = Recording(
        rec_id="test1",
        url="https://live.douyin.com/123456",
        streamer_name="测试主播",
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
    mock_app.record_manager.recordings = [existing_recording]
    
    # 测试短链接
    test_url = "https://v.douyin.com/abc123"
    result, reason = await RoomChecker.check_duplicate_room(
        mock_app,
        test_url,
        "测试主播"
    )
    
    print_test_result(
        "短链接处理",
        result is True and reason == "同平台房间ID相同",
        "同平台房间ID相同",
        reason,
        {
            "测试URL": test_url,
            "现有录制URL": existing_recording.url,
            "主播名称": "测试主播",
            "短链接解析结果": "123456",
            "平台": "douyin"
        }
    )
    
    assert result is True
    assert reason == "同平台房间ID相同"


@pytest.mark.asyncio
async def test_check_duplicate_room_different_platform(mock_app, mock_recorder):
    """测试不同平台的检测"""
    sys.stdout.write("\n开始测试不同平台检测...\n")
    sys.stdout.flush()
    
    # 设置模拟数据
    mock_recorder.fetch_stream.return_value = MockStreamInfo("测试主播", "测试标题")
    
    # 创建现有录制
    existing_recording = Recording(
        rec_id="test1",
        url="https://live.douyin.com/123456",
        streamer_name="测试主播",
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
    mock_app.record_manager.recordings = [existing_recording]
    
    # 测试不同平台
    test_url = "https://live.bilibili.com/123456"
    result, reason = await RoomChecker.check_duplicate_room(
        mock_app,
        test_url,
        "测试主播"
    )
    
    print_test_result(
        "不同平台检测",
        result is False and reason is None,
        "False, None",
        f"{result}, {reason}",
        {
            "测试URL": test_url,
            "现有录制URL": existing_recording.url,
            "主播名称": "测试主播",
            "房间ID": "123456",
            "测试平台": "bilibili",
            "现有平台": "douyin"
        }
    )
    
    assert result is False
    assert reason is None


@pytest.mark.asyncio
async def test_check_duplicate_room_no_stream_info(mock_app, mock_recorder):
    """测试无法获取直播间信息的情况"""
    sys.stdout.write("\n开始测试无法获取直播间信息...\n")
    sys.stdout.flush()
    
    # 设置模拟数据
    mock_recorder.fetch_stream.return_value = None
    
    # 测试无法获取直播间信息
    test_url = "https://live.douyin.com/123456"
    result, reason = await RoomChecker.check_duplicate_room(
        mock_app,
        test_url,
        "测试主播"
    )
    
    print_test_result(
        "无法获取直播间信息",
        result is False and reason is None,
        "False, None",
        f"{result}, {reason}",
        {
            "测试URL": test_url,
            "主播名称": "测试主播",
            "平台": "douyin",
            "错误原因": "无法获取直播间信息"
        }
    )
    
    assert result is False
    assert reason is None


@pytest.mark.asyncio
async def test_check_duplicate_room_no_anchor_name(mock_app, mock_recorder):
    """测试无法获取主播名称的情况"""
    sys.stdout.write("\n开始测试无法获取主播名称...\n")
    sys.stdout.flush()
    
    # 设置模拟数据
    mock_recorder.fetch_stream.return_value = MockStreamInfo(None, "测试标题")
    
    # 测试无法获取主播名称
    test_url = "https://live.douyin.com/123456"
    result, reason = await RoomChecker.check_duplicate_room(
        mock_app,
        test_url,
        "测试主播"
    )
    
    print_test_result(
        "无法获取主播名称",
        result is False and reason is None,
        "False, None",
        f"{result}, {reason}",
        {
            "测试URL": test_url,
            "主播名称": "测试主播",
            "平台": "douyin",
            "错误原因": "无法获取主播名称"
        }
    )
    
    assert result is False
    assert reason is None


@pytest.mark.asyncio
async def test_check_duplicate_room_empty_recordings(mock_app, mock_recorder):
    """测试空录制列表的情况"""
    sys.stdout.write("\n开始测试空录制列表...\n")
    sys.stdout.flush()
    
    # 设置模拟数据
    mock_recorder.fetch_stream.return_value = MockStreamInfo("测试主播", "测试标题")
    mock_app.record_manager.recordings = []
    
    # 测试空录制列表
    test_url = "https://live.douyin.com/123456"
    result, reason = await RoomChecker.check_duplicate_room(
        mock_app,
        test_url,
        "测试主播"
    )
    
    print_test_result(
        "空录制列表",
        result is False and reason is None,
        "False, None",
        f"{result}, {reason}",
        {
            "测试URL": test_url,
            "主播名称": "测试主播",
            "平台": "douyin",
            "录制列表长度": 0
        }
    )
    
    assert result is False
    assert reason is None


@pytest.mark.asyncio
async def test_check_duplicate_room_invalid_url(mock_app, mock_recorder):
    """测试无效URL的情况"""
    sys.stdout.write("\n开始测试无效URL...\n")
    sys.stdout.flush()
    
    # 设置模拟数据
    mock_recorder.fetch_stream.return_value = MockStreamInfo("测试主播", "测试标题")
    
    # 测试无效URL
    test_url = "invalid_url"
    result, reason = await RoomChecker.check_duplicate_room(
        mock_app,
        test_url,
        "测试主播"
    )
    
    print_test_result(
        "无效URL",
        result is False and reason is None,
        "False, None",
        f"{result}, {reason}",
        {
            "测试URL": test_url,
            "主播名称": "测试主播",
            "错误原因": "无效的URL格式"
        }
    )
    
    assert result is False
    assert reason is None


@pytest.mark.asyncio
async def test_all_platforms_duplicate_check(mock_app, mock_recorder, mock_platform_info):
    """测试所有平台的去重检测"""
    logger.info("开始测试所有平台的去重检测...")
    
    # 测试用例
    test_cases = [
        # 抖音
        {
            "platform": "douyin",
            "url": "https://live.douyin.com/745964462470",
            "room_id": "745964462470",
            "streamer_name": "测试主播1"
        },
        # TikTok
        {
            "platform": "tiktok",
            "url": "https://www.tiktok.com/@pearlgaga88/live",
            "room_id": "pearlgaga88",
            "streamer_name": "测试主播2"
        },
        # 快手
        {
            "platform": "kuaishou",
            "url": "https://live.kuaishou.com/u/yall1102",
            "room_id": "yall1102",
            "streamer_name": "测试主播3"
        },
        # 虎牙
        {
            "platform": "huya",
            "url": "https://www.huya.com/52333",
            "room_id": "52333",
            "streamer_name": "测试主播4"
        },
        # 斗鱼
        {
            "platform": "douyu",
            "url": "https://www.douyu.com/3637778",
            "room_id": "3637778",
            "streamer_name": "测试主播5"
        },
        # YY
        {
            "platform": "yy",
            "url": "https://www.yy.com/22490906/22490906",
            "room_id": "22490906",
            "streamer_name": "测试主播6"
        },
        # B站
        {
            "platform": "bilibili",
            "url": "https://live.bilibili.com/320",
            "room_id": "320",
            "streamer_name": "测试主播7"
        },
        # 小红书
        {
            "platform": "xiaohongshu",
            "url": "http://xhslink.com/xpJpfM",
            "room_id": None,  # 短链接无法直接提取房间ID
            "streamer_name": "测试主播8"
        },
        # Bigo
        {
            "platform": "bigo",
            "url": "https://www.bigo.tv/cn/716418802",
            "room_id": "716418802",
            "streamer_name": "测试主播9"
        },
        # 网易CC
        {
            "platform": "cc",
            "url": "https://cc.163.com/583946984",
            "room_id": "583946984",
            "streamer_name": "测试主播10"
        },
        # 猫耳FM
        {
            "platform": "missevan",
            "url": "https://fm.missevan.com/live/868895007",
            "room_id": "868895007",
            "streamer_name": "测试主播11"
        },
        # 映客直播
        {
            "platform": "inke",
            "url": "https://www.inke.cn/liveroom/index.html?uid=22954469&id=1720860391070904",
            "room_id": "1720860391070904",
            "streamer_name": "测试主播12"
        },
        # 微博直播
        {
            "platform": "weibo",
            "url": "https://weibo.com/l/wblive/p/show/1022:2321325026370190442592",
            "room_id": "2321325026370190442592",
            "streamer_name": "测试主播13"
        },
        # 酷狗直播
        {
            "platform": "kugou",
            "url": "https://fanxing2.kugou.com/50428671",
            "room_id": "50428671",
            "streamer_name": "测试主播14"
        },
        # Twitch
        {
            "platform": "twitch",
            "url": "https://www.twitch.tv/gamerbee",
            "room_id": "gamerbee",
            "streamer_name": "测试主播15"
        }
    ]
    
    # 测试结果统计
    results = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "failed_details": []
    }
    
    # 为每个平台创建测试
    for test_case in test_cases:
        platform = test_case["platform"]
        
        # 创建测试录制项
        existing_recording = Recording(
            rec_id=f"test_{platform}",
            url=test_case["url"],
            streamer_name=test_case["streamer_name"],
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
        
        # 设置模拟数据
        mock_recorder.fetch_stream.return_value = MockStreamInfo(test_case["streamer_name"], "测试标题")
        mock_recorder.get_room_id_from_short_url.return_value = "123456"
        
        # 测试1: URL完全相同
        results["total"] += 1
        is_duplicate, reason = await RoomChecker.check_duplicate_room(
            mock_app,
            test_case["url"],
            test_case["streamer_name"],
            [existing_recording]
        )
        
        # 对于短链接平台，URL完全相同测试可能失败，因为短链接无法直接比较
        if platform in ["xiaohongshu"] and "xhslink.com" in test_case["url"]:
            # 短链接平台，期望通过房间ID或主播名称匹配
            if is_duplicate and (reason == "同平台房间ID相同" or reason == "同平台同名主播"):
                results["passed"] += 1
            else:
                results["failed"] += 1
                results["failed_details"].append(f"平台 {platform} URL完全相同测试失败: {reason}")
        else:
            # 非短链接平台，期望URL完全相同
            if is_duplicate and reason == "URL完全相同":
                results["passed"] += 1
            else:
                results["failed"] += 1
                results["failed_details"].append(f"平台 {platform} URL完全相同测试失败: {reason}")
        
        # 测试2: 同平台房间ID相同
        results["total"] += 1
        is_duplicate, reason = await RoomChecker.check_duplicate_room(
            mock_app,
            f"{test_case['url']}?param=value",  # 添加参数使URL不同
            test_case["streamer_name"],
            [existing_recording]
        )
        
        # 对于短链接平台，同平台房间ID相同测试可能失败，因为短链接会获取真实房间ID
        if platform in ["xiaohongshu"] and "xhslink.com" in test_case["url"]:
            # 短链接平台，期望通过主播名称匹配
            if is_duplicate and reason == "同平台同名主播":
                results["passed"] += 1
            else:
                results["failed"] += 1
                results["failed_details"].append(f"平台 {platform} 同平台房间ID相同测试失败: {reason}")
        else:
            # 非短链接平台，期望同平台房间ID相同
            if is_duplicate and reason == "同平台房间ID相同":
                results["passed"] += 1
            else:
                results["failed"] += 1
                results["failed_details"].append(f"平台 {platform} 同平台房间ID相同测试失败: {reason}")
        
        # 测试3: 同平台同名主播
        results["total"] += 1
        
        # 根据不同平台使用不同的方式替换房间ID
        if platform == "inke":
            # 对于映客直播，使用不同的uid和id
            new_url = "https://www.inke.cn/liveroom/index.html?uid=999999&id=999999"
        elif platform == "xiaohongshu" and "xhslink.com" in test_case["url"]:
            # 对于小红书短链接，使用不同的短链接
            new_url = "http://xhslink.com/different"
        else:
            # 对于其他平台，使用原来的替换方式
            if test_case["room_id"] is not None:
                new_url = f"{test_case['url'].replace(test_case['room_id'], '999999')}"
            else:
                # 如果room_id为None，直接使用原URL
                new_url = test_case["url"]
        
        is_duplicate, reason = await RoomChecker.check_duplicate_room(
            mock_app,
            new_url,
            test_case["streamer_name"],
            [existing_recording]
        )
        
        if is_duplicate and reason == "同平台同名主播":
            results["passed"] += 1
        else:
            results["failed"] += 1
            results["failed_details"].append(f"平台 {platform} 同平台同名主播测试失败: {reason}")
    
    # 输出测试结果
    logger.info("\n测试结果汇总:")
    logger.info(f"总测试数: {results['total']}")
    logger.info(f"通过数: {results['passed']}")
    logger.info(f"失败数: {results['failed']}")
    logger.info(f"通过率: {(results['passed'] / results['total'] * 100):.2f}%")
    
    # 只输出失败的详细信息
    if results["failed_details"]:
        logger.info(f"\n❌ 失败的测试 ({results['failed']} 个):")
        for detail in results["failed_details"]:
            logger.info(f"  {detail}")
    else:
        logger.info("\n✅ 所有测试通过！")
    
    # 断言所有测试都通过
    assert results["failed"] == 0, f"有 {results['failed']} 个测试未通过"


@pytest.mark.asyncio
async def test_extract_room_id_comprehensive():
    """全面的URL提取测试，覆盖所有平台的各种URL格式"""
    sys.stdout.write("\n开始全面URL提取测试...\n")
    sys.stdout.flush()
    
    test_cases = [
        # 抖音 - 各种格式
        ("https://live.douyin.com/745964462470", "745964462470"),
        ("https://live.douyin.com/745964462470?param=value", "745964462470"),
        ("https://v.douyin.com/iQFeBnt/", None),  # 短链接
        ("https://live.douyin.com/yall1102", "yall1102"),  # 链接+抖音号
        ("https://v.douyin.com/CeiU5cbX", None),  # 主播主页地址
        ("https://www.douyin.com/user/abcdef", None),  # 用户主页
        
        # TikTok - 各种格式
        ("https://www.tiktok.com/@pearlgaga88/live", "pearlgaga88"),
        ("https://www.tiktok.com/@testuser/live?param=value", "testuser"),
        ("https://www.tiktok.com/@user123", None),  # 非直播链接
        
        # 快手 - 各种格式
        ("https://live.kuaishou.com/u/yall1102", "yall1102"),
        ("https://live.kuaishou.com/u/yall1102?param=value", "yall1102"),
        ("https://v.kuaishou.com/abc123", None),  # 短链接
        ("https://www.kuaishou.com/short-video/123", None),  # 短视频
        
        # 虎牙 - 各种格式
        ("https://www.huya.com/52333", "52333"),
        ("https://www.huya.com/52333?param=value", "52333"),
        ("https://m.huya.com/52333", "52333"),  # 移动端
        
        # 斗鱼 - 各种格式
        ("https://www.douyu.com/3637778", "3637778"),
        ("https://www.douyu.com/3637778?dyshid=", "3637778"),
        ("https://www.douyu.com/topic/wzDBLS6?rid=4921614&dyshid=", "4921614"),
        ("https://www.douyu.com/room/123456", "123456"),
        
        # YY - 各种格式
        ("https://www.yy.com/22490906/22490906", "22490906"),
        ("https://www.yy.com/22490906/22490906?param=value", "22490906"),
        
        # B站 - 各种格式
        ("https://live.bilibili.com/320", "320"),
        ("https://live.bilibili.com/320?param=value", "320"),
        ("https://live.bilibili.com/h5/320", "320"),  # H5版本
        
        # 小红书 - 各种格式
        ("http://xhslink.com/xpJpfM", None),  # 短链接
        ("https://www.xiaohongshu.com/user/profile/123456", "123456"),
        ("https://www.xiaohongshu.com/explore/123", None),  # 探索页面
        
        # Bigo - 各种格式
        ("https://www.bigo.tv/cn/716418802", "716418802"),
        ("https://www.bigo.tv/716418802", "716418802"),
        ("https://www.bigo.tv/cn/716418802?param=value", "716418802"),
        
        # Blued - 各种格式
        ("https://app.blued.cn/live?id=Mp6G2R", "Mp6G2R"),
        ("https://app.blued.cn/live?id=Mp6G2R&param=value", "Mp6G2R"),
        
        # SOOP - 各种格式
        ("https://play.sooplive.co.kr/sw7love", "sw7love"),
        ("https://play.sooplive.co.kr/sw7love?param=value", "sw7love"),
        
        # 网易CC - 各种格式
        ("https://cc.163.com/583946984", "583946984"),
        ("https://cc.163.com/583946984?param=value", "583946984"),
        
        # 千度热播 - 各种格式
        ("https://qiandurebo.com/web/video.php?roomnumber=33333", "33333"),
        ("https://qiandurebo.com/web/video.php?roomnumber=33333&param=value", "33333"),
        
        # PandaTV - 各种格式
        ("https://www.pandalive.co.kr/live/play/bara0109", "bara0109"),
        ("https://www.pandalive.co.kr/live/play/bara0109?param=value", "bara0109"),
        
        # 猫耳FM - 各种格式
        ("https://fm.missevan.com/live/868895007", "868895007"),
        ("https://fm.missevan.com/live/868895007?param=value", "868895007"),
        
        # Look直播 - 各种格式
        ("https://look.163.com/live?id=65108820&position=3", "65108820"),
        ("https://look.163.com/live?id=65108820", "65108820"),
        
        # WinkTV - 各种格式
        ("https://www.winktv.co.kr/live/play/anjer1004", "anjer1004"),
        ("https://www.winktv.co.kr/live/play/anjer1004?param=value", "anjer1004"),
        
        # TtingLive - 各种格式
        ("https://www.ttinglive.com/channels/52406/live", "52406"),
        ("https://www.ttinglive.com/channels/52406/live?param=value", "52406"),
        
        # PopkonTV - 各种格式
        ("https://www.popkontv.com/live/view?castId=wjfal007&partnerCode=P-00117", "wjfal007"),
        ("https://www.popkontv.com/channel/notices?mcid=wjfal007&mcPartnerCode=P-00117", "wjfal007"),
        
        # TwitCasting - 各种格式
        ("https://twitcasting.tv/c:uonq", "uonq"),
        ("https://twitcasting.tv/c:uonq?param=value", "uonq"),
        
        # 百度直播 - 各种格式
        ("https://live.baidu.com/m/media/pclive/pchome/live.html?room_id=9175031377&tab_category", "9175031377"),
        ("https://live.baidu.com/m/media/pclive/pchome/live.html?room_id=9175031377", "9175031377"),
        
        # 微博直播 - 各种格式
        ("https://weibo.com/l/wblive/p/show/1022:2321325026370190442592", "2321325026370190442592"),
        ("https://weibo.com/l/wblive/p/show/1022:123456", "123456"),
        
        # 酷狗直播 - 各种格式
        ("https://fanxing2.kugou.com/50428671?refer=2177&sourceFrom=", "50428671"),
        ("https://fanxing2.kugou.com/50428671", "50428671"),
        
        # Twitch - 各种格式
        ("https://www.twitch.tv/gamerbee", "gamerbee"),
        ("https://www.twitch.tv/gamerbee?param=value", "gamerbee"),
        
        # LiveMe - 各种格式
        ("https://www.liveme.com/zh/v/17141543493018047815/index.html", "17141543493018047815"),
        ("https://www.liveme.com/zh/v/17141543493018047815", "17141543493018047815"),
        
        # 花椒直播 - 各种格式
        ("https://www.huajiao.com/l/345096174", "345096174"),
        ("https://www.huajiao.com/l/345096174?param=value", "345096174"),
        
        # ShowRoom - 各种格式
        ("https://www.showroom-live.com/room/profile?room_id=480206", "480206"),
        ("https://www.showroom-live.com/room/profile?room_id=480206&param=value", "480206"),
        
        # Acfun - 各种格式
        ("https://live.acfun.cn/live/179922", "179922"),
        ("https://live.acfun.cn/live/179922?param=value", "179922"),
        
        # 映客直播 - 各种格式
        ("https://www.inke.cn/liveroom/index.html?uid=22954469&id=1720860391070904", "1720860391070904"),
        ("https://www.inke.cn/liveroom/index.html?uid=123456&id=789012", "789012"),
        ("https://www.inke.cn/liveroom/index.html?uid=123456", "123456"),  # 只有uid
        
        # 音播直播 - 各种格式
        ("https://live.ybw1666.com/800002949", "800002949"),
        ("https://live.ybw1666.com/800002949?param=value", "800002949"),
        
        # 知乎直播 - 各种格式
        ("https://www.zhihu.com/people/ac3a467005c5d20381a82230101308e9", "ac3a467005c5d20381a82230101308e9"),
        ("https://www.zhihu.com/people/ac3a467005c5d20381a82230101308e9?param=value", "ac3a467005c5d20381a82230101308e9"),
        
        # CHZZK - 各种格式
        ("https://chzzk.naver.com/live/458f6ec20b034f49e0fc6d03921646d2", "458f6ec20b034f49e0fc6d03921646d2"),
        ("https://chzzk.naver.com/live/458f6ec20b034f49e0fc6d03921646d2?param=value", "458f6ec20b034f49e0fc6d03921646d2"),
        
        # 嗨秀直播 - 各种格式
        ("https://www.haixiutv.com/6095106", "6095106"),
        ("https://www.haixiutv.com/6095106?param=value", "6095106"),
        
        # VV星球直播 - 各种格式
        ("https://h5webcdn-pro.vvxqiu.com//activity/videoShare/videoShare.html?h5Server=https://h5p.vvxqiu.com&roomId=LP115924473&platformId=vvstar", "LP115924473"),
        ("https://h5webcdn-pro.vvxqiu.com//activity/videoShare/videoShare.html?roomId=LP115924473", "LP115924473"),
        
        # 17Live - 各种格式
        ("https://17.live/en/live/6302408", "6302408"),
        ("https://17.live/en/live/6302408?param=value", "6302408"),
        
        # 浪Live - 各种格式
        ("https://www.lang.live/en-US/room/3349463", "3349463"),
        ("https://www.lang.live/en-US/room/3349463?param=value", "3349463"),
        
        # 畅聊直播 - 各种格式
        ("https://live.tlclw.com/106188", "106188"),
        ("https://live.tlclw.com/106188?param=value", "106188"),
        
        # 飘飘直播 - 各种格式
        ("https://m.pp.weimipopo.com/live/preview.html?uid=91648673&anchorUid=91625862&app=plpl", "91625862"),
        ("https://m.pp.weimipopo.com/live/preview.html?anchorUid=91625862", "91625862"),
        
        # 六间房直播 - 各种格式
        ("https://v.6.cn/634435", "634435"),
        ("https://v.6.cn/634435?param=value", "634435"),
        
        # 乐嗨直播 - 各种格式
        ("https://www.lehaitv.com/8059096", "8059096"),
        ("https://www.lehaitv.com/8059096?param=value", "8059096"),
        
        # 花猫直播 - 各种格式
        ("https://h.catshow168.com/live/preview.html?uid=19066357&anchorUid=18895331", "18895331"),
        ("https://h.catshow168.com/live/preview.html?anchorUid=18895331", "18895331"),
        
        # Shopee - 各种格式
        ("https://sg.shp.ee/GmpXeuf?uid=1006401066&session=802458", "1006401066"),
        ("https://sg.shp.ee/GmpXeuf?uid=1006401066", "1006401066"),
        
        # Youtube - 各种格式
        ("https://www.youtube.com/watch?v=cS6zS5hi1w0", "cS6zS5hi1w0"),
        ("https://www.youtube.com/watch?v=cS6zS5hi1w0&param=value", "cS6zS5hi1w0"),
        
        # 淘宝 - 各种格式
        ("https://m.tb.cn/h.TWp0HTd", None),  # 短链接
        ("https://item.taobao.com/item.htm?id=123456", None),  # 商品链接
        
        # 京东 - 各种格式
        ("https://3.cn/28MLBy-E", None),  # 短链接
        ("https://item.jd.com/123456.html", None),  # 商品链接
        
        # Faceit - 各种格式
        ("https://www.faceit.com/zh/players/Compl1/stream", "Compl1"),
        ("https://www.faceit.com/zh/players/Compl1/stream?param=value", "Compl1"),
        
        # 边界情况和错误处理
        ("", None),  # 空字符串
        ("invalid_url", None),  # 无效URL
        ("https://unknown.com/123", None),  # 未知平台
        ("https://douyin.com/", None),  # 缺少房间ID
        ("https://live.douyin.com/", None),  # 缺少房间ID
        ("https://live.douyin.com/?param=value", None),  # 缺少房间ID但有参数
    ]
    
    success_count = 0
    total_count = len(test_cases)
    failed_cases = []
    
    for url, expected in test_cases:
        result = RoomChecker.extract_room_id(url)
        is_success = result == expected
        if is_success:
            success_count += 1
        else:
            failed_cases.append((url, expected, result))
    
    # 输出总结
    sys.stdout.write(f"\nURL提取测试总结:\n")
    sys.stdout.write(f"总测试数: {total_count}\n")
    sys.stdout.write(f"通过数: {success_count}\n")
    sys.stdout.write(f"失败数: {total_count - success_count}\n")
    sys.stdout.write(f"通过率: {(success_count/total_count)*100:.2f}%\n")
    
    # 只输出失败的用例
    if failed_cases:
        sys.stdout.write(f"\n❌ 失败的测试用例 ({len(failed_cases)} 个):\n")
        for url, expected, actual in failed_cases:
            sys.stdout.write(f"  {url} -> {actual} (期望: {expected})\n")
    else:
        sys.stdout.write(f"\n✅ 所有测试通过！\n")
    
    sys.stdout.flush()
    
    assert success_count == total_count, f"URL提取测试失败: {total_count - success_count} 个测试未通过"


@pytest.mark.asyncio
async def test_performance_large_recordings(mock_app, mock_recorder, mock_platform_info):
    """测试大量录制项时的性能"""
    sys.stdout.write("\n开始性能测试...\n")
    sys.stdout.flush()
    
    import time
    
    # 创建大量录制项
    large_recordings = []
    for i in range(1000):
        recording = Recording(
            rec_id=f"test_{i}",
            url=f"https://live.douyin.com/{i}",
            streamer_name=f"主播{i}",
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
        large_recordings.append(recording)
    
    # 设置模拟数据
    mock_recorder.fetch_stream.return_value = MockStreamInfo("测试主播", "测试标题")
    mock_recorder.get_room_id_from_short_url.return_value = "123456"
    
    # 测试URL
    test_url = "https://live.douyin.com/999999"
    
    # 测量性能
    start_time = time.time()
    result, reason = await RoomChecker.check_duplicate_room(
        mock_app,
        test_url,
        "测试主播",
        large_recordings
    )
    end_time = time.time()
    
    execution_time = end_time - start_time
    
    sys.stdout.write(f"性能测试结果: {len(large_recordings)} 个录制项, {execution_time:.4f} 秒\n")
    sys.stdout.flush()
    
    # 性能要求：1000个录制项应该在5秒内完成
    assert execution_time < 5.0, f"性能测试失败: 执行时间 {execution_time:.4f} 秒超过5秒限制"


@pytest.mark.asyncio
async def test_edge_cases(mock_app, mock_recorder, mock_platform_info):
    """测试边界情况"""
    sys.stdout.write("\n开始边界情况测试...\n")
    sys.stdout.flush()
    
    # 设置模拟数据
    mock_recorder.fetch_stream.return_value = MockStreamInfo("测试主播", "测试标题")
    mock_recorder.get_room_id_from_short_url.return_value = "123456"
    
    # 测试用例
    edge_cases = [
        # 空录制列表
        {
            "name": "空录制列表",
            "url": "https://live.douyin.com/123456",
            "recordings": [],
            "expected": (False, None)
        },
        # 空URL
        {
            "name": "空URL",
            "url": "",
            "recordings": [],
            "expected": (False, None)
        },
        # 无效URL
        {
            "name": "无效URL",
            "url": "invalid_url",
            "recordings": [],
            "expected": (False, None)
        },
        # None URL
        {
            "name": "None URL",
            "url": None,
            "recordings": [],
            "expected": (False, None)
        },
        # 无法获取直播间信息
        {
            "name": "无法获取直播间信息",
            "url": "https://live.douyin.com/123456",
            "recordings": [],
            "mock_stream_info": None,
            "expected": (False, None)
        },
        # 无法获取主播名称
        {
            "name": "无法获取主播名称",
            "url": "https://live.douyin.com/123456",
            "recordings": [],
            "mock_anchor_name": None,
            "expected": (False, None)
        },
        # 短链接处理
        {
            "name": "短链接处理",
            "url": "https://v.douyin.com/abc123",
            "recordings": [],
            "expected": (False, None)  # 短链接无法直接提取房间ID
        },
        # 跨平台相同房间ID
        {
            "name": "跨平台相同房间ID",
            "url": "https://live.bilibili.com/123456",
            "recordings": [
                Recording(
                    rec_id="test1",
                    url="https://live.douyin.com/123456",
                    streamer_name="不同主播",
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
            ],
            "expected": (False, None)  # 不同平台不应被认为是重复
        },
        # 同平台不同房间ID相同主播
        {
            "name": "同平台不同房间ID相同主播",
            "url": "https://live.douyin.com/789012",
            "recordings": [
                Recording(
                    rec_id="test1",
                    url="https://live.douyin.com/123456",
                    streamer_name="测试主播",
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
            ],
            "expected": (True, "同平台同名主播")
        }
    ]
    
    success_count = 0
    total_count = len(edge_cases)
    failed_cases = []
    
    for test_case in edge_cases:
        # 设置模拟数据
        if "mock_stream_info" in test_case:
            mock_recorder.fetch_stream.return_value = test_case["mock_stream_info"]
        elif "mock_anchor_name" in test_case:
            mock_recorder.fetch_stream.return_value = MockStreamInfo(test_case["mock_anchor_name"], "测试标题")
        else:
            mock_recorder.fetch_stream.return_value = MockStreamInfo("测试主播", "测试标题")
        
        # 执行测试
        result, reason = await RoomChecker.check_duplicate_room(
            mock_app,
            test_case["url"],
            "测试主播",
            test_case["recordings"]
        )
        
        # 检查结果
        is_success = (result, reason) == test_case["expected"]
        if is_success:
            success_count += 1
        else:
            failed_cases.append((test_case["name"], test_case["expected"], (result, reason)))
    
    # 输出总结
    sys.stdout.write(f"边界情况测试总结: {success_count}/{total_count} 通过\n")
    
    # 只输出失败的用例
    if failed_cases:
        sys.stdout.write(f"❌ 失败的测试用例 ({len(failed_cases)} 个):\n")
        for name, expected, actual in failed_cases:
            sys.stdout.write(f"  {name}: {actual} (期望: {expected})\n")
    else:
        sys.stdout.write("✅ 所有边界情况测试通过！\n")
    
    sys.stdout.flush()
    
    assert success_count == total_count, f"边界情况测试失败: {total_count - success_count} 个测试未通过"


@pytest.mark.asyncio
async def test_concurrent_duplicate_check(mock_app, mock_recorder, mock_platform_info):
    """测试并发去重检测"""
    sys.stdout.write("\n开始并发测试...\n")
    sys.stdout.flush()
    
    import asyncio
    import time
    
    # 设置模拟数据
    mock_recorder.fetch_stream.return_value = MockStreamInfo("测试主播", "测试标题")
    mock_recorder.get_room_id_from_short_url.return_value = "123456"
    
    # 创建测试录制项
    existing_recording = Recording(
        rec_id="test1",
        url="https://live.douyin.com/123456",
        streamer_name="测试主播",
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
    
    # 并发测试用例
    test_urls = [
        "https://live.douyin.com/123456",  # 完全相同
        "https://live.douyin.com/123456?param=value",  # 房间ID相同
        "https://live.douyin.com/789012",  # 主播相同
        "https://live.bilibili.com/123456",  # 不同平台
        "https://live.douyin.com/999999",  # 完全不同
    ]
    
    async def check_duplicate(url):
        return await RoomChecker.check_duplicate_room(
            mock_app,
            url,
            "测试主播",
            [existing_recording]
        )
    
    # 执行并发测试
    start_time = time.time()
    tasks = [check_duplicate(url) for url in test_urls]
    results = await asyncio.gather(*tasks)
    end_time = time.time()
    
    execution_time = end_time - start_time
    
    sys.stdout.write(f"并发测试结果: {len(test_urls)} 个并发请求, {execution_time:.4f} 秒\n")
    
    # 验证结果 - 修正期望结果
    expected_results = [
        (True, "URL完全相同"),
        (True, "同平台房间ID相同"),
        (True, "同平台同名主播"),
        (False, None),
        (True, "同平台同名主播")  # 修正：999999的主播名称也是"测试主播"
    ]
    
    failed_cases = []
    for i, ((result, reason), expected) in enumerate(zip(results, expected_results)):
        if (result, reason) != expected:
            failed_cases.append((i+1, expected, (result, reason)))
    
    # 只输出失败的用例
    if failed_cases:
        sys.stdout.write(f"❌ 失败的并发测试 ({len(failed_cases)} 个):\n")
        for test_num, expected, actual in failed_cases:
            sys.stdout.write(f"  测试{test_num}: {actual} (期望: {expected})\n")
    else:
        sys.stdout.write("✅ 所有并发测试通过！\n")
    
    sys.stdout.flush()
    
    # 性能要求：5个并发请求应该在2秒内完成
    assert execution_time < 2.0, f"并发性能测试失败: 执行时间 {execution_time:.4f} 秒超过2秒限制"


@pytest.mark.asyncio
async def test_memory_usage(mock_app, mock_recorder, mock_platform_info):
    """测试内存使用情况"""
    sys.stdout.write("\n开始内存使用测试...\n")
    sys.stdout.flush()
    
    import psutil
    import os
    
    # 获取当前进程
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    # 创建大量录制项
    large_recordings = []
    for i in range(10000):
        recording = Recording(
            rec_id=f"test_{i}",
            url=f"https://live.douyin.com/{i}",
            streamer_name=f"主播{i}",
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
        large_recordings.append(recording)
    
    # 设置模拟数据
    mock_recorder.fetch_stream.return_value = MockStreamInfo("测试主播", "测试标题")
    mock_recorder.get_room_id_from_short_url.return_value = "123456"
    
    # 执行去重检测
    result, reason = await RoomChecker.check_duplicate_room(
        mock_app,
        "https://live.douyin.com/999999",
        "测试主播",
        large_recordings
    )
    
    # 获取内存使用情况
    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_increase = final_memory - initial_memory
    
    sys.stdout.write(f"内存使用测试结果: {len(large_recordings)} 个录制项, 内存增长 {memory_increase:.2f} MB\n")
    sys.stdout.flush()
    
    # 内存要求：10000个录制项内存增长不应超过500MB
    assert memory_increase < 500, f"内存使用测试失败: 内存增长 {memory_increase:.2f} MB超过500MB限制"


@pytest.mark.asyncio
async def test_cache_mechanism(mock_app, mock_recorder, mock_platform_info):
    """测试缓存机制"""
    sys.stdout.write("\n开始缓存机制测试...\n")
    sys.stdout.flush()
    
    # 清除缓存
    RoomChecker.clear_cache()
    
    # 设置模拟数据
    mock_recorder.fetch_stream.return_value = MockStreamInfo("测试主播", "测试标题")
    mock_recorder.get_room_id_from_short_url.return_value = "123456"
    
    # 创建测试录制项
    existing_recording = Recording(
        rec_id="test1",
        url="https://live.douyin.com/123456",
        streamer_name="测试主播",
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
    
    # 第一次调用，应该调用get_platform_info
    result1, reason1 = await RoomChecker.check_duplicate_room(
        mock_app,
        "https://live.douyin.com/789012",
        "测试主播",
        [existing_recording]
    )
    
    # 第二次调用相同URL，应该使用缓存
    result2, reason2 = await RoomChecker.check_duplicate_room(
        mock_app,
        "https://live.douyin.com/789012",
        "测试主播",
        [existing_recording]
    )
    
    # 检查缓存是否工作
    assert hasattr(RoomChecker, '_platform_cache'), "缓存字典不存在"
    assert len(RoomChecker._platform_cache) > 0, "缓存为空"
    
    # 检查结果一致性
    assert (result1, reason1) == (result2, reason2), "缓存机制导致结果不一致"
    
    sys.stdout.write(f"缓存机制测试结果: {len(RoomChecker._platform_cache)} 个缓存项\n")
    
    # 测试缓存清除
    RoomChecker.clear_cache()
    assert len(RoomChecker._platform_cache) == 0, "缓存清除失败"
    
    sys.stdout.write("✅ 缓存机制测试通过\n")
    sys.stdout.flush()


@pytest.mark.asyncio
async def test_optimization_benefits(mock_app, mock_recorder, mock_platform_info):
    """测试优化效果"""
    sys.stdout.write("\n开始优化效果测试...\n")
    sys.stdout.flush()
    
    import time
    
    # 清除缓存
    RoomChecker.clear_cache()
    
    # 设置模拟数据
    mock_recorder.fetch_stream.return_value = MockStreamInfo("测试主播", "测试标题")
    mock_recorder.get_room_id_from_short_url.return_value = "123456"
    
    # 创建大量录制项
    large_recordings = []
    for i in range(100):
        recording = Recording(
            rec_id=f"test_{i}",
            url=f"https://live.douyin.com/{i}",
            streamer_name=f"主播{i}",
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
        large_recordings.append(recording)
    
    # 测试优化后的性能
    test_url = "https://live.douyin.com/999999"
    
    start_time = time.time()
    result, reason = await RoomChecker.check_duplicate_room(
        mock_app,
        test_url,
        "测试主播",
        large_recordings
    )
    end_time = time.time()
    
    optimized_time = end_time - start_time
    
    sys.stdout.write(f"优化效果测试结果: {len(large_recordings)} 个录制项, {optimized_time:.4f} 秒, {len(RoomChecker._platform_cache)} 个缓存项\n")
    sys.stdout.flush()
    
    # 性能要求：100个录制项应该在1秒内完成
    assert optimized_time < 1.0, f"优化效果测试失败: 执行时间 {optimized_time:.4f} 秒超过1秒限制"
    
    # 验证缓存效果
    assert len(RoomChecker._platform_cache) > 0, "缓存机制未生效"


@pytest.mark.asyncio
async def test_debug_extract_room_id():
    """调试URL提取测试"""
    sys.stdout.write("\n开始调试URL提取测试...\n")
    sys.stdout.flush()
    
    # 测试可能失败的用例
    debug_cases = [
        ("https://live.bilibili.com/h5/320", "320"),  # B站H5版本
        ("https://www.inke.cn/liveroom/index.html?uid=123456", "123456"),  # 映客直播只有uid
    ]
    
    for url, expected in debug_cases:
        result = RoomChecker.extract_room_id(url)
        is_success = result == expected
        sys.stdout.write(f"调试测试: {url} -> {result} (期望: {expected}) {'✅' if is_success else '❌'}\n")
        sys.stdout.flush()
        assert is_success, f"调试测试失败: {url} -> {result}, 期望: {expected}"
    
    sys.stdout.write("调试测试通过\n")
    sys.stdout.flush()


if __name__ == "__main__":
    pytest.main(["-v", "-s", "test_room_checker.py"]) 