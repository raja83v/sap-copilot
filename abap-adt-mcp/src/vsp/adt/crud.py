"""CRUD operations for ADT objects.

Handles locking, creating, updating, and deleting ABAP objects.
All write operations require stateful sessions.
"""

from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import quote

from vsp.adt.http import Transport
from vsp.adt.xml_types import build_create_object_xml
from vsp.config import Config, SessionType

logger = logging.getLogger("vsp.adt.crud")

# Object type to creation URL mapping
CREATE_PATHS: dict[str, str] = {
    "PROG": "/sap/bc/adt/programs/programs",
    "CLAS": "/sap/bc/adt/oo/classes",
    "INTF": "/sap/bc/adt/oo/interfaces",
    "FUGR": "/sap/bc/adt/functions/groups",
    "DEVC": "/sap/bc/adt/packages",
    "TABL": "/sap/bc/adt/ddic/tables",
    "DDLS": "/sap/bc/adt/ddic/ddl/sources",
    "DDLX": "/sap/bc/adt/ddic/ddlx/sources",
    "SRVD": "/sap/bc/adt/ddic/srvd/sources",
    "BDEF": "/sap/bc/adt/bo/behaviordefinitions",
    "SRVB": "/sap/bc/adt/businessservices/bindings",
}

# Vendor-specific Content-Type required by each creation endpoint.
# Discovered via GET of existing objects (the 406 response lists accepted types).
CREATE_CONTENT_TYPES: dict[str, str] = {
    "CLAS": "application/vnd.sap.adt.oo.classes+xml; charset=utf-8",
    "INTF": "application/vnd.sap.adt.oo.interfaces+xml; charset=utf-8",
    "TABL": "application/vnd.sap.adt.tables.v2+xml; charset=utf-8",
    "DDLS": "application/vnd.sap.adt.ddlSource+xml; charset=utf-8",
    "SRVD": "application/vnd.sap.adt.ddic.srvd.v1+xml; charset=utf-8",
    "DDLX": "application/vnd.sap.adt.ddic.ddlx.v1+xml; charset=utf-8",
    "SRVB": "application/vnd.sap.adt.businessservices.servicebinding.v2+xml; charset=utf-8",
    "BDEF": "application/vnd.sap.adt.behaviordefinition+xml; charset=utf-8",
}

# Vendor-specific Accept header for creation and lock/unlock responses.
# Some endpoints reject the default application/xml Accept header.
CREATE_ACCEPT_TYPES: dict[str, str] = {
    "PROG": "application/vnd.sap.adt.programs.programs.v2+xml",
    "INCL": "application/vnd.sap.adt.programs.includes.v2+xml",
    "CLAS": "application/vnd.sap.adt.oo.classes+xml",
    "INTF": "application/vnd.sap.adt.oo.interfaces+xml",
    "FUNC": "application/vnd.sap.adt.functions.fmodules+xml",
    "FUGR": "application/vnd.sap.adt.functions.groups+xml",
    "TABL": "application/vnd.sap.adt.tables.v2+xml",
    "DDLS": "application/vnd.sap.adt.ddlSource+xml",
    "SRVD": "application/vnd.sap.adt.ddic.srvd.v1+xml",
    "DDLX": "application/vnd.sap.adt.ddic.ddlx.v1+xml",
    "SRVB": "application/vnd.sap.adt.businessservices.servicebinding.v2+xml",
    "BDEF": "application/vnd.sap.adt.behaviordefinition+xml",
}


# Object type to URI path mapping for lock/unlock
OBJECT_URI_PATHS: dict[str, str] = {
    "PROG": "/sap/bc/adt/programs/programs/{name}",
    "CLAS": "/sap/bc/adt/oo/classes/{name}",
    "INTF": "/sap/bc/adt/oo/interfaces/{name}",
    "FUNC": "/sap/bc/adt/functions/groups/{group}/fmodules/{name}",
    "FUGR": "/sap/bc/adt/functions/groups/{name}",
    "INCL": "/sap/bc/adt/programs/includes/{name}",
    "DDLS": "/sap/bc/adt/ddic/ddl/sources/{name}",
    "DDLX": "/sap/bc/adt/ddic/ddlx/sources/{name}",
    "TABL": "/sap/bc/adt/ddic/tables/{name}",
    "SRVD": "/sap/bc/adt/ddic/srvd/sources/{name}",
    "BDEF": "/sap/bc/adt/bo/behaviordefinitions/{name}",
    "SRVB": "/sap/bc/adt/businessservices/bindings/{name}",
    "DEVC": "/sap/bc/adt/packages/{name}",
}

