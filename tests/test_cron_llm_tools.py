import importlib
import sys
import types
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

UNAVAILABLE = (
    "此工具在当前上下文不可用，不要再用 shell/python/数据库等其他方式读取聊天记录，"
    "直接结束本次检查"
)


@pytest.fixture(scope="module")
def plugin_modules():
    patch = pytest.MonkeyPatch()

    def module(name, **attrs):
        value = types.ModuleType(name)
        value.__dict__.update(attrs)
        patch.setitem(sys.modules, name, value)
        return value

    def passthrough(*args, **kwargs):
        return lambda func: func

    class MessageType(Enum):
        GROUP_MESSAGE = "GroupMessage"
        FRIEND_MESSAGE = "FriendMessage"
        OTHER_MESSAGE = "OtherMessage"

    class AiocqhttpMessageEvent:
        def __init__(self, bot, session, role="admin"):
            self.bot = bot
            self.session = session
            self.role = role
            self.message_str = ""
            self.stopped = False

        def is_admin(self):
            return self.role == "admin"

        def get_messages(self):
            return []

        def get_self_id(self):
            return "42"

        def get_group_id(self):
            return (
                self.session.session_id
                if self.session.message_type == MessageType.GROUP_MESSAGE
                else ""
            )

        def get_sender_id(self):
            return "88"

        def get_sender_name(self):
            return "caller"

        def is_private_chat(self):
            return self.session.message_type == MessageType.FRIEND_MESSAGE

        def plain_result(self, text):
            return text

        def stop_event(self):
            self.stopped = True

    class CronEvent:
        def __init__(self, session, role="admin"):
            self.session = session
            self.role = role
            self.message_str = ""
            self.stopped = False

        def is_admin(self):
            return self.role == "admin"

        def get_messages(self):
            return []

        def get_self_id(self):
            return "astrbot"

        def get_group_id(self):
            return ""

        def get_sender_id(self):
            return self.session.session_id

        def get_sender_name(self):
            return "Scheduler"

        def is_private_chat(self):
            return self.session.message_type == MessageType.FRIEND_MESSAGE

        def plain_result(self, text):
            return text

        def stop_event(self):
            self.stopped = True

    class Star:
        def __init__(self, context):
            self.context = context

    class At:
        def __init__(self, qq):
            self.qq = qq

    class Plain:
        def __init__(self, text):
            self.text = text

    class Reply:
        pass

    filter_stub = SimpleNamespace(
        llm_tool=passthrough,
        command=passthrough,
        permission_type=passthrough,
        platform_adapter_type=passthrough,
        event_message_type=passthrough,
        EventMessageType=SimpleNamespace(GROUP_MESSAGE="group"),
    )
    logger = SimpleNamespace(
        debug=lambda *a: None,
        error=lambda *a: None,
        exception=lambda *a: None,
        warning=lambda *a: None,
    )
    module("aiocqhttp", CQHttp=object)
    module("astrbot")
    module("astrbot.api", logger=logger)
    module("astrbot.api.event", filter=filter_stub)
    module("astrbot.api.star", Context=object, Star=Star)
    module("astrbot.core")
    module("astrbot.core.config")
    module(
        "astrbot.core.config.astrbot_config",
        AstrBotConfig=type("AstrBotConfig", (), {}),
    )
    module("astrbot.core.message")
    module("astrbot.core.message.components", At=At, Plain=Plain, Reply=Reply)
    module("astrbot.core.platform")
    module("astrbot.core.platform.message_type", MessageType=MessageType)
    module("astrbot.core.platform.sources")
    module("astrbot.core.platform.sources.aiocqhttp")
    module(
        "astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event",
        AiocqhttpMessageEvent=AiocqhttpMessageEvent,
    )
    module("astrbot.core.star")
    module("astrbot.core.star.context", Context=object)
    module("astrbot.core.star.filter")
    module(
        "astrbot.core.star.filter.permission",
        PermissionType=SimpleNamespace(ADMIN="admin"),
    )
    module(
        "astrbot.core.star.filter.platform_adapter_type",
        PlatformAdapterType=SimpleNamespace(AIOCQHTTP="aiocqhttp"),
    )
    for name, class_name in (
        ("normal", "NormalHandle"),
        ("notice", "NoticeHandle"),
        ("request", "RequestHandle"),
    ):
        module(f"repo.core.{name}", **{class_name: type(class_name, (), {})})
    module("repo.core.expansion", ExpansionHandle=type("ExpansionHandle", (), {}))

    patch.syspath_prepend(str(Path(__file__).resolve().parents[2]))
    main = importlib.import_module("repo.main")
    yield SimpleNamespace(
        main=main,
        MessageType=MessageType,
        QQEvent=AiocqhttpMessageEvent,
        CronEvent=CronEvent,
    )
    patch.undo()


