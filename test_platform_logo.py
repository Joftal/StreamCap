#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试平台logo显示功能
测试各种平台的logo显示表现，包括正常情况、解析错误、解析失败和不支持平台等场景
"""

import asyncio
import os
import sys
import uuid
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import flet as ft

from app.app_manager import App
from app.core.platform_handlers import get_platform_info
from app.models.recording_model import Recording
from app.utils.logger import logger


# 测试用的直播间URL，包括各种平台
TEST_URLS = {
    "主流平台": [
        {"name": "抖音", "url": "https://live.douyin.com/74401479302"},
        {"name": "TikTok", "url": "https://www.tiktok.com/@tiktok/live"},
        {"name": "快手", "url": "https://live.kuaishou.com/u/3xjvaphgm2sqm2y"},
        {"name": "虎牙", "url": "https://www.huya.com/243547"},
        {"name": "斗鱼", "url": "https://www.douyu.com/topic/wzry"},
        {"name": "YY", "url": "https://www.yy.com/22490906/22490906"},
        {"name": "B站", "url": "https://live.bilibili.com/21852"},
        {"name": "小红书", "url": "https://www.xiaohongshu.com/user/profile/5ff0e6a1000000000101d84a"},
        {"name": "微博", "url": "https://weibo.com/l/wblive/p/show/1022:2321325026370190442592"},
    ],
    "国际平台": [
        {"name": "YouTube", "url": "https://www.youtube.com/watch?v=cS6zS5hi1w0"},
        {"name": "Twitch", "url": "https://www.twitch.tv/shroud"},
        {"name": "TwitCasting", "url": "https://twitcasting.tv/c:aikatsu_anime"},
        {"name": "Bigo", "url": "https://www.bigo.tv/cn/17936171"},
    ],
    "韩国平台": [
        {"name": "SOOP", "url": "https://sooplive.co.kr/on-air"},
        {"name": "TtingLive", "url": "https://www.ttinglive.com/channels/52406/live"},
        {"name": "PopkonTV", "url": "https://popkontv.com/index.php"},
        {"name": "WinkTV", "url": "https://www.winktv.co.kr/"},
        {"name": "CHZZK", "url": "https://chzzk.naver.com/live/35e4d91b15a11380a5c59db212e0cb5b"},
        {"name": "PandaTV", "url": "https://pandalive.co.kr/live/"},
    ],
    "其他平台": [
        {"name": "Acfun", "url": "https://live.acfun.cn/live/23682490"},
        {"name": "网易CC", "url": "https://cc.163.com/363936598/"},
        {"name": "猫耳FM", "url": "https://fm.missevan.com/live/126893"},
        {"name": "百度直播", "url": "https://live.baidu.com/"},
        {"name": "酷狗直播", "url": "https://fanxing.kugou.com/1673922023"},
        {"name": "LiveMe", "url": "https://www.liveme.com/"},
        {"name": "花椒直播", "url": "https://www.huajiao.com/user/278236915"},
        {"name": "Showroom", "url": "https://www.showroom-live.com/r/akbteamtp"},
        {"name": "映客直播", "url": "https://www.inke.cn/"},
        {"name": "音播直播", "url": "http://www.ybw1666.com/"},
        {"name": "知乎直播", "url": "https://www.zhihu.com/lives"},
        {"name": "嗨秀直播", "url": "https://www.haixiutv.com/anchor/31961"},
        {"name": "VV星球", "url": "https://www.vvxqiu.com/"},
        {"name": "17直播", "url": "https://17.live/zh-Hant/profile/r/185842"},
        {"name": "浪直播", "url": "https://www.lang.live/"},
        {"name": "漂漂直播", "url": "https://m.pp.weimipopo.com/"},
        {"name": "六间房", "url": "https://v.6.cn/"},
        {"name": "乐嗨直播", "url": "https://www.lehaitv.com/"},
    ],
    "电商平台": [
        {"name": "淘宝直播", "url": "https://tb.cn/"},
        {"name": "京东直播", "url": "https://3.cn/"},
        {"name": "Shopee直播", "url": "https://live.shopee.co.id/"},
    ],
    "游戏平台": [
        {"name": "Faceit", "url": "https://www.faceit.com/en/csgo/room/1-fb40b62c-1432-404c-b477-4e20f2f22c3b"},
    ],
    "解析错误": [
        {"name": "错误URL格式", "url": "https://www.douyin.com/invalid/url/format"},
        {"name": "不完整URL", "url": "https://www.huya.com/"},
        {"name": "缺少参数", "url": "https://live.bilibili.com/"},
    ],
    "解析失败": [
        {"name": "不存在的直播间", "url": "https://live.douyin.com/99999999999"},
        {"name": "已删除的直播间", "url": "https://www.huya.com/deleted123456"},
        {"name": "错误的房间号", "url": "https://www.douyu.com/error_room_id"},
    ],
    "不支持平台": [
        {"name": "不支持的平台", "url": "https://www.unsupported-platform.com/live/12345"},
        {"name": "未知平台", "url": "https://www.unknown-platform.xyz/stream/67890"},
        {"name": "自定义URL", "url": "rtmp://custom.stream.url/live/stream_key"},
    ],
    "特殊情况": [
        {"name": "空URL", "url": ""},
        {"name": "非HTTP协议", "url": "ftp://example.com/stream"},
        {"name": "本地文件", "url": "file:///path/to/local/file.mp4"},
        {"name": "带特殊字符", "url": "https://www.douyu.com/room/id?param=value&special=!@#$%^&*()"},
    ]
}


class LogoTestApp:
    def __init__(self):
        self.app = None
        self.page = None
        self.test_recordings = []
        self.platform_counts = {}
        self.test_results = {
            "成功": 0,
            "失败": 0,
            "未识别": 0,
            "错误": 0
        }

    async def initialize_app(self, page):
        """初始化应用"""
        self.page = page
        self.app = App(page)
        
        # 设置页面标题和主题
        page.title = "平台Logo测试工具"
        page.theme_mode = ft.ThemeMode.LIGHT
        page.padding = 20
        
        # 创建UI组件
        self.header = ft.Text("直播平台Logo测试", size=24, weight=ft.FontWeight.BOLD)
        self.description = ft.Text(
            "此工具测试各种直播平台的logo显示效果，包括正常情况、解析错误、解析失败和不支持平台等场景",
            size=14
        )
        
        self.status_text = ft.Text("准备测试...", size=16)
        self.progress_bar = ft.ProgressBar(width=600, value=0)
        self.progress_text = ft.Text("0%", size=14)
        
        # 创建一个可滚动的列表来显示结果
        results_column = ft.Column([
            ft.Text("测试结果将在这里显示", size=16, weight=ft.FontWeight.BOLD),
        ], spacing=5)
        
        # 使用ListView包装Column以支持滚动
        self.results_container = ft.Container(
            content=ft.ListView(
                controls=[results_column],
                expand=True,
            ),
            padding=10,
            border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=5,
            width=800,
            height=500,
        )
        
        self.start_button = ft.ElevatedButton(
            "开始测试",
            on_click=self.start_test,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.BLUE,
                padding=15
            )
        )
        
        # 构建页面布局
        page.add(
            ft.Column([
                self.header,
                self.description,
                ft.Divider(),
                ft.Row([self.status_text], alignment=ft.MainAxisAlignment.CENTER),
                ft.Row([self.progress_bar], alignment=ft.MainAxisAlignment.CENTER),
                ft.Row([self.progress_text], alignment=ft.MainAxisAlignment.CENTER),
                ft.Container(height=10),
                ft.Row([self.start_button], alignment=ft.MainAxisAlignment.CENTER),
                ft.Container(height=20),
                ft.Row([self.results_container], alignment=ft.MainAxisAlignment.CENTER),
            ])
        )
        
        # 确保assets/icons/platforms目录存在
        base_path = Path(__file__).parent
        platform_logo_dir = os.path.join(base_path, "assets", "icons", "platforms")
        if not os.path.exists(platform_logo_dir):
            self.status_text.value = f"错误: 平台logo目录不存在: {platform_logo_dir}"
            self.status_text.color = ft.Colors.RED
            self.page.update()
            return False
            
        default_logo_path = os.path.join(platform_logo_dir, "moren.png")
        if not os.path.exists(default_logo_path):
            self.status_text.value = f"错误: 默认logo文件不存在: {default_logo_path}"
            self.status_text.color = ft.Colors.RED
            self.page.update()
            return False
        
        return True

    async def start_test(self, e):
        """开始测试"""
        # 重置测试结果
        self.test_recordings = []
        self.platform_counts = {}
        self.test_results = {
            "成功": 0,
            "失败": 0,
            "未识别": 0,
            "错误": 0
        }
        
        # 清空结果容器
        self.results_container.content.controls = [
            ft.Text("测试进行中...", size=16, weight=ft.FontWeight.BOLD)
        ]
        
        # 禁用开始按钮
        self.start_button.disabled = True
        self.page.update()
        
        # 创建测试直播间
        await self.create_test_recordings()
        
        # 测试所有直播间的logo显示
        await self.test_all_logos()
        
        # 显示测试结果统计
        await self.show_test_summary()
        
        # 启用开始按钮
        self.start_button.disabled = False
        self.status_text.value = "测试完成!"
        self.status_text.color = ft.Colors.GREEN
        self.page.update()

    async def create_test_recordings(self):
        """创建测试用的直播间记录"""
        total_urls = sum(len(urls) for urls in TEST_URLS.values())
        processed = 0
        
        self.status_text.value = "创建测试直播间..."
        self.page.update()
        
        for category, urls in TEST_URLS.items():
            for url_info in urls:
                # 创建测试直播间记录
                rec_id = str(uuid.uuid4())
                recording = Recording(
                    rec_id=rec_id,
                    url=url_info["url"],
                    streamer_name=f"{category}-{url_info['name']}",
                    record_format="TS",
                    quality="OD",
                    segment_record=False,
                    segment_time="1800",
                    monitor_status=True,
                    scheduled_recording=False,
                    scheduled_start_time=None,
                    monitor_hours=None,
                    recording_dir=None,
                    enabled_message_push=False,
                    record_mode="auto"
                )
                
                # 添加到测试列表
                self.test_recordings.append({
                    "recording": recording,
                    "category": category,
                    "name": url_info["name"],
                    "url": url_info["url"],
                    "platform_info": None,
                    "logo_path": None,
                    "status": "待测试"
                })
                
                # 更新进度
                processed += 1
                progress = processed / total_urls
                self.progress_bar.value = progress
                self.progress_text.value = f"{int(progress * 100)}%"
                self.page.update()
                
                # 避免UI冻结
                await asyncio.sleep(0.01)
        
        self.status_text.value = f"已创建 {len(self.test_recordings)} 个测试直播间"
        self.page.update()

    async def test_all_logos(self):
        """测试所有直播间的logo显示"""
        self.status_text.value = "测试平台logo显示..."
        self.page.update()
        
        total = len(self.test_recordings)
        processed = 0
        
        for test_item in self.test_recordings:
            recording = test_item["recording"]
            
            try:
                # 获取平台信息
                platform_name, platform_key = get_platform_info(recording.url)
                test_item["platform_info"] = (platform_name, platform_key)
                
                # 记录平台统计
                if platform_key:
                    self.platform_counts[platform_key] = self.platform_counts.get(platform_key, 0) + 1
                
                # 获取logo路径
                if platform_key:
                    logo_path = self.app.platform_logo_cache.get_logo_path(recording.rec_id, platform_key)
                    test_item["logo_path"] = logo_path
                    
                    # 检查logo文件是否存在
                    if logo_path and os.path.exists(logo_path):
                        test_item["status"] = "成功"
                        self.test_results["成功"] += 1
                    else:
                        test_item["status"] = "失败"
                        self.test_results["失败"] += 1
                else:
                    test_item["status"] = "未识别"
                    self.test_results["未识别"] += 1
            except Exception as e:
                logger.error(f"测试出错: {str(e)}")
                test_item["status"] = "错误"
                test_item["error"] = str(e)
                self.test_results["错误"] += 1
            
            # 更新进度
            processed += 1
            progress = processed / total
            self.progress_bar.value = progress
            self.progress_text.value = f"{int(progress * 100)}%"
            self.page.update()
            
            # 避免UI冻结
            await asyncio.sleep(0.01)
        
        self.status_text.value = f"已测试 {processed} 个直播间的logo显示"
        self.page.update()

    async def show_test_summary(self):
        """显示测试结果摘要"""
        # 创建结果列表
        result_items = []
        
        # 添加统计信息
        result_items.append(ft.Text("测试结果统计", size=18, weight=ft.FontWeight.BOLD))
        result_items.append(ft.Text(f"总测试数: {len(self.test_recordings)}", size=14))
        result_items.append(ft.Text(f"成功: {self.test_results['成功']}", size=14, color=ft.Colors.GREEN))
        result_items.append(ft.Text(f"失败: {self.test_results['失败']}", size=14, color=ft.Colors.RED))
        result_items.append(ft.Text(f"未识别平台: {self.test_results['未识别']}", size=14, color=ft.Colors.ORANGE))
        result_items.append(ft.Text(f"测试错误: {self.test_results['错误']}", size=14, color=ft.Colors.RED_ACCENT))
        
        result_items.append(ft.Divider())
        
        # 添加平台统计
        result_items.append(ft.Text("平台统计", size=18, weight=ft.FontWeight.BOLD))
        for platform_key, count in self.platform_counts.items():
            result_items.append(ft.Text(f"{platform_key}: {count}个", size=14))
        
        result_items.append(ft.Divider())
        
        # 添加详细测试结果
        result_items.append(ft.Text("详细测试结果", size=18, weight=ft.FontWeight.BOLD))
        
        # 准备显示所有平台的logo
        base_path = Path(__file__).parent
        platform_logo_dir = os.path.join(base_path, "assets", "icons", "platforms")
        default_logo_path = os.path.join(platform_logo_dir, "moren.png")
        
        # 按类别分组显示测试结果
        for category, urls in TEST_URLS.items():
            result_items.append(ft.Container(
                content=ft.Text(f"类别: {category}", size=16, weight=ft.FontWeight.BOLD),
                bgcolor=ft.Colors.BLUE_50,
                padding=5,
                border_radius=5,
                width=750
            ))
            
            # 找出该类别的所有测试项
            category_items = [item for item in self.test_recordings if item["category"] == category]
            
            for item in category_items:
                status_color = {
                    "成功": ft.Colors.GREEN,
                    "失败": ft.Colors.RED,
                    "未识别": ft.Colors.ORANGE,
                    "错误": ft.Colors.RED_ACCENT,
                    "待测试": ft.Colors.GREY
                }.get(item["status"], ft.Colors.GREY)
                
                platform_info = item["platform_info"]
                platform_text = f"{platform_info[0]} ({platform_info[1]})" if platform_info else "未识别"
                
                # 创建logo图像控件
                logo_img = None
                if item["logo_path"] and os.path.exists(item["logo_path"]):
                    logo_img = ft.Image(
                        src=item["logo_path"],
                        width=24,
                        height=24,
                        fit=ft.ImageFit.CONTAIN
                    )
                else:
                    # 使用默认logo或显示占位符
                    if os.path.exists(default_logo_path):
                        logo_img = ft.Image(
                            src=default_logo_path,
                            width=24,
                            height=24,
                            fit=ft.ImageFit.CONTAIN
                        )
                    else:
                        logo_img = ft.Container(
                            width=24,
                            height=24,
                            bgcolor=ft.Colors.GREY_300,
                            border_radius=5
                        )
                
                result_row = ft.Row([
                    logo_img,
                    ft.Text(item["name"], width=100),
                    ft.Text(platform_text, width=150),
                    ft.Text(item["status"], color=status_color, width=80),
                    ft.Text(os.path.basename(item["logo_path"]) if item["logo_path"] else "无", width=120),
                    ft.Text(item["url"], width=250, overflow=ft.TextOverflow.ELLIPSIS)
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER)
                
                result_items.append(result_row)
            
            # 添加分隔符
            result_items.append(ft.Container(height=10))
        
        # 展示所有可用的平台logo
        result_items.append(ft.Divider())
        result_items.append(ft.Text("所有可用的平台logo", size=18, weight=ft.FontWeight.BOLD))
        
        # 获取平台logo目录中的所有文件
        logo_files = []
        if os.path.exists(platform_logo_dir):
            logo_files = [f for f in os.listdir(platform_logo_dir) if f.endswith('.png')]
        
        # 每行显示5个logo
        logos_per_row = 5
        logo_rows = []
        current_row = []
        
        for i, logo_file in enumerate(logo_files):
            logo_path = os.path.join(platform_logo_dir, logo_file)
            platform_key = logo_file.replace('.png', '')
            
            logo_container = ft.Column([
                ft.Image(
                    src=logo_path,
                    width=40,
                    height=40,
                    fit=ft.ImageFit.CONTAIN
                ),
                ft.Text(platform_key, size=12, text_align=ft.TextAlign.CENTER)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            
            current_row.append(logo_container)
            
            if len(current_row) >= logos_per_row or i == len(logo_files) - 1:
                logo_rows.append(ft.Row(current_row, alignment=ft.MainAxisAlignment.START))
                current_row = []
        
        result_items.extend(logo_rows)
        
        # 更新结果容器
        self.results_container.content.controls = result_items
        self.page.update()


async def main(page: ft.Page):
    test_app = LogoTestApp()
    if await test_app.initialize_app(page):
        # 应用初始化成功
        pass


if __name__ == "__main__":
    ft.app(target=main) 