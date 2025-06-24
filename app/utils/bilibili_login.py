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
    """B站登录工具类，支持账号密码登录获取cookie"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com',
            'Origin': 'https://www.bilibili.com'
        }
        self.session = httpx.AsyncClient(headers=self.headers)
    
    async def login_by_password(self, username: str, password: str) -> Tuple[bool, str, Dict]:
        """
        通过账号密码登录B站
        
        Args:
            username: 用户名/手机号
            password: 密码
            
        Returns:
            (成功与否, 消息, cookie字典)
        """
        try:
            # 获取加密公钥和哈希
            key_hash_url = "https://passport.bilibili.com/x/passport-login/web/key"
            key_hash_resp = await self.session.get(key_hash_url)
            key_hash_data = key_hash_resp.json()
            
            if key_hash_data["code"] != 0:
                return False, f"获取登录密钥失败: {key_hash_data['message']}", {}
            
            # 获取验证码参数
            captcha_url = "https://passport.bilibili.com/x/passport-login/captcha?source=main_web"
            captcha_resp = await self.session.get(captcha_url)
            captcha_data = captcha_resp.json()
            
            if captcha_data["code"] != 0:
                return False, f"获取验证码失败: {captcha_data['message']}", {}
            
            # 登录请求
            login_url = "https://passport.bilibili.com/x/passport-login/web/login"
            login_data = {
                "source": "main_web",
                "username": username,
                "password": password,  # 实际应用中需要对密码进行加密处理
                "keep": "true",
                "token": captcha_data["data"]["token"],
                "challenge": "",
                "validate": "",
                "seccode": "",
            }
            
            login_resp = await self.session.post(login_url, data=login_data)
            login_result = login_resp.json()
            
            if login_result["code"] == 0:
                # 登录成功
                cookies = login_resp.cookies
                cookie_dict = {k: v for k, v in cookies.items()}
                cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
                return True, "登录成功", cookie_dict
            else:
                # 登录失败
                return False, f"登录失败: {login_result.get('message', '未知错误')}", {}
                
        except Exception as e:
            return False, f"登录过程出现异常: {str(e)}", {}
    
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
    
    async def login_by_qrcode(self) -> Tuple[bool, str, Dict, Optional[bytes]]:
        """
        通过二维码登录B站
        
        Returns:
            (成功与否, 消息, cookie字典, 二维码图片数据)
        """
        qrcode_path = None
        try:
            # 先获取完整的初始cookie
            initial_cookies = await self.get_full_cookies()
            
            # 确保有buvid3
            if "buvid3" not in initial_cookies:
                print("警告: 无法获取buvid3，这可能会影响登录")
            else:
                print(f"成功获取buvid3: {initial_cookies['buvid3']}")
                
                # 更新session的cookie
                for k, v in initial_cookies.items():
                    self.session.cookies.set(k, v)
            
            # 获取二维码
            qrcode_url = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
            qrcode_resp = await self.session.get(qrcode_url)
            qrcode_data = qrcode_resp.json()
            
            if qrcode_data["code"] != 0:
                return False, f"获取二维码失败: {qrcode_data['message']}", {}, None
            
            # 获取二维码链接和密钥
            qrcode_url = qrcode_data["data"]["url"]
            qrcode_key = qrcode_data["data"]["qrcode_key"]
            
            # 生成二维码图片
            img = qrcode.make(qrcode_url)
            img_buffer = BytesIO()
            img.save(img_buffer, format="PNG")
            img_buffer.seek(0)
            qrcode_image_data = img_buffer.getvalue()
            
            # 保存二维码图片到logs目录
            logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'logs')
            os.makedirs(logs_dir, exist_ok=True)
            qrcode_path = os.path.join(logs_dir, "bilibili_qrcode.png")
            with open(qrcode_path, "wb") as f:
                f.write(qrcode_image_data)
            
            # 尝试打开二维码图片
            try:
                import webbrowser
                webbrowser.open(qrcode_path)
            except:
                pass
            
            print(f"请使用B站APP扫描二维码登录 (二维码已保存到: {qrcode_path})")
            
            # 轮询检查扫码状态
            poll_url = f"https://passport.bilibili.com/x/passport-login/web/qrcode/poll?qrcode_key={qrcode_key}"
            
            for _ in range(120):  # 最多等待120秒
                await asyncio.sleep(1)
                poll_resp = await self.session.get(poll_url)
                poll_data = poll_resp.json()
                
                if poll_data["code"] != 0:
                    continue
                
                # 0: 扫码登录成功
                # 86038: 二维码已失效
                # 86090: 二维码已扫码未确认
                # 86101: 未扫码
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
                    
                    # 检查是否包含必要的cookie
                    required_cookies = ["buvid3", "SESSDATA", "bili_jct", "DedeUserID"]
                    missing_cookies = [c for c in required_cookies if c not in all_cookies]
                    
                    # 删除二维码文件
                    if qrcode_path and os.path.exists(qrcode_path):
                        try:
                            os.remove(qrcode_path)
                            print(f"二维码文件已删除: {qrcode_path}")
                        except Exception as e:
                            print(f"删除二维码文件失败: {str(e)}")
                    
                    # 如果缺少buvid3，尝试使用特殊方法获取
                    if "buvid3" in missing_cookies:
                        try:
                            # 使用指纹API获取buvid3
                            special_headers = {
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                                'Referer': 'https://www.bilibili.com/',
                                'Origin': 'https://www.bilibili.com'
                            }
                            
                            async with httpx.AsyncClient(headers=special_headers, follow_redirects=True) as client:
                                buvid_url = "https://api.bilibili.com/x/frontend/finger/spi"
                                buvid_resp = await client.get(buvid_url)
                                if buvid_resp.status_code == 200:
                                    try:
                                        buvid_data = buvid_resp.json()
                                        if buvid_data.get("code") == 0 and "data" in buvid_data:
                                            if "b_3" in buvid_data["data"]:
                                                all_cookies["buvid3"] = buvid_data["data"]["b_3"]
                                                missing_cookies.remove("buvid3")
                                                print(f"通过指纹API获取buvid3成功: {all_cookies['buvid3']}")
                                    except Exception as e:
                                        print(f"解析buvid接口响应失败: {str(e)}")
                        except Exception as e:
                            print(f"尝试获取buvid3失败: {str(e)}")
                    
                    if missing_cookies:
                        return False, f"登录成功但缺少必要的Cookie: {', '.join(missing_cookies)}", all_cookies, qrcode_image_data
                    
                    return True, "扫码登录成功", all_cookies, qrcode_image_data
                elif scan_code == 86038:
                    # 二维码失效，删除文件
                    if qrcode_path and os.path.exists(qrcode_path):
                        try:
                            os.remove(qrcode_path)
                            print(f"二维码已失效，文件已删除: {qrcode_path}")
                        except Exception as e:
                            print(f"删除二维码文件失败: {str(e)}")
                    return False, "二维码已失效", {}, qrcode_image_data
                elif scan_code == 86090:
                    print("二维码已扫描，等待确认...")
                elif scan_code == 86101:
                    pass  # 不打印等待扫码的信息，避免刷屏
            
            # 超时，删除二维码文件
            if qrcode_path and os.path.exists(qrcode_path):
                try:
                    os.remove(qrcode_path)
                    print(f"登录超时，二维码文件已删除: {qrcode_path}")
                except Exception as e:
                    print(f"删除二维码文件失败: {str(e)}")
            
            return False, "扫码登录超时", {}, qrcode_image_data
            
        except Exception as e:
            # 发生异常，删除二维码文件
            if qrcode_path and os.path.exists(qrcode_path):
                try:
                    os.remove(qrcode_path)
                    print(f"登录异常，二维码文件已删除: {qrcode_path}")
                except Exception as ex:
                    print(f"删除二维码文件失败: {str(ex)}")
            return False, f"扫码登录过程出现异常: {str(e)}", {}, None

    async def close(self):
        """关闭会话"""
        await self.session.aclose() 