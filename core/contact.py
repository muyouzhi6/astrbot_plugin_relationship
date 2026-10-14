import random

from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)

from .config import PluginConfig
from .utils import (
    UNAVAILABLE_MESSAGE,
    get_aiocqhttp_client,
    get_ats,
    get_delivery_target,
)


class ContactHandle:
    def __init__(self, config: PluginConfig, context):
        self.cfg = config
        self.context = context

    async def cqhttp_send(self, event: AiocqhttpMessageEvent, payload: dict):
        """用 aiocqhttp 发送消息"""
        client = get_aiocqhttp_client(event, self.context)
        group_id, user_id = get_delivery_target(event)
        if client is None or (not group_id and not user_id):
            raise ValueError(UNAVAILABLE_MESSAGE)
        if group_id:
            payload["group_id"] = group_id
            action = "send_group_msg"
        else:
            payload["user_id"] = user_id
            action = "send_private_msg"

        try:
            result = await client.api.call_action(action, **payload)
            event.stop_event()
            return result
        except Exception as e:
            raise Exception(f"发送消息失败: {e}")

    async def _send_contact(self, event: AiocqhttpMessageEvent, *, uid=None, gid=None):
        """发送 qq / group contact（二选一）"""
        if uid is not None:
            contact = {"type": "qq", "id": int(uid)}
        elif gid is not None:
            contact = {"type": "group", "id": int(gid)}
        else:
            return

        payload = {"message": [{"type": "contact", "data": contact}]}
        await self.cqhttp_send(event, payload)

    async def _get_random_target(self, client) -> tuple[list[int], list[int]]:
        """当没有目标时，随机补一个"""
        if random.random() < 0.5:
            friend_list = await client.get_friend_list()
            return [random.choice(friend_list)["user_id"]], []
        else:
            group_list = await client.get_group_list()
            return [], [random.choice(group_list)["group_id"]]

    async def contact(self, event: AiocqhttpMessageEvent):
        """推荐 <群号/@群友/@qq>"""
        args = event.message_str.split()[1:]

        gids = [int(arg) for arg in args if arg.isdigit()]
        uids = get_ats(event)

        if not uids and not gids:
            uids, gids = await self._get_random_target(
                client=get_aiocqhttp_client(event, self.context)
            )

        if uids:
            for uid in uids:
                await self._send_contact(event, uid=uid)
        if gids:
            for gid in gids:
                await self._send_contact(event, gid=gid)
