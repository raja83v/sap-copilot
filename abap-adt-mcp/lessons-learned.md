# Lessons Learned — SAP ADT MCP Server

## 1. Lock/Unlock Accept Header (HTTP 406)

**Problem:** Every `WriteSource` and `EditSource` call failed with HTTP 406 Not Acceptable.

**Root Cause:** `lock_object()` used `CREATE_ACCEPT_TYPES["PROG"]` (`application/vnd.sap.adt.programs.programs.v2+xml`) as the `Accept` header. The SAP lock endpoint returns lock handles in generic `application/vnd.sap.as+xml` format, so the server correctly rejected the request with 406.

**Fix:** Changed both `lock_object()` and `unlock_object()` in `crud.py` to use `Accept: application/vnd.sap.as+xml` instead of the object-type-specific vendor MIME type. The `CREATE_ACCEPT_TYPES` dictionary is now only used for object **creation**, not for lock/unlock operations.

**Lesson:** SAP ADT lock and unlock endpoints always return XML in the generic `application/vnd.sap.as+xml` format regardless of the object type. Only object creation endpoints use type-specific vendor MIME types.

---

## 2. Source PUT Content-Type and Encoding

**Problem:** Writing source code failed intermittently with encoding-related errors.

**Root Cause:** The `update_source()` method was sending `Content-Type: application/xml` and relying on the HTTP library to encode the body. SAP ADT expects source code as `text/plain; charset=utf-8` with the body pre-encoded to bytes.

**Fix:** Changed `update_source()` to use `Content-Type: text/plain; charset=utf-8`, `Accept: text/plain, application/vnd.sap.as+xml`, and pre-encode the source string to `bytes` before sending.

**Lesson:** SAP ADT source endpoints treat source code as plain text, not XML. Always pre-encode to bytes to avoid double-encoding issues.

---

## 3. Activation Message XML Parsing (`<msg>` tags)

**Problem:** Activation appeared to succeed ("Successfully written and activated") but the object remained inactive in SAP. The server logs showed activation response XML with error messages logged as "unparsed".

**Root Cause:** `CheckMessage.parse_list()` in `xml_types.py` only matched `<checkMessage>`, `<message>`, `<finding>`, and `<alert>` XML tags. SAP's activation endpoint returns errors in `<msg>` tags. Additionally, `<shortText>` elements contain a nested `<txt>` child element, but the parser was reading `.text` directly from `<shortText>` (which returns `None` when there are child elements).

**Fix:**
1. Added `"msg"` to the tag match list in `CheckMessage.parse_list()`
2. Added nested `<txt>` element extraction — the parser now checks for a `<txt>` child before falling back to direct `.text`

**Lesson:** SAP ADT responses use multiple XML tag names for messages depending on the endpoint. Always inspect actual server responses when adding new endpoint support. Also pay attention to nested element structures in SAP XML — text content is often wrapped in child elements rather than placed directly in the parent.

---

## 4. Syntax Check Before Activation

**Problem:** Programs were being activated without prior syntax checking, leading to silent activation failures.

**Fix:** Added a syntax check step in the `write_source()` workflow (in `workflows.py`). The flow is now: lock → update → unlock → **syntax check** → activate. If syntax errors are found (messages with `type="E"`), activation is blocked and the errors are returned to the caller.

**Lesson:** Always validate before activating. SAP activation can silently fail and leave objects in an inactive state; checking syntax first catches most issues and provides clear error messages.

---

## 5. Python `__pycache__` Staleness with Editable Install

**Problem:** After modifying Python source files in the MCP server, the changes didn't take effect even after restarting the server.

**Root Cause:** The package is installed in editable mode (`pip install -e .`), but Python caches compiled bytecode in `__pycache__/` directories. If the `.pyc` files have timestamps matching or newer than the source, Python serves stale bytecode.

**Fix:** Delete all `__pycache__` directories before restarting the MCP server after making code changes.

**Lesson:** When working with editable Python packages, always clear `__pycache__` after modifying source files. Consider adding `PYTHONDONTWRITEBYTECODE=1` to the development environment.

---

## 6. SAP Enqueue Lock Persistence

**Problem:** After a failed `WriteSource` attempt, subsequent attempts to the same program name failed with HTTP 403 (lock conflict).

