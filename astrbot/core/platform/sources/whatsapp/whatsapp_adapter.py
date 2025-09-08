import asyncio
import sys
import uuid
from astrbot.api.platform import (
    Platform,
    AstrBotMessage,
    MessageMember,
    PlatformMetadata,
    MessageType,
    register_platform_adapter,
)
from astrbot.api.event import MessageChain
from astrbot.api.message_components import Plain, Image, File, Record
from astrbot.core.platform.astr_message_event import MessageSesion
from astrbot import logger

from .whatsapp_client import WhatsAppWebClient, WhatsAppMessage
from .whatsapp_event import WhatsAppPlatformEvent

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override


@register_platform_adapter(
    "whatsapp",
    "WhatsApp 适配器 (基于 WhatsApp Web)",
    default_config_tmpl={
        "whatsapp_headless": True,
        "whatsapp_timeout": 30,
        "whatsapp_poll_interval": 2,
        "whatsapp_max_retries": 3,
    },
    adapter_display_name="WhatsApp",
)
class WhatsAppPlatformAdapter(Platform):
    """WhatsApp平台适配器"""

    def __init__(
        self, platform_config: dict, platform_settings: dict, event_queue: asyncio.Queue
    ) -> None:
        super().__init__(event_queue)
        self.config = platform_config
        self.settings = platform_settings
        self.client_self_id = uuid.uuid4().hex[:8]

        # WhatsApp Web客户端
        self.whatsapp_client: WhatsAppWebClient = None

        # 配置选项
        self.headless = self.config.get("whatsapp_headless", True)
        self.timeout = self.config.get("whatsapp_timeout", 30)
        self.poll_interval = self.config.get("whatsapp_poll_interval", 2)
        self.max_retries = self.config.get("whatsapp_max_retries", 3)

        # 运行状态
        self.is_running = False
        self.polling_task = None
        self.retry_count = 0

    @override
    async def send_by_session(
        self, session: MessageSesion, message_chain: MessageChain
    ):
        """通过会话发送消息"""
        try:
            contact_name = session.session_id

            # 创建临时消息对象
            message_obj = AstrBotMessage()
            message_obj.session_id = contact_name
            message_obj.type = MessageType.FRIEND_MESSAGE
            message_obj.sender = MessageMember(
                user_id=str(self.client_self_id),
                nickname="AstrBot",
            )
            message_obj.self_id = self.client_self_id
            message_obj.message_str = message_chain.get_plain_text()
            message_obj.message = message_chain

            # 创建事件并发送
            event = WhatsAppPlatformEvent(
                message_str=message_chain.get_plain_text(),
                message_obj=message_obj,
                platform_meta=self.meta(),
                session_id=contact_name,
                whatsapp_client=self.whatsapp_client,
            )

            await event.send(message_chain)
            await super().send_by_session(session, message_chain)

        except Exception as e:
            logger.error(f"WhatsApp会话消息发送失败: {e}")

    @override
    def meta(self) -> PlatformMetadata:
        """返回平台元数据"""
        return PlatformMetadata(
            name="whatsapp",
            description="WhatsApp 适配器 (基于 WhatsApp Web)",
            id=self.config.get("id", "whatsapp"),
        )

    @override
    async def run(self):
        """运行WhatsApp适配器"""
        logger.info("正在启动WhatsApp适配器...")

        try:
            # 创建WhatsApp客户端
            self.whatsapp_client = WhatsAppWebClient(self.config)

            # 启动客户端
            if await self.whatsapp_client.start():
                self.is_running = True
                logger.info("WhatsApp适配器启动成功")

                # 开始轮询消息
                self.polling_task = asyncio.create_task(self._message_polling_loop())
                await self.polling_task
            else:
                logger.error("WhatsApp客户端启动失败")

        except Exception as e:
            logger.error(f"WhatsApp适配器运行时出错: {e}")
            await self.terminate()

    async def _message_polling_loop(self):
        """消息轮询循环"""
        logger.info("开始WhatsApp消息轮询...")

        while self.is_running:
            try:
                if self.whatsapp_client and self.whatsapp_client.is_connected():
                    # 获取新消息
                    new_messages = await self.whatsapp_client.get_new_messages()

                    # 处理每条新消息
                    for whatsapp_msg in new_messages:
                        await self._process_whatsapp_message(whatsapp_msg)

                    self.retry_count = 0  # 重置重试计数
                else:
                    logger.warning("WhatsApp客户端连接丢失，尝试重连...")
                    await self._attempt_reconnect()

                # 等待下次轮询
                await asyncio.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"WhatsApp消息轮询出错: {e}")
                await asyncio.sleep(self.poll_interval * 2)  # 出错时增加等待时间

    async def _process_whatsapp_message(self, whatsapp_msg: WhatsAppMessage):
        """处理WhatsApp消息"""
        try:
            # 转换为AstrBot消息格式
            astr_message = await self._convert_whatsapp_message(whatsapp_msg)

            if astr_message:
                # 创建消息事件
                event = WhatsAppPlatformEvent(
                    message_str=astr_message.message_str,
                    message_obj=astr_message,
                    platform_meta=self.meta(),
                    session_id=astr_message.session_id,
                    whatsapp_client=self.whatsapp_client,
                )

                # 提交事件到队列
                self.commit_event(event)

        except Exception as e:
            logger.error(f"处理WhatsApp消息失败: {e}")

    async def _convert_whatsapp_message(
        self, whatsapp_msg: WhatsAppMessage
    ) -> AstrBotMessage:
        """将WhatsApp消息转换为AstrBot消息格式"""
        try:
            message = AstrBotMessage()

            # 基本信息
            message.session_id = whatsapp_msg.sender
            message.message_id = f"whatsapp_{whatsapp_msg.timestamp}"
            message.sender = MessageMember(
                user_id=whatsapp_msg.sender,
                nickname=whatsapp_msg.sender,
            )
            message.self_id = str(self.client_self_id)
            message.raw_message = whatsapp_msg
            message.timestamp = int(whatsapp_msg.timestamp)

            # 消息类型
            if whatsapp_msg.is_group:
                message.type = MessageType.GROUP_MESSAGE
                message.group_id = whatsapp_msg.group_name or whatsapp_msg.sender
            else:
                message.type = MessageType.FRIEND_MESSAGE

            # 消息内容
            message.message_str = whatsapp_msg.content
            message.message = []

            # 根据消息类型处理内容
            if whatsapp_msg.message_type == "text":
                if whatsapp_msg.content:
                    message.message.append(Plain(whatsapp_msg.content))
            elif whatsapp_msg.message_type == "image" and whatsapp_msg.media_path:
                message.message.append(Image(file=whatsapp_msg.media_path))
                if whatsapp_msg.content:  # 图片可能有标题
                    message.message.append(Plain(whatsapp_msg.content))
            elif whatsapp_msg.message_type == "audio" and whatsapp_msg.media_path:
                message.message.append(Record(file=whatsapp_msg.media_path))
            elif whatsapp_msg.message_type == "document" and whatsapp_msg.media_path:
                filename = whatsapp_msg.media_path.split("/")[-1]
                message.message.append(
                    File(file=whatsapp_msg.media_path, name=filename)
                )

            return message

        except Exception as e:
            logger.error(f"转换WhatsApp消息失败: {e}")
            return None

    async def _attempt_reconnect(self):
        """尝试重连"""
        if self.retry_count >= self.max_retries:
            logger.error("WhatsApp重连次数超过限制，停止适配器")
            await self.terminate()
            return

        self.retry_count += 1
        logger.info(f"尝试重连WhatsApp... (第{self.retry_count}次)")

        try:
            if self.whatsapp_client:
                await self.whatsapp_client.stop()

            # 等待一段时间后重新连接
            await asyncio.sleep(5)

            self.whatsapp_client = WhatsAppWebClient(self.config)
            await self.whatsapp_client.start()

        except Exception as e:
            logger.error(f"WhatsApp重连失败: {e}")

    async def terminate(self):
        """终止适配器"""
        logger.info("正在关闭WhatsApp适配器...")

        self.is_running = False

        # 取消轮询任务
        if self.polling_task:
            self.polling_task.cancel()
            try:
                await self.polling_task
            except asyncio.CancelledError:
                pass

        # 关闭WhatsApp客户端
        if self.whatsapp_client:
            await self.whatsapp_client.stop()
            self.whatsapp_client = None

        logger.info("WhatsApp适配器已关闭")

    def get_client(self):
        """获取WhatsApp客户端"""
        return self.whatsapp_client