def make_bot():
    return SimpleNamespace(
        get_login_info=AsyncMock(return_value={"user_id": 42, "nickname": "bot"}),
        get_group_info=AsyncMock(return_value={"group_name": "source"}),
        get_group_member_info=AsyncMock(return_value={"nickname": "bot"}),
        get_stranger_info=AsyncMock(return_value={"nickname": "bot"}),
        get_group_list=AsyncMock(
            return_value=[{"group_id": 123, "group_name": "source"}]
        ),
        get_friend_list=AsyncMock(return_value=[{"user_id": 55, "nickname": "friend"}]),
        get_group_msg_history=AsyncMock(
            return_value={
                "messages": [
                    {"sender": {"nickname": "A", "user_id": 1}, "message": "hello"}
                ]
            }
        ),
        get_friend_msg_history=AsyncMock(
            return_value={
                "messages": [
                    {"sender": {"nickname": "B", "user_id": 2}, "message": "hi"}
                ]
            }
        ),
        send_group_forward_msg=AsyncMock(),
        send_private_forward_msg=AsyncMock(),
        set_group_leave=AsyncMock(),
        delete_friend=AsyncMock(),
        api=SimpleNamespace(call_action=AsyncMock()),
    )


def make_plugin(mods, platforms):
    context = SimpleNamespace(get_platform_inst=Mock(side_effect=platforms.get))
    plugin = mods.main.RelationshipPlugin.__new__(mods.main.RelationshipPlugin)
    plugin.context = context
    plugin.cfg = SimpleNamespace(check=SimpleNamespace(count=5))
    plugin.contact = mods.main.ContactHandle(plugin.cfg, context)
    return plugin


def platform(name, bot, platform_id):
    return SimpleNamespace(
        meta=lambda: SimpleNamespace(name=name, id=platform_id), get_client=lambda: bot
    )


def session(mods, kind, session_id, platform_id="qq-main"):
    return SimpleNamespace(
        message_type=kind, session_id=session_id, platform_id=platform_id
    )


