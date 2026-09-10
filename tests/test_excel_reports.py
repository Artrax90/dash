import io
import pytest
import openpyxl
from datetime import datetime, timezone, timedelta
from backend.app.services.excel_report_service import generate_monitoring_excel_report

def test_generate_monitoring_excel_report_structure():
    mock_devices = [
        {
            'id': 'PC-01',
            'name': 'ARM-01',
            'group_name': 'Accounting',
            'building': 'Main',
            'floor': 'Floor 2',
            'room': '204',
            'power_status': 'On',
            'agent_status': 'Connected',
            'ip_address': '192.168.1.50',
            'cpu': 25,
            'ram': 45,
            'disk': 60
        },
        {
            'id': 'PC-02',
            'name': 'ARM-02',
            'group_name': 'Accounting',
            'building': 'Main',
            'floor': 'Floor 2',
            'room': '204',
            'power_status': 'Off',
            'agent_status': 'Disconnected',
            'ip_address': '192.168.1.51',
            'cpu': 0,
            'ram': 0,
            'disk': 70
        }
    ]
    
    mock_telemetry_points = [
        {
            'time': (datetime.now(timezone.utc) - timedelta(hours=i)).timestamp(),
            'timestamp': (datetime.now(timezone.utc) - timedelta(hours=i)).isoformat(),
            'deviceId': 'PC-01',
            'cpu': 20 + i * 2,
            'ram': 40 + i,
            'disk': 60,
            'isOnline': True
        }
        for i in range(12)
    ]
    
    mock_power_events = [
        {
            'id': 'EVT-1',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'action': 'WAKE',
            'title': 'Wake by Schedule (WoL)',
            'deviceId': 'PC-01',
            'deviceName': 'ARM-01',
            'status': 'Success',
            'initiator': 'Schedule',
            'source': 'SCHEDULE',
            'details': 'Morning Wake'
        }
    ]
    
    mock_alerts = [
        {
            'id': 'ALT-1',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'deviceId': 'PC-01',
            'severity': 'Warning',
            'description': 'High CPU utilization (95 pct)',
            'category': 'Resource'
        }
    ]

    report_bytes = generate_monitoring_excel_report(
        period_type='hourly_24h',
        scope_title='Accounting (Main / Floor 2 / 204)',
        devices=mock_devices,
        telemetry_points=mock_telemetry_points,
        power_events=mock_power_events,
        alerts=mock_alerts
    )

    assert isinstance(report_bytes, bytes)
    assert len(report_bytes) > 0

    wb = openpyxl.load_workbook(io.BytesIO(report_bytes))
    sheet_names = wb.sheetnames
    
    assert 'Сводка и Графики' in sheet_names
    assert 'Телеметрия' in sheet_names
    assert 'События питания' in sheet_names
    assert 'Алерты и Инциденты' in sheet_names
    assert 'Список ПК' in sheet_names

    summary_sheet = wb['Сводка и Графики']
    assert len(summary_sheet._charts) >= 1

@pytest.mark.anyio
async def test_excel_report_endpoint():
    import httpx
    from backend.app.main import app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/devices/reports/excel?time_range=24h&group=ALL")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert len(resp.content) > 0
        wb = openpyxl.load_workbook(io.BytesIO(resp.content))
        assert "Сводка и Графики" in wb.sheetnames

def test_generate_monitoring_excel_report_with_illegal_xml_control_characters():
    """TDD: Ensure excel report generation does NOT crash on control characters like \x00, \x05, etc."""
    mock_devices = [
        {
            'id': 'PC-9AEB',
            'name': 'ARM-09\x00\x01',
            'group_name': 'Auditorium\x07',
            'building': 'Main\x08',
            'floor': 'Floor 1',
            'room': '101\x1f',
            'power_status': 'On',
            'agent_status': 'Connected',
            'ip_address': '172.16.42.0',
            'cpu': 10,
            'ram': 20,
            'disk': 30
        }
    ]
    mock_power_events = [
        {
            'id': 'EVT-USB-1',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'action': 'USB_PLUG',
            'title': 'USB Device Attached\x00',
            'deviceId': 'PC-9AEB',
            'deviceName': 'ARM-09\x05',
            'status': 'Success',
            'initiator': 'Agent\x00',
            'source': 'AGENT',
            'details': 'Flash drive inserted\x02'
        }
    ]
    mock_alerts = [
        {
            'id': 'ALT-USB-99',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'deviceId': 'PC-9AEB',
            'severity': 'Info',
            'description': 'Извлечен съемный USB-накопитель: Netac OnlyDisk USB Device (S/N: 0000000005\x00)',
            'category': 'Hardware\x00'
        }
    ]
    mock_telemetry_points = [
        {
            'time': datetime.now(timezone.utc).timestamp(),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'deviceId': 'PC-9AEB',
            'cpu': 15,
            'ram': 35,
            'disk': 45,
            'isOnline': True
        }
    ]

    report_bytes = generate_monitoring_excel_report(
        period_type='hourly_24h',
        scope_title='Test Scope with \x00 null byte',
        devices=mock_devices,
        telemetry_points=mock_telemetry_points,
        power_events=mock_power_events,
        alerts=mock_alerts
    )

    assert isinstance(report_bytes, bytes)
    assert len(report_bytes) > 0
    wb = openpyxl.load_workbook(io.BytesIO(report_bytes))
    ws_alerts = wb['Алерты и Инциденты']
    # Verify description is saved and illegal char was stripped
    assert 'Netac OnlyDisk USB Device' in ws_alerts.cell(row=2, column=6).value
    assert '\x00' not in ws_alerts.cell(row=2, column=6).value

