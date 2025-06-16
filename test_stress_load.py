#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
StreamCap 压力测试脚本
用于生成大量虚拟直播间卡片，测试界面切换和刷新时的性能表现
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


async def run_test(app, count):
    """运行测试并返回结果"""
    stress_test = StressTest(app)
    result = await stress_test.run_stress_test(count)
    return result


def main():
    parser = argparse.ArgumentParser(description="StreamCap 压力测试工具")
    parser.add_argument("-c", "--count", type=int, default=200, help="要生成的虚拟直播间数量，默认为200")
    parser.add_argument("-w", "--web", action="store_true", help="以Web模式运行")
    args = parser.parse_args()
    
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