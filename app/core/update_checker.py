import asyncio
import json
import os
from typing import Any
import platform
import aiohttp
import aiofiles
from pathlib import Path
import subprocess

import flet as ft
import httpx

from ..utils.logger import logger


class UpdateChecker:
    def __init__(self, app):
        self.app = app
        self.current_version = self._get_current_version()
        self.update_config = self._load_update_config()
        self.download_cancelled = False
        logger.info(f"UpdateChecker initialized with current version: {self.current_version}")
        
    def _get_current_version(self) -> str:
        try:
            config_path = os.path.join(self.app.run_path, "config", "version.json")
            with open(config_path, encoding="utf-8") as f:
                version_data = json.load(f)
                version = version_data["version_updates"][0]["version"]
                logger.info(f"Current version loaded from config: {version}")
                return version
        except Exception as e:
            logger.error(f"Failed to get current version: {e}")
            return "0.0.0"

    @staticmethod
    def _load_update_config() -> dict[str, Any]:
        auto_check = os.getenv("AUTO_CHECK_UPDATE", "false").lower() == "true"
        update_source = os.getenv("UPDATE_SOURCE", "both").lower()
        github_repo = os.getenv("GITHUB_REPO", "Joftal/StreamCap")
        custom_api = os.getenv("CUSTOM_UPDATE_API", "")
        check_interval = int(os.getenv("UPDATE_CHECK_INTERVAL", "86400"))
        
        update_sources = []
        
        if update_source in ["github", "both"]:
            update_sources.append({
                "name": "GitHub",
                "enabled": True,
                "priority": 1 if update_source == "github" else 0,
                "type": "github",
                "repo": github_repo,
                "timeout": 10
            })
        
        if update_source in ["custom", "both"] and custom_api:
            update_sources.append({
                "name": "Custom",
                "enabled": True,
                "priority": 1 if update_source == "custom" else 2,
                "type": "custom",
                "url": custom_api,
                "timeout": 5
            })
        
        return {
            "update_sources": update_sources,
            "check_interval": check_interval,
            "auto_check": auto_check
        }
    
    async def check_for_updates(self) -> dict[str, Any]:
        """Check for updates, prioritizing sources with higher priority"""
        sources = sorted(
            [s for s in self.update_config["update_sources"] if s["enabled"]],
            key=lambda x: x["priority"],
            reverse=True
        )
        
        if not sources:
            logger.warning("No available update sources configured")
            return {"has_update": False, "error": "No available update sources configured"}
        
        tasks = []
        for source in sources:
            if source["type"] == "github":
                tasks.append(self._check_github_update(source))
            elif source["type"] == "custom":
                tasks.append(self._check_custom_update(source))
        
        # Wait for any task to complete successfully or all to fail
        results = []
        for task in asyncio.as_completed(tasks):
            try:
                result = await task
                if result["has_update"] or "error" not in result:
                    return result
                results.append(result)
            except Exception as e:
                logger.error(f"Update check failed: {e}")
                results.append({"has_update": False, "error": str(e)})
        
        return results[-1] if results else {"has_update": False, "error": "All update sources check failed"}
    
    async def _check_github_update(self, source: dict[str, Any]) -> dict[str, Any]:
        """Check for updates from GitHub"""
        max_retries = 3
        retry_delay = 1  # 秒
        
        for attempt in range(max_retries):
            try:
                timeout = httpx.Timeout(source["timeout"])
                
                # 添加GitHub API认证头
                headers = {
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "StreamCap-Update-Checker"
                }
                
                async with httpx.AsyncClient(timeout=timeout) as client:
                    url = f"https://api.github.com/repos/{source['repo']}/releases/latest"
                    
                    response = await client.get(url, headers=headers)
                    logger.info(f"GitHub API响应状态码: {response.status_code}")

                    if response.status_code == 200:
                        latest_release = response.json()
                        latest_version = latest_release["tag_name"].lstrip("v")
                        
                        comparison_result = self._compare_versions(latest_version, self.current_version)
                        
                        if comparison_result > 0:
                            download_urls = {}
                            for asset in latest_release.get("assets", []):
                                name = asset["name"].lower()
                                if ("win" in name or "windows" in name) and "console" not in name:
                                    download_urls["windows"] = asset["browser_download_url"]
                                elif "mac" in name or "macos" in name:
                                    download_urls["macos"] = asset["browser_download_url"]
                                elif "linux" in name:
                                    download_urls["linux"] = asset["browser_download_url"]
                            
                            return {
                                "has_update": True,
                                "latest_version": latest_version,
                                "current_version": self.current_version,
                                "release_notes": latest_release["body"],
                                "download_url": latest_release["html_url"],
                                "download_urls": download_urls,
                                "source": source["name"]
                            }
                    elif response.status_code == 403:
                        logger.error("GitHub API访问受限，可能需要认证或已达到访问限制")
                        return {"has_update": False, "error": "GitHub API访问受限，请稍后重试", "source": source["name"]}
                    elif response.status_code == 404:
                        logger.error(f"GitHub仓库未找到: {source['repo']}")
                        return {"has_update": False, "error": "GitHub仓库未找到", "source": source["name"]}
                    else:
                        logger.error(f"GitHub API请求失败，状态码: {response.status_code}")
                        if attempt < max_retries - 1:
                            logger.info(f"将在{retry_delay}秒后重试...")
                            await asyncio.sleep(retry_delay)
                            continue
                        return {"has_update": False, "error": f"GitHub API请求失败: {response.status_code}", "source": source["name"]}
                    return {"has_update": False, "source": source["name"]}
            except httpx.ConnectTimeout:
                logger.error("连接GitHub超时")
                if attempt < max_retries - 1:
                    logger.info(f"将在{retry_delay}秒后重试...")
                    await asyncio.sleep(retry_delay)
                    continue
                return {"has_update": False, "error": "连接GitHub超时", "source": source["name"]}
            except httpx.RequestError as e:
                logger.error(f"请求GitHub失败: {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"将在{retry_delay}秒后重试...")
                    await asyncio.sleep(retry_delay)
                    continue
                return {"has_update": False, "error": f"请求GitHub失败: {str(e)}", "source": source["name"]}
            except Exception as e:
                logger.error(f"检查GitHub更新时发生错误: {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"将在{retry_delay}秒后重试...")
                    await asyncio.sleep(retry_delay)
                    continue
                return {"has_update": False, "error": str(e), "source": source["name"]}
        
        return {"has_update": False, "error": "多次尝试后仍然失败", "source": source["name"]}
    
    async def _check_custom_update(self, source: dict[str, Any]) -> dict[str, Any]:
        """Check for updates from custom source
        
        Expected API Response Format:
        {
            "has_update": bool,           # Whether there is a new version available
            "latest_version": str,        # Latest version number (e.g. "1.0.0")
            "current_version": str,       # Current version number
            "release_notes": str,         # Release notes or update description
            "download_url": str,          # Main download page URL
            "download_urls": {            # Optional: Platform-specific download URLs
                "windows": str,           # Windows download URL
                "macos": str,            # macOS download URL
                "linux": str             # Linux download URL
            }
        }
        """
        try:
            timeout = httpx.Timeout(source["timeout"])
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    source["url"],
                    params={"current_version": self.current_version}
                )
                if response.status_code == 200:
                    update_info = response.json()
                    if update_info.get("has_update", False):
                        return {
                            **update_info,
                            "source": source["name"]
                        }
                    return {"has_update": False, "source": source["name"]}
                return {"has_update": False, "error": f"API returned status code: {response.status_code}",
                        "source": source["name"]}
        except Exception as e:
            logger.error(f"Failed to check update from custom source: {e}")
            return {"has_update": False, "error": str(e), "source": source["name"]}

    @staticmethod
    def _compare_versions(version1: str, version2: str) -> int:
        """Compare version numbers, returns 1 if version1 > version2, 0 if equal, -1 if less"""
        try:
            v1_parts = [int(x) for x in version1.split(".")]
            v2_parts = [int(x) for x in version2.split(".")]
            
            max_parts = max(len(v1_parts), len(v2_parts))
            v1_parts.extend([0] * (max_parts - len(v1_parts)))
            v2_parts.extend([0] * (max_parts - len(v2_parts)))
            
            for i in range(max_parts):
                v1 = v1_parts[i]
                v2 = v2_parts[i]
                if v1 > v2:
                    return 1
                elif v1 < v2:
                    return -1
            return 0
        except ValueError as e:
            logger.error(f"版本号格式错误: {str(e)}")
            return 0
        except Exception as e:
            logger.error(f"比较版本时发生错误: {str(e)}")
            return 0
    
    async def show_update_dialog(self, update_info: dict[str, Any]) -> None:
        _ = self.app.language_manager.language.get("update", {})

        # 处理更新内容
        release_notes = update_info.get("release_notes", "")
        if not release_notes:
            release_notes = _["no_details"]
        
        # 格式化更新内容
        formatted_notes = []
        for line in release_notes.split('\n'):
            if line.strip():
                # 处理Markdown格式
                if line.startswith('#'):
                    # 标题
                    level = len(line.split()[0])
                    text = line.lstrip('#').strip()
                    formatted_notes.append(ft.Text(text, size=20-level, weight=ft.FontWeight.BOLD))
                elif line.startswith('- ') or line.startswith('* '):
                    # 列表项
                    text = line[2:].strip()
                    formatted_notes.append(ft.Text(f"• {text}", size=14))
                elif line.startswith('```'):
                    # 代码块开始或结束
                    continue
                elif line.startswith('    '):
                    # 代码块内容
                    text = line[4:].strip()
                    formatted_notes.append(ft.Text(text, size=14, font_family="monospace"))
                else:
                    # 普通文本
                    formatted_notes.append(ft.Text(line.strip(), size=14))

        dialog = ft.AlertDialog(
            title=ft.Text(_["new_version"].format(version=update_info.get("latest_version"))),
            content=ft.Column([
                ft.Text(_["current_version"].format(version=update_info.get("current_version"))),
                ft.Text(_["latest_version"].format(version=update_info.get("latest_version"))),
                ft.Text(_["update_source"].format(source=update_info.get("source", _["unknown"]))),
                ft.Text(_["release_notes"], weight=ft.FontWeight.BOLD, size=16),
                ft.Container(
                    content=ft.Column(formatted_notes, spacing=5, scroll=ft.ScrollMode.AUTO),
                    height=300,
                    width=550,  # 设置内容区域宽度
                    border=ft.border.all(1, ft.colors.OUTLINE),
                    border_radius=5,
                    padding=10,
                ),
            ], spacing=10, width=400, height=400),
            actions=[
                ft.TextButton(_["later"], on_click=lambda _: self.close_dialog()),
                ft.TextButton(_["download"], on_click=lambda e: self.app.page.loop.create_task(self.start_download(update_info)))
            ],
            modal=True,
        )

        self.app.dialog_area.content = dialog
        self.app.dialog_area.content.open = True
        self.app.dialog_area.update()

    def close_dialog(self) -> None:
        if self.app.dialog_area.content:
            self.app.dialog_area.content.open = False
            self.app.dialog_area.update()

    async def start_download(self, update_info: dict[str, Any]) -> None:
        """开始下载更新文件"""
        # 重置下载状态
        self.download_cancelled = False
        
        _ = self.app.language_manager.language.get("update", {})
        
        # 获取下载URL
        download_urls = update_info.get("download_urls", {})
        system = platform.system().lower()
        download_url = None
        
        if download_urls:
            if system == "windows" and "windows" in download_urls:
                download_url = download_urls["windows"]
            elif system == "darwin" and "macos" in download_urls:
                download_url = download_urls["macos"]
            elif system == "linux" and "linux" in download_urls:
                download_url = download_urls["linux"]
        
        if not download_url:
            # 如果没有找到对应的下载链接，使用网页下载
            self.open_download_page(update_info)
            return

        # 创建下载进度对话框
        self.progress_dialog = ft.AlertDialog(
            title=ft.Text(_["downloading"]),
            content=ft.Column([
                ft.ProgressBar(width=400),
                ft.Text("0%", key="download_progress_text"),
            ], spacing=10),
            actions=[
                ft.TextButton(_["cancel"], on_click=lambda _: self.cancel_download())
            ],
            modal=True,
        )

        self.app.dialog_area.content = self.progress_dialog
        self.app.dialog_area.content.open = True
        self.app.dialog_area.update()

        # 创建下载目录
        download_dir = Path(self.app.run_path) / "downloads"
        download_dir.mkdir(exist_ok=True)
        
        # 从URL中获取文件名
        filename = download_url.split("/")[-1]
        file_path = download_dir / filename

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url) as response:
                    if response.status != 200:
                        raise Exception(f"Download failed with status {response.status}")
                    
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded_size = 0
                    
                    async with aiofiles.open(file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            if self.download_cancelled:
                                await f.close()
                                if file_path.exists():
                                    file_path.unlink()
                                self.close_dialog()
                                return
                            
                            await f.write(chunk)
                            downloaded_size += len(chunk)
                            
                            # 更新进度
                            progress = (downloaded_size / total_size) * 100
                            self.progress_dialog.content.controls[0].value = progress / 100
                            self.progress_dialog.content.controls[1].value = f"{progress:.1f}%"
                            self.app.dialog_area.update()

            # 下载完成
            self.close_dialog()
            
            # 显示下载完成提示
            success_dialog = ft.AlertDialog(
                title=ft.Text(_["download_complete"]),
                content=ft.Column([
                    ft.Text(_["download_complete_message"]),
                    ft.Text(str(file_path)),
                ], spacing=10),
                actions=[
                    ft.TextButton(_["open_folder"], on_click=lambda _: self.open_download_folder(download_dir)),
                    ft.TextButton(_["ok"], on_click=lambda _: self.close_dialog())
                ],
                modal=True,
            )
            
            self.app.dialog_area.content = success_dialog
            self.app.dialog_area.content.open = True
            self.app.dialog_area.update()
            
        except Exception as e:
            logger.error(f"Download failed: {e}")
            if file_path.exists():
                file_path.unlink()
            self.close_dialog()
            # 显示错误对话框
            error_dialog = ft.AlertDialog(
                title=ft.Text(_["download_failed"]),
                content=ft.Text(str(e)),
                actions=[
                    ft.TextButton(_["ok"], on_click=lambda _: self.close_dialog())
                ],
                modal=True,
            )
            self.app.dialog_area.content = error_dialog
            self.app.dialog_area.content.open = True
            self.app.dialog_area.update()

    def cancel_download(self) -> None:
        """取消下载"""
        _ = self.app.language_manager.language.get("update", {})
        
        # 保存当前下载进度对话框的状态
        self.progress_dialog.open = False
        
        # 显示确认对话框
        confirm_dialog = ft.AlertDialog(
            title=ft.Text(_["confirm_cancel"]),
            content=ft.Text(_["confirm_cancel_download"]),
            actions=[
                ft.TextButton(_["no"], on_click=lambda _: self.close_confirm_dialog()),
                ft.TextButton(_["yes"], on_click=lambda _: self._confirm_cancel_download())
            ],
            modal=True,
        )
        
        self.app.dialog_area.content = confirm_dialog
        self.app.dialog_area.content.open = True
        self.app.dialog_area.update()

    def close_confirm_dialog(self) -> None:
        """关闭确认对话框并恢复下载进度对话框"""
        # 恢复下载进度对话框
        self.app.dialog_area.content = self.progress_dialog
        self.app.dialog_area.content.open = True
        self.app.dialog_area.update()

    def _confirm_cancel_download(self) -> None:
        """确认取消下载"""
        self.download_cancelled = True
        self.close_dialog()  # 关闭所有对话框

    def open_download_page(self, update_info: dict[str, Any]) -> None:
        """打开浏览器下载页面（用于Web端）"""
        import webbrowser
        
        url = update_info.get("download_url", "https://github.com/Joftal/StreamCap/releases/latest")
        webbrowser.open(url)
        self.close_dialog()

    def open_download_folder(self, folder_path: Path) -> None:
        """打开下载文件夹"""
        try:
            if platform.system() == "Windows":
                os.startfile(folder_path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", folder_path])
            else:  # Linux
                subprocess.run(["xdg-open", folder_path])
        except Exception as e:
            logger.error(f"打开文件夹失败: {e}")