@pytest.fixture
def expansion(plugin_modules, monkeypatch):
    handle = SimpleNamespace(
        add_friend=AsyncMock(return_value="好友申请成功"),
        add_group=AsyncMock(return_value="加群申请成功"),
    )
    monkeypatch.setattr(sys.modules["repo.core.expansion"], "ExpansionHandle", handle)
    return handle


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind,sid", [("GROUP_MESSAGE", "88_456"), ("FRIEND_MESSAGE", "777")]
)
@pytest.mark.parametrize("tool", ["friend", "group"])
@pytest.mark.parametrize("explicit", [False, True])
async def test_cron_extension_requests_use_selected_account(
    plugin_modules, expansion, kind, sid, tool, explicit
):
    mods = plugin_modules
    bot, other = make_bot(), make_bot()
    bot.get_login_info.return_value["user_id"] = "84"
    plugin = make_plugin(
        mods,
        {
            "qq-other": platform("aiocqhttp", other, "qq-other"),
            "qq-main": platform("aiocqhttp", bot, "qq-main"),
        },
    )
    event = mods.CronEvent(session(mods, getattr(mods.MessageType, kind), sid))
    assert event.get_self_id() == "astrbot"

    if tool == "friend":
        result = await plugin.llm_add_friend_request(
            event,
            user_id="55",
            verify="hello" if explicit else "",
            remark="备注",
            answer="答案",
        )
        expected_verify = (
            "我是来自source的bot" if kind == "GROUP_MESSAGE" else "我是bot"
        )
        expansion.add_friend.assert_awaited_once_with(
            client=bot,
            target_uin=55,
            self_id=84,
            verify="hello" if explicit else expected_verify,
            remark="备注",
            answer="答案",
        )
        assert result == "好友申请成功"
    else:
        result = await plugin.llm_add_group_request(
            event,
            group_id="123",
            answer="hello" if explicit else "",
        )
        expansion.add_group.assert_awaited_once_with(
            client=bot,
            target_gid=123,
            answer="hello" if explicit else "我是Scheduler推荐来的bot",
        )
        assert result == "加群申请成功"

    plugin.context.get_platform_inst.assert_called_once_with("qq-main")
    other.get_login_info.assert_not_awaited()
    if tool == "friend" or not explicit:
        bot.get_login_info.assert_awaited_once_with()
    else:
        bot.get_login_info.assert_not_awaited()
    if not explicit and kind == "GROUP_MESSAGE":
        bot.get_group_member_info.assert_awaited_once_with(group_id=456, user_id=84)
        if tool == "friend":
            bot.get_group_info.assert_awaited_once_with(group_id=456, no_cache=True)
    elif not explicit:
        bot.get_stranger_info.assert_awaited_once_with(user_id=84)
        bot.get_group_info.assert_not_awaited()
    else:
        bot.get_group_info.assert_not_awaited()
        bot.get_group_member_info.assert_not_awaited()
        bot.get_stranger_info.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", ["friend", "group"])
@pytest.mark.parametrize(
    "login_info",
    [
        None,
        {},
        {"user_id": "astrbot"},
        {"user_id": 0},
        {"user_id": -1},
        {"user_id": "9" * 4301},
        RuntimeError("offline"),
    ],
)
async def test_cron_extension_missing_identity_stops_cleanly(
    plugin_modules, expansion, tool, login_info
):
    mods = plugin_modules
    bot = make_bot()
    if isinstance(login_info, Exception):
        bot.get_login_info.side_effect = login_info
    else:
        bot.get_login_info.return_value = login_info
    plugin = make_plugin(mods, {"qq-main": platform("aiocqhttp", bot, "qq-main")})
    event = mods.CronEvent(session(mods, mods.MessageType.GROUP_MESSAGE, "88_456"))

    if tool == "friend":
        result = await plugin.llm_add_friend_request(
            event, user_id="55", verify="hello"
        )
    else:
        result = await plugin.llm_add_group_request(event, group_id="123")

    assert result == UNAVAILABLE
    expansion.add_friend.assert_not_awaited()
    expansion.add_group.assert_not_awaited()
    bot.get_group_info.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["GROUP_MESSAGE", "FRIEND_MESSAGE"])
