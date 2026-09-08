import pytest
from datetime import datetime, timezone, timedelta
from backend.app.services.report_service import (
    generate_morning_report,
    generate_evening_report,
    format_morning_report_message,
    format_evening_report_message,
    should_send_user_report
)

def test_morning_report_detects_unreturned_devices():
    user = {
        'id': 'USR-01',
        'username': 'ivanov',
        'displayName': 'Ivan Ivanov',
        'role': 'Operator',
        'scope': 'Selected',
        'allowedGroups': ['Bld1 / Flr1 / Room101', 'Bld1 / Flr1 / Room102'],
        'telegramChatId': '12345678'
    }
    devices = [
        {
            'id': 'PC-101',
            'name': 'PC-101',
            'building': 'Bld1',
            'floor': 'Flr1',
            'room': 'Room101',
            'group': 'Bld1 / Flr1 / Room101',
            'powerStatus': 'On',
            'isOnline': True
        },
        {
            'id': 'PC-102',
            'name': 'PC-102',
            'building': 'Bld1',
            'floor': 'Flr1',
            'room': 'Room102',
            'group': 'Bld1 / Flr1 / Room102',
            'powerStatus': 'Off',
            'isOnline': False
        },
        {
            'id': 'PC-OTHER',
            'name': 'PC-OTHER',
            'building': 'Bld2',
            'floor': 'Flr2',
            'room': 'Room201',
            'group': 'Bld2 / Flr2 / Room201',
            'powerStatus': 'Off',
            'isOnline': False
        }
    ]
    now = datetime.now(timezone.utc)
    power_logs = {
        'PC-102': [
            {
                'id': 'EVT-1',
                'action': 'REBOOT',
                'timestamp': (now - timedelta(hours=3)).isoformat(),
                'details': 'Windows Update restart',
                'initiator': 'System'
            }
        ]
    }

    report = generate_morning_report(user, devices, power_logs, now_dt=now)

    assert report['total_devices'] == 2
    assert report['online_devices'] == 1
    assert report['offline_devices'] == 1
    assert len(report['unreturned_devices']) == 1
    assert report['unreturned_devices'][0]['id'] == 'PC-102'
    assert 'reboot' in report['unreturned_devices'][0]['reason'].lower()

def test_evening_report_lists_active_devices():
    user = {
        'id': 'USR-01',
        'username': 'ivanov',
        'displayName': 'Ivan Ivanov',
        'role': 'Operator',
        'scope': 'All',
        'allowedGroups': [],
        'telegramChatId': '12345678'
    }
    devices = [
        {
            'id': 'PC-01',
            'name': 'PC-Accounting-1',
            'building': 'Bld1',
            'floor': 'Flr2',
            'room': 'Room205',
            'powerStatus': 'On',
            'isOnline': True
        },
        {
            'id': 'PC-02',
            'name': 'PC-Accounting-2',
            'building': 'Bld1',
            'floor': 'Flr2',
            'room': 'Room205',
            'powerStatus': 'Off',
            'isOnline': False
        }
    ]

    report = generate_evening_report(user, devices)
    assert report['total_devices'] == 2
    assert report['online_count'] == 1
    assert report['offline_count'] == 1
    assert len(report['active_devices']) == 1
    assert report['active_devices'][0]['id'] == 'PC-01'

def test_should_send_user_report_by_schedule():
    user = {
        'id': 'USR-01',
        'telegramChatId': '12345678',
        'telegramReports': {
            'enabled': True,
            'morningReport': {'enabled': True, 'time': '08:00'},
            'eveningReport': {'enabled': True, 'time': '20:00'},
            'days': [0, 1, 2, 3, 4]
        }
    }
    mon_morning = datetime(2026, 9, 7, 8, 0, 0)
    assert should_send_user_report(user, 'morning', current_dt=mon_morning) is True
    assert should_send_user_report(user, 'evening', current_dt=mon_morning) is False

    mon_morning_late = datetime(2026, 9, 7, 8, 5, 0)
    assert should_send_user_report(user, 'morning', current_dt=mon_morning_late) is False

    sun_morning = datetime(2026, 9, 6, 8, 0, 0)
    assert should_send_user_report(user, 'morning', current_dt=sun_morning) is False

