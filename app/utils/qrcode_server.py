import os
import json
import asyncio
import aiohttp.web
import subprocess
import psutil
import sys
import time
from typing import Dict, Optional, Callable
from pathlib import Path
from .bilibili_login import BilibiliLogin
from app.utils.logger import logger

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
        self.browser_process = None
        self.browser_pid = None
        self.is_frozen = getattr(sys, 'frozen', False)  # 检查是否为打包环境
        self._is_running = False  # 添加运行状态标志
        self._is_stopping = False  # 添加停止状态标志
        self.setup_routes()
        
    def setup_routes(self):
        """设置路由"""
        self.app.router.add_get('/', self.serve_html)
        self.app.router.add_get('/api/qrcode/generate', self.generate_qrcode)
        self.app.router.add_get('/api/qrcode/poll', self.poll_status)
        self.app.router.add_get('/api/close', self.close_browser)
        
    async def serve_html(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        """服务HTML页面"""
        html_content = None
        html_path = None
        
        # 尝试多种路径查找策略
        possible_paths = []
        
        if self.is_frozen:
            # 打包环境：尝试多种可能的路径
            base_dir = Path(sys.executable).parent
            possible_paths = [
                base_dir / 'assets' / 'bilibili_login.html',
                base_dir / 'app' / 'assets' / 'bilibili_login.html',
                base_dir / 'dist' / 'assets' / 'bilibili_login.html',
                base_dir / 'build' / 'assets' / 'bilibili_login.html',
                # 尝试相对路径
                Path('assets') / 'bilibili_login.html',
                Path('app/assets') / 'bilibili_login.html',
            ]
        else:
            # 开发环境：使用原来的路径
            assets_dir = Path(__file__).parent.parent.parent / 'assets'
            possible_paths = [assets_dir / 'bilibili_login.html']
        
        # 尝试查找HTML文件
        for path in possible_paths:
            logger.info(f"尝试查找HTML文件: {path}")
            if path.exists():
                html_path = path
                logger.info(f"找到HTML文件: {html_path}")
                break
        
        if not html_path:
            # 如果找不到文件，返回内嵌的HTML内容
            logger.info("未找到HTML文件，使用内嵌内容")
            html_content = self._get_embedded_html()
        else:
            try:
                with open(html_path, encoding='utf-8') as f:
                    html_content = f.read()
                logger.info(f"成功读取HTML文件，大小: {len(html_content)} 字符")
            except Exception as e:
                logger.info(f"读取HTML文件失败: {e}")
                # 如果读取失败，使用内嵌内容
                html_content = self._get_embedded_html()
        
        if not html_content:
            return aiohttp.web.Response(
                text="Login page not found",
                status=404
            )
            
        return aiohttp.web.Response(
            text=html_content,
            content_type='text/html'
        )
    
    def _get_embedded_html(self) -> str:
        """获取内嵌的HTML内容"""
        return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>B站扫码登录</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background-color: #f6f7f8;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            text-align: center;
            max-width: 400px;
            width: 90%;
        }
        .qrcode-container {
            margin: 20px 0;
        }
        .qrcode-container img {
            max-width: 200px;
            height: auto;
        }
        .status {
            margin: 15px 0;
            padding: 10px;
            border-radius: 4px;
            font-size: 14px;
        }
        .status.waiting {
            background-color: #fff7e6;
            color: #d46b08;
        }
        .status.success {
            background-color: #f6ffed;
            color: #389e0d;
        }
        .status.error {
            background-color: #fff2f0;
            color: #cf1322;
        }
        .refresh-btn {
            background-color: #00a1d6;
            color: white;
            border: none;
            padding: 8px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            transition: background-color 0.3s;
        }
        .refresh-btn:hover {
            background-color: #0091c2;
        }
        .refresh-btn:disabled {
            background-color: #ccc;
            cursor: not-allowed;
        }
        .close-btn {
            background-color: #ff4757;
            color: white;
            border: none;
            padding: 8px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            margin-left: 10px;
            transition: background-color 0.3s;
        }
        .close-btn:hover {
            background-color: #ff3742;
        }
    </style>
