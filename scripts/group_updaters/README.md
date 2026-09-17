# Скрипты обновления агентов по группам (Workstation Manager)

Данная директория содержит готовые PowerShell и Batch скрипты для автоматического обновления агентов до актуальной версии **v2.9.19** отдельно по каждой группе или по всему парку сразу.

---

## Таблица групп, токенов и скриптов

| № | Группа | Токен группы | Скрипт PowerShell | Батник 1-клик | ПК |
|---|--------|--------------|-------------------|---------------|----|
| 1 | **ГУК / 1 этаж / 111** | `wm_tok_060f74580d9652d7` | [`Update-GUK-111.ps1`](Update-GUK-111.ps1) | [`Update-GUK-111.bat`](Update-GUK-111.bat) | 3 |
| 2 | **МНОК / 3 этаж / 333Т** | `wm_tok_662a7290c2bcec36` | [`Update-MNOK-333T.ps1`](Update-MNOK-333T.ps1) | [`Update-MNOK-333T.bat`](Update-MNOK-333T.bat) | 11 |
| 3 | **МНОК / 4 этаж / 443Т** | `wm_tok_84b4480be512b7db` | [`Update-MNOK-443T.ps1`](Update-MNOK-443T.ps1) | [`Update-MNOK-443T.bat`](Update-MNOK-443T.bat) | 3 |
| 4 | **МНОК / 4 этаж / 444Т** | `wm_tok_c85c6b07cd5e5c3d` | [`Update-MNOK-444T.ps1`](Update-MNOK-444T.ps1) | [`Update-MNOK-444T.bat`](Update-MNOK-444T.bat) | 9 |
| 5 | **МНОК / 5 этаж / 518Т** | `wm_tok_071feaacce3b7ef1` | [`Update-MNOK-518T.ps1`](Update-MNOK-518T.ps1) | [`Update-MNOK-518T.bat`](Update-MNOK-518T.bat) | 14 |
| 6 | **ЦК B4 / 5 этаж / 512** | `wm_tok_2d20a75eef21e61d` | [`Update-CK-B4-512.ps1`](Update-CK-B4-512.ps1) | [`Update-CK-B4-512.bat`](Update-CK-B4-512.bat) | 5 |
| 7 | **ЦК B4 / 5 этаж / 513** | `wm_tok_a78863fc5308e95e` | [`Update-CK-B4-513.ps1`](Update-CK-B4-513.ps1) | [`Update-CK-B4-513.bat`](Update-CK-B4-513.bat) | 12 |
| 8 | **ЦК B4 / 5 этаж / 541** | `wm_tok_4470ec159a499f5f` | [`Update-CK-B4-541.ps1`](Update-CK-B4-541.ps1) | [`Update-CK-B4-541.bat`](Update-CK-B4-541.bat) | 2 |
| 9 | **Servers** | `wm_tok_f3a5231cc51af30d` | [`Update-Servers.ps1`](Update-Servers.ps1) | [`Update-Servers.bat`](Update-Servers.bat) | 2 |
| 10 | **МНОК / 4 этаж / 443** | `wm_tok_8bd126283a901236` | [`Update-MNOK-443.ps1`](Update-MNOK-443.ps1) | [`Update-MNOK-443.bat`](Update-MNOK-443.bat) | — |
| 11 | **МНОК / 4 этаж / 444** | `wm_tok_9dae52edee48d1b6` | [`Update-MNOK-444.ps1`](Update-MNOK-444.ps1) | [`Update-MNOK-444.bat`](Update-MNOK-444.bat) | — |
| 12 | **МНОК / 4 этаж / 446Т** | `wm_tok_8be3647c50f0d095` | [`Update-MNOK-446T.ps1`](Update-MNOK-446T.ps1) | [`Update-MNOK-446T.bat`](Update-MNOK-446T.bat) | — |
| 13 | **МНОК / 1 этаж / 111** | `wm_tok_06791590421adcf6` | [`Update-MNOK-111.ps1`](Update-MNOK-111.ps1) | [`Update-MNOK-111.bat`](Update-MNOK-111.bat) | — |
| 🚀 | **ГЛАВНЫЙ ПУЛЬТ (ВСЕ ГРУППЫ)** | — | [`Update-ALL-GROUPS.ps1`](Update-ALL-GROUPS.ps1) | [`Update-ALL-GROUPS.bat`](Update-ALL-GROUPS.bat) | **61** |

---

## Способы запуска

### Вариант 1. Запуск через интерактивное меню (самый удобный)
Просто запустите двойным кликом файл **`Update-ALL-GROUPS.bat`**.
Откроется окно с красивым цветным меню:
- Введите номер нужной группы (например, `5` для `518Т`) и нажмите `Enter`.
- Либо введите `A`, чтобы последовательно обновить все компьютеры во всех группах.
- Либо введите `P`, чтобы только проверить ping-доступность компьютеров.

### Вариант 2. Запуск батника конкретной группы
Двойным кликом запустите `.bat` файл нужной группы (например, `Update-MNOK-518T.bat`). Скрипт выполнит пинг всех ПК группы и запустит команду обновления.

### Вариант 3. Запуск от имени доменного администратора (рекомендуется при строгих политиках Windows)
Если на компьютерах включен UAC и удаленное WMI требует учетных данных администратора домена:
```powershell
.\Update-MNOK-518T.ps1 -Credential (Get-Credential)
```

### Вариант 4. Запуск локально на самом целевом ПК
Если вы находитесь за компьютером этой группы (или зашли по RDP):
```powershell
.\Update-MNOK-518T.ps1 -LocalInstall
```
Либо просто скопируйте батник и запустите от имени Администратора.
