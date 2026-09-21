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
            broadcast_ip="172.16.42.255"
        )
        assert res is True
        assert mock_sock.sendto.called
        # Verify packet was sent to multiple targets including directed broadcast
        calls = [c[0] for c in mock_sock.sendto.call_args_list]
        dests = {c[1][0] for c in calls}
        assert "172.16.42.255" in dests
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
            broadcast_ip="172.16.42.255",
            device_id=test_dev_id,
            hostname=test_host
        )
        assert res is True
        mock_sync_send.assert_called_once_with(
            mac_address="AA:BB:CC:DD:EE:FF",
            broadcast_ip="172.16.42.255",
            ip_address="172.16.42.100"
        )
        # Pending shutdown commands must be wiped out so PC won't shut down upon booting
        assert len(pending_device_commands[test_dev_id]) == 0
        assert len(pending_device_commands[test_host]) == 0