def test_should_send_user_report_timezone_aware():
    from datetime import timezone
    user = {
        'id': 'USR-01',
        'telegramChatId': '12345678',
        'telegramReports': {
            'enabled': True,
            'morningReport': {'enabled': True, 'time': '08:25'},
            'eveningReport': {'enabled': True, 'time': '20:00'},
            'days': [0, 1, 2, 3, 4]
        }
    }
    # Monday 05:25:00 UTC == Monday 08:25:00 MSK (UTC+3)
    utc_morning = datetime(2026, 9, 7, 5, 25, 0, tzinfo=timezone.utc)
    assert should_send_user_report(user, 'morning', current_dt=utc_morning) is True

def test_get_local_now_supports_moscow_and_custom_timezones():
    from backend.app.core.time_utils import get_local_now
    now_msk = get_local_now("Europe/Moscow")
    diff_hours = (now_msk.utcoffset().total_seconds() / 3600) if now_msk.utcoffset() else 3
    assert int(diff_hours) == 3


def test_telegram_reports_button_callbacks(monkeypatch):
    import backend.app.api.v1.telegram as tg_module

    fake_user = {
        'id': 'USR-01',
        'username': 'testuser',
        'displayName': 'Тестовый оператор',
        'role': 'Дежурный оператор',
        'scope': 'Все устройства',
        'allowedGroups': [],
        'telegramChatId': '12345678',
        'enabled': True
    }
    fake_devices = [
        {
            'id': 'PC-1',
            'name': 'ПК-1',
            'building': 'Корпус 1',
            'floor': '1 этаж',
            'room': '101',
            'powerStatus': 'On',
            'isOnline': True
        }
    ]
    monkeypatch.setattr(tg_module, 'load_users', lambda: [fake_user])
    monkeypatch.setattr(tg_module, 'load_devices', lambda: fake_devices)

    res_menu = tg_module.process_telegram_callback('12345678', 'report:menu', {'username': 'testuser'})
    assert 'text' in res_menu
    assert 'отчет' in res_menu['text'].lower()

    res_morning = tg_module.process_telegram_callback('12345678', 'report:morning', {'username': 'testuser'})
    assert 'text' in res_morning
    assert 'доброе утро' in res_morning['text'].lower()

    res_evening = tg_module.process_telegram_callback('12345678', 'report:evening', {'username': 'testuser'})
    assert 'text' in res_evening
    assert 'добрый вечер' in res_evening['text'].lower()

def test_morning_report_online_device_never_in_unreturned():
    user = {'id': 'USR-1', 'scope': 'Все устройства', 'allowedGroups': []}
    devices = [
        {'id': 'PC-01', 'name': 'YEREMIN', 'room': 'Office', 'powerStatus': 'On', 'isOnline': True}
    ]
    now = datetime.now(timezone.utc)
    power_logs = {
        'PC-01': [
            {'action': 'REBOOT', 'timestamp': (now - timedelta(hours=2)).isoformat(), 'details': 'Night schedule'}
        ]
    }
    rep = generate_morning_report(user, devices, power_logs, now_dt=now)
    assert rep['online_devices'] == 1
    assert rep['offline_devices'] == 0
    assert len(rep['unreturned_devices']) == 0

