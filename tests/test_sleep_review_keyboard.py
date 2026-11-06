"""Проверки клавиатуры и маршрутизации без PostgreSQL и Telegram."""

import asyncio
import importlib
import socket
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import dotenv
import psycopg
import pytest


@pytest.fixture
def modules(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Тест не должен обращаться к сети или PostgreSQL")

    monkeypatch.setattr(dotenv, "load_dotenv", lambda: None)
    monkeypatch.setattr(psycopg, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    return SimpleNamespace(
        keyboards=importlib.import_module("app.bot.keyboards"),
        commands=importlib.import_module("app.bot.commands"),
        notifications=importlib.import_module("app.services.sleep_notification"),
    )


@pytest.mark.parametrize("detected_id", [1, 42, 987654321])
def test_review_buttons_and_notification_compatibility(modules, detected_id):
    expected = [[
        ("✅ Подтвердить", f"confirm_sleep:{detected_id}"),
        ("✏️ Исправить", f"correct_sleep:{detected_id}"),
    ]]
    for keyboard in (
        modules.keyboards.sleep_review_keyboard(detected_id),
        modules.notifications.get_notification_keyboard(detected_id=detected_id),
    ):
        assert [
            [(button.text, button.callback_data) for button in row]
            for row in keyboard.inline_keyboard
        ] == expected


def test_review_and_notifications_use_shared_factory(modules, monkeypatch):
    shared = modules.keyboards.sleep_review_keyboard
    assert modules.commands.sleep_review_keyboard is shared
    assert modules.notifications.sleep_review_keyboard is shared

    factory = Mock(return_value=shared(42))
    monkeypatch.setattr(modules.commands, "sleep_review_keyboard", factory)
    monkeypatch.setattr(modules.notifications, "sleep_review_keyboard", factory)
    monkeypatch.setattr(modules.commands, "get_pending_sleep", Mock(return_value=[
        (42, "2026-11-05T23:00:00+03:00", "2026-11-06T07:00:00+03:00", 480, 0),
    ]))
    message = SimpleNamespace(from_user=SimpleNamespace(id=123), answer=AsyncMock())

    asyncio.run(modules.commands.review_command(message))
    assert message.answer.await_args_list[-1].kwargs["reply_markup"] is factory.return_value
    assert modules.notifications.get_notification_keyboard(detected_id=42) is factory.return_value
    assert factory.call_count == 2
    factory.assert_called_with(42)


@pytest.mark.parametrize("source", ["review", "notification"])
@pytest.mark.parametrize("button_index", [0, 1])
def test_buttons_route_to_existing_handlers(modules, monkeypatch, source, button_index):
    commands = modules.commands
    confirm = Mock(return_value="Сон сохранён: тест")
    get_record = Mock(return_value=(
        "2026-11-05T23:00:00+03:00", "2026-11-06T07:00:00+03:00", 0,
    ))
    monkeypatch.setattr(commands, "confirm_detected_sleep", confirm)
    monkeypatch.setattr(commands, "get_detected_sleep_by_id", get_record)
    factory = (
        commands.sleep_review_keyboard if source == "review"
        else modules.notifications.get_notification_keyboard
    )
    callback = SimpleNamespace(
        data=factory(42).inline_keyboard[0][button_index].callback_data,
        from_user=SimpleNamespace(id=123),
        answer=AsyncMock(),
        message=SimpleNamespace(answer=AsyncMock(), edit_reply_markup=AsyncMock()),
    )
    state = SimpleNamespace(update_data=AsyncMock(), set_state=AsyncMock())

    # Используем настоящий Router: проверяем фильтры и порядок регистрации,
    # включая то, что callback не попал в завершающий debug_callback.
    asyncio.run(commands.router.propagate_event(
        "callback_query", callback, state=state, raw_state=None,
    ))

    callback.answer.assert_awaited_once_with()
    if button_index == 0:
        confirm.assert_called_once_with(123, 42)
        get_record.assert_not_called()
        callback.message.edit_reply_markup.assert_awaited_once_with(reply_markup=None)
        callback.message.answer.assert_awaited_once_with("🌙 Сон сохранён: тест")
        state.set_state.assert_not_awaited()
    else:
        confirm.assert_not_called()
        get_record.assert_called_once_with(123, 42)
        state.update_data.assert_awaited_once_with(
            detected_id=42,
            sleep_start="2026-11-05T23:00:00+03:00",
            sleep_end="2026-11-06T07:00:00+03:00",
            awake_minutes=0,
        )
        state.set_state.assert_awaited_once_with(commands.SleepCorrection.choosing_field)
        assert "Редактирование сна" in callback.message.answer.await_args.args[0]