@pytest.mark.parametrize("explicit", [False, True])
async def test_normal_extension_requests_keep_event_identity_and_greetings(
    plugin_modules, expansion, kind, explicit
):
    mods = plugin_modules
    bot = make_bot()
    bot.get_login_info.side_effect = AssertionError(
        "QQ events already have an identity"
    )
    plugin = make_plugin(mods, {})
    event = mods.QQEvent(bot, session(mods, getattr(mods.MessageType, kind), "456"))

    assert (
        await plugin.llm_add_friend_request(
            event,
            user_id="55",
            verify="hello" if explicit else "",
        )
        == "好友申请成功"
    )
    expansion.add_friend.assert_awaited_once_with(
        client=bot,
        target_uin=55,
        self_id=42,
        verify="hello" if explicit else "我是来自source的bot",
        remark="",
        answer="",
    )
    assert (
        await plugin.llm_add_group_request(
            event,
            group_id="123",
            answer="hello" if explicit else "",
        )
        == "加群申请成功"
    )
    expansion.add_group.assert_awaited_once_with(
        client=bot,
        target_gid=123,
        answer="hello" if explicit else "我是caller推荐来的bot",
    )
    bot.get_login_info.assert_not_awaited()
    plugin.context.get_platform_inst.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind,sid,requested,expected",
    [
        ("GROUP_MESSAGE", "88_456", "", 456),
        ("GROUP_MESSAGE", "456", "", 456),
        ("GROUP_MESSAGE", "88_456", "123", 123),
        ("FRIEND_MESSAGE", "777", "", None),
        ("FRIEND_MESSAGE", "777", "123", 123),
        ("OTHER_MESSAGE", "job", "", None),
    ],
)
async def test_cron_leave_group_uses_original_group_only(
    plugin_modules, kind, sid, requested, expected
):
    mods = plugin_modules
    bot = make_bot()
    plugin = make_plugin(mods, {"qq-main": platform("aiocqhttp", bot, "qq-main")})
    event = mods.CronEvent(session(mods, getattr(mods.MessageType, kind), sid))

    result = await plugin.llm_leave_group(event, group_id=requested)

    if expected is None:
        if kind == "OTHER_MESSAGE":
            assert result == UNAVAILABLE
        else:
            assert "退群失败" in result
        bot.set_group_leave.assert_not_awaited()
    else:
        assert result == f"成功退出群聊: {expected}"
        bot.set_group_leave.assert_awaited_once_with(group_id=expected)


@pytest.mark.asyncio
async def test_cron_default_verification_api_error_returns_failure(
    plugin_modules, expansion
):
    mods = plugin_modules
    bot = make_bot()
    bot.get_group_info.side_effect = RuntimeError("group unavailable")
    plugin = make_plugin(mods, {"qq-main": platform("aiocqhttp", bot, "qq-main")})
    event = mods.CronEvent(session(mods, mods.MessageType.GROUP_MESSAGE, "88_456"))

    result = await plugin.llm_add_friend_request(event, user_id="55")

    assert result == "发起好友申请失败: group unavailable"
    expansion.add_friend.assert_not_awaited()


@pytest.mark.asyncio
async def test_cron_group_uses_matching_platform_and_target_session(plugin_modules):
    mods = plugin_modules
    other, bot = make_bot(), make_bot()
    plugin = make_plugin(
        mods,
        {
            "qq-other": platform("aiocqhttp", other, "qq-other"),
            "qq-main": platform("aiocqhttp", bot, "qq-main"),
        },
    )
    event = mods.CronEvent(session(mods, mods.MessageType.GROUP_MESSAGE, "88_456"))

    result = await plugin.llm_check_messages(event, target_id="999", count=3)

    assert "已发送" in result
    bot.get_group_msg_history.assert_awaited_once_with(group_id=999, count=3)
    bot.send_group_forward_msg.assert_awaited_once()
    assert bot.send_group_forward_msg.await_args.kwargs["group_id"] == 456
    bot.send_private_forward_msg.assert_not_awaited()
    other.get_group_msg_history.assert_not_awaited()
    plugin.context.get_platform_inst.assert_called_once_with("qq-main")


@pytest.mark.asyncio
async def test_cron_private_forwards_to_original_user(plugin_modules):
    mods = plugin_modules
    bot = make_bot()
    plugin = make_plugin(mods, {"qq-main": platform("aiocqhttp", bot, "qq-main")})
    event = mods.CronEvent(session(mods, mods.MessageType.FRIEND_MESSAGE, "777"))

    result = await plugin.llm_check_messages(event, target_id="999")

    assert "已发送" in result
    bot.send_private_forward_msg.assert_awaited_once()
    assert bot.send_private_forward_msg.await_args.kwargs["user_id"] == 777
    bot.send_group_forward_msg.assert_not_awaited()


