import asyncio
from datetime import datetime
from typing import List, Dict, Any
from backend.app.services.wol_service import wol_service
from backend.app.ws.manager import ws_manager

class SchedulerService:
    def __init__(self):
        self._running = False
        self._last_executed_step: Dict[str, str] = {}

    async def execute_action_for_devices(self, action: str, target_devs: List[Any], sch_name: str, sch_id: str, target_grp: str, trigger_type: str = "SCHEDULER_CRON"):
        """Dispatch low-level action on targeted devices via Direct LAN UDP + Heartbeat Queue, and create execution log entry."""
        from backend.app.api.v1.schedules import execution_logs_db
        from backend.app.api.v1.agents import queue_device_command, send_direct_lan_power_signal
        
        dev_count = max(1, len(target_devs))
        act_upper = action.upper()
        
        if act_upper == "WAKE":
            for dev in target_devs:
                mac = getattr(dev, "mac_address", None)
                bip = getattr(dev, "broadcast_ip", None)
                ip = getattr(dev, "ip_address", None)
                if mac:
                    await wol_service.send_magic_packet(mac, bip, ip_address=ip)
            summary = f"WoL Magic Packet отправлен на {dev_count} ПК"
        elif act_upper in ["SHUTDOWN", "FORCE_SHUTDOWN"]:
            for dev in target_devs:
                dev_id = getattr(dev, "id", None)
                hostname = getattr(dev, "hostname", None)
                ip = getattr(dev, "ip_address", None)
                mac = getattr(dev, "mac_address", None)
                if ip:
                    send_direct_lan_power_signal(
                        ip_address=ip,
                        action="SHUTDOWN",
                        device_id=dev_id or "",
                        mac_address=mac or "",
                        hostname=hostname or ""
                    )
                if dev_id:
                    queue_device_command(dev_id, "SHUTDOWN", force=True, reason=f"Schedule: {sch_name}")
                if hostname and hostname != dev_id:
                    queue_device_command(hostname, "SHUTDOWN", force=True, reason=f"Schedule: {sch_name}")
            summary = f"Команда выключения отправлена на {dev_count} ПК"
        elif act_upper == "REBOOT":
            for dev in target_devs:
                dev_id = getattr(dev, "id", None)
                hostname = getattr(dev, "hostname", None)
                ip = getattr(dev, "ip_address", None)
                mac = getattr(dev, "mac_address", None)
                if ip:
                    send_direct_lan_power_signal(
                        ip_address=ip,
                        action="REBOOT",
                        device_id=dev_id or "",
                        mac_address=mac or "",
                        hostname=hostname or ""
                    )
                if dev_id:
                    queue_device_command(dev_id, "REBOOT", force=True, reason=f"Schedule: {sch_name}")
                if hostname and hostname != dev_id:
                    queue_device_command(hostname, "REBOOT", force=True, reason=f"Schedule: {sch_name}")
            summary = f"Команда перезагрузки отправлена на {dev_count} ПК"
        elif act_upper in ["LOGOFF", "RDP_CLEANUP"]:
            for dev in target_devs:
                dev_id = getattr(dev, "id", None)
                hostname = getattr(dev, "hostname", None)
                ip = getattr(dev, "ip_address", None)
                mac = getattr(dev, "mac_address", None)
                if ip:
                    send_direct_lan_power_signal(
                        ip_address=ip,
                        action="LOGOFF",
                        device_id=dev_id or "",
                        mac_address=mac or "",
                        hostname=hostname or ""
                    )
                if dev_id:
                    queue_device_command(dev_id, "LOGOFF", force=True, reason=f"Schedule: {sch_name}")
                if hostname and hostname != dev_id:
                    queue_device_command(hostname, "LOGOFF", force=True, reason=f"Schedule: {sch_name}")
            summary = f"Команда очистки сессий выполнена на {dev_count} ПК"
        else:
            summary = f"Действие {action} отправлено на {dev_count} ПК"
            
        now_iso = datetime.utcnow().isoformat() + "Z"

        try:
            from backend.app.api.v1.devices import log_device_power_event
            for dev in target_devs:
                dev_id = getattr(dev, "id", None)
                if dev_id:
                    log_device_power_event(
                        device_id=dev_id,
                        action=act_upper,
                        details=f"Выполнено по расписанию: '{sch_name}'",
                        status="Success",
                        initiator=f"Планировщик ('{sch_name}')",
                        source="SCHEDULE",
                        device_name=getattr(dev, "name", None)
                    )
        except Exception as e:
            print(f"[Scheduler] Error logging device power event: {e}")
        
        log_entry = {
            "id": f"LOG-{len(execution_logs_db) + 1090}",
            "scheduleId": sch_id,
            "scheduleName": sch_name,
            "action": act_upper,
            "target": target_grp,
            "timestamp": now_iso,
            "status": "Success",
            "devicesTargeted": dev_count,
            "devicesSuccess": dev_count,
            "devicesFailed": 0,
            "triggeredBy": trigger_type,
            "details": f"{summary}. Инициировано правилом расписания."
        }
        execution_logs_db.insert(0, log_entry)
        try:
            from backend.app.api.v1.schedules import save_schedule_logs, save_schedules, schedules_db
            save_schedule_logs(execution_logs_db)
            save_schedules(schedules_db)
        except Exception:
            pass
        
        # Broadcast via WebSocket
        await ws_manager.broadcast_event("SCHEDULE_EXECUTED", {
            "scheduleId": sch_id,
            "scheduleName": sch_name,
            "action": act_upper,
            "log": log_entry
        })
        print(f"[Scheduler] Executed action '{act_upper}' for '{sch_name}' on {dev_count} devices ({trigger_type}).")

    async def start_background_loop(self):
        """Continuous background loop evaluating multi-step schedules every 5 seconds."""
        self._running = True
        print("[Scheduler] Background multi-step scheduler loop started.")
        
        while self._running:
            try:
                from backend.app.api.v1.schedules import schedules_db
                from backend.app.db.session import AsyncSessionLocal
                from backend.app.models.device import Device
                from sqlalchemy import select
                
                now = datetime.now()
                current_time_str = now.strftime("%H:%M")
                current_minute_key = now.strftime("%Y-%m-%d %H:%M")
                weekday_idx = now.weekday() # 0=ПН, ..., 5=СБ, 6=ВС
                day_names_ru = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
                day_names_en = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
                current_day_ru = day_names_ru[weekday_idx]
                current_day_en = day_names_en[weekday_idx]
                
                async with AsyncSessionLocal() as session:
                    res = await session.execute(select(Device))
                    devices = res.scalars().all()
                    
                    # 1. Device Offline / Shutdown Watchdog
                    from backend.app.models.device import PowerStatus, AgentStatus
                    from backend.app.api.v1.devices import log_device_power_event, device_power_logs, format_device_summary
                    
                    now_utc = datetime.utcnow()
                    status_changed = False
                    for dev in devices:
                        is_agentless = (
                            dev.agent_version == "Agentless" or 
                            dev.os_type == "ThinClient" or 
                            (dev.id and dev.id.upper().startswith("TC-")) or 
                            "Agentless" in (dev.tags or []) or
                            "Тонкий клиент" in (dev.tags or [])
                        )
                        if is_agentless:
                            # Thin clients have no background agent.
                            # Online status is determined via ICMP ping and fast TCP check:
                            if dev.ip_address:
                                ping_ok = False
                                try:
                                    ping_cmd = ["ping", "-n", "1", "-w", "600", dev.ip_address] if os.name == "nt" else ["ping", "-c", "1", "-W", "1", dev.ip_address]
                                    proc = await asyncio.create_subprocess_exec(*ping_cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
                                    rc = await asyncio.wait_for(proc.wait(), timeout=1.2)
                                    ping_ok = (rc == 0)
                                except Exception:
                                    pass

                                if not ping_ok:
                                    for p in [3389, 80, 443, 22, 8080]:
                                        try:
                                            _, writer = await asyncio.wait_for(asyncio.open_connection(dev.ip_address, p), timeout=0.2)
                                            writer.close()
                                            await writer.wait_closed()
                                            ping_ok = True
                                            break
                                        except Exception:
                                            pass

                                if ping_ok:
                                    if dev.power_status != PowerStatus.ON or dev.agent_status != AgentStatus.CONNECTED:
                                        dev.power_status = PowerStatus.ON
                                        dev.agent_status = AgentStatus.CONNECTED
                                        status_changed = True
                                        await ws_manager.broadcast_event("device.updated", format_device_summary(dev))
                                    dev.last_seen = now_utc
                                else:
                                    sec_since_seen = (now_utc - dev.last_seen).total_seconds() if dev.last_seen else 999999
                                    if dev.power_status == PowerStatus.ON and sec_since_seen > 180:
                                        dev.power_status = PowerStatus.OFF
                                        dev.agent_status = AgentStatus.DISCONNECTED
                                        status_changed = True
                                        await ws_manager.broadcast_event("device.updated", format_device_summary(dev))
                            continue

                        dev_interval = dev.heartbeat_interval or 60
                        timeout_threshold = max(75, dev_interval * 2 + 15)
                        sec_since_last_seen = (now_utc - dev.last_seen).total_seconds() if dev.last_seen else 999999
                        
                        if dev.power_status == PowerStatus.ON and sec_since_last_seen > timeout_threshold:
                            dev.power_status = PowerStatus.OFF
                            dev.agent_status = AgentStatus.DISCONNECTED
                            status_changed = True
                            
                            # Check if a shutdown was already logged in the last 180 seconds
                            recent_logs = device_power_logs.get(dev.id.upper(), [])
                            has_recent = False
                            for entry in recent_logs[:5]:
                                if entry.get("action") in ["SHUTDOWN", "FORCE_SHUTDOWN", "POWEROFF"]:
                                    try:
                                        from datetime import timezone
                                        t_entry = datetime.fromisoformat(entry.get("timestamp", "").replace("Z", "+00:00"))
                                        if (datetime.now(timezone.utc) - t_entry).total_seconds() < 180:
                                            has_recent = True
                                            break
                                    except Exception:
                                        pass
                                        
                            if not has_recent:
                                curr_user = dev.current_user or "Пользователь"
                                log_device_power_event(
                                    device_id=dev.id,
                                    action="SHUTDOWN",
                                    details=f"Связь с агентом прервана (компьютер выключен локально, пользователь: {curr_user})",
                                    status="Success",
                                    initiator="Локальный пользователь (Завершение работы ОС / Кнопка)",
                                    source="LOCAL",
                                    device_name=dev.name
                                )
                            
                            await ws_manager.broadcast_event("device.updated", format_device_summary(dev))
                            
                    if status_changed:
                        await session.commit()
                    
                    # 2. Multi-step schedules evaluation
                    for sch in list(schedules_db):
                        if not sch.get("enabled", True):
                            continue
                        
                        sch_id = sch.get("id")
                        sch_days = sch.get("daysList", [])
                        target_grp = sch.get("target", "All")
                        
                        # Flexible day matching (supports Russian, English, strings, lists, daily/all)
                        is_today_active = True
                        if sch_days:
                            if isinstance(sch_days, str):
                                s_str = sch_days.strip().lower()
                                if "каждый" in s_str or "all" in s_str or "daily" in s_str or "ежедневно" in s_str:
                                    is_today_active = True
                                elif "пн-пт" in s_str or "будн" in s_str:
                                    is_today_active = current_day_ru in ["ПН", "ВТ", "СР", "ЧТ", "ПТ"]
                                elif "вых" in s_str or "сб-вс" in s_str:
                                    is_today_active = current_day_ru in ["СБ", "ВС"]
                                else:
                                    items = [x.strip().upper() for x in sch_days.split(",")]
                                    is_today_active = (current_day_ru in items or current_day_en in items)
                            elif isinstance(sch_days, list):
                                upper_list = [str(x).strip().upper() for x in sch_days]
                                if len(upper_list) == 0:
                                    is_today_active = True
                                else:
                                    is_today_active = (
                                        current_day_ru in upper_list or 
                                        current_day_en in upper_list or
                                        "ALL" in upper_list or
                                        "DAILY" in upper_list or
                                        "КАЖДЫЙ ДЕНЬ" in upper_list
                                    )
                        
                        if not is_today_active:
                            continue
                            
                        # Resolve target devices
                        if target_grp in ["All", "Все", "Все компьютеры"]:
                            target_devs = devices
                        else:
                            target_devs = [
                                d for d in devices 
                                if target_grp.lower() in [g.strip().lower() for g in (getattr(d, "group_name", "") or "").split(",")]
                                or target_grp.lower() == (getattr(d, "name", "") or "").lower()
                                or target_grp.lower() == (getattr(d, "hostname", "") or "").lower()
                                or target_grp.lower() == (getattr(d, "id", "") or "").lower()
                            ]
                        
                        # Fallback to all devices if specific group filter yielded 0 devices
                        if not target_devs and devices:
                            target_devs = devices
                            
                        # Evaluate steps if lifecycle rule
                        steps = sch.get("steps") or []
                        if steps:
                            for idx, st in enumerate(steps):
                                if not st.get("enabled", True):
                                    continue
                                step_time = str(st.get("time", "00:00")).strip()[:5]
                                step_action = st.get("action", "WAKE")
                                
                                # Step-level days check
                                step_days = st.get("daysList") or sch_days
                                step_active_today = True
                                if step_days:
                                    if isinstance(step_days, str):
                                        s_str = step_days.strip().lower()
                                        if "каждый" in s_str or "all" in s_str or "daily" in s_str or "ежедневно" in s_str:
                                            step_active_today = True
                                        elif "пн-пт" in s_str or "будн" in s_str:
                                            step_active_today = current_day_ru in ["ПН", "ВТ", "СР", "ЧТ", "ПТ"]
                                        elif "вых" in s_str or "сб-вс" in s_str:
                                            step_active_today = current_day_ru in ["СБ", "ВС"]
                                        else:
                                            items = [x.strip().upper() for x in step_days.split(",")]
                                            step_active_today = (current_day_ru in items or current_day_en in items)
                                    elif isinstance(step_days, list):
                                        upper_list = [str(x).strip().upper() for x in step_days]
                                        if len(upper_list) == 0:
                                            step_active_today = True
                                        else:
                                            step_active_today = (
                                                current_day_ru in upper_list or 
                                                current_day_en in upper_list or
                                                "ALL" in upper_list or
                                                "DAILY" in upper_list or
                                                "КАЖДЫЙ ДЕНЬ" in upper_list
                                            )
                                
                                if not step_active_today:
                                    continue
                                
                                if step_time == current_time_str:
                                    if self._last_executed_step.get(f"{sch_id}_{idx}") != current_minute_key:
                                        self._last_executed_step[f"{sch_id}_{idx}"] = current_minute_key
                                        sch["lastRun"] = now.strftime("%Y-%m-%d %H:%M:%S")
                                        sch["lastRunResult"] = "Success"
                                        sch["lastRunSummary"] = f"Этап {step_action}: Успешно"
                                        await self.execute_action_for_devices(
                                            action=step_action,
                                            target_devs=target_devs,
                                            sch_name=sch.get("name", "Суточный цикл"),
                                            sch_id=sch_id,
                                            target_grp=target_grp,
                                            trigger_type="SCHEDULER_CRON"
                                        )
                        else:
                            # Single action rule
                            sch_time = str(sch.get("time", "00:00")).strip()[:5]
                            sch_action = sch.get("action", "WAKE")
                            if sch_time == current_time_str:
                                if self._last_executed_step.get(sch_id) != current_minute_key:
                                    self._last_executed_step[sch_id] = current_minute_key
                                    sch["lastRun"] = now.strftime("%Y-%m-%d %H:%M:%S")
                                    sch["lastRunResult"] = "Success"
                                    sch["lastRunSummary"] = f"Действие {sch_action}: Успешно"
                                    await self.execute_action_for_devices(
                                        action=sch_action,
                                        target_devs=target_devs,
                                        sch_name=sch.get("name", "Расписание"),
                                        sch_id=sch_id,
                                        target_grp=target_grp,
                                        trigger_type="SCHEDULER_CRON"
                                    )
                                
            except Exception as e:
                print(f"[Scheduler Error] Loop exception: {e}")
                
            await asyncio.sleep(5)

scheduler_service = SchedulerService()
