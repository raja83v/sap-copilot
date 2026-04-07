"""Probe CLAS creation with corrected namespace on SC9."""
import asyncio, sys, os
os.environ["NO_PROXY"] = "localhost,127.0.0.1,dl0992sc9sa09.dev.sap.nsw.education"
os.environ["no_proxy"] = os.environ["NO_PROXY"]
sys.path.insert(0, "src")

from vsp.config import Config
from vsp.adt.http import Transport
from vsp.adt.crud import CRUDOperations
from vsp.adt.xml_types import build_create_object_xml


async def main():
    cfg = Config(
        base_url="http://dl0992sc9sa09.dev.sap.nsw.education:8000",
        username="10014950",
        password="Mydevportal@02",
        client="010",
    )
    async with Transport(cfg) as t:
        # Show what XML we're building now
        xml = build_create_object_xml("CLAS", "ZCL_DEMO_CARRIER2", description="Demo Carrier Class", package="$TMP")
        print("XML:")
        print(xml)
        print()

        crud = CRUDOperations(t, cfg)
        try:
            uri = await crud.create_object("CLAS", "ZCL_DEMO_CARRIER2", description="Demo Carrier Class", package="$TMP")
            print(f"SUCCESS: {uri}")
        except Exception as e:
            print(f"FAIL: {str(e)[:400]}")


asyncio.run(main())
