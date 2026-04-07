import httpx, base64
AUTH = "10014950:Mydevportal@02"
BASE = "http://dl0991sd1na00.apps.dev.det.nsw.edu.au:8000"
auth_b64 = base64.b64encode(AUTH.encode()).decode()
bh = {"Authorization": "Basic "+auth_b64, "sap-client":"100", "x-sap-adt-sessiontype":"stateful"}
c = httpx.Client(follow_redirects=True)
r = c.head(BASE+"/sap/bc/adt/core/discovery", headers={**bh,"X-CSRF-Token":"Fetch"})
csrf = r.headers.get("x-csrf-token","")
print("CSRF:", csrf, "Cookies:", list(c.cookies.keys()))
xml = '<?xml version="1.0" encoding="UTF-8"?><ddl:source xmlns:ddl="http://www.sap.com/adt/ddic/ddl" xmlns:adtcore="http://www.sap.com/adt/core" adtcore:description="Travel" adtcore:name="ZI_TRAVEL_X" adtcore:type="DDLS"><adtcore:packageRef adtcore:name="\"/></ddl:source>'
for ct in ["application/xml","application/vnd.sap.adt.ddl.source+xml; charset=utf-8","application/vnd.sap.adt.ddl.source.v2+xml; charset=utf-8"]:
    r2=c.post(BASE+"/sap/bc/adt/ddic/ddl/sources",content=xml.encode(),headers={**bh,"X-CSRF-Token":csrf,"Content-Type":ct})
    print(r2.status_code, ct[:45], r2.headers.get("Location",""), r2.text[:80])
    if r2.status_code not in (415,403): break
c.close()
