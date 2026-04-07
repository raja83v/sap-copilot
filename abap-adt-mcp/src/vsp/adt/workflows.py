"""High-level workflow operations.

Unified source operations (GetSource/WriteSource/EditSource),
grep, compare, and clone.
"""

from __future__ import annotations

import difflib
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from vsp.adt.client import ADTClient
from vsp.adt.crud import CRUDOperations
from vsp.adt.devtools import DevTools
from vsp.adt.xml_types import CheckMessage

logger = logging.getLogger("vsp.adt.workflows")


@dataclass
class GrepMatch:
    """A match from grep across objects."""
    object_name: str = ""
    object_type: str = ""
    line_number: int = 0
    line_text: str = ""
    match_text: str = ""


@dataclass
class GrepResult:
    """Result of grep across objects."""
    pattern: str = ""
    matches: list[GrepMatch] = field(default_factory=list)
    objects_searched: int = 0
    objects_matched: int = 0


class Workflows:
    """High-level workflow operations combining multiple ADT calls."""

    def __init__(
        self,
        client: ADTClient,
        crud: CRUDOperations,
        devtools: DevTools,
    ):
        self.client = client
        self.crud = crud
        self.devtools = devtools

    # =========================================================================
    # Unified Write
    # =========================================================================

    async def write_source(
        self,
        object_type: str,
        name: str,
        content: str,
        *,
        method: str = "",
        group: str = "",
        transport: str = "",
        activate: bool = True,
    ) -> str:
        """Write source code with lock → update → activate → unlock flow.

        Args:
            object_type: Object type (PROG, CLAS, etc.)
            name: Object name.
            content: New source code.
            method: Optional method name for method-level write.
            group: Function group (for FUNC type).
            transport: Transport request number (if required).
            activate: Whether to activate after writing.

        Returns:
            Result message string.
        """
        obj_type = object_type.upper()

        # For method-level writes, merge with full source
        if method and obj_type == "CLAS":
            content = await self._merge_method_source(name, method, content)

        # Lock
        lock_handle = await self.crud.lock_object(obj_type, name, group=group)

        try:
            # Update
            await self.crud.update_source(obj_type, name, content, lock_handle, group=group, transport=transport)
        finally:
            # Always unlock BEFORE activating — SAP ADT requires the object to
            # be unlocked before activation (same order as Eclipse ADT plugin).
            await self.crud.unlock_object(obj_type, name, lock_handle, group=group)

        # Syntax check + Activate AFTER unlock
        messages: list[CheckMessage] = []
        if activate:
            uri = self.crud._get_object_uri(obj_type, name, group=group)

            # Always run syntax check first
            _, syntax_msgs = await self.devtools.syntax_check(uri)
            syntax_errors = [m for m in syntax_msgs if m.type == "E"]
            if syntax_errors:
                msg_lines = ["Written but NOT activated — syntax errors found:"]
                for m in syntax_errors:
                    loc = f" line {m.line}" if m.line else ""
                    msg_lines.append(f"  [E]{loc} {m.text}")
                return "\n".join(msg_lines)

            # Syntax clean — proceed to activate
            messages, raw_body = await self.devtools.activate(uri, obj_type, name.upper())
            if not messages and raw_body.strip():
                logger.warning("Activation raw response (unparsed): %s", raw_body)

        # Format result
        if messages:
            msg_lines = ["Written. Activation messages:"]
            for m in messages:
                loc = f" line {m.line}" if m.line else ""
                msg_lines.append(f"  [{m.type}]{loc} {m.text}")
            return "\n".join(msg_lines)
        return f"Successfully written and {'activated' if activate else 'saved (not activated)'}."

    async def edit_source(
        self,
        object_type: str,
        name: str,
        *,
        search: str = "",
        replace: str = "",
        method: str = "",
        group: str = "",
        transport: str = "",
        regex: bool = False,
        is_regex: bool = False,
        activate: bool = True,
    ) -> str:
        """Search-and-replace in source code.

        Args:
            object_type: Object type.
            name: Object name.
            search: String or regex pattern to find.
            replace: Replacement string.
            method: Optional method name for class method edits.
            group: Function group (for FUNC type).
            transport: Transport request number.
            regex: Whether search is a regex pattern.
            is_regex: Alias for regex (backwards compat).
            activate: Whether to activate after editing.

        Returns:
            Result message string.
        """
        use_regex = regex or is_regex

        # Get current source
        source = await self.client.get_source(object_type, name, method=method, group=group)

        # Perform replacement
        if use_regex:
            new_source = re.sub(search, replace, source)
        else:
            new_source = source.replace(search, replace)

        if new_source == source:
            return "No changes — search pattern not found in source."

        # Write back
        result = await self.write_source(
            object_type, name, new_source,
            method=method, group=group, transport=transport, activate=activate,
        )
        return result

    # =========================================================================
    # Compare
    # =========================================================================

    async def compare_source(
        self,
        object_type: str,
        name: str,
        new_content: str,
        *,
        group: str = "",
    ) -> str:
        """Compare current source with new content (unified diff).

        Args:
            object_type: Object type.
            name: Object name.
            new_content: New content to compare against.
            group: Function group (for FUNC type).

        Returns:
            Unified diff string.
        """
        current = await self.client.get_source(object_type, name, group=group)
        diff = difflib.unified_diff(
            current.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"{name} (current)",
            tofile=f"{name} (new)",
        )
        return "".join(diff)

    # =========================================================================
    # Grep
    # =========================================================================

    async def grep_objects(
        self,
        pattern: str,
        object_names: list[str],
        object_type: str = "PROG",
        *,
        group: str = "",
        max_matches: int = 100,
    ) -> GrepResult:
        """Search for a pattern across multiple objects.

        Args:
            pattern: Regex pattern to search for.
            object_names: List of object names to search in.
            object_type: Object type for all objects.
            group: Function group (for FUNC type).
            max_matches: Maximum matches to return.

        Returns:
            GrepResult with matches.
        """
        result = GrepResult(pattern=pattern, objects_searched=len(object_names))
        compiled = re.compile(pattern, re.IGNORECASE)
        matched_objects: set[str] = set()

        for obj_name in object_names:
            try:
                source = await self.client.get_source(object_type, obj_name, group=group)
            except Exception:
                continue

            for line_no, line in enumerate(source.splitlines(), 1):
                match = compiled.search(line)
                if match:
                    result.matches.append(GrepMatch(
                        object_name=obj_name,
                        object_type=object_type,
                        line_number=line_no,
                        line_text=line.strip(),
                        match_text=match.group(),
                    ))
                    matched_objects.add(obj_name)

                    if len(result.matches) >= max_matches:
                        break

            if len(result.matches) >= max_matches:
                break

        result.objects_matched = len(matched_objects)
        return result

    async def grep_package(
        self,
        pattern: str,
        package: str,
        *,
        type_filter: str = "",
        max_matches: int = 100,
    ) -> GrepResult:
        """Search for a pattern across all objects in a package.

        Args:
            pattern: Regex pattern.
            package: Package name.
            type_filter: Optional object type filter.
            max_matches: Maximum matches.

        Returns:
            GrepResult with matches.
        """
        pkg = await self.client.get_package(package)

        result = GrepResult(pattern=pattern)
        compiled = re.compile(pattern, re.IGNORECASE)
        matched_objects: set[str] = set()
        searched = 0

        for obj in pkg.objects:
            # Apply type filter
            if type_filter and obj.type.upper() != type_filter.upper():
                continue

            # Only search source-bearing types
            obj_type = _normalize_type(obj.type)
            if not obj_type:
                continue

            searched += 1
            try:
                source = await self.client.get_source(obj_type, obj.name)
            except Exception:
                continue

            for line_no, line in enumerate(source.splitlines(), 1):
                match = compiled.search(line)
                if match:
                    result.matches.append(GrepMatch(
                        object_name=obj.name,
                        object_type=obj_type,
                        line_number=line_no,
                        line_text=line.strip(),
                        match_text=match.group(),
                    ))
                    matched_objects.add(obj.name)

                    if len(result.matches) >= max_matches:
                        break

            if len(result.matches) >= max_matches:
                break

        result.objects_searched = searched
        result.objects_matched = len(matched_objects)
        return result

    # =========================================================================
    # Clone
    # =========================================================================

    async def clone_object(
        self,
        source_type: str,
        source_name: str,
        target_name: str,
        target_package: str,
        *,
        group: str = "",
        transport: str = "",
        description: str = "",
    ) -> str:
        """Clone an object by copying its source to a new object.

        Args:
            source_type: Source object type.
            source_name: Source object name.
            target_name: Target object name.
            target_package: Target package.
            group: Function group.
            transport: Transport request.
            description: Description for the new object.

        Returns:
            URI of the new object.
        """
        # Get source code
        source = await self.client.get_source(source_type, source_name, group=group)

        if not description:
            description = f"Clone of {source_name}"

        # Create new object with the source
        uri = await self.crud.create_object(
            source_type, target_name, description, target_package,
            transport=transport, source=source,
        )
        return uri

    # =========================================================================
    # Helpers
    # =========================================================================

    async def _merge_method_source(self, class_name: str, method_name: str, new_method_source: str) -> str:
        """Merge new method source into the full class source."""
        full_source = await self.client.get_class_source(class_name)
        methods = await self.client.get_class_methods(class_name)

        method_upper = method_name.upper()
        for m in methods:
            if m.name.upper() == method_upper and m.implementation_start > 0 and m.implementation_end > 0:
                lines = full_source.splitlines()
                new_lines = (
                    lines[:m.implementation_start - 1]
                    + new_method_source.splitlines()
                    + lines[m.implementation_end:]
                )
                return "\n".join(new_lines)

        raise ValueError(f"Method '{method_name}' not found in class '{class_name}'")


def _normalize_type(type_str: str) -> str:
    """Normalize ADT object type string to our type codes."""
    t = type_str.upper()
    type_map = {
        "PROG/P": "PROG",
        "CLAS/OC": "CLAS",
        "INTF/OI": "INTF",
        "FUGR/F": "FUGR",
        "FUNC/FM": "FUNC",
        "PROG/I": "INCL",
        "DDLS/DF": "DDLS",
        "TABL/DT": "TABL",
        "VIEW/DV": "VIEW",
        "DTEL/DE": "DTEL",
        "SRVD/SVD": "SRVD",
        "BDEF/BDO": "BDEF",
        "SRVB/SVB": "SRVB",
        "MSAG/MN": "MSAG",
    }
    return type_map.get(t, t.split("/")[0] if "/" in t else t)