@pytest.mark.asyncio
async def test_cron_contact_card_uses_original_group(plugin_modules):
    mods = plugin_modules
    bot = make_bot()
    plugin = make_plugin(mods, {"qq-main": platform("aiocqhttp", bot, "qq-main")})
    event = mods.CronEvent(session(mods, mods.MessageType.GROUP_MESSAGE, "88_456"))

    result = await plugin.llm_send_contact_card(event, target_id="55")

    assert "已成功发送" in result
    bot.api.call_action.assert_awaited_once_with(
        "send_group_msg",
        group_id=456,
        message=[{"type": "contact", "data": {"type": "qq", "id": 55}}],
    )


@pytest.mark.asyncio
async def test_cron_contact_card_without_delivery_session_is_unavailable(
    plugin_modules,
):
    mods = plugin_modules
    bot = make_bot()
    plugin = make_plugin(mods, {"qq-main": platform("aiocqhttp", bot, "qq-main")})
    event = mods.CronEvent(session(mods, mods.MessageType.OTHER_MESSAGE, "cron-job"))

    assert await plugin.llm_send_contact_card(event, target_id="55") == UNAVAILABLE
    bot.api.call_action.assert_not_awaited()


@pytest.mark.asyncio
async def test_cron_contact_card_uses_original_private_session(plugin_modules):
    mods = plugin_modules
    bot = make_bot()
    plugin = make_plugin(mods, {"qq-main": platform("aiocqhttp", bot, "qq-main")})
    event = mods.CronEvent(session(mods, mods.MessageType.FRIEND_MESSAGE, "777"))

    result = await plugin.llm_send_contact_card(event, target_id="55")

    assert "已成功发送" in result
    bot.api.call_action.assert_awaited_once_with(
        "send_private_msg",
        user_id=777,
        message=[{"type": "contact", "data": {"type": "qq", "id": 55}}],
    )


@pytest.mark.asyncio
async def test_missing_client_checked_before_optional_expansion(
    plugin_modules, monkeypatch
):
    mods = plugin_modules
    monkeypatch.delitem(sys.modules, "repo.core.expansion")
    plugin = make_plugin(mods, {})
    event = mods.CronEvent(session(mods, mods.MessageType.GROUP_MESSAGE, "456"))

    assert await plugin.llm_add_friend_request(event, user_id="55") == UNAVAILABLE
    assert await plugin.llm_add_group_request(event, group_id="123") == UNAVAILABLE


