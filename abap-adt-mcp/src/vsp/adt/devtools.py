"""Development tools — syntax check, activation, unit tests, ATC, pretty print."""

from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import quote

from vsp.adt.http import Transport
from vsp.adt.xml_types import (
    ATCFinding,
    CheckMessage,
    UnitTestResult,
    build_activation_xml,
    build_atc_run_xml,
    build_syntax_check_xml,
    build_unit_test_xml,
)
from vsp.config import Config

logger = logging.getLogger("vsp.adt.devtools")

# Mapping from 4-char ABAP type to the ADT sub-type required in activation XML.
ADT_TYPE_MAP: dict[str, str] = {
    "PROG": "PROG/P",
    "INCL": "PROG/I",
    "CLAS": "CLAS/OC",
    "INTF": "INTF/OI",
    "FUGR": "FUGR/F",
    "FUNC": "FUGR/FF",
    "TABL": "TABL/DT",
    "VIEW": "VIEW/DV",
    "DTEL": "DTEL/DE",
    "DOMA": "DOMA/DO",
    "DDLS": "DDLS/DF",
    "MSAG": "MSAG/E",
    "DEVC": "DEVC/K",
    "TRAN": "TRAN/T",
    "TYPE": "TYPE/TG",
}


class DevTools:
    """Development tools for ABAP via ADT API."""

    def __init__(self, transport: Transport, config: Config):
        self.transport = transport
        self.config = config

    # =========================================================================
    # Syntax Check
    # =========================================================================

    async def syntax_check(self, uri: str) -> tuple[str, list[CheckMessage]]:
        """Run syntax check on an ABAP object.

        Args:
            uri: ADT URI of the object (e.g., /sap/bc/adt/programs/programs/ZTEST).

        Returns:
            List of check messages (errors, warnings, info).
        """
        xml_body = build_syntax_check_xml(uri)
        resp = await self.transport.post(
            "/sap/bc/adt/checkruns",
            content=xml_body,
            content_type="application/vnd.sap.adt.checkobjects+xml; charset=utf-8",
            accept="application/vnd.sap.adt.checkmessages+xml",
        )
        logger.debug("SyntaxCheck raw response: %s", resp.text)
        messages = CheckMessage.parse_list(resp.text)
        return resp.text, messages

    # =========================================================================
    # Activation
    # =========================================================================

    async def activate(self, uri: str, obj_type: str = "", name: str = "") -> tuple[list[CheckMessage], str]:
        """Activate a single ABAP object.

        Args:
            uri: ADT URI of the object.
            obj_type: 4-char ABAP object type (e.g. "PROG", "CLAS").
            name: Object name (e.g. "ZMM_PO_UPLOAD_OOP").

        Returns:
            Tuple of (messages, raw_body). Messages empty = success.
        """
        adt_type = ADT_TYPE_MAP.get(obj_type.upper(), obj_type.upper())
        messages, raw = await self.activate_list([(uri, adt_type, name.upper())])
        return messages, raw

    async def activate_list(self, objects: list[tuple[str, str, str]]) -> tuple[list[CheckMessage], str]:
        """Activate multiple ABAP objects.

        Args:
            objects: List of (uri, adtcore_type, name) tuples.

        Returns:
            Tuple of (messages, raw_body). Messages empty = clean activation.
        """
        from vsp.adt.http import ADTHTTPError
        xml_body = build_activation_xml(objects)
        logger.debug("Activation XML: %s", xml_body)
        try:
            resp = await self.transport.post(
                "/sap/bc/adt/activation",
                content=xml_body,
                content_type="application/xml",
                accept="application/xml",
                params={"method": "activate", "preauditRequested": "true"},
            )
            logger.debug("Activation response status: %s, body: %s", resp.status_code, resp.text)
            body = resp.text
        except ADTHTTPError as e:
            # ADT returns 400 when there are compile errors; parse the body
            body = e.response.text if e.response is not None else str(e)
        return CheckMessage.parse_list(body), body

    async def activate_package(self, package: str) -> tuple[list[CheckMessage], str]:
        """Activate all inactive objects in a package.

        Args:
            package: Package name.

        Returns:
            Tuple of (messages, raw_body).
        """
        uri = f"/sap/bc/adt/packages/{quote(package.upper())}"
        return await self.activate(uri, "DEVC", package.upper())

    async def get_inactive_objects(self) -> list[CheckMessage]:
        """Get list of inactive objects for the current user.

        Returns:
            List of inactive objects as check messages.
        """
        resp = await self.transport.get(
            "/sap/bc/adt/activation",
            params={"method": "getInactiveObjects"},
        )
        return CheckMessage.parse_list(resp.text)

    # =========================================================================
    # Unit Tests
    # =========================================================================

    async def run_unit_tests(self, uri: str) -> UnitTestResult:
        """Run ABAP unit tests.

        Args:
            uri: ADT URI of the object or package.

        Returns:
            UnitTestResult with class/method results.
        """
        xml_body = build_unit_test_xml(uri)
        resp = await self.transport.post(
            "/sap/bc/adt/abapunit/testruns",
            content=xml_body,
            content_type="application/xml",
            accept="application/xml",
        )
        return UnitTestResult.from_xml(resp.text)

    # =========================================================================
    # ATC (ABAP Test Cockpit)
    # =========================================================================

    async def run_atc_check(self, uri: str, *, variant: str = "DEFAULT") -> list[ATCFinding]:
        """Run ATC (ABAP Test Cockpit) check.

        Args:
            uri: ADT URI of the object.
            variant: ATC check variant.

        Returns:
            List of ATC findings.
        """
        xml_body = build_atc_run_xml(uri, variant)

        # Start the ATC run
        resp = await self.transport.post(
            "/sap/bc/adt/atc/runs",
            content=xml_body,
            content_type="application/xml",
            accept="application/xml",
            params={"objectSetIsComplete": "true"},
        )

        # The response may contain a worklist ID for async results
        # For now, parse directly
        return ATCFinding.parse_list(resp.text)

    async def get_atc_customizing(self) -> str:
        """Get ATC customizing settings.

        Returns:
            Raw XML response with ATC settings.
        """
        resp = await self.transport.get("/sap/bc/adt/atc/customizing")
        return resp.text

    # =========================================================================
    # Pretty Printer
    # =========================================================================

    async def pretty_print(self, source: str, uri: str = "") -> str:
        """Pretty-print ABAP source code.

        Args:
            source: Source code to format.
            uri: Optional ADT URI for context.

        Returns:
            Formatted source code.
        """
        headers: dict[str, str] = {}
        if uri:
            headers["Content-Location"] = uri

        resp = await self.transport.post(
            "/sap/bc/adt/abapsource/prettyprinter",
            content=source,
            content_type="text/plain",
            accept="text/plain",
            headers=headers if headers else None,
        )
        return resp.text

    async def get_pretty_printer_settings(self) -> str:
        """Get pretty printer settings.

        Returns:
            XML response with current settings.
        """
        resp = await self.transport.get("/sap/bc/adt/abapsource/prettyprinter/settings")
        return resp.text

    async def set_pretty_printer_settings(self, settings_xml: str) -> None:
        """Set pretty printer settings.

        Args:
            settings_xml: XML with new settings.
        """
        await self.transport.put(
            "/sap/bc/adt/abapsource/prettyprinter/settings",
            content=settings_xml,
            content_type="application/xml",
        )