</head>
<body>
    <div class="container">
        <h2>B站扫码登录</h2>
        <div class="qrcode-container">
            <img id="qrcode" src="" alt="二维码加载中...">
        </div>
        <div id="status" class="status waiting">
            请使用B站APP扫描二维码登录
        </div>
        <div>
            <button id="refreshBtn" class="refresh-btn" onclick="refreshQRCode()">刷新二维码</button>
            <button id="closeBtn" class="close-btn" onclick="closeWindow()">关闭页面</button>
        </div>
    </div>

    <script>
        let qrcodeKey = '';
        let pollTimer = null;
        let isClosing = false;

        // 页面关闭时通知服务器
        window.addEventListener('beforeunload', function(e) {
            if (!isClosing) {
                // 发送同步请求通知服务器关闭浏览器进程
                try {
                    const xhr = new XMLHttpRequest();
                    xhr.open('GET', '/api/close', false); // 同步请求
                    xhr.send();
                } catch (error) {
                    console.log('通知服务器关闭失败:', error);
                }
            }
        });

        // 页面可见性变化时也处理关闭
        document.addEventListener('visibilitychange', function() {
            if (document.visibilityState === 'hidden' && !isClosing) {
                try {
                    const xhr = new XMLHttpRequest();
                    xhr.open('GET', '/api/close', false);
                    xhr.send();
                } catch (error) {
                    console.log('通知服务器关闭失败:', error);
                }
            }
        });

        async function getQRCode() {
            try {
                const response = await fetch('/api/qrcode/generate');
                const data = await response.json();
                
                if (data.success) {
                    document.getElementById('qrcode').src = data.qrcode_base64;
                    qrcodeKey = data.qrcode_key;
                    startPolling();
                } else {
                    showError('获取二维码失败，请刷新重试');
                }
            } catch (error) {
                showError('网络错误，请检查连接后重试');
            }
        }

        async function pollQRCodeStatus() {
            try {
                const response = await fetch(`/api/qrcode/poll?key=${qrcodeKey}`);
                const data = await response.json();
                
                if (data.code === 0) {
                    // 登录成功
                    showSuccess('登录成功！页面即将关闭...');
                    stopPolling();
                    isClosing = true;
                    
                    // 立即通知服务器关闭浏览器进程
                    try {
                        await fetch('/api/close');
                        console.log('已通知服务器关闭浏览器');
                    } catch (error) {
                        console.log('通知服务器关闭失败:', error);
                    }
                    
                    // 延迟关闭，让用户看到成功消息
                    setTimeout(() => {
                        try {
                            // 尝试多种方式关闭窗口
                            if (window.opener) {
                                // 如果是弹窗，关闭当前窗口
                                window.close();
                            } else {
                                // 如果是主窗口，尝试关闭
                                window.close();
                                // 如果window.close()失败，尝试其他方法
                                setTimeout(() => {
                                    // 尝试通过location.href跳转到空白页面
                                    window.location.href = 'about:blank';
                                }, 1000);
                            }
                        } catch (error) {
                            console.log('关闭窗口失败:', error);
                            // 最后的备选方案：跳转到空白页面
                            window.location.href = 'about:blank';
                        }
                    }, 2000);
                } else if (data.code === -2) {
                    // 缺少必要cookie
                    showError(data.message);
                    stopPolling();
                } else if (data.code === 86038) {
                    // 二维码已失效
                    showError('二维码已失效，请点击刷新按钮重试');
                    stopPolling();
                } else if (data.code === 86090) {
                    // 已扫码未确认
                    document.getElementById('status').className = 'status waiting';
                    document.getElementById('status').innerText = '已扫描，请在手机上确认登录';
                } else if (data.code === 86101) {
                    // 未扫码
                    document.getElementById('status').className = 'status waiting';
                    document.getElementById('status').innerText = '请使用B站APP扫描二维码登录';
                } else {
                    // 其他错误状态
                    showError(data.message || '未知错误，请重试');
                    stopPolling();
                }
            } catch (error) {
                showError('网络错误，请检查连接后重试');
                stopPolling();
            }
        }

        function startPolling() {
            if (pollTimer) clearInterval(pollTimer);
            pollTimer = setInterval(pollQRCodeStatus, 1000);
        }

        function stopPolling() {
            if (pollTimer) {
                clearInterval(pollTimer);
                pollTimer = null;
            }
        }

        function showError(message) {
            const status = document.getElementById('status');
            status.className = 'status error';
            status.innerText = message;
        }

        function showSuccess(message) {
            const status = document.getElementById('status');
            status.className = 'status success';
            status.innerText = message;
        }

        function refreshQRCode() {
            const btn = document.getElementById('refreshBtn');
            btn.disabled = true;
            setTimeout(() => btn.disabled = false, 3000);
            
            stopPolling();
            document.getElementById('status').className = 'status waiting';
            document.getElementById('status').innerText = '正在刷新二维码...';
            getQRCode();
        }

        async function closeWindow() {
            isClosing = true;
            stopPolling();
            
            try {
                // 通知服务器关闭浏览器进程
                await fetch('/api/close');
            } catch (error) {
                console.log('通知服务器关闭失败:', error);
            }
            
            window.close();
        }

        // 初始化加载
        getQRCode();
    </script>