@pytest.mark.asyncio
async def test_client_lookup_error_is_unavailable(plugin_modules):
    mods = plugin_modules
    plugin = make_plugin(mods, {})
    plugin.context.get_platform_inst.side_effect = RuntimeError("platform offline")
    event = mods.CronEvent(session(mods, mods.MessageType.GROUP_MESSAGE, "456"))

    assert await plugin.llm_check_messages(event, target_id="999") == UNAVAILABLE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "platforms,kind,session_id",
    [
        ({}, "GROUP_MESSAGE", "456"),
        ({"qq-main": None}, "GROUP_MESSAGE", "456"),
        ({"qq-main": "no_client"}, "GROUP_MESSAGE", "456"),
        ({"qq-main": "foreign"}, "GROUP_MESSAGE", "456"),
        ({"qq-main": "qq"}, "OTHER_MESSAGE", "cron-job"),
        ({"qq-main": "qq"}, "GROUP_MESSAGE", "bad-id"),
    ],
)
async def test_cron_unavailable_returns_stop_instruction(
    plugin_modules, platforms, kind, session_id
):
    mods = plugin_modules
    bot = make_bot()
    resolved = {
        key: platform(
            "discord" if value == "foreign" else "aiocqhttp",
            None if value == "no_client" else bot,
            key,
        )
        if value
        else None
        for key, value in platforms.items()
    }
    plugin = make_plugin(mods, resolved)
    event = mods.CronEvent(session(mods, getattr(mods.MessageType, kind), session_id))

    result = await plugin.llm_check_messages(event, target_id="999")

    assert UNAVAILABLE in result
    bot.get_group_msg_history.assert_not_awaited()
    bot.send_group_forward_msg.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_id",
    ["²", "9" * 4301],
    ids=["superscript_digit", "4301_digits"],
)
@pytest.mark.parametrize(
    "kind,prefix",
    [("GROUP_MESSAGE", ""), ("GROUP_MESSAGE", "88_"), ("FRIEND_MESSAGE", "")],
    ids=["group", "prefixed_group", "private"],
)
@pytest.mark.parametrize(
    "method,kwargs",
    [
        ("llm_check_messages", {"target_id": "999"}),
        ("llm_check_messages", {}),
        ("llm_send_contact_card", {"target_id": "55"}),
        ("llm_send_contact_card", {}),
        ("llm_leave_group", {}),
    ],
    ids=["check_explicit", "check_random", "card_explicit", "card_random", "leave"],
)
async def test_cron_numeric_conversion_failure_stops_before_api_calls(
    plugin_modules, invalid_id, kind, prefix, method, kwargs
):
    mods = plugin_modules
    bot = make_bot()
    plugin = make_plugin(mods, {"qq-main": platform("aiocqhttp", bot, "qq-main")})
    event = mods.CronEvent(
        session(mods, getattr(mods.MessageType, kind), prefix + invalid_id)
    )

    assert await getattr(plugin, method)(event, **kwargs) == UNAVAILABLE

    for api in vars(bot).values():
        if isinstance(api, AsyncMock):
            api.assert_not_called()
    bot.api.call_action.assert_not_called()
    assert not event.stopped


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["GROUP_MESSAGE", "FRIEND_MESSAGE"])
async def test_normal_qq_default_leave_group_keeps_existing_behavior(
    plugin_modules, kind
):
    mods = plugin_modules
    bot = make_bot()
    plugin = make_plugin(mods, {})
    event = mods.QQEvent(bot, session(mods, getattr(mods.MessageType, kind), "456"))

    result = await plugin.llm_leave_group(event)

    if kind == "GROUP_MESSAGE":
        assert result == "成功退出群聊: 456"
        bot.set_group_leave.assert_awaited_once_with(group_id=456)
    else:
        assert result == "退群失败: group_id 必须为纯数字群号。"
        bot.set_group_leave.assert_not_called()
    plugin.context.get_platform_inst.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,kwargs",
    [
        ("llm_get_group_list", {}),
        ("llm_get_friend_list", {}),
        ("llm_leave_group", {"group_id": "123"}),
        ("llm_leave_group", {}),
        ("llm_delete_friend", {"user_id": "55"}),
        ("llm_delete_friend", {"user_id": ""}),
        ("llm_send_contact_card", {"target_id": "55"}),
        ("llm_send_contact_card", {}),
        ("llm_add_friend_request", {"user_id": "55"}),
        ("llm_add_group_request", {"group_id": "123"}),
    ],
)
async def test_related_llm_tools_cleanly_reject_missing_client(
    plugin_modules, method, kwargs
):
    mods = plugin_modules
    plugin = make_plugin(mods, {})
    event = mods.CronEvent(session(mods, mods.MessageType.GROUP_MESSAGE, "456"))

    result = await getattr(plugin, method)(event, **kwargs)

    assert UNAVAILABLE in result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind,destination", [("GROUP_MESSAGE", 456), ("FRIEND_MESSAGE", 88)]
)
async def test_normal_qq_events_keep_direct_bot_and_destination(
    plugin_modules, kind, destination
):
    mods = plugin_modules
    bot = make_bot()
    plugin = make_plugin(mods, {})
    event = mods.QQEvent(
        bot, session(mods, getattr(mods.MessageType, kind), str(destination))
    )

    result = await plugin.llm_check_messages(event, target_id="999")

    assert "已发送" in result
    if kind == "GROUP_MESSAGE":
        bot.send_group_forward_msg.assert_awaited_once()
        assert bot.send_group_forward_msg.await_args.kwargs["group_id"] == destination
    else:
        bot.send_private_forward_msg.assert_awaited_once()
        assert bot.send_private_forward_msg.await_args.kwargs["user_id"] == 88
    assert (
        await plugin.llm_get_group_list(event)
        == "共加入 1 个群聊:\n1. 群号: 123, 群名: source"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind,action,target_key,target_id",
    [
        ("GROUP_MESSAGE", "send_group_msg", "group_id", 456),
        ("FRIEND_MESSAGE", "send_private_msg", "user_id", 88),
    ],
)
async def test_normal_qq_contact_card_keeps_direct_bot(
    plugin_modules, kind, action, target_key, target_id
):
    mods = plugin_modules
    bot = make_bot()
    plugin = make_plugin(mods, {})
    event = mods.QQEvent(bot, session(mods, getattr(mods.MessageType, kind), "456"))

    result = await plugin.llm_send_contact_card(event, target_id="55")

    assert "已成功发送" in result
    assert bot.api.call_action.await_args.args == (action,)
    assert bot.api.call_action.await_args.kwargs[target_key] == target_id
    plugin.context.get_platform_inst.assert_not_called()


