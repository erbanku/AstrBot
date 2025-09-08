import asyncio
import os
from typing import Any
from astrbot.api.event import AstrMessageEvent, MessageChain
from astrbot.api.platform import AstrBotMessage, PlatformMetadata, MessageType
from astrbot.api.message_components import Plain, Image, File, Record
from astrbot import logger
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

try:
    import selenium  # noqa: F401
except ImportError:
    logger.warning("Selenium not available for WhatsApp integration")


class WhatsAppPlatformEvent(AstrMessageEvent):
    """WhatsApp平台消息事件处理器"""

    def __init__(
        self,
        message_str: str,
        message_obj: AstrBotMessage,
        platform_meta: PlatformMetadata,
        session_id: str,
        whatsapp_client: Any,
    ):
        super().__init__(message_str, message_obj, platform_meta, session_id)
        self.whatsapp_client = whatsapp_client

    async def send(self, message: MessageChain):
        """发送消息到WhatsApp"""
        try:
            if self.get_message_type() == MessageType.GROUP_MESSAGE:
                await self._send_to_group(message)
            else:
                await self._send_to_contact(message)
        except Exception as e:
            logger.error(f"WhatsApp消息发送失败: {e}")

        await super().send(message)

    async def _send_to_contact(self, message: MessageChain):
        """发送消息到联系人"""
        for component in message.chain:
            if isinstance(component, Plain):
                await self._send_text_message(component.text)
            elif isinstance(component, Image):
                await self._send_image_message(component)
            elif isinstance(component, File):
                await self._send_file_message(component)
            elif isinstance(component, Record):
                await self._send_audio_message(component)

    async def _send_to_group(self, message: MessageChain):
        """发送消息到群组"""
        # 群组消息的处理逻辑与联系人消息类似
        await self._send_to_contact(message)

    async def _send_text_message(self, text: str):
        """发送文本消息"""
        try:
            if self.whatsapp_client:
                await asyncio.get_event_loop().run_in_executor(
                    None, self.whatsapp_client.send_text_message, text, self.session_id
                )
        except Exception as e:
            logger.error(f"发送WhatsApp文本消息失败: {e}")

    async def _send_image_message(self, image: Image):
        """发送图片消息"""
        try:
            if self.whatsapp_client:
                image_path = await image.convert_to_file_path()
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.whatsapp_client.send_image_message,
                    image_path,
                    self.session_id,
                )
        except Exception as e:
            logger.error(f"发送WhatsApp图片消息失败: {e}")

    async def _send_file_message(self, file: File):
        """发送文件消息"""
        try:
            if self.whatsapp_client:
                # 处理远程文件
                file_path = file.file
                if file.file.startswith("https://"):
                    from astrbot.core.utils.io import download_file

                    temp_dir = os.path.join(get_astrbot_data_path(), "temp")
                    file_path = os.path.join(temp_dir, file.name)
                    await download_file(file.file, file_path)

                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.whatsapp_client.send_file_message,
                    file_path,
                    self.session_id,
                )
        except Exception as e:
            logger.error(f"发送WhatsApp文件消息失败: {e}")

    async def _send_audio_message(self, record: Record):
        """发送音频消息"""
        try:
            if self.whatsapp_client:
                audio_path = await record.convert_to_file_path()
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.whatsapp_client.send_audio_message,
                    audio_path,
                    self.session_id,
                )
        except Exception as e:
            logger.error(f"发送WhatsApp音频消息失败: {e}")

    async def send_streaming(self, generator, use_fallback: bool = False):
        """流式发送消息（WhatsApp不支持流式，使用批量发送）"""
        try:
            full_message = ""
            async for chain in generator:
                if isinstance(chain, MessageChain):
                    for component in chain.chain:
                        if isinstance(component, Plain):
                            full_message += component.text
                        else:
                            # 对于非文本消息，立即发送
                            await self.send(MessageChain([component]))

            # 发送累积的文本消息
            if full_message.strip():
                await self.send(MessageChain([Plain(full_message)]))

        except Exception as e:
            logger.error(f"WhatsApp流式消息发送失败: {e}")

        return await super().send_streaming(generator, use_fallback)
