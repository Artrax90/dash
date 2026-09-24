import pytest
from unittest.mock import patch, MagicMock
from backend.app.services.wol_service import wol_service
from backend.app.api.v1.agents import pending_device_commands, queue_device_command
from backend.app.api.v1.telegram import send_wol_packet, process_telegram_command


def test_wol_service_send_magic_packet_sync():
    """Verify WolService has a working synchronous dispatch method."""
    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock_cls.return_value.__enter__.return_value = mock_sock

        res = wol_service.send_magic_packet_sync(
            mac_address="00:11:22:33:44:55",
            ip_address="172.16.42.50",
            broadcast_ip="172.16.43.255"
        )
        assert res is True
        assert mock_sock.sendto.called
        # Verify packet was sent to multiple targets including directed broadcast
        calls = [c[0] for c in mock_sock.sendto.call_args_list]
        dests = {c[1][0] for c in calls}
        assert "172.16.43.255" in dests
        assert "255.255.255.255" in dests


def test_telegram_send_wol_packet_clears_pending_and_calls_wol_service():
    """Verify send_wol_packet clears stale shutdown commands and invokes wol_service."""
    test_dev_id = "DEV-TG-WOL-TEST"
    test_host = "HOST-TG-WOL-TEST"
    
    # Pre-queue a shutdown command
    queue_device_command(test_dev_id, "SHUTDOWN", reason="Pre-test shutdown")
    queue_device_command(test_host, "SHUTDOWN", reason="Pre-test shutdown")
    assert len(pending_device_commands[test_dev_id]) > 0
    assert len(pending_device_commands[test_host]) > 0

    with patch.object(wol_service, "send_magic_packet_sync", return_value=True) as mock_sync_send:
        res = send_wol_packet(
            mac_str="AA:BB:CC:DD:EE:FF",
            ip_address="172.16.42.100",
            broadcast_ip="172.16.43.255",
            device_id=test_dev_id,
            hostname=test_host
        )
        assert res is True
        mock_sync_send.assert_called_once_with(
            mac_address="AA:BB:CC:DD:EE:FF",
            broadcast_ip="172.16.43.255",
            ip_address="172.16.42.100"
        )
        # Pending shutdown commands must be wiped out so PC won't shut down upon booting
        assert len(pending_device_commands[test_dev_id]) == 0
        assert len(pending_device_commands[test_host]) == 0