@pytest.mark.asyncio
async def test_normal_command_check_reports_delivery_failure(plugin_modules):
    mods = plugin_modules
    bot = make_bot()
    bot.send_group_forward_msg.side_effect = RuntimeError("send failed")
    plugin = make_plugin(mods, {})
    event = mods.QQEvent(bot, session(mods, mods.MessageType.GROUP_MESSAGE, "456"))

    results = [
        result async for result in plugin.check_messages(event, group_id=999, count=2)
    ]

    assert len(results) == 1
    assert "抽查失败" in results[0]


@pytest.mark.asyncio
async def test_non_admin_cannot_check_messages_or_leave_group(plugin_modules):
    mods = plugin_modules
    bot = make_bot()
    plugin = make_plugin(mods, {"qq-main": platform("aiocqhttp", bot, "qq-main")})
    event = mods.CronEvent(
        session(mods, mods.MessageType.GROUP_MESSAGE, "456"), role="member"
    )

    assert "仅管理员" in await plugin.llm_check_messages(event, target_id="999")
    assert "仅管理员" in await plugin.llm_leave_group(event, group_id="123")
    bot.get_group_msg_history.assert_not_awaited()
    bot.set_group_leave.assert_not_awaited()


@pytest.mark.asyncio
async def test_normal_qq_non_admin_keeps_permission_check(plugin_modules):
    mods = plugin_modules
    bot = make_bot()
    plugin = make_plugin(mods, {})
    event = mods.QQEvent(
        bot, session(mods, mods.MessageType.GROUP_MESSAGE, "456"), role="member"
    )

    assert "仅管理员" in await plugin.llm_check_messages(event, target_id="999")
    assert "仅管理员" in await plugin.llm_leave_group(event, group_id="123")
    bot.get_group_msg_history.assert_not_awaited()
    bot.set_group_leave.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["empty", "send_error"])
async def test_check_messages_does_not_claim_success_without_delivery(
    plugin_modules, failure
):
    mods = plugin_modules
    bot = make_bot()
    if failure == "empty":
        bot.get_group_msg_history.return_value = {"messages": []}
    else:
        bot.send_group_forward_msg.side_effect = RuntimeError("send failed")
    plugin = make_plugin(mods, {"qq-main": platform("aiocqhttp", bot, "qq-main")})
    event = mods.CronEvent(session(mods, mods.MessageType.GROUP_MESSAGE, "456"))

    result = await plugin.llm_check_messages(event, target_id="999")

    assert "失败" in result
    assert "已发送" not in result
