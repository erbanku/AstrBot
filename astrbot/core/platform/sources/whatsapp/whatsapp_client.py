import time
import asyncio
import os
from typing import List, Optional
from dataclasses import dataclass
from astrbot import logger
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException

    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logger.error(
        "Selenium not installed. Please install selenium to use WhatsApp integration."
    )


@dataclass
class WhatsAppMessage:
    """WhatsApp消息数据类"""

    sender: str
    content: str
    timestamp: str
    is_group: bool = False
    group_name: Optional[str] = None
    message_type: str = "text"  # text, image, audio, document
    media_path: Optional[str] = None


class WhatsAppWebClient:
    """WhatsApp Web客户端，使用Selenium进行自动化"""

    def __init__(self, config: dict):
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium is required for WhatsApp integration")

        self.config = config
        self.driver: Optional[webdriver.Chrome] = None
        self.is_authenticated = False
        self.last_message_count = 0
        self.processed_messages: set = set()

        # 配置选项
        self.headless = config.get("whatsapp_headless", True)
        self.user_data_dir = os.path.join(get_astrbot_data_path(), "whatsapp_profile")
        self.timeout = config.get("whatsapp_timeout", 30)

        # 确保用户数据目录存在
        os.makedirs(self.user_data_dir, exist_ok=True)

    def _setup_chrome_options(self) -> Options:
        """设置Chrome选项"""
        options = Options()

        if self.headless:
            options.add_argument("--headless")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument(f"--user-data-dir={self.user_data_dir}")

        # 设置用户代理
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )

        return options

    async def start(self) -> bool:
        """启动WhatsApp Web客户端"""
        try:
            options = self._setup_chrome_options()
            self.driver = webdriver.Chrome(options=options)

            logger.info("正在启动WhatsApp Web...")
            self.driver.get("https://web.whatsapp.com")

            # 等待加载
            await asyncio.sleep(5)

            # 检查是否需要扫码登录
            if await self._check_qr_code():
                logger.info("请扫描二维码完成WhatsApp Web登录")
                await self._wait_for_authentication()

            self.is_authenticated = True
            logger.info("WhatsApp Web客户端启动成功")
            return True

        except Exception as e:
            logger.error(f"启动WhatsApp Web客户端失败: {e}")
            await self.stop()
            return False

    async def _check_qr_code(self) -> bool:
        """检查是否存在二维码（需要登录）"""
        try:
            # 等待页面加载
            await asyncio.sleep(3)

            # 查找二维码元素
            qr_elements = self.driver.find_elements(
                By.CSS_SELECTOR, "canvas[aria-label*='Scan']"
            )
            return len(qr_elements) > 0
        except Exception:
            return False

    async def _wait_for_authentication(self, max_wait: int = 120):
        """等待用户扫码认证"""
        start_time = time.time()

        while time.time() - start_time < max_wait:
            try:
                # 检查是否已经登录（查找聊天列表）
                chats = self.driver.find_elements(
                    By.CSS_SELECTOR, "div[data-testid='chat-list']"
                )
                if chats:
                    logger.info("WhatsApp Web登录成功")
                    return True

                await asyncio.sleep(2)
            except Exception:
                await asyncio.sleep(2)

        raise TimeoutException("等待WhatsApp Web登录超时")

    async def stop(self):
        """停止客户端"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"关闭WhatsApp Web客户端时出错: {e}")
            finally:
                self.driver = None
        self.is_authenticated = False

    def send_text_message(self, text: str, contact_name: str):
        """发送文本消息"""
        if not self.is_authenticated or not self.driver:
            logger.error("WhatsApp客户端未认证或未启动")
            return False

        try:
            # 搜索并打开联系人
            if self._open_chat(contact_name):
                # 找到消息输入框
                message_box = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "div[contenteditable='true'][data-tab='10']")
                    )
                )

                # 输入消息
                message_box.clear()
                message_box.send_keys(text)

                # 发送消息
                send_button = self.driver.find_element(
                    By.CSS_SELECTOR, "span[data-testid='send']"
                )
                send_button.click()

                logger.debug(f"已发送文本消息到 {contact_name}: {text[:50]}...")
                return True

        except Exception as e:
            logger.error(f"发送文本消息失败: {e}")
            return False

    def _open_chat(self, contact_name: str) -> bool:
        """打开指定联系人的聊天"""
        try:
            # 点击搜索框
            search_box = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "div[contenteditable='true'][data-tab='3']")
                )
            )
            search_box.click()
            search_box.clear()
            search_box.send_keys(contact_name)

            # 等待搜索结果
            time.sleep(2)

            # 点击第一个搜索结果
            first_result = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "div[data-testid='cell-frame-container']")
                )
            )
            first_result.click()

            time.sleep(1)
            return True

        except Exception as e:
            logger.error(f"打开聊天失败 {contact_name}: {e}")
            return False

    def send_image_message(self, image_path: str, contact_name: str):
        """发送图片消息"""
        if not self.is_authenticated or not self.driver:
            logger.error("WhatsApp客户端未认证或未启动")
            return False

        try:
            if self._open_chat(contact_name):
                # 点击附件按钮
                attachment_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "div[title='Attach']"))
                )
                attachment_button.click()

                # 点击照片和视频选项
                photo_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable(
                        (
                            By.CSS_SELECTOR,
                            "input[accept='image/*,video/mp4,video/3gpp,video/quicktime']",
                        )
                    )
                )

                # 上传文件
                photo_button.send_keys(image_path)

                # 等待上传完成并点击发送
                time.sleep(3)
                send_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, "span[data-testid='send']")
                    )
                )
                send_button.click()

                logger.debug(f"已发送图片到 {contact_name}: {image_path}")
                return True

        except Exception as e:
            logger.error(f"发送图片消息失败: {e}")
            return False

    def send_file_message(self, file_path: str, contact_name: str):
        """发送文件消息"""
        # 文件发送逻辑与图片类似，但使用文档选择器
        if not self.is_authenticated or not self.driver:
            logger.error("WhatsApp客户端未认证或未启动")
            return False

        try:
            if self._open_chat(contact_name):
                # 点击附件按钮
                attachment_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "div[title='Attach']"))
                )
                attachment_button.click()

                # 点击文档选项
                document_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[accept='*']"))
                )

                # 上传文件
                document_button.send_keys(file_path)

                # 等待上传完成并点击发送
                time.sleep(3)
                send_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, "span[data-testid='send']")
                    )
                )
                send_button.click()

                logger.debug(f"已发送文件到 {contact_name}: {file_path}")
                return True

        except Exception as e:
            logger.error(f"发送文件消息失败: {e}")
            return False

    def send_audio_message(self, audio_path: str, contact_name: str):
        """发送音频消息"""
        # 音频发送逻辑
        return self.send_file_message(audio_path, contact_name)

    async def get_new_messages(self) -> List[WhatsAppMessage]:
        """获取新消息"""
        if not self.is_authenticated or not self.driver:
            return []

        try:
            messages = []

            # 获取所有聊天中的未读消息
            # 这是一个简化的实现，实际需要更复杂的消息检测逻辑
            chat_elements = self.driver.find_elements(
                By.CSS_SELECTOR, "div[data-testid='cell-frame-container']"
            )

            for chat in chat_elements[:5]:  # 限制检查的聊天数量
                try:
                    # 检查是否有未读消息指示器
                    unread_elements = chat.find_elements(
                        By.CSS_SELECTOR, "span[data-testid='icon-unread-count']"
                    )
                    if unread_elements:
                        # 点击进入聊天
                        chat.click()
                        await asyncio.sleep(1)

                        # 获取最新消息
                        message_elements = self.driver.find_elements(
                            By.CSS_SELECTOR,
                            "div[data-testid='conversation-panel-messages'] div[data-testid*='msg']",
                        )

                        if message_elements:
                            last_message = message_elements[-1]
                            message_text = last_message.text

                            # 简单的消息去重
                            message_id = hash(message_text + str(time.time()))
                            if message_id not in self.processed_messages:
                                self.processed_messages.add(message_id)

                                # 获取发送者信息
                                sender = "Unknown"
                                try:
                                    sender_element = self.driver.find_element(
                                        By.CSS_SELECTOR, "header span[title]"
                                    )
                                    sender = sender_element.get_attribute("title")
                                except Exception:
                                    pass

                                message = WhatsAppMessage(
                                    sender=sender,
                                    content=message_text,
                                    timestamp=str(int(time.time())),
                                    is_group=False,
                                    message_type="text",
                                )
                                messages.append(message)

                except Exception as e:
                    logger.debug(f"处理聊天时出错: {e}")
                    continue

            return messages

        except Exception as e:
            logger.error(f"获取WhatsApp消息失败: {e}")
            return []

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self.is_authenticated and self.driver is not None