def test_telegram_bulk_shutdown_callbacks_and_hierarchy():
    """Verify Telegram bulk shutdown callbacks for room, floor, building, and group."""
    from backend.app.api.v1.telegram import process_telegram_callback
    
    mock_users = [{
        "username": "admin",
        "displayName": "Администратор",
        "role": "Суперадминистратор",
        "scope": "Все устройства",
        "allowedGroups": [],
        "telegramChatId": "999888",
        "enabled": True
    }]
    mock_devices = [
        {
            "id": "DEV-01",
            "name": "PC-518-01",
            "hostname": "host-518-01",
            "building": "МНОК",
            "floor": "5 этаж",
            "room": "518Т",
            "group": "МНОК / 5 этаж / 518Т",
            "ip": "172.16.42.10",
            "mac": "AA:BB:CC:DD:EE:01",
            "powerStatus": "On",
            "isOnline": True
        },
        {
            "id": "DEV-02",
            "name": "PC-518-02",
            "hostname": "host-518-02",
            "building": "МНОК",
            "floor": "5 этаж",
            "room": "518Т",
            "group": "МНОК / 5 этаж / 518Т",
            "ip": "172.16.42.11",
            "mac": "AA:BB:CC:DD:EE:02",
            "powerStatus": "On",
            "isOnline": True
        }
    ]

    with patch("backend.app.api.v1.telegram.load_users", return_value=mock_users):
        with patch("backend.app.api.v1.telegram.load_devices", return_value=mock_devices):
            with patch("backend.app.api.v1.agents.send_direct_lan_power_signal") as mock_lan:
                with patch("backend.app.api.v1.agents.queue_device_command") as mock_queue:
                    # 1. Test room confirmation view
                    conf_res = process_telegram_callback("999888", "confirm:shutrm:МНОК:5 этаж:518Т", {"username": "admin"})
                    assert "Подтверждение выключения кабинета" in conf_res["text"]
                    assert "do:shutrm:МНОК:5 этаж:518Т" in str(conf_res["reply_markup"])

                    # 2. Test execute room shutdown
                    do_rm_res = process_telegram_callback("999888", "do:shutrm:МНОК:5 этаж:518Т", {"username": "admin"})
                    assert "Команда выключения отправлена" in do_rm_res["text"]
                    assert "2" in do_rm_res["text"]

                    # 3. Test floor confirmation and execute
                    conf_flr = process_telegram_callback("999888", "confirm:shutflr:МНОК:5 этаж", {"username": "admin"})
                    assert "Подтверждение выключения этажа" in conf_flr["text"]
                    assert "do:shutflr:МНОК:5 этаж" in str(conf_flr["reply_markup"])

                    do_flr_res = process_telegram_callback("999888", "do:shutflr:МНОК:5 этаж", {"username": "admin"})
                    assert "Команда выключения отправлена" in do_flr_res["text"]

                    # 4. Test building confirmation and execute
                    conf_bld = process_telegram_callback("999888", "confirm:shutbld:МНОК", {"username": "admin"})
                    assert "Подтверждение выключения корпуса" in conf_bld["text"]
                    assert "do:shutbld:МНОК" in str(conf_bld["reply_markup"])

                    do_bld_res = process_telegram_callback("999888", "do:shutbld:МНОК", {"username": "admin"})
                    assert "Команда выключения отправлена" in do_bld_res["text"]

                    # 5. Test group confirmation and execute
                    conf_grp = process_telegram_callback("999888", "confirm:shutgrp:МНОК / 5 этаж / 518Т", {"username": "admin"})
                    assert "Подтверждение выключения группы" in conf_grp["text"]
                    assert "do:shutgrp:МНОК / 5 этаж / 518Т" in str(conf_grp["reply_markup"])

                    do_grp_res = process_telegram_callback("999888", "do:shutgrp:МНОК / 5 этаж / 518Т", {"username": "admin"})
                    assert "Команда выключения отправлена" in do_grp_res["text"]


def test_telegram_text_command_bulk_room_and_group():
    """Verify /shutdown and /wake text commands when passing cabinet/room name."""
    from backend.app.api.v1.telegram import process_telegram_command

    mock_users = [{
        "username": "admin",
        "displayName": "Администратор",
        "role": "Суперадминистратор",
        "scope": "Все устройства",
        "allowedGroups": [],
        "telegramChatId": "999888",
        "enabled": True
    }]
    mock_devices = [
        {
            "id": "DEV-01",
            "name": "PC-518-01",
            "hostname": "host-518-01",
            "building": "МНОК",
            "floor": "5 этаж",
            "room": "518Т",
            "group": "МНОК / 5 этаж / 518Т",
            "ip": "172.16.42.10",
            "mac": "AA:BB:CC:DD:EE:01",
            "powerStatus": "On",
            "isOnline": True
        }
    ]

    with patch("backend.app.api.v1.telegram.load_users", return_value=mock_users):
        with patch("backend.app.api.v1.telegram.load_devices", return_value=mock_devices):
            with patch("backend.app.api.v1.agents.send_direct_lan_power_signal"):
                with patch("backend.app.api.v1.agents.queue_device_command"):
                    # 1. /shutdown with room number
                    res_shut = process_telegram_command("999888", "/shutdown 518Т", {"username": "admin"})
                    assert "Команда выключения отправлена" in res_shut["text"]
                    assert "518Т" in res_shut["text"]

                    # 2. /wake with room number
                    with patch("backend.app.api.v1.telegram.send_wol_packet") as mock_wol:
                        res_wake = process_telegram_command("999888", "/wake 518Т", {"username": "admin"})
                        assert "Wake-on-LAN отправлен" in res_wake["text"]
                        assert mock_wol.called


