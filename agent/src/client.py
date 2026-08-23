import time
import json
import os
import requests
from agent.src.collector import HardwareCollector
from agent.src.telemetry import TelemetryCollector
from agent.src.executor import CommandExecutor

class AgentClient:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> dict:
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "server_url": "http://localhost:2301/api/v1",
            "enrollment_token": "wm_tok_live_7f8a92b3c4d5e6f7",
            "device_id": "",
            "agent_secret": "",
        }

    def _save_config(self):
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

    def enroll_if_needed(self) -> bool:
        if self.config.get("device_id") and self.config.get("agent_secret"):
            return True

        url = f"{self.config['server_url']}/agents/enroll"
        try:
            resp = requests.post(url, json={"token": self.config.get("enrollment_token")}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                self.config["device_id"] = data["deviceId"]
                self.config["agent_secret"] = data["agentSecret"]
                self._save_config()
                print(f"[Agent] Successfully enrolled as {data['deviceId']}")
                return True
        except Exception as e:
            print(f"[Agent] Enrollment failed: {e}")
        return False

    def send_inventory(self):
        spec = HardwareCollector.collect_all()
        url = f"{self.config['server_url']}/agents/inventory"
        try:
            requests.post(url, json={
                "deviceId": self.config.get("device_id"),
                "hardwareSpec": spec
            }, timeout=15)
            print("[Agent] Hardware inventory dispatched to server.")
        except Exception as e:
            print(f"[Agent] Inventory dispatch error: {e}")

    def send_heartbeat(self):
        telemetry = TelemetryCollector.get_live_metrics()
        url = f"{self.config['server_url']}/agents/heartbeat"
        try:
            requests.post(url, json={
                "deviceId": self.config.get("device_id"),
                **telemetry
            }, timeout=8)
            print(f"[Agent] Heartbeat sent. CPU: {telemetry['cpuPercent']}% | RAM: {telemetry['ramPercent']}%")
        except Exception as e:
            print(f"[Agent] Heartbeat error: {e}")

    def run_loop(self):
        print("Starting Workstation Manager Agent...")
        if not self.enroll_if_needed():
            print("[Agent] Could not enroll, exiting.")
            return

        self.send_inventory()

        while True:
            self.send_heartbeat()
            time.sleep(self.config.get("heartbeat_interval_seconds", 30))

if __name__ == "__main__":
    client = AgentClient()
    client.run_loop()