# Source URL paths (for update operations)
SOURCE_PATHS: dict[str, str] = {
    "PROG": "/sap/bc/adt/programs/programs/{name}/source/main",
    "CLAS": "/sap/bc/adt/oo/classes/{name}/source/main",
    "INTF": "/sap/bc/adt/oo/interfaces/{name}/source/main",
    "FUNC": "/sap/bc/adt/functions/groups/{group}/fmodules/{name}/source/main",
    "INCL": "/sap/bc/adt/programs/includes/{name}/source/main",
    "DDLS": "/sap/bc/adt/ddic/ddl/sources/{name}/source/main",
    "DDLX": "/sap/bc/adt/ddic/ddlx/sources/{name}/source/main",
    "TABL": "/sap/bc/adt/ddic/tables/{name}/source/main",
    "SRVD": "/sap/bc/adt/ddic/srvd/sources/{name}/source/main",
    "BDEF": "/sap/bc/adt/bo/behaviordefinitions/{name}/source/main",
}


class CRUDOperations:
    """CRUD operations for ABAP objects via ADT API."""

    def __init__(self, transport: Transport, config: Config):
        self.transport = transport
        self.config = config

    # =========================================================================
    # Lock / Unlock
    # =========================================================================

    async def lock_object(
        self,
        object_type: str,
        name: str,
        *,
        group: str = "",
    ) -> str:
        """Lock an ABAP object for editing.

        Args:
            object_type: Object type (PROG, CLAS, etc.)
            name: Object name.
            group: Function group (for FUNC type).

        Returns:
            Lock handle string.
        """
