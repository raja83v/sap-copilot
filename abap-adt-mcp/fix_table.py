"""Script to lock and write DDLS source - trying different lock approaches."""
import httpx
import re
import sys

base = 'http://dl0992sc9sa00.dev.sap.nsw.education:8000'
c = httpx.Client(auth=('10014950', 'Mydevportal@02'), timeout=30)

def collect_cookies(resp, cookies):
    for header_val in resp.headers.get_list("set-cookie"):
        try:
            name_val = header_val.split(";")[0]
            name, val = name_val.split("=", 1)
            cookies[name.strip()] = val.strip()
        except ValueError:
            pass

def get_cookie_str(cookies):
    return "; ".join(f"{k}={v}" for k, v in cookies.items())

session_cookies = {}

# Step 1: Get CSRF
print("Fetching CSRF token...")
r = c.head(
    f'{base}/sap/bc/adt/core/discovery',
    params={'sap-client': '010', 'sap-language': 'EN'},
    headers={'Accept': '*/*', 'X-CSRF-Token': 'Fetch'}
)
collect_cookies(r, session_cookies)
t = r.headers.get('X-CSRF-Token', '')
print(f'CSRF: {t[:20]}... (status={r.status_code})')

# Try different lock approaches
lock_url = f'{base}/sap/bc/adt/ddic/ddl/sources/zi_travel'
base_headers = {
    'X-CSRF-Token': t,
    'Cookie': get_cookie_str(session_cookies),
}

# Approach 1: Try with X-sap-adt-version header
for version in ['0048.0000', '0046.0000', '0044.0000', '0042.0000']:
    print(f"\nTrying lock with X-sap-adt-version: {version}...")
    hdrs = dict(base_headers)
    hdrs['Accept'] = 'application/vnd.sap.adt.ddlSource+xml'
    hdrs['X-sap-adt-version'] = version
    r2 = c.post(lock_url, params={'sap-client': '010', 'sap-language': 'EN', '_action': 'LOCK', 'accessMode': 'MODIFY'}, headers=hdrs)
    collect_cookies(r2, session_cookies)
    base_headers['Cookie'] = get_cookie_str(session_cookies)
    print(f'  Status: {r2.status_code}')
    if r2.status_code < 400:
        print(f'  Response: {r2.text[:300]}')
        break
    # Check if error message gives a hint
    if 'accepted' in r2.text.lower() or 'version' in r2.text.lower():
        print(f'  Hint: {r2.text[:300]}')

# Approach 2: Try with different URL pattern
print("\nTrying lock via programs endpoint pattern...")
hdrs = dict(base_headers)
hdrs['Accept'] = 'application/xml'
hdrs['X-sap-adt-sessiontype'] = 'stateful'
r3 = c.post(lock_url, params={'sap-client': '010', 'sap-language': 'EN', '_action': 'LOCK', 'accessMode': 'MODIFY'}, headers=hdrs)
collect_cookies(r3, session_cookies)
print(f'  Status: {r3.status_code}')

# Approach 3: Try OPTIONS to see what methods are supported
print("\nChecking OPTIONS...")
r4 = c.options(lock_url, params={'sap-client': '010', 'sap-language': 'EN'}, headers={'Cookie': get_cookie_str(session_cookies)})
print(f'  Status: {r4.status_code}')
print(f'  Allow: {r4.headers.get("Allow", "N/A")}')
print(f'  Headers: {dict(r4.headers)}')

# Approach 4: Try GET with _action=LOCK (some old systems)
print("\nTrying GET with _action=LOCK...")
hdrs = dict(base_headers)
hdrs['Accept'] = 'application/vnd.sap.adt.ddlSource+xml'
r5 = c.get(lock_url, params={'sap-client': '010', 'sap-language': 'EN', '_action': 'LOCK', 'accessMode': 'MODIFY'}, headers=hdrs)
collect_cookies(r5, session_cookies)
print(f'  Status: {r5.status_code}')
if r5.status_code < 400:
    print(f'  Response: {r5.text[:300]}')
else:
    print(f'  Error: {r5.text[:200]}')
