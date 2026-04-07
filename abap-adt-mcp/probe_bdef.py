"""Probe BDEF endpoint discovery on SC9."""
import asyncio, sys, os
os.environ["NO_PROXY"] = "localhost,127.0.0.1,dl0992sc9sa09.dev.sap.nsw.education"
os.environ["no_proxy"] = os.environ["NO_PROXY"]
sys.path.insert(0, "src")

from vsp.config import Config
from vsp.adt.http import Transport
from vsp.adt.xml_types import build_create_object_xml


async def main():
    cfg = Config(
        base_url="http://dl0992sc9sa09.dev.sap.nsw.education:8000",
        username="10014950",
        password="Mydevportal@02",
        client="010",
    )
    async with Transport(cfg) as t:
        # 1. Check what paths exist for BDEF
        for path in [
            "/sap/bc/adt/bo/behaviordefinitions",
            "/sap/bc/adt/behaviordefinitions",
        ]:
            try:
                resp = await t.get(path, accept="application/xml")
                print(f"GET {path} -> {resp.status_code}")
                print(f"  CT: {resp.headers.get('content-type', '')}")
                print(f"  Body: {resp.text[:300]}")
            except Exception as e:
                print(f"GET {path} -> {str(e)[:150]}")
            print()

        # 2. Check discovery for BDEF link type
        try:
            resp = await t.get("/sap/bc/adt/core/discovery", accept="application/atomsvc+xml")
            body = resp.text
            # Find BDEF-related lines
            lines = [l for l in body.splitlines() if 'bdef' in l.lower() or 'behaviour' in l.lower() or 'behavior' in l.lower()]
            print("Discovery BDEF entries:", len(lines))
            for l in lines[:20]:
                print(' ', l.strip())
        except Exception as e:
            print(f"Discovery -> {str(e)[:150]}")

        # 3. Try the POST with the correct content types incl. new candidates
        print()
        print("=== POST trials ===")
        xml_body = build_create_object_xml(
            "BDEF", "ZDEMO_I_TRAVEL", description="Demo BDEF", package="$TMP"
        )
        for ct in [
            "application/vnd.sap.adt.behaviordefinition+xml; charset=utf-8",
            "application/vnd.sap.adt.bo.behaviordefinitions+xml; charset=utf-8",
            "application/vnd.sap.adt.bo.behaviordefinition+xml; charset=utf-8",
            "application/xml; charset=utf-8",
        ]:
            try:
                resp = await t.post(
                    "/sap/bc/adt/bo/behaviordefinitions",
                    content=xml_body,
                    content_type=ct,
                    accept="application/vnd.sap.adt.behaviordefinition+xml, application/xml",
                )
                print(f"SUCCESS ct={ct}  status={resp.status_code}  Loc={resp.headers.get('Location', '')}")
                break
            except Exception as e:
                print(f"FAIL    ct={ct[:70]}  {str(e)[5:100]}")


asyncio.run(main())
