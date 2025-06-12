import asyncio
import os
import sys
import time
import argparse

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.messages.notification_service import NotificationService
from app.core.config_manager import ConfigManager


async def test_multiple_notifications(test_mode=None):
    """测试多条Windows通知是否能够同时显示
    
    Args:
        test_mode: 测试模式，1=直接通知测试，2=队列通知测试，None=全部测试
    """
    if sys.platform != "win32":
        print("此测试脚本仅适用于Windows系统")
        return

    # 测试不同平台的图标
    platforms = ["youtube", "bilibili", "douyin", "tiktok", "twitch"]
    
    print("开始测试多条Windows通知...")
    
    # 测试1：连续发送5条通知，不添加延迟
    if test_mode is None or test_mode == 1:
        print("\n测试1：连续发送5条通知，不使用队列")
        # 初始化通知服务
        notifier = NotificationService()
        
        for i, platform in enumerate(platforms):
            # 构建图标路径
            ico_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "assets", "icons", "icoplatforms", f"{platform}.ico"
            )
            
            # 检查图标是否存在
            if not os.path.exists(ico_path):
                print(f"警告：图标文件不存在 - {ico_path}")
                ico_path = ""
            
            # 发送通知
            title = f"测试通知 {i+1} - {platform}"
            content = f"{platform} 直播开始了！这是测试消息 {i+1}"
            
            print(f"发送通知：{title}")
            result = notifier.send_to_windows(
                title=title,
                content=content,
                icon_path=ico_path
            )
            
            if result.get("success"):
                print(f"通知发送成功：{title}")
            else:
                print(f"通知发送失败：{result.get('error')}")
        
        # 等待所有通知显示完毕
        if test_mode == 1:
            print("等待5秒...")
            await asyncio.sleep(5)
            print("\n测试1完成！")
        else:
            await asyncio.sleep(5)
    
    # 测试2：使用MessagePusher类的队列机制发送通知
    if test_mode is None or test_mode == 2:
        print("\n测试2：使用MessagePusher的队列机制发送通知")
        
        # 初始化配置管理器
        config_manager = ConfigManager(os.path.dirname(os.path.abspath(__file__)))
        config_manager.user_config = {"windows_notify_enabled": True}
        
        # 动态导入MessagePusher
        from app.messages.message_pusher import MessagePusher
        
        # 初始化MessagePusher
        pusher = MessagePusher(config_manager)
        
        # 清空已发送消息记录，确保测试消息不会被去重
        MessagePusher._sent_messages.clear()
        
        # 发送5条测试通知
        tasks = []
        for i, platform in enumerate(platforms):
            title = f"队列通知 {i+1} - {platform}"
            content = f"{platform} 直播开始了！这是队列测试消息 {i+1}"
            
            print(f"添加通知到队列：{title}")
            # 将消息添加到队列中，不等待每个消息的处理
            await pusher.push_messages(title, content, platform)
        
        # 让队列处理程序有机会启动并处理消息
        print("等待队列处理...")
        await asyncio.sleep(2)
        
        # 等待所有通知任务完成显示
        print("等待通知显示完成...")
        await asyncio.sleep(10)
        
        print("\n测试2完成！")
    
    print("\n所有测试完成！")


if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="测试Windows通知功能")
    parser.add_argument(
        "--mode", 
        type=int, 
        choices=[1, 2],
        help="测试模式：1=直接通知测试，2=队列通知测试，不指定=全部测试"
    )
    args = parser.parse_args()

    # 运行测试
    asyncio.run(test_multiple_notifications(args.mode)) 