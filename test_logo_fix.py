#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试logo加载功能
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from app.models.platform_logo_cache import PlatformLogoCache
from app.messages.notification_service import NotificationService
from app.utils.logger import logger

def test_platform_logo_cache():
    """测试平台logo缓存功能"""
    logger.info("开始测试平台logo缓存...")
    
    # 初始化平台logo缓存
    logo_cache = PlatformLogoCache()
    
    # 测试获取各个平台的logo
    platforms = [
        "bilibili", "douyin", "youtube", "huya", "douyu", "twitch", "tiktok"
    ]
    
    success_count = 0
    for platform in platforms:
        # 使用一个随机ID来测试
        test_id = f"test-{platform}"
        logo_path = logo_cache.get_logo_path(test_id, platform)
        
        if logo_path and os.path.exists(logo_path):
            logger.info(f"平台 {platform} logo加载成功: {logo_path}")
            success_count += 1
        else:
            logger.error(f"平台 {platform} logo加载失败")
    
    # 输出测试结果
    logger.info(f"平台logo测试完成: {success_count}/{len(platforms)} 成功")
    return success_count == len(platforms)

def test_notification_icon():
    """测试通知图标功能"""
    logger.info("开始测试通知图标...")
    
    # 初始化通知服务
    notifier = NotificationService()
    
    # 测试默认图标
    result1 = notifier.send_to_windows(
        title="测试默认图标",
        content="这是一个测试通知，使用默认图标"
    )
    
    if result1.get("success"):
        logger.info("默认图标通知发送成功")
    else:
        logger.error(f"默认图标通知发送失败: {result1.get('error')}")
    
    # 测试系统图标
    system_icon = os.path.join(
        notifier.base_path, "assets", "icons", "icoplatforms", "system.ico"
    )
    
    result2 = notifier.send_to_windows(
        title="测试系统图标",
        content="这是一个测试通知，使用系统图标",
        icon_path=system_icon
    )
    
    if result2.get("success"):
        logger.info("系统图标通知发送成功")
    else:
        logger.error(f"系统图标通知发送失败: {result2.get('error')}")
    
    # 测试平台图标
    platform_icon = os.path.join(
        notifier.base_path, "assets", "icons", "icoplatforms", "bilibili.ico"
    )
    
    result3 = notifier.send_to_windows(
        title="测试平台图标",
        content="这是一个测试通知，使用平台图标",
        icon_path=platform_icon
    )
    
    if result3.get("success"):
        logger.info("平台图标通知发送成功")
    else:
        logger.error(f"平台图标通知发送失败: {result3.get('error')}")
    
    # 输出测试结果
    success_count = sum(1 for r in [result1, result2, result3] if r.get("success"))
    logger.info(f"通知图标测试完成: {success_count}/3 成功")
    return success_count == 3

if __name__ == "__main__":
    logger.info("开始执行logo修复测试...")
    
    # 测试平台logo缓存
    platform_logo_success = test_platform_logo_cache()
    
    # 测试通知图标
    notification_icon_success = False
    if sys.platform == "win32":
        notification_icon_success = test_notification_icon()
    else:
        logger.info("非Windows平台，跳过通知图标测试")
        notification_icon_success = True
    
    # 输出总体测试结果
    if platform_logo_success and notification_icon_success:
        logger.info("所有测试通过！logo修复成功")
        print("测试成功！logo加载功能正常")
    else:
        logger.error("测试失败！logo修复不完全")
        print("测试失败！请查看日志获取详细信息") 