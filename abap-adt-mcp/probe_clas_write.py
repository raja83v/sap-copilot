"""Direct write-source probe for ZCL_DEMO_CARRIER2 on SC9."""
import asyncio, sys, os, logging
os.environ["NO_PROXY"] = "localhost,127.0.0.1,dl0992sc9sa09.dev.sap.nsw.education"
os.environ["no_proxy"] = os.environ["NO_PROXY"]
logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s %(message)s", stream=sys.stderr)
logging.getLogger("httpcore").setLevel(logging.WARNING)
sys.path.insert(0, "src")

from vsp.config import Config
from vsp.adt.http import Transport
from vsp.adt.crud import CRUDOperations
from vsp.config import SessionType

SOURCE = """CLASS zcl_demo_carrier2 DEFINITION
  PUBLIC
  CREATE PUBLIC.

  PUBLIC SECTION.
    CLASS-METHODS get_all_carriers
      RETURNING VALUE(rt_carriers) TYPE STANDARD TABLE OF scarr.

  PROTECTED SECTION.
  PRIVATE SECTION.
ENDCLASS.

CLASS zcl_demo_carrier2 IMPLEMENTATION.

  METHOD get_all_carriers.
    SELECT * FROM scarr INTO TABLE @rt_carriers ORDER BY carrid.
  ENDMETHOD.

ENDCLASS."""


async def main():
    cfg = Config(
        base_url="http://dl0992sc9sa09.dev.sap.nsw.education:8000",
        username="10014950",
        password="Mydevportal@02",
        client="010",
    )
    async with Transport(cfg) as t:
        crud = CRUDOperations(t, cfg)

        # Step 1: Lock
        print("Locking ZCL_DEMO_CARRIER2 ...")
        try:
            handle = await crud.lock_object("CLAS", "ZCL_DEMO_CARRIER2")
            print(f"  Lock handle: {handle[:20]!r}")
        except Exception as e:
            print(f"  Lock FAILED: {e}")
            return

        # Step 2: Write
        print("Writing source ...")
        try:
            await crud.update_source("CLAS", "ZCL_DEMO_CARRIER2", SOURCE, handle)
            print("  Write OK")
        except Exception as e:
            print(f"  Write FAILED: {str(e)[:400]}")

        # Step 3: Unlock (always)
        print("Unlocking ...")
        try:
            await crud.unlock_object("CLAS", "ZCL_DEMO_CARRIER2", handle)
            print("  Unlock OK")
        except Exception as e:
            print(f"  Unlock FAILED: {e}")


asyncio.run(main())