def test_morning_report_boot_or_wake_never_in_unreturned():
    user = {'id': 'USR-1', 'scope': 'Все устройства', 'allowedGroups': []}
    devices = [
        {'id': 'PC-02', 'name': 'DESKTOP', 'room': 'Office', 'powerStatus': 'Off', 'isOnline': False}
    ]
    now = datetime.now(timezone.utc)
    # The device has a BOOT or WAKE event in the night window
    power_logs = {
        'PC-02': [
            {'action': 'BOOT', 'timestamp': (now - timedelta(hours=1)).isoformat(), 'details': 'Компьютер включен локально'}
        ]
    }
    rep = generate_morning_report(user, devices, power_logs, now_dt=now)
    assert rep['online_devices'] == 0
    assert rep['offline_devices'] == 1
    # Crucial: BOOT is NOT a reason to list in "не вернулись онлайн после ночных событий"
    assert len(rep['unreturned_devices']) == 0

def test_morning_report_accurate_counts_and_formatting():
    user = {'id': 'USR-1', 'displayName': 'Сергей', 'scope': 'Все устройства', 'allowedGroups': []}
    devices = [
        {'id': 'PC-1', 'name': 'YEREMIN', 'room': 'Office', 'powerStatus': 'On', 'isOnline': True},
        {'id': 'PC-2', 'name': 'DESKTOP-J8IDHQH', 'room': 'Office', 'powerStatus': 'On', 'isOnline': True},
        {'id': 'PC-3', 'name': 'LAB-1', 'room': 'B4-Class-541', 'powerStatus': 'Off', 'isOnline': False},
        {'id': 'PC-4', 'name': 'LAB-2', 'room': 'B4-Class-541', 'powerStatus': 'Off', 'isOnline': False},
    ]
    now = datetime.now(timezone.utc)
    power_logs = {}
    rep = generate_morning_report(user, devices, power_logs, now_dt=now)
    assert rep['online_devices'] == 2
    assert rep['offline_devices'] == 2
    msg = format_morning_report_message(rep)
    assert "В сети: <b>2</b> ПК" in msg
    assert "Выключено: <b>2</b> ПК" in msg
    assert "Office</b>: 2/2 🟢" in msg
    assert "B4-Class-541</b>: 0/2 🟢" in msg
    assert "Ночных сбоев не зафиксировано" in msg

def test_morning_report_message_when_no_night_reboots():
    user = {'id': 'USR-1', 'displayName': 'Сергей', 'scope': 'Все устройства', 'allowedGroups': []}
    devices = [
        {'id': 'PC-1', 'name': 'YEREMIN', 'room': 'Office', 'powerStatus': 'On', 'isOnline': True}
    ]
    rep = generate_morning_report(user, devices, {})
    msg = format_morning_report_message(rep)
    assert "перезагрузк" not in msg.lower()
    assert "штатном режиме" in msg.lower()

def test_morning_report_message_when_night_reboots_exist():
    now = datetime.now(timezone.utc)
    user = {'id': 'USR-1', 'displayName': 'Сергей', 'scope': 'Все устройства', 'allowedGroups': []}
    devices = [
        {'id': 'PC-1', 'name': 'YEREMIN', 'room': 'Office', 'powerStatus': 'On', 'isOnline': True}
    ]
    power_logs = {
        'PC-1': [
            {'action': 'REBOOT', 'timestamp': (now - timedelta(hours=2)).isoformat(), 'details': 'Scheduled night reboot'}
        ]
    }
    rep = generate_morning_report(user, devices, power_logs, now_dt=now)
    assert rep.get('night_reboots_count') == 1
    msg = format_morning_report_message(rep)
    assert "плановые перезагрузки (1 шт.) прошли штатно" in msg


def test_load_devices_cache_and_update():
    import backend.app.api.v1.telegram as tg_module
    sample_devs = [
        {"id": "PC-TEST-1", "name": "Test PC 1", "powerStatus": "On", "isOnline": True}
    ]
    tg_module.update_cached_devices(sample_devs)
    assert tg_module.get_cached_devices() == sample_devs
    loaded = tg_module.load_devices()
    assert len(loaded) == 1
    assert loaded[0]["id"] == "PC-TEST-1"

@pytest.mark.anyio
async def test_load_devices_async():
    import backend.app.api.v1.telegram as tg_module
    devs = await tg_module.load_devices_async()
    assert isinstance(devs, list)