# Lock operations require STATEFUL sessions so the lock handle persists
        # across subsequent update/unlock requests within the same HTTP session.
        # NOTE: Creation endpoints (DDLS, SRVD, etc.) reject the session-type
        # header — but lock/update endpoints need it.  Only TABL is excluded
        # here because its lock endpoint also rejects the session-type header.
        _KEEP_SESSION_TYPES = {"TABL"}
        obj_upper = object_type.upper()
        if obj_upper in _KEEP_SESSION_TYPES:
            await self.transport.set_session_type(SessionType.KEEP)
        else:
            await self.transport.set_session_type(SessionType.STATEFUL)

        uri = self._get_object_uri(object_type, name, group=group)
        # Lock responses return lock-handle XML in application/vnd.sap.as+xml
        # format — NOT the object-type-specific MIME used for creation.
        lock_accept = "application/vnd.sap.as+xml"
        # Lock POST has no body; avoid sending Content-Type for endpoints
        # that reject unexpected media types (TABL, etc.).
        resp = await self.transport.post(
            uri,
            params={"_action": "LOCK", "accessMode": "MODIFY"},
            content_type="",
            accept=lock_accept,
        )

        # Extract lock handle from response
        lock_handle = ""
        if resp.text:
            import re
            # Try all known ADT lock-handle XML patterns (namespace-qualified first)
            for pattern in (
                r'<adtcore:lockHandle[^>]*>(.*?)</adtcore:lockHandle>',
                r'<[^:>]+:lockHandle[^>]*>(.*?)</[^:>]+:lockHandle>',
                r'<lockHandle[^>]*>(.*?)</lockHandle>',
                r'<LOCK_HANDLE>(.*?)</LOCK_HANDLE>',
                r'lockHandle="([^"]+)"',
            ):
                match = re.search(pattern, resp.text, re.IGNORECASE | re.DOTALL)
                if match:
                    lock_handle = match.group(1).strip()
                    break

        if not lock_handle:
            lock_handle = resp.headers.get("X-Lock-Handle", "")
            if not lock_handle:
                lock_handle = resp.headers.get("x-lock-handle", "")

        # Last resort: if the body is a short string with no angle brackets,
        # treat the whole body as the lock handle (some systems return plain text)
        if not lock_handle and resp.text and "<" not in resp.text:
            lock_handle = resp.text.strip()

        logger.debug(
            "Locked %s %s (handle=%s, raw_resp=%s)",
            object_type, name,
            lock_handle[:16] if lock_handle else "<EMPTY>",
            resp.text[:200] if resp.text else "<empty>",
        )
        if not lock_handle:
            raise ValueError(
                f"Could not extract lock handle for {object_type} {name}. "
                f"Response: {resp.text[:300]}"
            )
        return lock_handle

    async def unlock_object(
        self,
        object_type: str,
        name: str,
        lock_handle: str,
        *,
        group: str = "",
    ) -> None:
        """Unlock an ABAP object.

        Args:
            object_type: Object type.
            name: Object name.
            lock_handle: Lock handle from lock_object().
            group: Function group (for FUNC type).
        """
        uri = self._get_object_uri(object_type, name, group=group)
        # Unlock uses the same generic accept as lock.
        unlock_accept = "application/vnd.sap.as+xml"
        await self.transport.post(
            uri,
            params={"_action": "UNLOCK", "lockHandle": lock_handle},
            content_type="",
            accept=unlock_accept,
        )
        logger.debug("Unlocked %s %s", object_type, name)

    # =========================================================================
    # Create
    # =========================================================================

    async def create_object(
        self,
        object_type: str,
        name: str,
        description: str,
        package: str,
        *,
        transport: str = "",
        source: str = "",
        **kwargs: str,
    ) -> str:
        """Create a new ABAP object.

        Args:
            object_type: Object type to create.
            name: Object name.
            description: Object description.
            package: Target package.
            transport: Transport request (required for transportable packages).
            source: Optional initial source code.
            **kwargs: Extra parameters for specific object types (e.g. service_definition for SRVB).

        Returns:
            URI of the created object.
        """
        obj_type = object_type.upper()
        create_path = CREATE_PATHS.get(obj_type)
        if not create_path:
            raise ValueError(f"Cannot create objects of type: {object_type}")

        # Creation endpoints (DDLS, SRVD, SRVB, etc.) return HTTP 415 when any
        # X-sap-adt-sessiontype header is present.  Use KEEP so no session-type
        # header is sent for the creation POST; lock_object switches to STATEFUL.
        await self.transport.set_session_type(SessionType.KEEP)

        xml_body = build_create_object_xml(obj_type, name.upper(), description, package.upper(), transport, **kwargs)

        params: dict[str, str] = {}
        if transport:
            params["corrNr"] = transport

        accept_type = CREATE_ACCEPT_TYPES.get(obj_type, "application/xml")
        resp = await self.transport.post(
            create_path,
            content=xml_body,
            content_type=CREATE_CONTENT_TYPES.get(obj_type, "application/xml"),
            accept=accept_type,
            params=params if params else None,
        )

        # URI is typically in the Location header
        uri = resp.headers.get("Location", "")
        logger.debug("Created %s %s in %s (uri=%s)", object_type, name, package, uri)

        # If initial source provided, update it
        if source and obj_type in SOURCE_PATHS:
            lock_handle = await self.lock_object(obj_type, name)
            try:
                await self.update_source(obj_type, name, source, lock_handle)
            finally:
                await self.unlock_object(obj_type, name, lock_handle)

        return uri

    async def create_package(
        self,
        name: str,
        description: str,
        *,
        super_package: str = "",
        transport: str = "",
    ) -> str:
        """Create a new ABAP package.

        Args:
            name: Package name.
            description: Package description.
            super_package: Parent package.
            transport: Transport request.

        Returns:
            URI of the created package.
        """
        xml_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<pak:package xmlns:pak="http://www.sap.com/adt/packages"
    xmlns:adtcore="http://www.sap.com/adt/core"
    adtcore:description="{description}"
    adtcore:name="{name.upper()}"
    adtcore:type="DEVC/K">
  <pak:superPackage adtcore:name="{super_package.upper()}"/>
  <pak:applicationComponent/>
  <pak:transport>
    <pak:softwareComponent/>
    <pak:transportLayer/>
  </pak:transport>
  <pak:translation/>
  <pak:attributes packageType="development"/>
