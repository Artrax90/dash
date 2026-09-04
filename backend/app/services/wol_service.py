import socket
import struct
import re
import asyncio
import ipaddress
import time
from typing import Optional, List, Set
import psutil

class WolService:
    @staticmethod
    def create_magic_packet(mac_address: str) -> bytes:
        """
        Construct standard Wake-on-LAN Magic Packet:
        6 bytes of 0xFF followed by 16 repetitions of 6-byte MAC address.
        """
        clean_mac = re.sub(r'[^a-fA-F0-9]', '', mac_address or '')
        if len(clean_mac) != 12:
            raise ValueError(f"Invalid MAC address format: {mac_address}")
        
        mac_bytes = bytes.fromhex(clean_mac)
        magic_packet = b'\xff' * 6 + mac_bytes * 16
        return magic_packet

    @staticmethod
    def get_local_ipv4_interfaces() -> List[tuple]:
        """
        Enumerate all active local IPv4 interfaces (interface_name, ip_address, netmask, subnet_broadcast).
        """
        interfaces = []
        try:
            for ifname, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        ip = addr.address
                        # Skip loopback and unassigned APIPA
                        if ip.startswith("127.") or ip.startswith("169.254."):
                            continue
                        mask = addr.netmask or "255.255.255.0"
                        try:
                            net = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
                            bcast = str(net.broadcast_address)
                        except Exception:
                            parts = ip.split(".")
                            bcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255" if len(parts) == 4 else "255.255.255.255"
                        interfaces.append((ifname, ip, mask, bcast))
        except Exception as e:
            print(f"[WoL Warning] Error enumerating network interfaces: {e}")
        
        if not interfaces:
            interfaces.append(("default", "0.0.0.0", "255.255.255.0", "255.255.255.255"))
        return interfaces

    @staticmethod
    def get_broadcast_targets(ip_address: Optional[str] = None, custom_broadcast: Optional[str] = None) -> Set[str]:
        """
        Generate set of broadcast destinations to ensure maximum delivery.
        """
        targets = set()
        targets.add("255.255.255.255")
        
        if custom_broadcast and custom_broadcast.strip() and custom_broadcast != "255.255.255.255":
            targets.add(custom_broadcast.strip())
            
        if ip_address and ip_address.strip() and not ip_address.startswith("127.") and not ip_address.startswith("169.254."):
            targets.add(ip_address.strip())
            try:
                ip_obj = ipaddress.IPv4Interface(f"{ip_address.strip()}/24")
                targets.add(str(ip_obj.network.broadcast_address))
            except Exception:
                parts = ip_address.strip().split(".")
                if len(parts) == 4:
                    targets.add(f"{parts[0]}.{parts[1]}.{parts[2]}.255")
        
        return targets

    @classmethod
    async def send_magic_packet(
        cls,
        mac_address: str,
        broadcast_ip: Optional[str] = "255.255.255.255",
        ip_address: Optional[str] = None,
        ports: Optional[List[int]] = None,
        bursts: int = 4
    ) -> bool:
        """
        Broadcast Wake-on-LAN Magic Packet asynchronously via UDP sockets bound to every local physical NIC.
        """
        if not mac_address:
            return False
            
        if ports is None:
            ports = [9, 7]

        try:
            packet = cls.create_magic_packet(mac_address)
            extra_targets = cls.get_broadcast_targets(ip_address, broadcast_ip)
            local_nics = cls.get_local_ipv4_interfaces()
            loop = asyncio.get_running_loop()
            
            def _send_all():
                dispatched_count = 0
                for nic_name, local_ip, _, nic_bcast in local_nics:
                    all_targets = set(extra_targets)
                    all_targets.add(nic_bcast)
                    all_targets.add("255.255.255.255")

                    try:
                        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                            try:
                                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                            except Exception:
                                pass
                            
                            # Bind socket specifically to local interface IP if not 0.0.0.0
                            if local_ip != "0.0.0.0":
                                try:
                                    sock.bind((local_ip, 0))
                                except Exception as bind_err:
                                    print(f"[WoL Warning] Could not bind to {local_ip}: {bind_err}")

                            for burst in range(bursts):
                                for dest in all_targets:
                                    for port in ports:
                                        try:
                                            sock.sendto(packet, (dest, port))
                                            dispatched_count += 1
                                        except Exception as err:
                                            print(f"[WoL Warning] Send via {local_ip} to {dest}:{port} error: {err}")
                                if burst < bursts - 1:
                                    time.sleep(0.02)
                    except Exception as e:
                        print(f"[WoL Error] Socket creation on {local_ip} failed: {e}")

                print(f"[WoL Success] Dispatched {dispatched_count} Magic Packets for {mac_address} across {len(local_nics)} NICs to {extra_targets}")

            await loop.run_in_executor(None, _send_all)
            return True
        except Exception as e:
            print(f"[WoL Error] Failed to dispatch magic packet for {mac_address} - {e}")
            return False

    @staticmethod
    async def ping_device(ip_address: str, timeout_seconds: float = 1.5) -> bool:
        """
        Check if machine IP responds to connection.
        """
        if not ip_address:
            return False
        try:
            loop = asyncio.get_running_loop()
            for port in [2301, 8000, 3389, 445, 135]:
                try:
                    future = asyncio.open_connection(ip_address, port)
                    reader, writer = await asyncio.wait_for(future, timeout=timeout_seconds)
                    writer.close()
                    await writer.wait_closed()
                    return True
                except Exception:
                    continue
            return False
        except Exception:
            return False

wol_service = WolService()
