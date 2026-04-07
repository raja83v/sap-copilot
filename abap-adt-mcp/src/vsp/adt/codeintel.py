"""Code intelligence — find definition, references, code completion, type hierarchy."""

from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import quote

from vsp.adt.http import Transport
from vsp.config import Config

logger = logging.getLogger("vsp.adt.codeintel")


class CodeIntelligence:
    """Code intelligence operations via ADT API."""

    def __init__(self, transport: Transport, config: Config):
        self.transport = transport
        self.config = config

    async def find_definition(self, uri: str, *, line: int = 0, column: int = 0) -> str:
        """Navigate to the definition of a symbol.

        Args:
            uri: ADT URI of the source object.
            line: Line number (1-based).
            column: Column number (1-based).

        Returns:
            XML response with target location.
        """
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
<adtcore:objectReference xmlns:adtcore="http://www.sap.com/adt/core"
    adtcore:uri="{uri}"
    adtcore:name=""
    adtcore:type="">
  <adtcore:position line="{line}" column="{column}"/>
</adtcore:objectReference>"""

        resp = await self.transport.post(
            "/sap/bc/adt/navigation/target",
            content=body,
            content_type="application/xml",
            accept="application/xml",
        )
        return resp.text

    async def find_references(self, uri: str) -> str:
        """Find all references to an object.

        Args:
            uri: ADT URI of the object.

        Returns:
            XML response with reference locations.
        """
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
<adtcore:objectReference xmlns:adtcore="http://www.sap.com/adt/core"
    adtcore:uri="{uri}"/>"""

        resp = await self.transport.post(
            "/sap/bc/adt/repository/informationsystem/objectreferences",
            content=body,
            content_type="application/xml",
            accept="application/xml",
        )
        return resp.text

    async def code_completion(self, uri: str, source: str, line: int, column: int) -> str:
        """Get code completion proposals.

        Args:
            uri: ADT URI of the source object.
            source: Current source code.
            line: Cursor line (1-based).
            column: Cursor column (1-based).

        Returns:
            XML response with completion proposals.
        """
        resp = await self.transport.post(
            "/sap/bc/adt/abapsource/codecompletion",
            content=source,
            content_type="text/plain",
            accept="application/xml",
            headers={
                "Content-Location": uri,
            },
            params={
                "line": str(line),
                "column": str(column),
            },
        )
        return resp.text

    async def get_type_hierarchy(self, uri: str) -> str:
        """Get type hierarchy for a class/interface.

        Args:
            uri: ADT URI of the class or interface.

        Returns:
            XML response with type hierarchy.
        """
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
<adtcore:objectReference xmlns:adtcore="http://www.sap.com/adt/core"
    adtcore:uri="{uri}"/>"""

        resp = await self.transport.post(
            "/sap/bc/adt/oo/typehierarchy",
            content=body,
            content_type="application/xml",
            accept="application/xml",
        )
        return resp.text

    async def get_class_components(self, name: str) -> str:
        """Get class components (methods, attributes, etc.).

        Args:
            name: Class name.

        Returns:
            XML response with component list.
        """
        path = f"/sap/bc/adt/oo/classes/{quote(name.upper())}/objectstructure/components"
        resp = await self.transport.get(path)
        return resp.text

    async def get_class_info(self, name: str) -> str:
        """Get class metadata and structure.

        Args:
            name: Class name.

        Returns:
            XML response with class metadata.
        """
        path = f"/sap/bc/adt/oo/classes/{quote(name.upper())}/objectstructure"
        resp = await self.transport.get(path)
        return resp.text
