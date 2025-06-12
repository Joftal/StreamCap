import base64
import re
import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional
import os
import sys

import httpx

from ..utils.logger import logger

# 根据系统判断是否导入winotify
WINDOWS_NOTIFY_AVAILABLE = False
if sys.platform == "win32":
    try:
        from winotify import Notification, audio
        WINDOWS_NOTIFY_AVAILABLE = True
        logger.info("成功导入winotify库")
    except ImportError:
        logger.warning("未安装winotify库，Windows通知功能将不可用")
    except Exception as e:
        logger.error(f"导入winotify库时出错: {str(e)}")


class NotificationService:
    def __init__(self):
        self.headers = {"Content-Type": "application/json"}
        # 初始化Windows通知相关变量
        self.win_notifier_available = WINDOWS_NOTIFY_AVAILABLE

    async def _async_post(self, url: str, json_data: dict[str, Any]) -> dict[str, Any]:
        try:
            logger.info(f"发送POST请求到: {url}")
            logger.info(f"请求头: {self.headers}")
            logger.info(f"请求数据: {json_data}")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=json_data, headers=self.headers)
                status_code = response.status_code
                logger.info(f"响应状态码: {status_code}")
                
                try:
                    response_json = response.json()
                    logger.info(f"响应内容: {response_json}")
                    return response_json
                except Exception as json_error:
                    logger.error(f"解析响应JSON失败: {str(json_error)}")
                    response_text = response.text
                    logger.info(f"响应文本: {response_text}")
                    return {"error": f"解析JSON失败: {str(json_error)}", "text": response_text}
        except httpx.RequestError as req_error:
            error_msg = f"请求错误: {str(req_error)}"
            logger.error(error_msg)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"推送失败, URL: {url}, 错误信息: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}

    async def send_to_dingtalk(
        self, url: str, content: str, number: Optional[str] = None, is_atall: bool = False
    ) -> dict[str, list[str]]:
        results = {"success": [], "error": []}
        api_list = [u.strip() for u in url.replace("，", ",").split(",") if u.strip()]
        for api in api_list:
            json_data = {
                "msgtype": "text",
                "text": {"content": content},
                "at": {"atMobiles": [number] if number else [], "isAtAll": is_atall},
            }
            resp = await self._async_post(api, json_data)
            if resp.get("errcode") == 0:
                results["success"].append(api)
            else:
                results["error"].append(api)
        return results

    async def send_to_wechat(self, url: str, title: str, content: str) -> dict[str, Any]:
        results = {"success": [], "error": []}
        api_list = url.replace("，", ",").split(",") if url.strip() else []
        for api in api_list:
            json_data = {"title": title, "content": content}
            resp = await self._async_post(api, json_data)
            if resp.get("code") == 200:
                results["success"].append(api)
            else:
                results["error"].append(api)
                logger.info(f"WeChat push failed, push address: {api},  Failure message: {json_data.get('msg')}")
        return results

    @staticmethod
    async def send_to_email(
        email_host: str,
        login_email: str,
        password: str,
        sender_email: str,
        sender_name: str,
        to_email: str,
        title: str,
        content: str,
        smtp_port: str | None = None,
        open_ssl: bool = True,
    ) -> dict[str, Any]:
        receivers = to_email.replace("，", ",").split(",") if to_email.strip() else []

        try:
            message = MIMEMultipart()
            send_name = base64.b64encode(sender_name.encode("utf-8")).decode()
            message["From"] = f"=?UTF-8?B?{send_name}?= <{sender_email}>"
            message["Subject"] = Header(title, "utf-8")
            if len(receivers) == 1:
                message["To"] = receivers[0]

            t_apart = MIMEText(content, "plain", "utf-8")
            message.attach(t_apart)

            if open_ssl:
                smtp_port = smtp_port or 465
                smtp_obj = smtplib.SMTP_SSL(email_host, int(smtp_port))
            else:
                smtp_port = smtp_port or 25
                smtp_obj = smtplib.SMTP(email_host, int(smtp_port))
            smtp_obj.login(login_email, password)
            smtp_obj.sendmail(sender_email, receivers, message.as_string())
            return {"success": receivers, "error": []}
        except smtplib.SMTPException as e:
            logger.info(f"Email push failed, push email: {to_email},  Error message: {e}")
            return {"success": [], "error": receivers}

    async def send_to_telegram(self, chat_id: int, token: str, content: str) -> dict[str, Any]:
        try:
            json_data = {"chat_id": chat_id, "text": content}
            url = "https://api.telegram.org/bot" + token + "/sendMessage"
            _resp = await self._async_post(url, json_data)
            return {"success": [1], "error": []}
        except Exception as e:
            logger.info(f"Telegram push failed, chat ID: {chat_id},  Error message: {e}")
            return {"success": [], "error": [1]}

    async def send_to_bark(
        self,
        api: str,
        title: str = "message",
        content: str = "test",
        level: str = "active",
        badge: int = 1,
        auto_copy: int = 1,
        sound: str = "",
        icon: str = "",
        group: str = "",
        is_archive: int = 1,
        url: str = "",
    ) -> dict[str, Any]:
        results = {"success": [], "error": []}
        api_list = api.replace("，", ",").split(",") if api.strip() else []
        logger.info(f"Bark API列表: {api_list}")
        
        if not api_list:
            logger.error("Bark API地址为空，无法发送推送")
            return {"success": [], "error": ["API地址为空"]}
            
        for _api in api_list:
            logger.info(f"正在向Bark API发送请求: {_api}")
            json_data = {
                "title": title,
                "body": content,
                "level": level,
                "badge": badge,
                "autoCopy": auto_copy,
                "sound": sound,
                "icon": icon,
                "group": group,
                "isArchive": is_archive,
                "url": url,
            }
            try:
                logger.info(f"Bark请求数据: {json_data}")
                resp = await self._async_post(_api, json_data)
                logger.info(f"Bark响应结果: {resp}")
                
                if resp.get("code") == 200:
                    results["success"].append(_api)
                    logger.info(f"Bark推送成功: {_api}")
                else:
                    results["error"].append(_api)
                    error_msg = resp.get("message", "未知错误")
                    logger.error(f"Bark推送失败, API: {_api}, 错误信息: {error_msg}")
            except Exception as e:
                results["error"].append(_api)
                logger.error(f"Bark推送异常: {_api}, 异常信息: {str(e)}")
                
        return results

    async def send_to_ntfy(
        self,
        api: str,
        title: str = "message",
        content: str = "test",
        tags: str = "tada",
        priority: int = 3,
        action_url: str = "",
        attach: str = "",
        filename: str = "",
        click: str = "",
        icon: str = "",
        delay: str = "",
        email: str = "",
        call: str = "",
    ) -> dict[str, Any]:
        results = {"success": [], "error": []}
        api_list = api.replace("，", ",").split(",") if api.strip() else []
        tags = tags.replace("，", ",").split(",") if tags else ["partying_face"]
        actions = [{"action": "view", "label": "view live", "url": action_url}] if action_url else []
        for _api in api_list:
            server, topic = _api.rsplit("/", maxsplit=1)
            json_data = {
                "topic": topic,
                "title": title,
                "message": content,
                "tags": tags,
                "priority": priority,
                "attach": attach,
                "filename": filename,
                "click": click,
                "actions": actions,
                "markdown": False,
                "icon": icon,
                "delay": delay,
                "email": email,
                "call": call,
            }

            resp = await self._async_post(_api, json_data)
            if "error" not in resp:
                results["success"].append(_api)
            else:
                results["error"].append(_api)
                logger.info(f"Ntfy push failed, push address: {_api},  Failure message: {json_data['error']}")
        return results

    async def send_to_serverchan(
            self,
            sendkey: str,
            title: str = "message",
            content: str = "test",
            short: str = "",
            channel: int = 9,
            tags: str = "partying_face"
    ) -> dict[str, Any]:

        results = {"success": [], "error": []}
        sendkey_list = sendkey.replace("，", ",").split(",") if sendkey.strip() else []

        for key in sendkey_list:
            if key.startswith('sctp'):
                match = re.match(r'sctp(\d+)t', key)
                if match:
                    num = match.group(1)
                    url = f'https://{num}.push.ft07.com/send/{key}.send'
                else:
                    logger.error(f"Invalid sendkey format for sctp: {key}")
                    results["error"].append(key)
                    continue
            else:
                url = f'https://sctapi.ftqq.com/{key}.send'

            json_data = {
                "title": title,
                "desp": content,
                "short": short,
                "channel": channel,
                "tags": tags
            }
            resp = await self._async_post(url, json_data)
            if resp.get("code") == 0:
                results["success"].append(key)
            else:
                results["error"].append(key)
                logger.info(f"ServerChan push failed, SCKEY/SendKey: {key}, Error message: {resp.get('message')}")

        return results

    def send_to_windows(
        self,
        title: str = "StreamCap",
        content: str = "通知内容",
        icon_path: str = "",
        duration: int = 5,
        threaded: bool = True
    ) -> dict[str, Any]:
        """发送Windows系统通知"""
        results = {"success": [], "error": []}
        
        if sys.platform != "win32":
            results["error"].append("不支持的系统平台")
            return results
            
        if not self.win_notifier_available:
            results["error"].append("Windows通知功能不可用")
            return results
            
        try:
            # 尝试使用默认图标
            if not icon_path:
                # 首先尝试查找ico格式的默认图标
                possible_icons = [
                    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "icons", "icoplatforms", "moren.ico"),
                    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "icon.ico"),
                    os.path.join(os.getcwd(), "assets", "icon.ico"),
                    os.path.join(os.getcwd(), "assets", "icons", "icoplatforms", "moren.ico")
                ]
                
                for icon in possible_icons:
                    if os.path.exists(icon):
                        icon_path = icon
                        break
            else:
                # 验证指定的图标路径是否存在
                if not os.path.exists(icon_path):
                    icon_path = None
                    # 如果指定的图标不存在，尝试使用默认图标
                    possible_icons = [
                        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "icons", "icoplatforms", "moren.ico"),
                        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "icon.ico"),
                        os.path.join(os.getcwd(), "assets", "icon.ico")
                    ]
                    for icon in possible_icons:
                        if os.path.exists(icon):
                            icon_path = icon
                            break
            
            # 使用winotify库发送通知
            from winotify import Notification, audio
            import time
            
            # 生成唯一标识符，确保多个通知不会覆盖
            unique_id = f"StreamCap-{int(time.time() * 1000)}"
            
            toast = Notification(
                app_id=unique_id,  # 为每个通知生成唯一的app_id
                title=title,
                msg=content,
                icon=icon_path if icon_path else None
            )
            toast.set_audio(audio.Default, loop=False)
            toast.show()
            
            # 短暂停顿，让系统有时间显示通知
            time.sleep(0.2)
            
            results["success"].append(f"通知已发送")
            return results
        except Exception as e:
            results["error"].append(str(e))
            return results
