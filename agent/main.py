#!/usr/bin/env python3
"""
Workstation Manager Background Agent
Cross-platform Service for Windows and Linux.
"""
from agent.src.client import AgentClient

def main():
    agent = AgentClient()
    agent.run_loop()

if __name__ == "__main__":
    main()
