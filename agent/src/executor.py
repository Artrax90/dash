import sys
import os
import subprocess
import platform

class CommandExecutor:
    @staticmethod
    def shutdown(force: bool = False, delay_seconds: int = 0) -> bool:
        """
        Execute system shutdown command.
        """
        try:
            if platform.system() == "Windows":
                flag = "/f" if force else ""
                cmd = f"shutdown /s {flag} /t {delay_seconds}"
            else:
                flag = "-P now" if force else f"+{delay_seconds // 60}"
                cmd = f"shutdown {flag}"
            
            subprocess.run(cmd, shell=True, check=True)
            return True
        except Exception as e:
            print(f"[Executor Error] Shutdown failed: {e}")
            return False

    @staticmethod
    def reboot() -> bool:
        """
        Execute system reboot command.
        """
        try:
            if platform.system() == "Windows":
                cmd = "shutdown /r /t 0"
            else:
                cmd = "reboot"
            subprocess.run(cmd, shell=True, check=True)
            return True
        except Exception as e:
            print(f"[Executor Error] Reboot failed: {e}")
            return False

    @staticmethod
    def logoff_session(username_or_session_id: str) -> bool:
        """
        Logoff named user or session.
        """
        try:
            if platform.system() == "Windows":
                cmd = f"logoff {username_or_session_id}"
            else:
                cmd = f"pkill -u {username_or_session_id}"
            subprocess.run(cmd, shell=True, check=True)
            return True
        except Exception as e:
            print(f"[Executor Error] Logoff failed: {e}")
            return False
