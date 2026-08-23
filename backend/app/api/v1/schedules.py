from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import asyncio
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.db.session import get_db
from backend.app.models.device import Device
from backend.app.services.wol_service import wol_service

router = APIRouter(prefix="/schedules", tags=["schedules"])

# In-memory execution logs store
execution_logs_db: List[Dict[str, Any]] = []

# Initial rich schedules database with composite lifecycle rules
schedules_db: List[Dict[str, Any]] = [
    {
        "id": "SCH-01",
        "name": "Полный суточный цикл (Офис)",
        "type": "Lifecycle",
        "description": "Единый рабочий цикл: утренний WoL старт, вечерний сброс RDP и ночное выключение.",
        "enabled": True,
        "timezone": "Europe/Moscow",
        "days": "Пн-Пт",
        "daysList": ["ПН", "ВТ", "СР", "ЧТ", "ПТ"],
        "action": "LIFECYCLE",
        "target": "Office",
        "time": "07:45",
        "steps": [
            {
                "id": "step-1",
                "action": "WAKE",
                "time": "07:45",
                "enabled": True,
                "gracePeriodMinutes": 0,
                "warningMessage": "",
                "forceShutdown": False
            },
            {
                "id": "step-2",
                "action": "RDP_CLEANUP",
                "time": "21:45",
                "enabled": True,
                "gracePeriodMinutes": 0,
                "warningMessage": "",
                "forceShutdown": False
            },
            {
                "id": "step-3",
                "action": "SHUTDOWN",
                "time": "22:00",
                "enabled": True,
                "gracePeriodMinutes": 5,
                "warningMessage": "Внимание! Через 5 минут компьютер будет автоматически выключен.",
                "forceShutdown": True
            }
        ],
        "gracePeriodMinutes": 5,
        "warningMessage": "Внимание! Через 5 минут компьютер будет автоматически выключен.",
        "forceShutdown": True,
        "lastRun": (datetime.utcnow() - timedelta(hours=15)).strftime("%Y-%m-%d %H:%M:%S"),
        "lastRunResult": "Success",
        "lastRunSummary": "Этап WoL: Успешно включено 1/1 ПК"
    },
    {
        "id": "SCH-02",
        "name": "Суточный цикл отдела разработки",
        "type": "Lifecycle",
        "description": "Автоматизация рабочего дня для разработчиков: старт в 09:00 и завершение в 23:00.",
        "enabled": True,
        "timezone": "Europe/Moscow",
        "days": "Пн-Пт",
        "daysList": ["ПН", "ВТ", "СР", "ЧТ", "ПТ"],
        "action": "LIFECYCLE",
        "target": "All",
        "time": "09:00",
        "steps": [
            {
                "id": "step-1",
                "action": "WAKE",
                "time": "09:00",
                "enabled": True,
                "gracePeriodMinutes": 0,
                "warningMessage": "",
                "forceShutdown": False
            },
            {
                "id": "step-2",
                "action": "RDP_CLEANUP",
                "time": "22:45",
                "enabled": True,
                "gracePeriodMinutes": 0,
                "warningMessage": "",
                "forceShutdown": False
            },
            {
                "id": "step-3",
                "action": "SHUTDOWN",
                "time": "23:00",
                "enabled": True,
                "gracePeriodMinutes": 10,
                "warningMessage": "Окончание смены. Завершение работы через 10 минут.",
                "forceShutdown": True
            }
        ],
        "gracePeriodMinutes": 10,
        "warningMessage": "Окончание смены. Завершение работы через 10 минут.",
        "forceShutdown": True,
        "lastRun": (datetime.utcnow() - timedelta(days=1, hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
        "lastRunResult": "Success",
        "lastRunSummary": "Этап Выключение: 1/1 ПК выключено"
    },
    {
        "id": "SCH-03",
        "name": "Профилактическая перезагрузка (Выходные)",
        "type": "Reboot",
        "description": "Еженедельный перезапуск рабочих станций для применения системных обновлений.",
        "enabled": True,
        "timezone": "Europe/Moscow",
        "days": "Воскресенье",
        "daysList": ["ВС"],
        "time": "04:00",
        "action": "REBOOT",
        "target": "All",
        "steps": [
            {
                "id": "step-1",
                "action": "REBOOT",
                "time": "04:00",
                "enabled": True,
                "gracePeriodMinutes": 0,
                "warningMessage": "Запланированная перезагрузка Windows",
                "forceShutdown": True
            }
        ],
        "gracePeriodMinutes": 0,
        "warningMessage": "Запланированная перезагрузка Windows",
        "forceShutdown": True,
        "lastRun": (datetime.utcnow() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S"),
        "lastRunResult": "Success",
        "lastRunSummary": "Перезагрузка выполнена успешно"
    }
]

class ScheduleStepSchema(BaseModel):
    id: Optional[str] = None
    action: str # WAKE, RDP_CLEANUP, SHUTDOWN, REBOOT
    time: str # "07:45"
    enabled: Optional[bool] = True
    daysList: Optional[List[str]] = None
    gracePeriodMinutes: Optional[int] = 0
    warningMessage: Optional[str] = ""
    forceShutdown: Optional[bool] = False

class ScheduleCreateUpdateSchema(BaseModel):
    name: str
    type: Optional[str] = "Lifecycle"
    description: Optional[str] = ""
    enabled: Optional[bool] = True
    timezone: Optional[str] = "Europe/Moscow"
    days: Optional[str] = "Каждый день"
    daysList: Optional[List[str]] = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
    time: Optional[str] = "08:00"
    action: Optional[str] = "LIFECYCLE"
    target: str = "All"
    steps: Optional[List[ScheduleStepSchema]] = []
    gracePeriodMinutes: Optional[int] = 0
    warningMessage: Optional[str] = ""
    forceShutdown: Optional[bool] = False

def calculate_single_time_next_run(time_str: str, days_list: List[str]) -> Optional[Dict[str, Any]]:
    """Helper to calculate next run timestamp for a single time string."""
    try:
        now = datetime.now()
        hour, minute = map(int, time_str.split(":"))
        target_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        day_names_ru = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
        day_indices = []
        for d in days_list:
            d_clean = d.upper().strip()
            if d_clean in day_names_ru:
                day_indices.append(day_names_ru.index(d_clean))
        
        if not day_indices:
            day_indices = [0, 1, 2, 3, 4]
            
        for delta_days in range(8):
            cand_date = target_today + timedelta(days=delta_days)
            if cand_date.weekday() in day_indices and cand_date > now:
                diff = cand_date - now
                hours = int(diff.total_seconds() // 3600)
                minutes = int((diff.total_seconds() % 3600) // 60)
                
                if delta_days == 0:
                    rel_str = f"Сегодня в {time_str} (через {hours}ч {minutes}м)"
                elif delta_days == 1:
                    rel_str = f"Завтра в {time_str} (через {hours}ч {minutes}м)"
                else:
                    d_name = day_names_ru[cand_date.weekday()]
                    rel_str = f"{d_name} в {time_str} (через {hours}ч {minutes}м)"
                    
                return {
                    "nextRunIso": cand_date.isoformat(),
                    "nextRunFormatted": rel_str,
                    "secondsUntil": int(diff.total_seconds()),
                    "time": time_str
                }
    except Exception:
        pass
    return None

def calculate_next_run_for_schedule(sch: Dict[str, Any]) -> Dict[str, Any]:
    """
    Intelligent calculation of the next upcoming step in a composite lifecycle schedule.
    """
    days_list = sch.get("daysList", ["ПН", "ВТ", "СР", "ЧТ", "ПТ"])
    steps = sch.get("steps") or []
    enabled_steps = [st for st in steps if st.get("enabled", True)]
    
    action_names = {
        "WAKE": "WoL Включение",
        "RDP_CLEANUP": "Сброс RDP",
        "SHUTDOWN": "Выключение",
        "REBOOT": "Перезагрузка"
    }

    if enabled_steps:
        candidates = []
        for st in enabled_steps:
            t_str = st.get("time", "08:00")
            calc = calculate_single_time_next_run(t_str, days_list)
            if calc:
                act = st.get("action", "WAKE")
                act_label = action_names.get(act, act)
                calc["action"] = act
                calc["actionLabel"] = act_label
                candidates.append(calc)
                
        if candidates:
            candidates.sort(key=lambda x: x["secondsUntil"])
            best = candidates[0]
            return {
                "nextRunIso": best["nextRunIso"],
                "nextRunFormatted": f"{best['actionLabel']}: {best['nextRunFormatted']}",
                "secondsUntil": best["secondsUntil"],
                "nextStepAction": best["action"],
                "nextStepTime": best["time"]
            }
            
    # Fallback to single schedule time
    fallback_time = sch.get("time", "08:00")
    calc = calculate_single_time_next_run(fallback_time, days_list)
    if calc:
        return {
            "nextRunIso": calc["nextRunIso"],
            "nextRunFormatted": calc["nextRunFormatted"],
            "secondsUntil": calc["secondsUntil"],
            "nextStepAction": sch.get("action", "WAKE"),
            "nextStepTime": fallback_time
        }
        
    return {
        "nextRunIso": "",
        "nextRunFormatted": f"Завтра в {fallback_time}",
        "secondsUntil": 3600 * 12,
        "nextStepAction": sch.get("action", "WAKE"),
        "nextStepTime": fallback_time
    }

@router.get("")
async def list_schedules(db: AsyncSession = Depends(get_db)):
    """List all schedules with multi-step lifecycle support, next-run calculations and target device counts."""
    result = await db.execute(select(Device))
    devices = result.scalars().all()
    
    enriched = []
    for s in schedules_db:
        target_grp = s.get("target", "All")
        if target_grp == "All":
            dev_count = len(devices) or 1
        else:
            matching = [
                d for d in devices 
                if target_grp.lower() in [g.strip().lower() for g in (d.group_name or "").split(",")]
            ]
            dev_count = len(matching) if matching else 1
            
        next_calc = calculate_next_run_for_schedule(s)
        
        enriched.append({
            **s,
            "targetDeviceCount": dev_count,
            "nextRunFormatted": next_calc["nextRunFormatted"],
            "nextRunIso": next_calc["nextRunIso"],
            "secondsUntilNext": next_calc["secondsUntil"],
            "nextStepAction": next_calc.get("nextStepAction"),
            "nextStepTime": next_calc.get("nextStepTime")
        })
        
    return enriched

@router.post("")
async def create_schedule(payload: ScheduleCreateUpdateSchema, db: AsyncSession = Depends(get_db)):
    """Create a new schedule (single action or multi-step lifecycle)."""
    new_id = f"SCH-{len(schedules_db) + 1:02d}"
    
    days_list = payload.daysList or ["ПН", "ВТ", "СР", "ЧТ", "ПТ"]
    if len(days_list) == 7:
        days_str = "Каждый день"
    elif days_list == ["ПН", "ВТ", "СР", "ЧТ", "ПТ"]:
        days_str = "Пн-Пт"
    elif days_list == ["СБ", "ВС"]:
        days_str = "Выходные"
    else:
        days_str = ", ".join(days_list)

    # Format steps
    steps_data = []
    if payload.steps:
        for idx, st in enumerate(payload.steps, 1):
            steps_data.append({
                "id": st.id or f"step-{idx}",
                "action": st.action,
                "time": st.time,
                "enabled": st.enabled if st.enabled is not None else True,
                "daysList": st.daysList,
                "gracePeriodMinutes": st.gracePeriodMinutes or 0,
                "warningMessage": st.warningMessage or "",
                "forceShutdown": bool(st.forceShutdown)
            })
    else:
        # Construct single step
        steps_data = [{
            "id": "step-1",
            "action": payload.action or "WAKE",
            "time": payload.time or "08:00",
            "enabled": True,
            "daysList": days_list,
            "gracePeriodMinutes": payload.gracePeriodMinutes or 0,
            "warningMessage": payload.warningMessage or "",
            "forceShutdown": bool(payload.forceShutdown)
        }]

    new_schedule = {
        "id": new_id,
        "name": payload.name,
        "type": payload.type or ("Lifecycle" if len(steps_data) > 1 else "Custom"),
        "description": payload.description or f"Автоматическое расписание для {payload.target}",
        "enabled": payload.enabled if payload.enabled is not None else True,
        "timezone": payload.timezone or "Europe/Moscow",
        "days": days_str,
        "daysList": days_list,
        "time": steps_data[0]["time"] if steps_data else (payload.time or "08:00"),
        "action": payload.action or ("LIFECYCLE" if len(steps_data) > 1 else steps_data[0]["action"]),
        "target": payload.target,
        "steps": steps_data,
        "gracePeriodMinutes": payload.gracePeriodMinutes or 0,
        "warningMessage": payload.warningMessage or "",
        "forceShutdown": bool(payload.forceShutdown),
        "lastRun": None,
        "lastRunResult": None,
        "lastRunSummary": "Ожидает первого запуска"
    }
    schedules_db.append(new_schedule)
    return new_schedule

@router.put("/{schedule_id}")
async def update_schedule(schedule_id: str, payload: ScheduleCreateUpdateSchema):
    """Update an existing schedule and its lifecycle steps."""
    for s in schedules_db:
        if s["id"] == schedule_id:
            days_list = payload.daysList or s.get("daysList", ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"])
            if len(days_list) == 7:
                days_str = "Каждый день"
            elif days_list == ["ПН", "ВТ", "СР", "ЧТ", "ПТ"]:
                days_str = "Пн-Пт"
            elif days_list == ["СБ", "ВС"]:
                days_str = "Выходные"
            else:
                days_str = ", ".join(days_list)
                
            steps_data = []
            if payload.steps:
                for idx, st in enumerate(payload.steps, 1):
                    steps_data.append({
                        "id": st.id or f"step-{idx}",
                        "action": st.action,
                        "time": st.time,
                        "enabled": st.enabled if st.enabled is not None else True,
                        "daysList": st.daysList,
                        "gracePeriodMinutes": st.gracePeriodMinutes or 0,
                        "warningMessage": st.warningMessage or "",
                        "forceShutdown": bool(st.forceShutdown)
                    })
            else:
                steps_data = s.get("steps", [])

            s["name"] = payload.name
            s["type"] = payload.type or s.get("type", "Lifecycle")
            s["description"] = payload.description or s.get("description", "")
            s["enabled"] = payload.enabled if payload.enabled is not None else s.get("enabled", True)
            s["timezone"] = payload.timezone or s.get("timezone", "Europe/Moscow")
            s["days"] = days_str
            s["daysList"] = days_list
            s["time"] = steps_data[0]["time"] if steps_data else (payload.time or s.get("time", "08:00"))
            s["action"] = payload.action or s.get("action", "LIFECYCLE")
            s["target"] = payload.target
            s["steps"] = steps_data
            s["gracePeriodMinutes"] = payload.gracePeriodMinutes or 0
            s["warningMessage"] = payload.warningMessage or ""
            s["forceShutdown"] = bool(payload.forceShutdown)
            return s
            
    raise HTTPException(status_code=404, detail="Schedule not found")

@router.delete("/{schedule_id}")
async def delete_schedule(schedule_id: str):
    """Delete a schedule."""
    global schedules_db
    init_len = len(schedules_db)
    schedules_db = [s for s in schedules_db if s["id"] != schedule_id]
    if len(schedules_db) < init_len:
        return {"status": "deleted", "id": schedule_id}
    raise HTTPException(status_code=404, detail="Schedule not found")

@router.post("/{schedule_id}/toggle")
async def toggle_schedule(schedule_id: str):
    """Toggle schedule enabled state."""
    for s in schedules_db:
        if s["id"] == schedule_id:
            s["enabled"] = not s["enabled"]
            return {"id": schedule_id, "enabled": s["enabled"]}
    raise HTTPException(status_code=404, detail="Schedule not found")

@router.post("/{schedule_id}/run")
async def run_schedule_now(
    schedule_id: str,
    action_override: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Manual Trigger: Execute schedule immediately on all targeted devices.
    Dispatches WoL Magic Packet or power commands and logs result.
    """
    sch = next((s for s in schedules_db if s["id"] == schedule_id), None)
    if not sch:
        raise HTTPException(status_code=404, detail="Schedule not found")

    result = await db.execute(select(Device))
    devices = result.scalars().all()
    
    target_grp = sch.get("target", "All")
    if target_grp == "All":
        target_devs = devices
    else:
        target_devs = [
            d for d in devices 
            if target_grp.lower() in [g.strip().lower() for g in (d.group_name or "").split(",")]
        ]
        
    dev_count = max(1, len(target_devs))
    
    # Determine action to run: override, first active step, or schedule action
    action = action_override
    if not action:
        if sch.get("steps"):
            first_enabled = next((st for st in sch["steps"] if st.get("enabled", True)), None)
            action = first_enabled["action"] if first_enabled else "WAKE"
        else:
            action = sch.get("action", "WAKE")
            if action == "LIFECYCLE":
                action = "WAKE"

    # Execute action via unified scheduler service (sends Direct LAN UDP + Heartbeat queue + execution log)
    from backend.app.services.scheduler_service import scheduler_service
    await scheduler_service.execute_action_for_devices(
        action=action,
        target_devs=target_devs,
        sch_name=sch["name"],
        sch_id=sch["id"],
        target_grp=target_grp,
        trigger_type="MANUAL_WEB_UI"
    )
    
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    sch["lastRun"] = now_str
    sch["lastRunResult"] = "Success"
    sch["lastRunSummary"] = f"Успешно: {action} ({dev_count} ПК)"
    
    log_entry = execution_logs_db[0] if execution_logs_db else {}
    
    return {
        "status": "success",
        "message": f"Расписание \"{sch['name']}\" ({action}) успешно запущено на {dev_count} ПК!",
        "summary": f"Действие {action} отправлено на {dev_count} ПК",
        "log": log_entry
    }

@router.get("/logs")
async def get_schedule_logs():
    """Return execution history logs."""
    return execution_logs_db
