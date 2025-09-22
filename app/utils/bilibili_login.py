import json
import httpx
import asyncio
import base64
import qrcode
import os
import time
from io import BytesIO
from typing import Dict, Optional, Tuple, Union

class BilibiliLogin:
    """B站登录工具类，支持二维码登录获取cookie"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com',
            'Origin': 'https://www.bilibili.com'
        }
        self.session = httpx.AsyncClient(headers=self.headers)
    
    async def get_full_cookies(self) -> Dict:
        """
        获取完整的B站cookie，特别是确保能获取到buvid3
        
        Returns:
            cookie字典
        """
        try:
            # 访问B站主页获取完整cookie
            urls = [
                "https://www.bilibili.com",
                "https://live.bilibili.com",
                "https://api.bilibili.com/x/web-interface/nav"
            ]
            
            all_cookies = {}
            
            # 设置特殊的请求头，模拟浏览器访问
            special_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Origin': 'https://www.bilibili.com'
            }
            
            # 先访问一次主页，获取初始cookie
            async with httpx.AsyncClient(headers=special_headers, follow_redirects=True) as client:
                resp = await client.get("https://www.bilibili.com")
                for k, v in resp.cookies.items():
                    all_cookies[k] = v
                
                # 特别处理buvid3
                if "buvid3" not in all_cookies:
                    # 尝试从响应头中提取
                    for header_name, header_value in resp.headers.items():
                        if header_name.lower() == "set-cookie":
                            if "buvid3=" in header_value:
                                buvid3_start = header_value.find("buvid3=")
                                if buvid3_start != -1:
                                    buvid3_end = header_value.find(";", buvid3_start)
                                    if buvid3_end != -1:
                                        buvid3_value = header_value[buvid3_start+7:buvid3_end]
                                        all_cookies["buvid3"] = buvid3_value
                
                # 如果还是没有buvid3，尝试访问特定接口
                if "buvid3" not in all_cookies:
                    buvid_url = "https://api.bilibili.com/x/frontend/finger/spi"
                    buvid_resp = await client.get(buvid_url)
                    if buvid_resp.status_code == 200:
                        try:
                            buvid_data = buvid_resp.json()
                            if buvid_data.get("code") == 0 and "data" in buvid_data:
                                if "b_3" in buvid_data["data"]:
                                    all_cookies["buvid3"] = buvid_data["data"]["b_3"]
                                elif "b_4" in buvid_data["data"]:
                                    all_cookies["buvid3"] = buvid_data["data"]["b_4"]
                        except Exception as e:
                            print(f"解析buvid接口响应失败: {str(e)}")
                
                # 访问其他URL获取更多cookie
                for url in urls:
                    try:
                        resp = await client.get(url)
                        for k, v in resp.cookies.items():
                            all_cookies[k] = v
                    except Exception as e:
                        print(f"访问 {url} 失败: {str(e)}")
            
            return all_cookies
        except Exception as e:
            print(f"获取完整cookie失败: {str(e)}")
            return {}

    async def get_qrcode_data(self) -> Tuple[bool, str, str, str]:
        """
        获取二维码数据
        
        Returns:
            (成功与否, 消息, 二维码key, 二维码base64数据)
        """
        try:
            # 获取二维码
            qrcode_url = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
            qrcode_resp = await self.session.get(qrcode_url)
            qrcode_data = qrcode_resp.json()
            
            if qrcode_data["code"] != 0:
                return False, "bilibili_get_cookie_failed", "", ""
            
            # 获取二维码链接和密钥
            qrcode_url = qrcode_data["data"]["url"]
            qrcode_key = qrcode_data["data"]["qrcode_key"]
            
            # 生成二维码图片
            img = qrcode.make(qrcode_url)
            img_buffer = BytesIO()
            img.save(img_buffer, format="PNG")
            img_buffer.seek(0)
            qrcode_image_data = img_buffer.getvalue()
            
            # 转换为base64
            qrcode_base64 = base64.b64encode(qrcode_image_data).decode('utf-8')
            
            return True, "bilibili_get_cookie_success", qrcode_key, qrcode_base64
            
        except Exception as e:
            return False, "bilibili_get_cookie_failed", "", ""

    async def check_qrcode_status(self, qrcode_key: str) -> Tuple[bool, str, Dict, int]:
        """
        检查二维码状态
        
        Args:
            qrcode_key: 二维码key
            
        Returns:
            (成功与否, 消息key, cookie字典, 状态码)
        """
        try:
            # 获取初始cookie
            initial_cookies = await self.get_full_cookies()
            
            # 检查二维码状态
            poll_url = f"https://passport.bilibili.com/x/passport-login/web/qrcode/poll?qrcode_key={qrcode_key}"
            poll_resp = await self.session.get(poll_url)
            poll_data = poll_resp.json()
            
            if poll_data["code"] != 0:
                return False, "bilibili_get_cookie_failed", {}, poll_data["code"]
            
            scan_code = poll_data["data"]["code"]
            
            if scan_code == 0:
                # 扫码成功，合并所有cookie
                login_cookies = poll_resp.cookies
                
                # 再次获取完整cookie
                final_cookies = await self.get_full_cookies()
                
                # 合并所有cookie
                all_cookies = {}
                
                # 添加初始cookie
                for k, v in initial_cookies.items():
                    all_cookies[k] = v
                
                # 添加登录cookie
                for k, v in login_cookies.items():
                    all_cookies[k] = v
                
                # 添加最终cookie
                for k, v in final_cookies.items():
                    all_cookies[k] = v
                
                return True, "bilibili_get_cookie_success", all_cookies, scan_code
            else:
                # 返回当前状态
                return False, poll_data["data"].get("message", "unknown status"), {}, scan_code
                
        except Exception as e:
            return False, "bilibili_get_cookie_failed", {}, -1

    @staticmethod
    def parse_cookie_string(cookie_str: str) -> dict:
        """
        将cookie字符串解析为字典
        
        Args:
            cookie_str: cookie字符串，格式如 "key1=value1; key2=value2"
            
        Returns:
            cookie字典
        """
        if not cookie_str:
            return {}
            
        cookies = {}
        for item in cookie_str.split(';'):
            item = item.strip()
            if not item:
                continue
            if '=' not in item:
                continue
            key, value = item.split('=', 1)
            cookies[key.strip()] = value.strip()
        return cookies

    async def verify_cookies(self, cookies: Union[str, Dict]) -> Tuple[bool, str, Dict]:
        """
        验证B站cookie是否有效
        
        Args:
            cookies: cookie字符串或字典
            
        Returns:
            (是否有效, 消息key, 消息参数字典)
        """
        try:
            # 如果传入的是字符串，解析为字典
            if isinstance(cookies, str):
                cookies = self.parse_cookie_string(cookies)
            
            # 检查必要的cookie是否存在
            required_cookies = ["buvid3", "SESSDATA", "bili_jct", "DedeUserID"]
            missing_cookies = [c for c in required_cookies if c not in cookies]
            
            if missing_cookies:
                return False, "bilibili_cookie_missing_fields", {"fields": ", ".join(missing_cookies)}
            
            # 创建新的session用于验证
            async with httpx.AsyncClient(headers=self.headers, cookies=cookies) as client:
                # 调用用户信息接口验证cookie
                resp = await client.get("https://api.bilibili.com/x/web-interface/nav")
                data = resp.json()
                
                if data["code"] != 0:
                    return False, "bilibili_cookie_invalid", {"message": data.get('message', 'unknown error')}
                
                # 获取用户信息
                user_info = data["data"]
                is_login = user_info.get("isLogin", False)
                uname = user_info.get("uname", "")
                
                if not is_login:
                    return False, "bilibili_cookie_not_logged_in", {}
                
                return True, "bilibili_cookie_valid", {"username": uname}
                
        except Exception as e:
            return False, "bilibili_cookie_check_error", {"error": str(e)}

    async def close(self):
        """关闭会话"""
        await self.session.aclose() 