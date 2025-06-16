#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
StreamCap 压力测试脚本
用于生成大量虚拟直播间卡片，测试界面切换和刷新时的性能表现
还可用于生成批量URL地址，以及特殊的重复URL测试用例
"""

import os
import sys
import time
import uuid
import random
import asyncio
import argparse
from datetime import datetime, timedelta

# 确保能够导入StreamCap的模块
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

import flet as ft
from app.models.recording_model import Recording
from app.models.recording_status_model import RecordingStatus
from app.utils.logger import logger


# 支持的平台列表，用于随机生成不同平台的直播间
PLATFORMS = [
    ("https://live.bilibili.com/", "bilibili"),
    ("https://www.douyu.com/", "douyu"),
    ("https://www.huya.com/", "huya"),
    ("https://www.youtube.com/", "youtube"),
    ("https://www.twitch.tv/", "twitch"),
    ("https://www.tiktok.com/", "tiktok"),
    ("https://www.douyin.com/", "douyin"),
    ("https://www.kuaishou.com/", "kuaishou"),
    ("https://www.zhihu.com/", "zhihu"),
    ("https://www.zhibo.tv/", "zhibo"),
    ("https://www.panda.tv/", "panda"),
    ("https://www.huajiao.com/", "huajiao"),
    ("https://cc.163.com/", "netease_cc"),
    ("https://yy.com/", "yy"),
    ("https://www.pandatv.live/", "pandalive"),
    ("https://chzzk.naver.com/", "chzzk"),
    ("https://www.inke.cn/", "inke"),
    ("https://www.17app.co/", "17live"),
    ("https://www.showroom-live.com/", "showroom"),
    ("https://www.acfun.cn/", "acfun"),
    ("https://www.6.cn/", "6room"),
    ("https://www.bigo.tv/", "bigo"),
    ("https://www.facebook.com/gaming/", "facebook"),
    ("https://www.twitcasting.tv/", "twitcasting"),
    ("https://www.hkdtv.com/", "hkdtv"),
    ("https://www.yizhibo.com/", "yizhibo"),
    ("https://www.blued.com/", "blued"),
    ("https://www.soop.com/", "soop"),
    ("https://www.afreecatv.com/", "afreecatv"),
    ("https://www.winktv.co.kr/", "winktv")
]

# 视频质量选项
QUALITY_OPTIONS = ["OD", "UHD", "HD", "SD"]

# 随机生成的主播名称前缀
STREAMER_PREFIXES = ["主播", "大神", "小姐姐", "老师", "解说", "歌手", "玩家", "UP主", "博主", "达人",
                     "舞者", "画师", "作家", "明星", "学霸", "厨师", "教练", "技术", "萌妹", "小哥哥",
                     "大佬", "专家", "高手", "新秀", "导师", "能手", "学者", "创作者", "艺术家", "大神"]

# 随机生成的主播名称
STREAMER_NAMES = [
    "星海", "月影", "阳光", "雨林", "雪花", "风云", "电竞", "游戏", "音乐", "舞蹈",
    "美食", "旅行", "科技", "数码", "知识", "生活", "搞笑", "萌宠", "动漫", "影视",
    "体育", "健身", "户外", "手工", "绘画", "摄影", "时尚", "美妆", "汽车", "教育",
    "文学", "诗词", "历史", "哲学", "物理", "化学", "生物", "地理", "心理", "医学",
    "法律", "经济", "金融", "管理", "营销", "设计", "编程", "网络", "安全", "人工智能",
    "机器学习", "大数据", "云计算", "区块链", "物联网", "虚拟现实", "增强现实", "机器人", "无人机", "航天",
    "海洋", "环保", "农业", "畜牧", "园艺", "烘焙", "调酒", "咖啡", "茶道", "香道",
    "书法", "篆刻", "国画", "油画", "素描", "雕塑", "陶艺", "布艺", "皮革", "木工",
    "金属", "玻璃", "珠宝", "服装", "鞋履", "包袋", "家居", "装饰", "古董", "收藏"
]


class StressTest:
    def __init__(self, app):
        self.app = app
        self.recordings = []
        self.base_recording_dir = os.path.join(current_dir, "test_output")
        
        # 确保测试输出目录存在
        if not os.path.exists(self.base_recording_dir):
            os.makedirs(self.base_recording_dir)

    def generate_random_recording(self):
        """生成一个随机的Recording对象"""
        # 随机选择平台
        platform_url, platform_key = random.choice(PLATFORMS)
        
        # 生成随机主播ID和名称
        streamer_id = str(random.randint(10000, 999999))
        streamer_prefix = random.choice(STREAMER_PREFIXES)
        streamer_name = f"{streamer_prefix}{random.choice(STREAMER_NAMES)}{random.randint(1, 999)}"
        
        # 生成完整URL
        url = f"{platform_url}{streamer_id}"
        
        # 随机选择视频质量
        quality = random.choice(QUALITY_OPTIONS)
        
        # 随机决定是否启用分段录制
        segment_record = random.choice([True, False])
        segment_time = random.randint(10, 60) if segment_record else 30
        
        # 随机决定监控状态
        monitor_status = random.choice([True, False])
        
        # 随机决定是否启用定时录制
        scheduled_recording = random.choice([True, False])
        
        # 随机生成定时录制时间
        hour = random.randint(0, 23)
        minute = random.randint(0, 59)
        scheduled_start_time = f"{hour:02d}:{minute:02d}:00"
        
        # 随机监控小时数
        monitor_hours = random.randint(1, 12)
        
        # 生成唯一ID
        rec_id = str(uuid.uuid4())
        
        # 创建录制目录
        recording_dir = os.path.join(self.base_recording_dir, rec_id)
        
        # 随机决定是否启用消息推送
        enabled_message_push = random.choice([True, False])
        
        # 随机录制模式
        record_mode = random.choice(["auto", "manual"])
        
        # 随机备注
        remark_options = [
            "高质量直播",
            "定期开播",
            "精彩内容",
            "热门主播",
            "新人推荐",
            "正在崛起",
            "偶尔掉线",
            "重点关注",
            "优质内容",
            "互动很好",
            "画质清晰",
            "特别收藏"
        ]
        
        # 创建Recording对象
        recording = Recording(
            rec_id=rec_id,
            url=url,
            streamer_name=streamer_name,
            record_format=random.choice(["mp4", "ts", "mkv", "flv", "webm", "m3u8"]),
            quality=quality,
            segment_record=segment_record,
            segment_time=segment_time,
            monitor_status=monitor_status,
            scheduled_recording=scheduled_recording,
            scheduled_start_time=scheduled_start_time,
            monitor_hours=monitor_hours,
            recording_dir=recording_dir,
            enabled_message_push=enabled_message_push,
            record_mode=record_mode,
            remark=random.choice(remark_options) if random.random() > 0.3 else None  # 70%概率有备注
        )
        
        # 随机设置直播状态
        recording.is_live = random.choice([True, False])
        
        # 如果是直播中，随机设置是否正在录制
        if recording.is_live:
            recording.recording = random.choice([True, False])
            
            # 如果正在录制，设置开始时间和速度
            if recording.recording:
                recording.start_time = datetime.now() - timedelta(minutes=random.randint(5, 120))
                recording.speed = f"{random.randint(500, 10000)} KB/s"
                recording.cumulative_duration = timedelta(seconds=random.randint(60, 3600))
                recording.status_info = RecordingStatus.RECORDING
            else:
                # 直播中但未录制
                recording.status_info = RecordingStatus.NOT_RECORDING
        else:
            # 未开播
            recording.recording = False
            if monitor_status:
                recording.status_info = RecordingStatus.MONITORING
            else:
                recording.status_info = RecordingStatus.STOPPED_MONITORING
        
        # 随机设置直播标题
        recording.live_title = f"{''.join(random.sample(STREAMER_NAMES, 3))}直播间"
        
        # 随机添加一些特殊状态
        if not recording.recording and random.random() < 0.2:  # 20%概率出现特殊状态
            status_options = [
                RecordingStatus.RECORDING_ERROR,
                RecordingStatus.LIVE_STATUS_CHECK_ERROR,
                RecordingStatus.STATUS_CHECKING,
                RecordingStatus.NOT_IN_SCHEDULED_CHECK,
                RecordingStatus.PREPARING_RECORDING,
                RecordingStatus.NOT_RECORDING_SPACE
            ]
            recording.status_info = random.choice(status_options)
        
        return recording

    async def generate_recordings(self, count):
        """生成指定数量的随机Recording对象"""
        self.recordings = []
        for _ in range(count):
            recording = self.generate_random_recording()
            self.recordings.append(recording)
        
        return self.recordings

    async def add_recordings_to_app(self):
        """将生成的Recording对象添加到应用中"""
        if not self.recordings:
            logger.error("没有生成的Recording对象")
            return
            
        # 获取应用的record_manager
        record_manager = self.app.record_manager
        
        # 清空现有的recordings
        record_manager.recordings.clear()
        
        # 添加生成的recordings
        import app.core.record_manager as rm
        rm.GlobalRecordingState.recordings = self.recordings.copy()
        
        # 保存到配置
        await record_manager.persist_recordings()
        
        # 发布添加卡片的消息
        for recording in self.recordings:
            self.app.page.pubsub.send_all(recording)
            
        logger.info(f"成功添加 {len(self.recordings)} 个虚拟直播间")

    async def run_stress_test(self, count):
        """运行压力测试"""
        start_time = time.time()
        
        logger.info(f"开始生成 {count} 个虚拟直播间...")
        await self.generate_recordings(count)
        
        generation_time = time.time() - start_time
        logger.info(f"生成完成，耗时: {generation_time:.2f}秒")
        
        logger.info("开始添加虚拟直播间到应用...")
        add_start_time = time.time()
        await self.add_recordings_to_app()
        
        add_time = time.time() - add_start_time
        logger.info(f"添加完成，耗时: {add_time:.2f}秒")
        
        total_time = time.time() - start_time
        logger.info(f"压力测试完成，总耗时: {total_time:.2f}秒")
        
        return {
            "total_time": total_time,
            "generation_time": generation_time,
            "add_time": add_time,
            "count": count
        }


def generate_url_list(count, output_file=None, include_quality=True):
    """
    生成指定数量的虚拟URL地址并保存到文件
    
    Args:
        count: 要生成的URL数量
        output_file: 输出文件路径，如果为None则输出到控制台
        include_quality: 是否包含质量信息，格式: "0,URL,主播名"
    """
    url_list = []
    
    for i in range(count):
        # 随机选择平台
        platform_url, platform_key = random.choice(PLATFORMS)
        
        # 生成随机主播ID和名称
        streamer_id = str(random.randint(10000, 999999))
        streamer_prefix = random.choice(STREAMER_PREFIXES)
        streamer_name = f"{streamer_prefix}{random.choice(STREAMER_NAMES)}{random.randint(1, 999)}"
        
        # 生成完整URL
        url = f"{platform_url}{streamer_id}"
        
        # 随机选择视频质量编号
        quality_num = str(random.randint(0, 4))
        
        if include_quality:
            # 格式: "0,URL,主播名"
            url_entry = f"{quality_num},{url},{streamer_name}"
        else:
            # 只包含URL
            url_entry = url
            
        url_list.append(url_entry)
    
    # 如果指定了输出文件，则写入文件
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(url_list))
        print(f"已生成 {count} 个URL地址并保存到: {output_file}")
    else:
        # 否则输出到控制台
        print("\n".join(url_list))
    
    return url_list


def generate_duplicate_test_cases(output_file=None):
    """
    生成用于测试重复检测的URL测试用例
    
    Args:
        output_file: 输出文件路径，如果为None则输出到控制台
    """
    test_cases = []
    
    # 1. 生成一些正常的URL作为基础
    base_cases = generate_url_list(10, None, True)
    test_cases.extend(base_cases)
    test_cases.append("\n# 以下是 URL完全相同 的测试用例")
    
    # 2. 生成URL完全相同的测试用例（duplicate_reason_identical_url）
    for i in range(3):
        # 随机选择一个已有的URL条目
        original_entry = random.choice(base_cases)
        test_cases.append(original_entry)  # 直接添加相同的URL条目
        
    test_cases.append("\n# 以下是 同平台同名主播 的测试用例")
    
    # 3. 生成同平台同名主播的测试用例（duplicate_reason_same_streamer）
    platform_test_cases = []
    for platform_url, platform_key in PLATFORMS[:5]:  # 只用前几个平台做测试
        # 为每个平台创建一个固定主播名
        streamer_name = f"测试主播{platform_key}"
        
        # 生成3个不同ID但相同主播名的URL
        for i in range(3):
            streamer_id = str(random.randint(10000, 999999))
            url = f"{platform_url}{streamer_id}"
            quality_num = "0"  # 使用原画质量
            url_entry = f"{quality_num},{url},{streamer_name}"
            platform_test_cases.append(url_entry)
    
    test_cases.extend(platform_test_cases)
    test_cases.append("\n# 以下是 同平台房间ID相同 的测试用例")
    
    # 4. 生成同平台房间ID相同的测试用例（duplicate_reason_same_room_id）
    # 这里我们使用不同的URL格式但实际指向相同ID
    room_id_test_cases = []
    for platform_url, platform_key in PLATFORMS[:5]:  # 只用前几个平台做测试
        room_id = str(random.randint(10000, 999999))
        
        # 为同一个房间ID创建3个不同格式的URL
        base_url = f"{platform_url}{room_id}"
        
        # 变体1：基本URL
        url_entry1 = f"0,{base_url},主播{room_id}A"
        
        # 变体2：添加参数
        url_entry2 = f"1,{base_url}?param=value,主播{room_id}B"
        
        # 变体3：添加锚点
        url_entry3 = f"2,{base_url}#anchor,主播{room_id}C"
        
        room_id_test_cases.extend([url_entry1, url_entry2, url_entry3])
    
    test_cases.extend(room_id_test_cases)
    
    # 5. 添加一个完整的测试场景说明
    test_cases.insert(0, "# StreamCap 批量添加URL测试用例")
    test_cases.insert(1, "# 包含：普通URL、URL完全相同、同平台同名主播、同平台房间ID相同")
    test_cases.insert(2, "# 格式：质量编号(0-4),直播间URL,主播名称")
    test_cases.insert(3, "# 说明：0=原画, 1=超清, 2=高清, 3=标清, 4=流畅\n")
    
    # 如果指定了输出文件，则写入文件
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(test_cases))
        print(f"已生成重复测试用例并保存到: {output_file}")
    else:
        # 否则输出到控制台
        print("\n".join(test_cases))
    
    return test_cases


def generate_platform_duplicate_tests(platform_key, output_file=None):
    """
    生成特定平台的重复URL测试用例
    
    Args:
        platform_key: 平台标识，如"bilibili", "douyu", "douyin", "kuaishou"等
        output_file: 输出文件路径，如果为None则输出到控制台
    """
    test_cases = []
    platform_map = {p[1]: p[0] for p in PLATFORMS}
    
    if platform_key not in platform_map:
        print(f"不支持的平台: {platform_key}")
        print(f"请使用 -l/--list-platforms 参数查看支持的平台列表")
        return []
    
    platform_url = platform_map[platform_key]
    test_cases.append(f"# {platform_key} 平台URL重复测试用例")
    test_cases.append(f"# 包含：普通URL、URL完全相同、同平台同名主播、同平台房间ID相同")
    test_cases.append("# 格式：质量编号(0-4),直播间URL,主播名称")
    test_cases.append("# 说明：0=原画, 1=超清, 2=高清, 3=标清, 4=流畅\n")
    
    # 基本测试用例 - 每种平台生成5个基本URL
    base_cases = []
    for i in range(5):
        room_id = str(random.randint(10000, 999999))
        streamer_name = f"{platform_key}主播{i+1}"
        url = f"{platform_url}{room_id}"
        quality_num = "0"  # 使用原画质量
        url_entry = f"{quality_num},{url},{streamer_name}"
        base_cases.append(url_entry)
    
    test_cases.extend(base_cases)
    test_cases.append("\n# URL完全相同")
    
    # URL完全相同测试
    duplicate_url = random.choice(base_cases)
    test_cases.append(duplicate_url)
    test_cases.append(duplicate_url)
    
    test_cases.append("\n# 同平台同名主播")
    
    # 同平台同名主播测试
    streamer_name = f"重复主播{platform_key}"
    for i in range(3):
        room_id = str(random.randint(10000, 999999))
        url = f"{platform_url}{room_id}"
        quality_num = str(random.randint(0, 2))  # 使用不同质量
        url_entry = f"{quality_num},{url},{streamer_name}"
        test_cases.append(url_entry)
    
    test_cases.append("\n# 同平台房间ID相同 - 不同URL格式")
    
    # 根据不同平台生成特定的URL格式
    room_id = str(random.randint(100000, 999999))
    
    if platform_key == "bilibili":
        # bilibili直播间格式变体
        test_cases.append(f"0,https://live.bilibili.com/{room_id},B站主播A")
        test_cases.append(f"1,https://live.bilibili.com/h5/{room_id},B站主播B")
        test_cases.append(f"2,https://live.bilibili.com/{room_id}?visit_id=123456,B站主播C")
        
    elif platform_key == "douyu":
        # 斗鱼直播间格式变体
        test_cases.append(f"0,https://www.douyu.com/{room_id},斗鱼主播A")
        test_cases.append(f"1,https://www.douyu.com/room/{room_id},斗鱼主播B")
        test_cases.append(f"2,https://www.douyu.com/{room_id}?rid={room_id},斗鱼主播C")
        
    elif platform_key == "douyin":
        # 抖音直播间格式变体
        test_cases.append(f"0,https://live.douyin.com/{room_id},抖音主播A")
        test_cases.append(f"1,https://v.douyin.com/{room_id},抖音主播B")  # 短链接
        test_cases.append(f"2,https://live.douyin.com/{room_id}?enter_from=main_page,抖音主播C")
        
    elif platform_key == "kuaishou":
        # 快手直播间格式变体
        test_cases.append(f"0,https://live.kuaishou.com/{room_id},快手主播A")
        test_cases.append(f"1,https://live.kuaishou.com/u/{room_id},快手主播B")
        test_cases.append(f"2,https://v.kuaishou.com/{room_id},快手主播C")  # 短链接
        
    elif platform_key == "huya":
        # 虎牙直播间格式变体
        test_cases.append(f"0,https://www.huya.com/{room_id},虎牙主播A")
        test_cases.append(f"1,https://www.huya.com/{room_id}/,虎牙主播B")
        test_cases.append(f"2,https://www.huya.com/{room_id}?huya_abc=123,虎牙主播C")
    
    elif platform_key == "yy":
        # YY直播间格式变体
        test_cases.append(f"0,https://yy.com/{room_id},YY主播A")
        test_cases.append(f"1,https://www.yy.com/{room_id},YY主播B")
        test_cases.append(f"2,https://www.yy.com/s/{room_id},YY主播C")
    
    elif platform_key == "netease_cc":
        # 网易CC直播间格式变体
        test_cases.append(f"0,https://cc.163.com/{room_id},网易CC主播A")
        test_cases.append(f"1,https://cc.163.com/{room_id}/,网易CC主播B")
        test_cases.append(f"2,https://cc.163.com/{room_id}?param=value,网易CC主播C")
    
    elif platform_key == "xiaohongshu":
        # 小红书直播间格式变体
        test_cases.append(f"0,https://www.xiaohongshu.com/user/profile/{room_id},小红书主播A")
        test_cases.append(f"1,https://www.xiaohongshu.com/{room_id},小红书主播B")
        test_cases.append(f"2,https://xhslink.com/{room_id},小红书主播C")
    
    elif platform_key == "twitch":
        # Twitch直播间格式变体
        test_cases.append(f"0,https://www.twitch.tv/{room_id},Twitch主播A")
        test_cases.append(f"1,https://twitch.tv/{room_id}/,Twitch主播B")
        test_cases.append(f"2,https://m.twitch.tv/{room_id},Twitch主播C")
        
    elif platform_key == "youtube":
        # YouTube直播间格式变体
        vid_id = f"{room_id[:6]}{random.choice(['AB','CD','EF'])}"
        test_cases.append(f"0,https://www.youtube.com/watch?v={vid_id},YouTube主播A")
        test_cases.append(f"1,https://youtu.be/{vid_id},YouTube主播B")
        test_cases.append(f"2,https://www.youtube.com/watch?v={vid_id}&feature=live,YouTube主播C")
    
    else:
        # 通用格式变体
        test_cases.append(f"0,{platform_url}{room_id},平台主播A")
        test_cases.append(f"1,{platform_url}{room_id}?param=value,平台主播B")
        test_cases.append(f"2,{platform_url}{room_id}#anchor,平台主播C")
    
    # 添加更多URL格式变体的测试
    test_cases.append("\n# 更多URL格式变体测试")
    room_id2 = str(random.randint(100000, 999999))
    
    if platform_key == "bilibili":
        test_cases.append(f"0,https://live.bilibili.com/{room_id2},B站变体测试A")
        test_cases.append(f"1,https://space.bilibili.com/{room_id2}/live,B站变体测试B")  # 用户空间直播页
        test_cases.append(f"2,https://live.bilibili.com/blanc/{room_id2},B站变体测试C")  # 特殊版式
    
    elif platform_key == "douyin":
        nickname = f"user{room_id2}"
        test_cases.append(f"0,https://live.douyin.com/{room_id2},抖音变体测试A")
        test_cases.append(f"1,https://live.douyin.com/@{nickname},抖音变体测试B")  # @用户名格式
        test_cases.append(f"2,https://www.douyin.com/user/{nickname}/live,抖音变体测试C")  # 用户页面直播
    
    # 如果指定了输出文件，则写入文件
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(test_cases))
        print(f"已生成 {platform_key} 平台重复测试用例并保存到: {output_file}")
    else:
        # 否则输出到控制台
        print("\n".join(test_cases))
    
    return test_cases


async def run_test(app, count):
    """运行测试并返回结果"""
    stress_test = StressTest(app)
    result = await stress_test.run_stress_test(count)
    return result


def list_supported_platforms():
    """列出所有支持的平台"""
    print("支持的平台列表:")
    print("=" * 50)
    print(f"{'平台名称':<15} {'平台URL':<30}")
    print("-" * 50)
    for platform_url, platform_key in sorted(PLATFORMS, key=lambda x: x[1]):
        print(f"{platform_key:<15} {platform_url:<30}")
    return {p[1]: p[0] for p in PLATFORMS}


def main():
    parser = argparse.ArgumentParser(description="StreamCap 压力测试与测试数据生成工具")
    parser.add_argument("-c", "--count", type=int, default=200, help="要生成的虚拟直播间数量，默认为200")
    parser.add_argument("-w", "--web", action="store_true", help="以Web模式运行")
    parser.add_argument("-g", "--generate-urls", action="store_true", help="生成URL列表而不是运行压力测试")
    parser.add_argument("-d", "--duplicate-test", action="store_true", help="生成重复检测测试用例")
    parser.add_argument("-o", "--output", type=str, help="输出文件路径")
    parser.add_argument("-q", "--quality", action="store_true", default=True, help="包含质量信息和主播名称")
    parser.add_argument("-p", "--platform", type=str, help="为特定平台生成重复测试用例，例如：bilibili, douyu, douyin, kuaishou")
    parser.add_argument("-l", "--list-platforms", action="store_true", help="列出所有支持的平台")
    args = parser.parse_args()
    
    # 显示帮助信息
    if len(sys.argv) == 1:
        parser.print_help()
        print("\n使用示例:")
        print("  1. 运行压力测试生成100个虚拟直播间: python test_stress_load.py -c 100")
        print("  2. 以Web模式运行压力测试: python test_stress_load.py -c 50 -w")
        print("  3. 生成50个URL地址并保存到文件: python test_stress_load.py -g -c 50 -o urls.txt")
        print("  4. 生成重复检测测试用例: python test_stress_load.py -d -o duplicate_tests.txt")
        print("  5. 生成B站特定的重复测试用例: python test_stress_load.py -p bilibili -o bilibili_tests.txt")
        print("  6. 列出支持的平台: python test_stress_load.py -l")
        return
    
    # 显示平台列表
    if args.list_platforms:
        list_supported_platforms()
        return
    
    # 处理生成特定平台重复测试用例的情况
    if args.platform:
        generate_platform_duplicate_tests(args.platform, args.output)
        return
    
    # 处理生成URL列表的情况
    if args.generate_urls:
        generate_url_list(args.count, args.output, args.quality)
        return
        
    # 处理生成重复测试用例的情况
    if args.duplicate_test:
        generate_duplicate_test_cases(args.output)
        return
    
    async def main_async(page: ft.Page):
        page.title = "StreamCap 压力测试"
        
        # 创建一个简单的UI来显示测试结果
        title = ft.Text("StreamCap 压力测试工具", size=24, weight=ft.FontWeight.BOLD)
        description = ft.Text(f"将生成 {args.count} 个虚拟直播间卡片，测试界面性能")
        
        progress = ft.ProgressBar(width=400, visible=False)
        status_text = ft.Text("准备测试...", size=16)
        
        result_container = ft.Container(
            content=ft.Column([
                ft.Text("测试结果将在这里显示", italic=True)
            ]),
            padding=10,
            border=ft.border.all(1, ft.colors.GREY_400),
            border_radius=5,
            visible=False
        )
        
        async def start_test(_):
            nonlocal page
            
            # 显示进度条
            progress.visible = True
            status_text.value = "正在初始化应用..."
            page.update()
            
            # 导入App类并创建实例
            from app.app_manager import App
            app = App(page)
            
            # 更新状态
            status_text.value = "正在运行压力测试..."
            page.update()
            
            # 运行测试
            result = await run_test(app, args.count)
            
            # 显示结果
            result_container.content = ft.Column([
                ft.Text("测试结果", weight=ft.FontWeight.BOLD, size=18),
                ft.Text(f"生成的虚拟直播间数量: {result['count']}"),
                ft.Text(f"生成耗时: {result['generation_time']:.2f}秒"),
                ft.Text(f"添加到UI耗时: {result['add_time']:.2f}秒"),
                ft.Text(f"总耗时: {result['total_time']:.2f}秒"),
                ft.Text(f"平均每个直播间处理时间: {(result['total_time'] / result['count']) * 1000:.2f}毫秒")
            ])
            
            # 更新UI
            progress.visible = False
            result_container.visible = True
            status_text.value = "测试完成!"
            page.update()
        
        # 创建开始测试按钮
        start_button = ft.ElevatedButton("开始测试", on_click=start_test)
        
        # 添加组件到页面
        page.add(
            ft.Column([
                title,
                description,
                ft.Container(height=20),
                start_button,
                ft.Container(height=10),
                progress,
                status_text,
                ft.Container(height=20),
                result_container
            ], spacing=10, alignment=ft.MainAxisAlignment.CENTER)
        )
    
    # 启动应用
    ft.app(target=main_async, view=ft.AppView.WEB if args.web else ft.AppView.FLET_APP)


if __name__ == "__main__":
    main() 