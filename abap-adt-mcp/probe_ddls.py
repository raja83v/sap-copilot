"""Probe DDLS lock endpoint."""
import asyncio
import httpx
import re
import os

os.environ["NO_PROXY"] = "localhost,127.0.0.1,dl0992sc9sa00.dev.sap.nsw.education"

BASE = "http://dl0992sc9sa00.dev.sap.nsw.education:8000"
AUTH = ("10014950", "Mydevportal@02")


async def main():
    async with httpx.AsyncClient(timeout=60, auth=AUTH) as c:
        # Save discovery
        r = await c.get(
            f"{BASE}/sap/bc/adt/core/discovery?sap-client=010",
            headers={"Accept": "application/atomsvc+xml"},
        )
        with open("live_discovery.xml", "w", encoding="utf-8") as f:
            f.write(r.text)
        print(f"Discovery saved ({len(r.text)} bytes)")

        # Find DDL hrefs
        matches = re.findall(r'href="([^"]*ddl[^"]*)"', r.text, re.IGNORECASE)
        print(f"\nDDL endpoints ({len(matches)}):")
        for m in matches:
            print(f"  {m}")

        # Now test LOCK with various approaches
        # First get CSRF
        r0 = await c.head(
            f"{BASE}/sap/bc/adt/core/discovery?sap-client=010",
            headers={"x-csrf-token": "Fetch"},
        )
        csrf = r0.headers.get("x-csrf-token", "")
        # Collect cookies manually
        cookies = {}
        for sc in r0.headers.get_list("set-cookie"):
            parts = sc.split(";")[0]
            if "=" in parts:
                k, v = parts.split("=", 1)
                cookies[k.strip()] = v.strip()
        print(f"\nCSRF: {csrf[:20]}...")
        print(f"Cookies: {list(cookies.keys())}")

        # Try LOCK with X-sap-adt-sessiontype removed entirely
        lock_url = f"{BASE}/sap/bc/adt/ddic/ddl/sources/zi_travel_expense"
        params = {"_action": "LOCK", "accessMode": "MODIFY", "sap-client": "010", "sap-language": "EN"}

        # Approach 1: Minimal headers, no session type, no content-type
        hdrs = {"x-csrf-token": csrf, "Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items())}
        r1 = await c.post(lock_url, params=params, headers=hdrs)
        print(f"\nA1 (minimal): {r1.status_code}")
        if r1.status_code != 200:
            # Check if the response gives a hint about accepted types
            if "Accepted content types:" in r1.text:
                acc_match = re.search(r"Accepted content types:\s*(.+?)(?:<|$)", r1.text)
                if acc_match:
                    print(f"  Accepted: {acc_match.group(1)}")
            print(f"  Body: {r1.text[:300]}")
        else:
            print(f"  OK: {r1.text[:200]}")

        # Approach 2: Try with Accept header listing vendor types
        hdrs2 = {
            "x-csrf-token": csrf,
            "Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()),
            "Accept": "application/vnd.sap.as.adt.lock.handle.v1+xml, application/vnd.sap.adt.ddlSource+xml, application/xml, */*",
            "X-sap-adt-sessiontype": "stateful",
        }
        r2 = await c.post(lock_url, params=params, headers=hdrs2)
        print(f"\nA2 (multi-accept): {r2.status_code}")
        if r2.status_code != 200:
            print(f"  Body: {r2.text[:300]}")
        else:
            print(f"  OK: {r2.text[:200]}")

        # Approach 3: Use the "corrNr" trick - maybe we just pass an empty corrNr
        params3 = {"_action": "LOCK", "accessMode": "MODIFY", "corrNr": "", "sap-client": "010", "sap-language": "EN"}
        hdrs3 = {
            "x-csrf-token": csrf,
            "Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()),
            "X-sap-adt-sessiontype": "stateful",
        }
        r3 = await c.post(lock_url, params=params3, headers=hdrs3)
        print(f"\nA3 (corrNr=''): {r3.status_code}")
        if r3.status_code != 200:
            print(f"  Body: {r3.text[:300]}")
        else:
            print(f"  OK: {r3.text[:200]}")

        # Approach 4: Supply Content-Length: 0 explicitly and no content-type 
        hdrs4 = {
            "x-csrf-token": csrf,
            "Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()),
            "X-sap-adt-sessiontype": "stateful",
            "Content-Length": "0",
        }
        r4 = await c.post(lock_url, params=params, headers=hdrs4, content=b"")
        print(f"\nA4 (Content-Length:0): {r4.status_code}")
        if r4.status_code != 200:
            print(f"  Body: {r4.text[:300]}")
        else:
            print(f"  OK: {r4.text[:200]}")


asyncio.run(main())
