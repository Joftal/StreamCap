import os
import json
import asyncio
import aiohttp.web
from typing import Dict, Optional
from pathlib import Path
from .bilibili_login import BilibiliLogin

class QRCodeLoginServer:
    def __init__(self, port: int = 0):
        """
        初始化QRCode登录服务器
        
        Args:
            port: 服务器端口，0表示随机端口
        """
        self.port = port
        self.app = aiohttp.web.Application()
        self.runner = None
        self.site = None
        self.login_instance: Optional[BilibiliLogin] = None
        self.cookie_callback = None
        self.setup_routes()
        
    def setup_routes(self):
        """设置路由"""
        self.app.router.add_get('/', self.serve_html)
        self.app.router.add_get('/api/qrcode/generate', self.generate_qrcode)
        self.app.router.add_get('/api/qrcode/poll', self.poll_status)
        
    async def serve_html(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        """服务HTML页面"""
        assets_dir = Path(__file__).parent.parent.parent / 'assets'
        html_path = assets_dir / 'bilibili_login.html'
        
        if not html_path.exists():
            return aiohttp.web.Response(
                text="Login page not found",
                status=404
            )
            
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
            
        return aiohttp.web.Response(
            text=html_content,
            content_type='text/html'
        )
        
    async def generate_qrcode(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        """生成二维码"""
        if not self.login_instance:
            self.login_instance = BilibiliLogin()
            
        success, message, qrcode_key, qrcode_base64 = await self.login_instance.get_qrcode_data()
        
        return aiohttp.web.json_response({
            'success': success,
            'message': message,
            'qrcode_key': qrcode_key,
            'qrcode_base64': f"data:image/png;base64,{qrcode_base64}" if qrcode_base64 else ""
        })
        
    async def poll_status(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        """轮询登录状态"""
        if not self.login_instance:
            return aiohttp.web.json_response({
                'code': -1,
                'message': '登录会话已失效'
            })
            
        qrcode_key = request.query.get('key', '')
        if not qrcode_key:
            return aiohttp.web.json_response({
                'code': -1,
                'message': '缺少二维码key'
            })
            
        success, message, cookies, code = await self.login_instance.check_qrcode_status(qrcode_key)
        
        if success:
            # 检查必要的cookie是否都存在
            required_cookies = ["buvid3", "SESSDATA", "bili_jct", "DedeUserID"]
            missing_cookies = [c for c in required_cookies if c not in cookies]
            
            if missing_cookies:
                # 如果缺少必要cookie，返回错误状态
                return aiohttp.web.json_response({
                    'code': -2,
                    'message': f'登录成功但缺少必要的Cookie: {", ".join(missing_cookies)}'
                })
            
            # 所有必要cookie都存在，调用回调函数保存cookie
            if self.cookie_callback:
                await self.cookie_callback(cookies)
                
            return aiohttp.web.json_response({
                'code': code,
                'message': f'登录成功！已获取所有必要的Cookie'
            })
        else:
            # 返回当前状态
            status_messages = {
                86038: '二维码已失效，请刷新重试',
                86090: '已扫描，请在手机上确认登录',
                86101: '等待扫描二维码...',
                -1: '登录失败，请重试'
            }
            
            return aiohttp.web.json_response({
                'code': code,
                'message': status_messages.get(code, message)
            })
        
    async def start(self, cookie_callback=None):
        """
        启动服务器
        
        Args:
            cookie_callback: 获取到cookie时的回调函数
        """
        self.cookie_callback = cookie_callback
        self.runner = aiohttp.web.AppRunner(self.app)
        await self.runner.setup()
        self.site = aiohttp.web.TCPSite(self.runner, 'localhost', self.port)
        await self.site.start()
        
        # 获取实际使用的端口
        for sock in self.site._server.sockets:
            self.port = sock.getsockname()[1]
            break
            
        return f"http://localhost:{self.port}"
        
    async def stop(self):
        """停止服务器"""
        if self.login_instance:
            await self.login_instance.close()
            self.login_instance = None
            
        if self.site:
            await self.site.stop()
            
        if self.runner:
            await self.runner.cleanup() 