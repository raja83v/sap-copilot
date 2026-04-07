"""Probe class object links and try writing to individual includes."""
import asyncio, sys, os
os.environ["NO_PROXY"] = "localhost,127.0.0.1,dl0992sc9sa09.dev.sap.nsw.education"
os.environ["no_proxy"] = os.environ["NO_PROXY"]
sys.path.insert(0, "src")

from vsp.config import Config, SessionType
from vsp.adt.http import Transport
from vsp.adt.crud import CRUDOperations
import re


async def main():
    cfg = Config(
        base_url="http://dl0992sc9sa09.dev.sap.nsw.education:8000",
        username="10014950",
        password="Mydevportal@02",
        client="010",
    )
    async with Transport(cfg) as t:
        crud = CRUDOperations(t, cfg)

        # 1. GET the class object to see what links are exposed
        print("=== GET class object ===")
        try:
            resp = await t.get(
                "/sap/bc/adt/oo/classes/ZCL_DEMO_CARRIER2",
                accept="application/vnd.sap.adt.oo.classes+xml",
            )
            print(f"Status: {resp.status_code}")
            # Print links
            for m in re.finditer(r'href="([^"]*source[^"]*)"', resp.text):
                print(f"  Link: {m.group(1)}")
            # Print all hrefs
            hrefs = re.findall(r'href="([^"]+)"', resp.text)
            for h in hrefs[:20]:
                print(f"  href: {h}")
        except Exception as e:
            print(f"GET class error: {str(e)[:300]}")

        print()

        # 2. Try writing to classincludes individually
        DEF_SOURCE = "CLASS zcl_demo_carrier2 DEFINITION PUBLIC CREATE PUBLIC.\n  PUBLIC SECTION.\n    CLASS-METHODS get_all_carriers RETURNING VALUE(rt_carriers) TYPE STANDARD TABLE OF scarr.\n  PROTECTED SECTION.\n  PRIVATE SECTION.\nENDCLASS."
        IMP_SOURCE = "CLASS zcl_demo_carrier2 IMPLEMENTATION.\n  METHOD get_all_carriers.\n    SELECT * FROM scarr INTO TABLE rt_carriers ORDER BY carrid.\n  ENDMETHOD.\nENDCLASS."

        include_paths = [
            ("/sap/bc/adt/oo/classes/ZCL_DEMO_CARRIER2/includes/source/main", "global-include-main"),
            ("/sap/bc/adt/oo/classes/ZCL_DEMO_CARRIER2/classificationincludes/main/source/main", "classif-main"),
        ]

        for path, label in include_paths:
            print(f"=== GET {label} ===")
            try:
                resp = await t.get(path, accept="text/plain")
                print(f"  Status: {resp.status_code}")
                print(f"  Body: {resp.text[:200]}")
            except Exception as e:
                print(f"  Error: {str(e)[:150]}")


asyncio.run(main())
