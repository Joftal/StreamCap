from asyncio import create_task, Queue, Task, sleep as asyncio_sleep
import time
from typing import Dict, List, Tuple
import sys
import os
from pathlib import Path

from ..utils.logger import logger
from .notification_service import NotificationService


class MessagePusher:
    # 静态队列用于存储待发送的消息
    _message_queue: Queue = Queue()
    # 标记队列处理是否已启动
    _queue_processing: bool = False
    # 跟踪已发送的消息，避免重复发送
    # 键为 "标题+内容" 的哈希，值为发送时间戳
    _sent_messages: Dict[str, float] = {}
    # 消息去重的时间窗口（秒）
    _deduplication_window: int = 30

    def __init__(self, settings=None):
        """
        初始化消息推送器
        
        :param settings: 设置对象
        """
        self.settings = settings
        self.notifier = NotificationService()
        # 获取应用程序基础路径
        self.base_path = self._get_base_path()

    def _get_base_path(self):
        """获取应用程序基础路径，考虑打包和开发环境"""
        if getattr(sys, 'frozen', False):
            # 如果是打包后的可执行文件，使用可执行文件所在目录
            base_path = os.path.dirname(sys.executable)
            # logger.info(f"消息推送服务运行在打包环境中，基础路径: {base_path}")
        else:
            # 开发环境，使用项目根目录
            base_path = Path(__file__).parent.parent.parent
            # logger.info(f"消息推送服务运行在开发环境中，基础路径: {base_path}")
        return base_path

    @classmethod
    def _get_message_hash(cls, title: str, content: str) -> str:
        """生成消息的唯一标识，用于去重"""
        return f"{title}:{content}"

    @classmethod
    async def _process_message_queue(cls):
        """处理消息队列中的所有消息"""
        if cls._queue_processing:
            return
        
        cls._queue_processing = True
        # logger.info("开始处理消息队列")
        
        try:
            while not cls._message_queue.empty():
                msg_data = await cls._message_queue.get()
                pusher, msg_title, push_content, platform_code = msg_data
                
                # 执行实际的消息推送
                await pusher._push_messages_impl(msg_title, push_content, platform_code)
                
                # 标记任务完成
                cls._message_queue.task_done()
                
                # 短暂延迟，避免过快发送消息
                await asyncio_sleep(0.5)
        except Exception as e:
            logger.error(f"处理消息队列时出错: {str(e)}")
        finally:
            cls._queue_processing = False
            # logger.info("消息队列处理完毕")

    async def push_messages(self, msg_title: str, push_content: str, platform_code: str = None):
        """将消息加入队列进行推送
        
        Args:
            msg_title: 消息标题
            push_content: 消息内容
            platform_code: 平台代码，用于显示平台图标（可选）
        """
        # logger.info(f"接收到推送请求: {msg_title}, 平台: {platform_code or '未指定'}")
        
        # 检查是否是重复消息
        msg_hash = self._get_message_hash(msg_title, push_content)
        current_time = time.time()
        
        # 清理过期的已发送消息记录
        expired_hashes = [h for h, t in self._sent_messages.items() 
                         if current_time - t > self._deduplication_window]
        for h in expired_hashes:
            self._sent_messages.pop(h, None)
        
        # 检查是否在去重窗口内已经发送过相同消息
        if msg_hash in self._sent_messages:
            # logger.info(f"跳过重复消息: {msg_title} (在{self._deduplication_window}秒内已发送)")
            return []
        
        # 记录此消息已请求发送
        self._sent_messages[msg_hash] = current_time
        
        # 将消息放入队列
        await self._message_queue.put((self, msg_title, push_content, platform_code))
        
        # 启动队列处理（如果尚未启动）
        if not self._queue_processing:
            create_task(self._process_message_queue())
            
        # 返回一个空任务列表，因为实际任务会在队列处理中创建
        # 这是为了保持API兼容性
        return []

    async def _push_messages_impl(self, msg_title: str, push_content: str, platform_code: str = None):
        """实际执行消息推送的内部方法"""
        # logger.info(f"开始推送消息: {msg_title}, 平台: {platform_code or '未指定'}")
        
        user_config = self.settings.user_config
        tasks = []
        
        if user_config.get("dingtalk_enabled"):
            webhook_url = user_config.get("dingtalk_webhook_url", "")
            if webhook_url.strip():
                # logger.info("准备推送钉钉消息")
                task = create_task(
                    self.notifier.send_to_dingtalk(
                        url=webhook_url,
                        content=push_content,
                        number=user_config.get("dingtalk_at_objects"),
                        is_atall=user_config.get("dingtalk_at_all"),
                    )
                )
                tasks.append(task)
                # logger.info("钉钉消息推送任务已创建")
            else:
                #logger.warning("钉钉推送已启用，但未配置Webhook URL")
                pass

        if user_config.get("wechat_enabled"):
            webhook_url = user_config.get("wechat_webhook_url", "")
            if webhook_url.strip():
                # logger.info("准备推送微信消息")
                task = create_task(
                    self.notifier.send_to_wechat(
                        url=webhook_url, title=msg_title, content=push_content
                    )
                )
                tasks.append(task)
                # logger.info("微信消息推送任务已创建")
            else:
                #logger.warning("微信推送已启用，但未配置Webhook URL")
                pass

        if user_config.get("bark_enabled"):
            bark_url = user_config.get("bark_webhook_url", "")
            if bark_url.strip():
                # logger.info(f"准备推送Bark消息，URL: {bark_url}")
                task = create_task(
                    self.notifier.send_to_bark(
                        api=bark_url,
                        title=msg_title,
                        content=push_content,
                        level=user_config.get("bark_interrupt_level"),
                        sound=user_config.get("bark_sound"),
                    )
                )
                tasks.append(task)
                # logger.info("Bark消息推送任务已创建")
            else:
                #logger.warning("Bark推送已启用，但未配置Webhook URL")
                pass

        if user_config.get("ntfy_enabled"):
            ntfy_url = user_config.get("ntfy_server_url", "")
            if ntfy_url.strip():
                # logger.info("准备推送Ntfy消息")
                task = create_task(
                    self.notifier.send_to_ntfy(
                        api=ntfy_url,
                        title=msg_title,
                        content=push_content,
                        tags=user_config.get("ntfy_tags"),
                        action_url=user_config.get("ntfy_action_url"),
                        email=user_config.get("ntfy_email"),
                    )
                )
                tasks.append(task)
                # logger.info("Ntfy消息推送任务已创建")
            else:
                #logger.warning("Ntfy推送已启用，但未配置Server URL")
                pass

        if user_config.get("telegram_enabled"):
            chat_id = user_config.get("telegram_chat_id")
            token = user_config.get("telegram_api_token", "")
            if chat_id and token.strip():
                # logger.info("准备推送Telegram消息")
                task = create_task(
                    self.notifier.send_to_telegram(
                        chat_id=chat_id,
                        token=token,
                        content=push_content,
                    )
                )
                tasks.append(task)
                # logger.info("Telegram消息推送任务已创建")
            else:
                #logger.warning("Telegram推送已启用，但未配置完整的Chat ID或API Token")
                pass

        if user_config.get("email_enabled"):
            email_host = user_config.get("smtp_server", "")
            login_email = user_config.get("email_username", "")
            password = user_config.get("email_password", "")
            sender_email = user_config.get("sender_email", "")
            to_email = user_config.get("recipient_email", "")
            
            if email_host.strip() and login_email.strip() and password.strip() and sender_email.strip() and to_email.strip():
                # logger.info("准备推送Email消息")
                task = create_task(
                    self.notifier.send_to_email(
                        email_host=email_host,
                        login_email=login_email,
                        password=password,
                        sender_email=sender_email,
                        sender_name=user_config.get("sender_name", "StreamCap"),
                        to_email=to_email,
                        title=msg_title,
                        content=push_content,
                    )
                )
                tasks.append(task)
                # logger.info("Email消息推送任务已创建")
            else:
                #logger.warning("Email推送已启用，但配置不完整")
                pass
        
        if user_config.get("serverchan_enabled"):
            sendkey = user_config.get("serverchan_sendkey", "")
            if sendkey.strip():
                # logger.info("准备推送ServerChan消息")
                task = create_task(
                    self.notifier.send_to_serverchan(
                        sendkey=sendkey,
                        title=msg_title,
                        content=push_content,
                    )
                )
                tasks.append(task)
                # logger.info("ServerChan消息推送任务已创建")
            else:
                #logger.warning("ServerChan推送已启用，但未配置SendKey")
                pass
        
        # 添加Windows系统通知渠道
        if user_config.get("windows_notify_enabled") and sys.platform == "win32":
            # logger.info("准备推送Windows系统通知")
            # Windows通知是同步操作，但我们使用create_task让它在异步环境中运行
            task = create_task(self._send_windows_notification(msg_title, push_content, platform_code))
            tasks.append(task)
            # logger.info("Windows系统通知任务已创建")
        
        if not tasks:
            #logger.warning("没有创建任何推送任务，可能是因为所有渠道都未启用或配置不正确")
            pass
            
        # 等待所有推送任务完成
        for task in tasks:
            try:
                await task
            except Exception as e:
                logger.error(f"执行推送任务时发生错误: {str(e)}")
        
        # logger.info(f"消息 '{msg_title}' 推送完成")
        return tasks
        
    async def _send_windows_notification(self, title: str, content: str, platform_code: str = None):
        """发送Windows系统通知的辅助方法"""
        try:
            # 使用固定默认值，不从配置中读取
            icon_path = ""  # 默认图标
            
            # 如果提供了平台代码，尝试查找对应的平台图标
            if platform_code:
                if platform_code == "system":
                    # 系统类通知使用专门的系统图标
                    system_icon_path = os.path.join(
                        self.base_path,
                        "assets", "icons", "icoplatforms", "system.ico"
                    )
                    
                    if os.path.exists(system_icon_path):
                        icon_path = system_icon_path
                        # logger.info(f"使用系统通知图标: {icon_path}")
                    else:
                        # 如果系统图标不存在，尝试使用默认图标
                        #logger.warning(f"系统通知图标不存在: {system_icon_path}，将使用默认图标")
                        pass
                else:
                    # 查找平台特定的.ico图标
                    ico_platform_path = os.path.join(
                        self.base_path,
                        "assets", "icons", "icoplatforms", f"{platform_code}.ico"
                    )
                    
                    if os.path.exists(ico_platform_path):
                        icon_path = ico_platform_path
                        # logger.info(f"找到平台ICO图标: {icon_path}")
            
            # 如果没有找到特定图标，使用默认图标
            if not icon_path:
                default_icon_path = os.path.join(
                    self.base_path,
                    "assets", "icons", "icoplatforms", "moren.ico"
                )
                
                if os.path.exists(default_icon_path):
                    icon_path = default_icon_path
                    # logger.info(f"使用默认图标: {icon_path}")
            
            # logger.info(f"准备Windows系统通知 - 标题: '{title}', 平台: {platform_code or '未指定'}, 图标路径: {icon_path or '无'}")
            
            # 调用NotificationService中的方法发送Windows通知
            result = self.notifier.send_to_windows(
                title=title,
                content=content,
                icon_path=icon_path
            )
            
            # 添加短暂延迟，确保多个通知不会重叠
            await asyncio_sleep(1.0)  # 1秒延迟，避免通知重叠
            
            if result.get("success"):
                # logger.info(f"Windows系统通知发送成功: {result.get('success')}")
                pass
            else:
                error_msgs = result.get('error', [])
                for error in error_msgs:
                    logger.warning(f"Windows系统通知发送失败: {error}")
                
            return result
        except Exception as e:
            error_msg = f"发送Windows系统通知时出错: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": [], "error": [error_msg]}
