"""Probe CLAS source write variants on SC9.
Tests incrementally more complex sources to find where the SAP OO scanner fails.
"""
import asyncio, sys, os, html, re
os.environ["NO_PROXY"] = "localhost,127.0.0.1,dl0992sc9sa09.dev.sap.nsw.education"
os.environ["no_proxy"] = os.environ["NO_PROXY"]
sys.path.insert(0, "src")

from urllib.parse import quote
from vsp.config import Config, SessionType
from vsp.adt.http import Transport
from vsp.adt.crud import CRUDOperations

SOURCES = {
    "returning_string": (
        "CLASS zcl_demo_carrier2 DEFINITION PUBLIC CREATE PUBLIC.\n"
        "  PUBLIC SECTION.\n"
        "    CLASS-METHODS get_name RETURNING VALUE(rv_name) TYPE string.\n"
        "  PROTECTED SECTION.\n"
        "  PRIVATE SECTION.\n"
        "ENDCLASS.\n"
        "CLASS zcl_demo_carrier2 IMPLEMENTATION.\n"
        "  METHOD get_name.\n"
        "    rv_name = 'test'.\n"
        "  ENDMETHOD.\n"
        "ENDCLASS."
    ),
    "returning_stdtab": (
        "CLASS zcl_demo_carrier2 DEFINITION PUBLIC CREATE PUBLIC.\n"
        "  PUBLIC SECTION.\n"
        "    CLASS-METHODS get_all RETURNING VALUE(rt_data) TYPE STANDARD TABLE.\n"
        "  PROTECTED SECTION.\n"
        "  PRIVATE SECTION.\n"
        "ENDCLASS.\n"
        "CLASS zcl_demo_carrier2 IMPLEMENTATION.\n"
        "  METHOD get_all.\n"
        "  ENDMETHOD.\n"
        "ENDCLASS."
    ),
    "returning_tabof_scarr": (
        "CLASS zcl_demo_carrier2 DEFINITION PUBLIC CREATE PUBLIC.\n"
        "  PUBLIC SECTION.\n"
        "    CLASS-METHODS get_carriers RETURNING VALUE(rt_carriers) TYPE STANDARD TABLE OF scarr.\n"
        "  PROTECTED SECTION.\n"
        "  PRIVATE SECTION.\n"
        "ENDCLASS.\n"
        "CLASS zcl_demo_carrier2 IMPLEMENTATION.\n"
        "  METHOD get_carriers.\n"
        "  ENDMETHOD.\n"
        "ENDCLASS."
    ),
}


async def try_write(t: Transport, crud: CRUDOperations, label: str, source: str) -> bool:
    handle = await crud.lock_object("CLAS", "ZCL_DEMO_CARRIER2")
    await t.set_session_type(SessionType.STATEFUL)
    path = f"/sap/bc/adt/oo/classes/{quote('ZCL_DEMO_CARRIER2')}/source/main"
    content_bytes = source.encode("utf-8")
    try:
        resp = await t.put(
            path,
            content=content_bytes,
            content_type="text/plain; charset=utf-8",
            accept="text/plain, application/vnd.sap.as+xml",
            params={"lockHandle": handle},
            headers={"X-Lock-Handle": handle},
        )
        print(f"  [{label}] PUT {resp.status_code} OK")
        return True
    except Exception as e:
        full_body = getattr(getattr(e, "response", None), "text", str(e))
        lt = re.search(r'<entry key="LONGTEXT">(.*?)</entry>', full_body, re.DOTALL)
        if lt:
            decoded = html.unescape(lt.group(1))
            text_only = re.sub(r"<[^>]+>", " ", decoded)
            text_only = re.sub(r"\s+", " ", text_only).strip()
            print(f"  [{label}] FAIL: {text_only[:200]}")
        else:
            print(f"  [{label}] FAIL: {full_body[:200]}")
        return False
    finally:
        await crud.unlock_object("CLAS", "ZCL_DEMO_CARRIER2", handle)


async def main() -> None:
    cfg = Config(
        base_url="http://dl0992sc9sa09.dev.sap.nsw.education:8000",
        username="10014950",
        password="Mydevportal@02",
        client="010",
    )
    async with Transport(cfg) as t:
        crud = CRUDOperations(t, cfg)
        for label, source in SOURCES.items():
            ok = await try_write(t, crud, label, source)
            # Don't break — test all variants


asyncio.run(main())
