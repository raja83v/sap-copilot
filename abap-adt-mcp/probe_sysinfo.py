"""Probe to verify the fixed get_system_info() on sc9sa03."""
import asyncio, sys, os
os.environ["NO_PROXY"] = "localhost,127.0.0.1,dl0992sc9sa03.dev.sap.nsw.education,.dev.sap.nsw.education"
os.environ["no_proxy"] = os.environ["NO_PROXY"]
sys.path.insert(0, "src")

from vsp.config import Config
from vsp.adt.client import ADTClient

async def main():
    cfg = Config(
        base_url="http://dl0992sc9sa03.dev.sap.nsw.education:8000",
        username="10014950",
        password="Mydevportal@02",
        client="010",
    )
    async with ADTClient(cfg) as client:
        info = await client.get_system_info()
        print("=== SystemInfo from fixed client ===")
        print(f"  node_name:        {info.node_name}")
        print(f"  app_server:       {info.app_server}")
        print(f"  kernel_release:   {info.kernel_release}")
        print(f"  database_system:  {info.database_system}")
        print(f"  database_release: {info.database_release}")
        print(f"  database_name:    {info.database_name}")
        print(f"  os_name:          {info.os_name}")
        print(f"  ip_address:       {info.ip_address}")
        print()
        print("=== GetConnectionInfo output ===")
        lines = [
            f"URL: {cfg.base_url}",
            f"Client: {cfg.client}",
            f"User: {cfg.username}",
            f"Language: {cfg.language}",
            f"Host: {info.node_name}",
            f"App Server: {info.app_server}",
            f"Kernel: {info.kernel_release}",
            f"DB: {info.database_system} {info.database_release}",
            f"IP: {info.ip_address}",
        ]
        print("\n".join(lines))

asyncio.run(main())