</body>
</html>"""
        
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
                'message': '登录成功！已获取所有必要的Cookie'
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
    
    async def close_browser(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        """关闭浏览器"""
        try:
            await self.close_browser_process()
            return aiohttp.web.json_response({
                'success': True,
                'message': '浏览器已关闭'
            })
        except Exception as e:
            return aiohttp.web.json_response({
                'success': False,
                'message': f'关闭浏览器失败: {str(e)}'
            })
        
    def _get_browser_command(self, url: str) -> list:
        """获取浏览器启动命令"""
        if sys.platform == "win32":
            # Windows平台 - 改进的浏览器检测
            browsers = [
                # 尝试常见的Chrome安装路径
                ["C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", "--new-window", "--disable-web-security", "--disable-features=VizDisplayCompositor"],
                ["C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe", "--new-window", "--disable-web-security", "--disable-features=VizDisplayCompositor"],
                # 尝试常见的Edge安装路径
                ["C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", "--new-window", "--disable-web-security"],
                ["C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe", "--new-window", "--disable-web-security"],
                # 尝试常见的Firefox安装路径
                ["C:\\Program Files\\Mozilla Firefox\\firefox.exe", "-new-window"],
                ["C:\\Program Files (x86)\\Mozilla Firefox\\firefox.exe", "-new-window"],
                # 尝试使用where命令查找
                ["chrome", "--new-window", "--disable-web-security", "--disable-features=VizDisplayCompositor"],
                ["msedge", "--new-window", "--disable-web-security"],
                ["firefox", "-new-window"],
                # 最后尝试IE
                ["iexplore"]
            ]
        elif sys.platform == "darwin":
            # macOS平台
            browsers = [
                ["open", "-a", "Google Chrome", "--args", "--new-window", "--disable-web-security"],
                ["open", "-a", "Safari"],
                ["open", "-a", "Firefox", "--args", "-new-window"]
            ]
        else:
            # Linux平台
            browsers = [
                ["google-chrome", "--new-window", "--disable-web-security"],
                ["chromium-browser", "--new-window", "--disable-web-security"],
                ["firefox", "-new-window"],
                ["xdg-open"]
            ]
        
        # 尝试找到可用的浏览器
        for browser_cmd in browsers:
            try:
                if browser_cmd[0] in ["open", "xdg-open"]:
                    # 对于open和xdg-open，直接使用
                    return browser_cmd + [url]
                elif browser_cmd[0].endswith('.exe') or browser_cmd[0].endswith('.app'):
                    # 对于完整路径，检查文件是否存在
                    if os.path.exists(browser_cmd[0]):
                        return browser_cmd + [url]
                else:
                    # 对于其他浏览器，检查是否存在
                    if sys.platform == "win32":
                        # Windows: 使用where命令查找
                        try:
                            result = subprocess.run(
                                ["where", browser_cmd[0]],
                                capture_output=True,
                                text=True,
                                timeout=5
                            )
                            if result.returncode == 0:
                                return browser_cmd + [url]
                        except (subprocess.TimeoutExpired, FileNotFoundError):
                            continue
                    else:
                        # Linux/macOS: 使用which命令查找
                        try:
                            result = subprocess.run(
                                ["which", browser_cmd[0]],
                                capture_output=True,
                                text=True,
                                timeout=5
                            )
                            if result.returncode == 0:
                                return browser_cmd + [url]
                        except (subprocess.TimeoutExpired, FileNotFoundError):
                            continue
            except Exception:
                continue
        
        # 如果都找不到，使用系统默认浏览器
        if sys.platform == "win32":
            return ["start", url]
        elif sys.platform == "darwin":
            return ["open", url]
        else:
            return ["xdg-open", url]
    
    async def open_browser(self, url: str):
        """启动浏览器进程"""
        try:
            browser_cmd = self._get_browser_command(url)
            logger.info(f"尝试启动浏览器，命令: {browser_cmd}")
            
            # 在打包环境中，使用subprocess.Popen启动浏览器
            if self.is_frozen:
                # 打包环境：使用subprocess启动
                try:
                    self.browser_process = subprocess.Popen(
                        browser_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
                    )
                    self.browser_pid = self.browser_process.pid
                    logger.info(f"浏览器进程已启动，PID: {self.browser_pid}")
                except FileNotFoundError as e:
                    logger.info(f"浏览器可执行文件未找到: {e}")
                    # 尝试使用webbrowser作为备选方案
                    await self._fallback_browser_open(url)
                except Exception as e:
                    logger.info(f"启动浏览器失败: {e}")
                    # 尝试使用webbrowser作为备选方案
                    await self._fallback_browser_open(url)
            else:
                # 开发环境：使用webbrowser模块
                await self._fallback_browser_open(url)
            
        except Exception as e:
            logger.info(f"启动浏览器失败: {str(e)}")
            # 如果启动失败，尝试使用webbrowser作为备选方案
            await self._fallback_browser_open(url)
    
    async def _fallback_browser_open(self, url: str):
        """使用webbrowser模块作为备选方案启动浏览器"""
        try:
            import webbrowser
            logger.info("使用webbrowser模块启动浏览器...")
            webbrowser.open(url)
            logger.info("webbrowser启动成功")
            # 在开发环境中，我们无法直接获取浏览器进程ID
            self.browser_pid = None
        except Exception as e:
            logger.info(f"webbrowser启动也失败: {str(e)}")
            # 最后的备选方案：尝试使用系统命令
            await self._system_browser_open(url)
    
    async def _system_browser_open(self, url: str):
        """使用系统命令启动浏览器"""
        try:
            if sys.platform == "win32":
                # Windows: 使用start命令
                cmd = ["start", url]
            elif sys.platform == "darwin":
                # macOS: 使用open命令
                cmd = ["open", url]
            else:
                # Linux: 使用xdg-open命令
                cmd = ["xdg-open", url]
            
            logger.info(f"尝试使用系统命令启动浏览器: {cmd}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                logger.info("系统命令启动浏览器成功")
            else:
                logger.info(f"系统命令启动浏览器失败: {result.stderr}")
        except Exception as e:
            logger.info(f"系统命令启动浏览器失败: {str(e)}")
    
    async def close_browser_process(self):
        """关闭浏览器进程"""
        try:
            if self.browser_process:
                # 如果有进程对象，尝试终止它
                try:
                    logger.info(f"正在终止浏览器进程 PID={self.browser_process.pid}")
                    self.browser_process.terminate()
                    # 使用asyncio.wait_for包装同步的wait调用
                    await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(None, self.browser_process.wait),
                        timeout=3.0
                    )
                    logger.info(f"浏览器进程已正常终止 PID={self.browser_process.pid}")
                except asyncio.TimeoutError:
                    logger.info(f"浏览器进程终止超时，强制终止 PID={self.browser_process.pid}")
                    self.browser_process.kill()
                    # 使用asyncio.wait_for包装同步的wait调用
                    await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(None, self.browser_process.wait),
                        timeout=3.0
                    )
                    logger.info(f"浏览器进程已被强制终止 PID={self.browser_process.pid}")
                finally:
                    self.browser_process = None
                    self.browser_pid = None
            
            elif self.browser_pid:
                # 如果有进程ID，使用psutil终止
                try:
                    if psutil.pid_exists(self.browser_pid):
                        logger.info(f"正在终止浏览器进程 PID={self.browser_pid}")
                        proc = psutil.Process(self.browser_pid)
                        
                        # 先尝试终止子进程
                        children = proc.children(recursive=True)
                        for child in children:
                            try:
                                child.terminate()
                                logger.info(f"已终止子进程 PID={child.pid}")
                            except psutil.NoSuchProcess:
                                pass
                        
                        # 终止主进程
                        proc.terminate()
                        # 使用asyncio.wait_for包装同步的wait调用
                        await asyncio.wait_for(
                            asyncio.get_event_loop().run_in_executor(None, proc.wait, 3),
                            timeout=3.0
                        )
                        logger.info(f"浏览器进程已正常终止 PID={self.browser_pid}")
                    else:
                        logger.info(f"浏览器进程不存在 PID={self.browser_pid}")
                except (psutil.NoSuchProcess, asyncio.TimeoutError):
                    try:
                        if psutil.pid_exists(self.browser_pid):
                            logger.info(f"强制终止浏览器进程 PID={self.browser_pid}")
                            proc = psutil.Process(self.browser_pid)
                            proc.kill()
                            logger.info(f"浏览器进程已被强制终止 PID={self.browser_pid}")
                    except psutil.NoSuchProcess:
                        logger.info(f"浏览器进程已不存在 PID={self.browser_pid}")
                finally:
                    self.browser_pid = None
                    
            # 额外的清理：查找并终止可能的残留浏览器进程
            await self._cleanup_browser_processes()
                    
        except Exception as e:
            logger.info(f"关闭浏览器进程时出错: {str(e)}")
    
    async def _cleanup_browser_processes(self):
        """清理可能的残留浏览器进程"""
        try:
            # 查找可能的浏览器进程
            browser_names = ['chrome', 'firefox', 'msedge', 'iexplore', 'safari']
            current_pid = os.getpid()
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    proc_info = proc.info
                    proc_name = proc_info['name'].lower()
                    
                    # 检查是否是浏览器进程
                    is_browser = any(browser in proc_name for browser in browser_names)
                    
                    if is_browser and proc_info['pid'] != current_pid:
                        # 检查命令行参数，看是否是我们的登录页面
                        cmdline = proc_info.get('cmdline', [])
                        if any('localhost' in arg for arg in cmdline):
                            logger.info(f"发现残留浏览器进程 PID={proc_info['pid']}, 名称={proc_name}")
                            try:
                                proc_obj = psutil.Process(proc_info['pid'])
                                proc_obj.terminate()
                                # 使用asyncio.wait_for包装同步的wait调用
                                await asyncio.wait_for(
                                    asyncio.get_event_loop().run_in_executor(None, proc_obj.wait, 2),
                                    timeout=2.0
                                )
                                logger.info(f"已终止残留浏览器进程 PID={proc_info['pid']}")
                            except (psutil.NoSuchProcess, asyncio.TimeoutError):
                                try:
                                    proc_obj = psutil.Process(proc_info['pid'])
                                    proc_obj.kill()
                                    logger.info(f"已强制终止残留浏览器进程 PID={proc_info['pid']}")
                                except psutil.NoSuchProcess:
                                    pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.info(f"清理浏览器进程时出错: {str(e)}")
    
    async def start(self, cookie_callback=None):
        """
        启动服务器
        
        Args:
            cookie_callback: 获取到cookie时的回调函数
        """
        if self._is_running:
            return f"http://localhost:{self.port}"
            
        self.cookie_callback = cookie_callback
        self.runner = aiohttp.web.AppRunner(self.app)
        await self.runner.setup()
        self.site = aiohttp.web.TCPSite(self.runner, 'localhost', self.port)
        await self.site.start()
        
        # 获取实际使用的端口
        for sock in self.site._server.sockets:
            self.port = sock.getsockname()[1]
            break
            
        self._is_running = True
        return f"http://localhost:{self.port}"
    
    async def start_with_browser(self, cookie_callback=None):
        """
        启动服务器并打开浏览器
        
        Args:
            cookie_callback: 获取到cookie时的回调函数
        """
        url = await self.start(cookie_callback)
        await self.open_browser(url)
        return url
        
    async def stop(self):
        """停止服务器"""
        # 防止重复停止
        if self._is_stopping or not self._is_running:
            return
            
        self._is_stopping = True
        
        try:
            # 先关闭浏览器进程
            await self.close_browser_process()
            
            # 然后关闭web服务器
            if self.login_instance:
                await self.login_instance.close()
                self.login_instance = None
                
            if self.site and self.runner:
                try:
                    await self.site.stop()
                except Exception as e:
                    logger.info(f"停止站点时出错: {str(e)}")
                    
            if self.runner:
                try:
                    await self.runner.cleanup()
                except Exception as e:
                    logger.info(f"清理运行器时出错: {str(e)}")
                    
        except Exception as e:
            logger.info(f"停止服务器时出错: {str(e)}")
        finally:
            self._is_running = False
            self._is_stopping = False
            self.site = None
            self.runner = None 