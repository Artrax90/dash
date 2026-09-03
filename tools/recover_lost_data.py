#!/usr/bin/env python3
# Workstation Manager - Emergency Data Recovery Tool
import os, sys, json, subprocess

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
GIT_DIR = os.path.join(PROJECT_ROOT, '.git')

def inspect_json(content_str):
    try:
        data = json.loads(content_str)
        if isinstance(data, list) and len(data) > 0 and any('username' in u or 'passwordHash' in u for u in data):
            return 'users', data
        if isinstance(data, list) and len(data) > 0 and any('desc' in g and 'color' in g for g in data):
            return 'groups', data
        if isinstance(data, dict) and ('botToken' in data or 'chatId' in data or 'eventsConfig' in data):
            if data.get('botToken') or data.get('chatId'):
                return 'telegram_config', data
        if isinstance(data, list) and len(data) > 0 and any('targetGroup' in t for t in data):
            return 'tokens', data
        if isinstance(data, list) and len(data) > 0 and any('cron' in s or 'days' in s for s in data):
            return 'schedules', data
    except Exception:
        pass
    return None, None

def run_git(args):
    try:
        res = subprocess.run(['git'] + args, cwd=PROJECT_ROOT, capture_output=True, text=True, errors='replace')
        return res.stdout
    except Exception:
        return ''

def main():
    print('=' * 70)
    print('  WORKSTATION MANAGER - EMERGENCY DATA RECOVERY TOOL')
    print('=' * 70)
    os.makedirs(DATA_DIR, exist_ok=True)
    recovered = {}

    stashes = run_git(['stash', 'list']).strip().splitlines()
    for s in stashes:
        stash_id = s.split(':')[0].strip()
        for fn in ['users.json', 'groups.json', 'telegram_config.json', 'tokens.json', 'schedules.json']:
            c = run_git(['show', f'{stash_id}:data/{fn}'])
            if c:
                ftype, data = inspect_json(c)
                if ftype and ftype not in recovered:
                    recovered[ftype] = (data, f'git stash ({stash_id})')
                    print(f'[*] Found {ftype} in {stash_id}!')

    reflog = run_git(['reflog', '-n', '50']).strip().splitlines()
    for r in reflog:
        ch = r.split()[0].strip() if r.split() else ''
        if not ch: continue
        for fn in ['users.json', 'groups.json', 'telegram_config.json', 'tokens.json', 'schedules.json']:
            c = run_git(['show', f'{ch}:data/{fn}'])
            if c:
                ftype, data = inspect_json(c)
                if ftype and ftype not in recovered:
                    recovered[ftype] = (data, f'reflog {ch}')
                    print(f'[*] Found {ftype} in reflog commit {ch}!')

    run_git(['fsck', '--lost-found', '--unreachable'])
    lost_dir = os.path.join(GIT_DIR, 'lost-found', 'other')
    if os.path.exists(lost_dir):
        for f in os.listdir(lost_dir):
            bp = os.path.join(lost_dir, f)
            try:
                with open(bp, 'r', encoding='utf-8', errors='ignore') as bf:
                    c = bf.read()
                    ftype, data = inspect_json(c)
                    if ftype and ftype not in recovered:
                        recovered[ftype] = (data, f'lost-found blob {f[:8]}')
                        print(f'[*] Found {ftype} in lost-found blob {f[:8]}!')
            except Exception:
                pass

    if not recovered:
        print('[-] No lost files found in git history or lost-found.')
        return

    for ftype, (data, src) in recovered.items():
        tj = os.path.join(DATA_DIR, f'{ftype}.json')
        tb = os.path.join(DATA_DIR, f'{ftype}.backup.json')
        with open(tj, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)
        with open(tb, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)
        print(f'[+] RESTORED: {ftype}.json from {src}')
    print('=' * 70)
    print('  RECOVERY COMPLETE! Restart containers with: docker compose restart')
    print('=' * 70)

if __name__ == '__main__':
    main()