</pak:package>"""

        params: dict[str, str] = {}
        if transport:
            params["corrNr"] = transport

        resp = await self.transport.post(
            "/sap/bc/adt/packages",
            content=xml_body,
            content_type="application/xml",
            params=params if params else None,
        )
        return resp.headers.get("Location", "")

    async def create_table(
        self,
        name: str,
        description: str,
        package: str,
        source: str,
        *,
        transport: str = "",
    ) -> str:
        """Create a new database table."""
        return await self.create_object("TABL", name, description, package, transport=transport, source=source)

    # =========================================================================
    # Update
    # =========================================================================

    async def update_source(
        self,
        object_type: str,
        name: str,
        content: str,
        lock_handle: str,
        *,
        group: str = "",
        transport: str = "",
    ) -> None:
        """Update the source code of an object.

        Args:
            object_type: Object type.
            name: Object name.
            content: New source code.
            lock_handle: Lock handle.
            group: Function group (for FUNC type).
            transport: Transport request number (corrNr).
        """
        obj_type = object_type.upper()
        source_path = SOURCE_PATHS.get(obj_type)
        if not source_path:
            raise ValueError(f"Cannot update source for type: {object_type}")

        path = source_path.format(name=quote(name.upper()), group=quote(group.upper()) if group else "")

        # Source endpoints: SAP returns source as text/plain, so PUT must also
        # use text/plain for Content-Type.  The Accept header indicates
        # what format we expect in the *response* (status message).
        source_ct = "text/plain; charset=utf-8"
        source_accept = "text/plain, application/vnd.sap.as+xml"
        # Encode content to bytes to prevent httpx from overriding Content-Type
        content_bytes = content.encode("utf-8") if isinstance(content, str) else content
        params: dict[str, str] = {"lockHandle": lock_handle} if lock_handle else {}
        if transport:
            params["corrNr"] = transport
        await self.transport.put(
            path,
            content=content_bytes,
            content_type=source_ct,
            accept=source_accept,
            params=params if params else None,
            headers={"X-Lock-Handle": lock_handle} if lock_handle else None,
        )
        logger.debug("Updated source for %s %s", object_type, name)

    async def update_class_include(
        self,
        name: str,
        include_type: str,
        content: str,
        lock_handle: str,
    ) -> None:
        """Update a class include (testclasses, locals_def, etc.).

        Args:
            name: Class name.
            include_type: Include type (testclasses, locals_def, locals_imp, macros).
            content: New include source code.
            lock_handle: Lock handle.
        """
        path = f"/sap/bc/adt/oo/classes/{quote(name.upper())}/includes/{include_type}"
        await self.transport.put(
            path,
            content=content,
            content_type="text/plain",
            headers={"X-Lock-Handle": lock_handle} if lock_handle else None,
        )

    # =========================================================================
    # Delete
    # =========================================================================

    async def delete_object(
        self,
        object_type: str,
        name: str,
        lock_handle: str,
        *,
        group: str = "",
        transport: str = "",
    ) -> None:
        """Delete an ABAP object.

        Args:
            object_type: Object type.
            name: Object name.
            lock_handle: Lock handle.
            group: Function group (for FUNC type).
            transport: Transport request.
        """
        uri = self._get_object_uri(object_type, name, group=group)

        params: dict[str, str] = {"lockHandle": lock_handle}
        if transport:
            params["corrNr"] = transport

        await self.transport.delete(
            uri,
            params=params,
            headers={"X-Lock-Handle": lock_handle},
        )
        logger.debug("Deleted %s %s", object_type, name)

    # =========================================================================
    # Helpers
    # =========================================================================

    def _get_object_uri(self, object_type: str, name: str, *, group: str = "") -> str:
        """Get the ADT URI for an object."""
        obj_type = object_type.upper()
        path_template = OBJECT_URI_PATHS.get(obj_type)
        if not path_template:
            raise ValueError(f"Unknown object type: {object_type}")
        return path_template.format(
            name=quote(name.upper()),
            group=quote(group.upper()) if group else "",
        )
