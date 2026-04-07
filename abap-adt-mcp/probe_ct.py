"""Direct test of DDLS creation via vsp's own CRUD code."""
import asyncio
import logging
import sys

logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s %(message)s", stream=sys.stderr)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.DEBUG)

sys.path.insert(0, "src")

from vsp.config import Config
from vsp.adt.http import Transport
from vsp.adt.crud import CRUDOperations


async def main():
    cfg = Config(
        base_url="http://dl0991sd1na00.apps.dev.det.nsw.edu.au:8000",
        username="10014950",
        password="Mydevportal@02",
        client="100",
    )
    async with Transport(cfg) as transport:
        crud = CRUDOperations(transport, cfg)

        # Monkey-patch _execute to log request headers
        orig_execute = transport._execute
        async def patched_execute(method, url, content, headers):
            if method == "POST":
                print(f"\n>>> {method} {url}", file=sys.stderr)
                for k, v in headers.items():
                    print(f"    {k}: {v}", file=sys.stderr)
                if content and len(content) < 500:
                    body = content if isinstance(content, str) else content.decode("utf-8", errors="replace")
                    print(f"    BODY: {body[:200]}", file=sys.stderr)
            return await orig_execute(method, url, content, headers)
        transport._execute = patched_execute
        source = (
            "@AbapCatalog.sqlViewName: 'ZVI_TRAVEL'\n"
            "@AbapCatalog.compiler.compareFilter: true\n"
            "@AccessControl.authorizationCheck: #NOT_REQUIRED\n"
            "@EndUserText.label: 'Travel View on Flight Schedule'\n"
            "define view ZI_TRAVEL as select from spfli {\n"
            "  key carrid,\n"
            "  key connid,\n"
            "      cityfrom,\n"
            "      cityto\n"
            "}"
        )
        try:
            uri = await crud.create_object("DDLS", "ZI_TRAVEL", "Travel View on Flight Schedule", "$TMP", source=source)
            print(f"SUCCESS: {uri}")
        except Exception as e:
            print(f"ERROR: {e}")


asyncio.run(main())