**Root Cause:** SAP enqueue locks are server-side and persist even after the MCP client session ends. If `lock_object()` succeeds but the workflow fails before `unlock_object()`, the lock remains until it times out or is manually released.

**Lesson:** Always ensure unlock happens in a `finally` block. When debugging lock issues, either wait for timeout, manually release locks in SAP (SM12), or use a new program name.

---

## 7. BAPI Structure Field Names

**Problem:** ABAP syntax check failed because `ls_per-title_key` was used but `BAPIBUS1006_CENTRAL_PERSON` doesn't have a `title_key` component.

**Root Cause:** The field was guessed as `title_key` but the actual field name is `title_aca1` (academic title 1). The structure uses `title_aca1`, `title_aca2`, `title_sppl` for different title types.

**Fix:** Changed to `ls_per-title_aca1 = is_bp-title.`

**Lesson:** Always verify BAPI structure fields using `GetStructure` before writing ABAP code. SAP naming conventions are often non-obvious (e.g., `title_aca1` instead of `title` or `title_key`).

---

## 8. Session Type Handling

**Problem:** Certain object types (TABL, DDLS, SRVD, SRVB, BDEF) require stateful sessions but the transport selection was overriding the session type.

**Fix:** Added `_KEEP_SESSION_TYPES` set in `crud.py` to preserve stateful sessions for these object types, preventing the transport parameter logic from switching to stateless mode.

**Lesson:** SAP ADT distinguishes between stateful and stateless HTTP sessions. Complex object types that involve multi-step server-side processing require stateful sessions.

---

## 9. CLAS/INTF/BDEF Creation XML and Content-Type

**Problem:** Creating CLAS, INTF, or BDEF objects failed (HTTP 415 for CLAS/INTF, wrong element name for all three).

**Root Causes:**
1. `CLAS` and `INTF` were missing from `CREATE_CONTENT_TYPES` → SAP returned 415 (server received generic `application/xml` instead of the required vendor MIME).
2. XML element name for CLAS was `class` — should be `abapClass`. Must also include `oo:category="1"`.
3. XML element name for INTF was `interface` — should be `abapInterface`.
4. BDEF element name was `behaviorDefinition` (capital D) — should be `behaviordefinition` (lowercase). Type code `BDEF` should be `BDEF/BDL`.

**Fix:**
- Added `"CLAS": "application/vnd.sap.adt.oo.classes+xml; charset=utf-8"` and `"INTF": "application/vnd.sap.adt.oo.interfaces+xml; charset=utf-8"` to `CREATE_CONTENT_TYPES` in `crud.py`.
- Updated `_TYPE_META` in `build_create_object_xml()` (`xml_types.py`): CLAS element → `abapClass`, INTF element → `abapInterface`, BDEF element → `behaviordefinition`, BDEF type code → `BDEF/BDL`.
- Added `"CLAS": ' oo:category="1"'` to `_EXTRA_ATTRS`.

**Lesson:** Cross-reference element names *and* Content-Types against actual SAP ADT responses. The `CREATE_ACCEPT_TYPES` dict stores what to accept back; `CREATE_CONTENT_TYPES` must store what to send. Missing entries silently fall back to `application/xml` which SAP rejects with 415.

---

## 10. RunReport Has No Standard ADT REST Endpoint

**Problem:** `RunReport` called `/sap/bc/adt/programs/programs/run` which does not exist in standard SAP ADT, causing 404 connectivity errors.

**Root Cause:** SAP ADT is a development tool API — it has no synchronous report-execution endpoint. Report execution is a runtime concern that SAP handles via ABAP submit/RFC, not via ADT REST.

**Fix:** Updated `RunReport` handler to route through the WebSocket client (ZADT_VSP) when available (same as `RunReportAsync`). When `ws_client` is None it returns a clear explanation listing alternatives (install ZADT_VSP, use GetReportOutput for spool, etc.) instead of making a doomed HTTP call.

**Lesson:** SAP ADT REST endpoints cover object lifecycle (read/create/edit/activate) not program execution. Any "run" functionality requires either ZADT_VSP WebSocket extension or RFC/BAPI access outside the ADT API surface.
