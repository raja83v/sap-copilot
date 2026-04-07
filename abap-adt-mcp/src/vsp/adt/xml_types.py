"""XML types and parsing for SAP ADT responses.

All ADT API responses are XML. Each dataclass here has a `from_xml()` class method
for parsing and optionally a `to_xml()` method for building request bodies.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from xml.etree import ElementTree as ET

# ADT XML namespaces
NS = {
    "adtcore": "http://www.sap.com/adt/core",
    "atom": "http://www.w3.org/2005/Atom",
    "program": "http://www.sap.com/adt/programs/programs",
    "class": "http://www.sap.com/adt/oo/classes",
    "interface": "http://www.sap.com/adt/oo/interfaces",
    "function": "http://www.sap.com/adt/functions",
    "search": "http://www.sap.com/adt/repository/search",
    "package": "http://www.sap.com/adt/packages",
    "check": "http://www.sap.com/adt/checkruns",
    "unit": "http://www.sap.com/adt/abapunit",
    "activation": "http://www.sap.com/adt/activation",
    "atc": "http://www.sap.com/adt/atc",
    "nav": "http://www.sap.com/adt/navigation",
    "codecompletion": "http://www.sap.com/adt/codecompletion",
    "cts": "http://www.sap.com/adt/cts",
    "node": "http://www.sap.com/adt/repository/nodestructure",
    "msg": "http://www.sap.com/adt/messageclass",
    "component": "http://www.sap.com/adt/system/components",
    "srvb": "http://www.sap.com/adt/ddic/srvb",
    "bdef": "http://www.sap.com/adt/bo/behaviordefinitions",
    "cds": "http://www.sap.com/adt/ddic/ddl",
}


def _register_namespaces() -> None:
    """Register all known namespaces so serialization uses proper prefixes."""
    for prefix, uri in NS.items():
        ET.register_namespace(prefix, uri)


_register_namespaces()


def _text(elem: Optional[ET.Element], xpath: str, namespaces: Optional[dict[str, str]] = None) -> str:
    """Extract text from an optional sub-element."""
    if elem is None:
        return ""
    child = elem.find(xpath, namespaces or NS)
    return (child.text or "").strip() if child is not None else ""


def _attr(elem: Optional[ET.Element], attr: str, ns: str = "adtcore") -> str:
    """Extract an attribute with namespace prefix."""
    if elem is None:
        return ""
    ns_uri = NS.get(ns, "")
    return elem.get(f"{{{ns_uri}}}{attr}", "") if ns_uri else elem.get(attr, "")


def _attr_plain(elem: Optional[ET.Element], attr: str) -> str:
    """Extract a plain (non-namespaced) attribute."""
    if elem is None:
        return ""
    return elem.get(attr, "")


# =============================================================================
# Search
# =============================================================================


@dataclass
class SearchResult:
    """A single object from a search result."""
    name: str = ""
    type: str = ""
    uri: str = ""
    description: str = ""
    package_name: str = ""

    @classmethod
    def from_element(cls, elem: ET.Element) -> SearchResult:
        return cls(
            name=_attr(elem, "name"),
            type=_attr(elem, "type"),
            uri=_attr_plain(elem, "uri") or _attr(elem, "uri"),
            description=_attr(elem, "description"),
            package_name=_attr(elem, "packageName"),
        )

    @classmethod
    def parse_list(cls, xml_text: str) -> list[SearchResult]:
        """Parse a search results XML response."""
        if not xml_text.strip():
            return []
        root = ET.fromstring(xml_text)
        results = []
        # objectReferences format
        for elem in root.iter():
            name = _attr(elem, "name")
            if name:
                results.append(cls.from_element(elem))
        return results


# =============================================================================
# Package
# =============================================================================


@dataclass
class PackageObject:
    """An object within a package."""
    type: str = ""
    name: str = ""
    uri: str = ""
    description: str = ""
    tech_type: str = ""


@dataclass
class PackageContent:
    """Contents of an ABAP package."""
    name: str = ""
    objects: list[PackageObject] = field(default_factory=list)
    sub_packages: list[str] = field(default_factory=list)

    @classmethod
    def from_xml(cls, xml_text: str, package_name: str = "") -> PackageContent:
        """Parse package node structure response."""
        if not xml_text.strip():
            return cls(name=package_name)

        root = ET.fromstring(xml_text)
        content = cls(name=package_name)

        # Parse object nodes
        for node in root.iter("{http://www.sap.com/adt/repository/nodestructure}objectNode"):
            obj = PackageObject(
                type=node.get("OBJECT_TYPE", ""),
                name=node.get("OBJECT_NAME", ""),
                uri=node.get("OBJECT_URI", ""),
                description=node.get("DESCRIPTION", ""),
                tech_type=node.get("TECH_TYPE", ""),
            )
            content.objects.append(obj)

        # Parse sub-package nodes
        for node in root.iter("{http://www.sap.com/adt/repository/nodestructure}categoryNode"):
            cat = node.get("CATEGORY", "")
            if cat == "package":
                for sub in node.iter("{http://www.sap.com/adt/repository/nodestructure}objectNode"):
                    content.sub_packages.append(sub.get("OBJECT_NAME", ""))

        return content


# =============================================================================
# Function Group
# =============================================================================


@dataclass
class FunctionModule:
    """A function module within a function group."""
    name: str = ""
    uri: str = ""
    description: str = ""


@dataclass
class FunctionGroup:
    """A function group with its modules."""
    name: str = ""
    description: str = ""
    modules: list[FunctionModule] = field(default_factory=list)

    @classmethod
    def from_xml(cls, xml_text: str) -> FunctionGroup:
        if not xml_text.strip():
            return cls()
        root = ET.fromstring(xml_text)
        fg = cls(
            name=_attr(root, "name"),
            description=_attr(root, "description"),
        )
        for child in root.iter():
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "fmodule":
                fm = FunctionModule(
                    name=_attr(child, "name"),
                    uri=_attr_plain(child, "uri") or _attr(child, "uri"),
                    description=_attr(child, "description"),
                )
                fg.modules.append(fm)
        return fg


# =============================================================================
# Table / Data preview
# =============================================================================


@dataclass
class TableColumn:
    """Column metadata for table data preview."""
    name: str = ""
    type: str = ""
    description: str = ""
    length: int = 0
    is_key: bool = False


@dataclass
class TableContentsResult:
    """Result from table data preview."""
    columns: list[TableColumn] = field(default_factory=list)
    rows: list[dict[str, str]] = field(default_factory=list)
    total_rows: int = 0

    @classmethod
    def from_xml(cls, xml_text: str) -> TableContentsResult:
        """Parse ADT data preview response.

        The response uses a column-oriented layout:
          <dataPreview:columns>
            <dataPreview:metadata name="COL1" .../>
            <dataPreview:dataSet>
              <dataPreview:data>val1</dataPreview:data>
              ...
            </dataPreview:dataSet>
          </dataPreview:columns>
        """
        result = cls()
        if not xml_text.strip():
            return result

        NS = "http://www.sap.com/adt/dataPreview"
        root = ET.fromstring(xml_text)

        # Total rows
        total_elem = root.find(f"{{{NS}}}totalRows")
        if total_elem is not None and total_elem.text:
            try:
                result.total_rows = int(total_elem.text)
            except ValueError:
                pass

        # Parse column-oriented structure
        col_data: list[list[str]] = []
        for col_elem in root.iter(f"{{{NS}}}columns"):
            meta = col_elem.find(f"{{{NS}}}metadata")
            if meta is not None:
                col = TableColumn(
                    name=meta.get(f"{{{NS}}}name", meta.get("name", "")),
                    description=meta.get(f"{{{NS}}}description", meta.get("description", "")),
                    type=meta.get(f"{{{NS}}}type", meta.get("type", "")),
                    is_key=meta.get(f"{{{NS}}}keyAttribute", meta.get("keyAttribute", "false")).lower() == "true",
                )
                result.columns.append(col)

            dataset = col_elem.find(f"{{{NS}}}dataSet")
            values: list[str] = []
            if dataset is not None:
                for data_elem in dataset.findall(f"{{{NS}}}data"):
                    values.append(data_elem.text or "")
            col_data.append(values)

        # Transpose columns into rows
        if col_data:
            num_rows = max(len(vals) for vals in col_data) if col_data else 0
            col_names = [c.name for c in result.columns]
            for i in range(num_rows):
                row: dict[str, str] = {}
                for j, name in enumerate(col_names):
                    row[name] = col_data[j][i] if i < len(col_data[j]) else ""
                result.rows.append(row)

        return result


# =============================================================================
# Service Binding
# =============================================================================


@dataclass
class ServiceBinding:
    """SAP service binding metadata."""
    name: str = ""
    type: str = ""
    description: str = ""
    published: bool = False
    binding_type: str = ""
    binding_version: str = ""
    service_url: str = ""
    service_def_name: str = ""

    @classmethod
    def from_xml(cls, xml_text: str) -> ServiceBinding:
        if not xml_text.strip():
            return cls()
        root = ET.fromstring(xml_text)
        return cls(
            name=_attr(root, "name"),
            type=_attr(root, "type"),
            description=_attr(root, "description"),
            published=root.get("published", "false").lower() == "true",
            binding_type=root.get("bindingType", ""),
            binding_version=root.get("bindingVersion", ""),
            service_url=root.get("serviceUrl", ""),
            service_def_name=root.get("serviceDefinitionName", ""),
        )


# =============================================================================
# System Info
# =============================================================================


@dataclass
class SystemInfo:
    """SAP system information (parsed from /sap/bc/adt/system/information Atom Feed)."""
    node_name: str = ""          # NodeName — app server hostname
    app_server: str = ""         # ApplicationServerName
    kernel_release: str = ""     # KernelRelease
    database_release: str = ""   # DBRelease
    database_system: str = ""    # DBSystem
    database_name: str = ""      # DBName
    os_name: str = ""            # OSName
    os_version: str = ""         # OSVersion
    machine_type: str = ""       # MachineType
    install_number: str = ""     # SAPSystemNumber
    ip_address: str = ""         # IPAddress

    @classmethod
    def from_xml(cls, xml_text: str) -> SystemInfo:
        if not xml_text.strip():
            return cls()
        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries: dict[str, str] = {}
        for entry in root.findall("atom:entry", ns):
            eid = entry.findtext("atom:id", default="", namespaces=ns) or ""
            etitle = entry.findtext("atom:title", default="", namespaces=ns) or ""
            entries[eid] = etitle
        return cls(
            node_name=entries.get("NodeName", ""),
            app_server=entries.get("ApplicationServerName", ""),
            kernel_release=entries.get("KernelRelease", ""),
            database_release=entries.get("DBRelease", ""),
            database_system=entries.get("DBSystem", ""),
            database_name=entries.get("DBName", ""),
            os_name=entries.get("OSName", ""),
            os_version=entries.get("OSVersion", ""),
            machine_type=entries.get("MachineType", ""),
            install_number=entries.get("SAPSystemNumber", ""),
            ip_address=entries.get("IPAddress", ""),
        )


@dataclass
class InstalledComponent:
    """An installed SAP component."""
    name: str = ""
    release: str = ""
    support_pack: str = ""
    description: str = ""

    @classmethod
    def parse_list(cls, xml_text: str) -> list[InstalledComponent]:
        if not xml_text.strip():
            return []
        root = ET.fromstring(xml_text)
        components = []
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "component":
                comp = cls(
                    name=elem.get("name", "") or _text(elem, "name"),
                    release=elem.get("release", "") or _text(elem, "release"),
                    support_pack=elem.get("supportPack", "") or _text(elem, "supportPack"),
                    description=elem.get("description", "") or _text(elem, "description"),
                )
                components.append(comp)
        return components


# =============================================================================
# Message Class
# =============================================================================


@dataclass
class MessageClassMessage:
    """A single message in a message class."""
    number: str = ""
    text: str = ""


@dataclass
class MessageClass:
    """An ABAP message class."""
    name: str = ""
    description: str = ""
    messages: list[MessageClassMessage] = field(default_factory=list)

    @classmethod
    def from_xml(cls, xml_text: str) -> MessageClass:
        if not xml_text.strip():
            return cls()
        root = ET.fromstring(xml_text)
        mc = cls(
            name=_attr(root, "name"),
            description=_attr(root, "description"),
        )
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "message":
                msg = MessageClassMessage(
                    number=elem.get("msgNumber", "") or elem.get("number", ""),
                    text=elem.get("msgText", "") or elem.text or "",
                )
                mc.messages.append(msg)
        return mc


# =============================================================================
# Transaction
# =============================================================================


@dataclass
class Transaction:
    """SAP transaction code info."""
    name: str = ""
    description: str = ""
    program: str = ""

    @classmethod
    def from_xml(cls, xml_text: str) -> Transaction:
        if not xml_text.strip():
            return cls()
        root = ET.fromstring(xml_text)
        return cls(
            name=_attr(root, "name"),
            description=_attr(root, "description"),
            program=_text(root, ".//program") or root.get("program", ""),
        )


# =============================================================================
# Type Info
# =============================================================================


@dataclass
class TypeInfo:
    """ABAP type information."""
    name: str = ""
    type: str = ""
    description: str = ""
    length: int = 0
    decimals: int = 0

    @classmethod
    def from_xml(cls, xml_text: str) -> TypeInfo:
        if not xml_text.strip():
            return cls()
        root = ET.fromstring(xml_text)
        ti = cls(
            name=_attr(root, "name"),
            type=_attr(root, "type"),
            description=_attr(root, "description"),
        )
        try:
            ti.length = int(root.get("length", "0"))
        except ValueError:
            pass
        try:
            ti.decimals = int(root.get("decimals", "0"))
        except ValueError:
            pass
        return ti


# =============================================================================
# Method Info (for method-level source operations)
# =============================================================================


@dataclass
class MethodInfo:
    """Method boundary information within a class source."""
    name: str = ""
    implementation_start: int = 0
    implementation_end: int = 0

    @classmethod
    def parse_object_structure(cls, xml_text: str) -> list[MethodInfo]:
        """Parse class objectstructure to extract method boundaries."""
        methods: list[MethodInfo] = []
        if not xml_text.strip():
            return methods

        root = ET.fromstring(xml_text)
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag in ("method", "classMethod"):
                name = _attr(elem, "name") or elem.get("name", "")
                start = 0
                end = 0
                # Look for source range
                for child in elem.iter():
                    child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    if child_tag == "implementationStart":
                        try:
                            start = int(child.get("line", "0") or child.text or "0")
                        except ValueError:
                            pass
                    elif child_tag == "implementationEnd":
                        try:
                            end = int(child.get("line", "0") or child.text or "0")
                        except ValueError:
                            pass
                if name:
                    methods.append(cls(name=name, implementation_start=start, implementation_end=end))
        return methods


# =============================================================================
# Syntax Check / Activation
# =============================================================================


@dataclass
class CheckMessage:
    """A message from syntax check or ATC."""
    uri: str = ""
    type: str = ""  # E, W, I
    line: int = 0
    offset: int = 0
    text: str = ""

    @classmethod
    def parse_list(cls, xml_text: str) -> list[CheckMessage]:
        """Parse check run or activation results."""
        messages: list[CheckMessage] = []
        if not xml_text.strip():
            return messages

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return messages

        def _attr(elem: ET.Element, *names: str) -> str:
            """Get attribute value by local name, stripping any namespace prefix."""
            # Build a lookup from localname -> value for all attributes
            local_attrs: dict[str, str] = {}
            for k, v in elem.attrib.items():
                local_key = k.split("}")[-1] if "}" in k else k
                local_attrs.setdefault(local_key, v)
            for name in names:
                if name in local_attrs:
                    return local_attrs[name]
            return ""

        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag in ("checkMessage", "message", "msg", "finding", "alert"):
                # Try to get shortText from child element (ADT inactive-objects format)
                short_text = ""
                for child in elem:
                    child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    if child_tag in ("shortText", "text"):
                        # shortText may contain nested <txt> elements
                        txt_parts = []
                        for sub in child:
                            sub_tag = sub.tag.split("}")[-1] if "}" in sub.tag else sub.tag
                            if sub_tag == "txt" and sub.text:
                                txt_parts.append(sub.text.strip())
                        if txt_parts:
                            short_text = "; ".join(txt_parts)
                        elif child.text:
                            short_text = child.text.strip()
                        break

                msg = cls(
                    uri=_attr(elem, "uri"),
                    type=_attr(elem, "type", "severity"),
                    text=_attr(elem, "shortText", "text") or short_text or _get_text_content(elem),
                )
                try:
                    msg.line = int(_attr(elem, "line") or "0")
                except ValueError:
                    pass
                try:
                    msg.offset = int(_attr(elem, "offset", "column") or "0")
                except ValueError:
                    pass
                messages.append(msg)
        return messages


# =============================================================================
# Unit Test Results
# =============================================================================


@dataclass
class UnitTestAlert:
    """An alert (failure/error) from a unit test."""
    kind: str = ""
    severity: str = ""
    title: str = ""
    details: str = ""
    expected: str = ""
    actual: str = ""
    stack: str = ""


@dataclass
class UnitTestMethod:
    """A unit test method result."""
    name: str = ""
    uri: str = ""
    execution_time: str = ""
    alerts: list[UnitTestAlert] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.alerts) == 0


@dataclass
class UnitTestClass:
    """A unit test class result."""
    name: str = ""
    uri: str = ""
    methods: list[UnitTestMethod] = field(default_factory=list)


@dataclass
class UnitTestResult:
    """Complete unit test run result."""
    classes: list[UnitTestClass] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(len(c.methods) for c in self.classes)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.classes for m in c.methods if m.passed)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    @classmethod
    def from_xml(cls, xml_text: str) -> UnitTestResult:
        """Parse unit test run results."""
        result = cls()
        if not xml_text.strip():
            return result

        root = ET.fromstring(xml_text)

        for class_elem in root.iter():
            class_tag = class_elem.tag.split("}")[-1] if "}" in class_elem.tag else class_elem.tag
            if class_tag != "testClass":
                continue

            tc = UnitTestClass(
                name=_attr(class_elem, "name") or class_elem.get("name", ""),
                uri=_attr(class_elem, "uri") or class_elem.get("uri", ""),
            )

            for method_elem in class_elem:
                method_tag = method_elem.tag.split("}")[-1] if "}" in method_elem.tag else method_elem.tag
                if method_tag != "testMethod":
                    continue

                tm = UnitTestMethod(
                    name=_attr(method_elem, "name") or method_elem.get("name", ""),
                    uri=_attr(method_elem, "uri") or method_elem.get("uri", ""),
                    execution_time=method_elem.get("executionTime", ""),
                )

                for alert_elem in method_elem:
                    alert_tag = alert_elem.tag.split("}")[-1] if "}" in alert_elem.tag else alert_elem.tag
                    if alert_tag != "alert":
                        continue

                    alert = UnitTestAlert(
                        kind=alert_elem.get("kind", ""),
                        severity=alert_elem.get("severity", ""),
                        title=_text(alert_elem, ".//title") or alert_elem.get("title", ""),
                        details=_text(alert_elem, ".//details"),
                        expected=_text(alert_elem, ".//expected") or _text(alert_elem, ".//expectedValue"),
                        actual=_text(alert_elem, ".//actual") or _text(alert_elem, ".//actualValue"),
                        stack=_text(alert_elem, ".//stack") or _text(alert_elem, ".//stackTrace"),
                    )
                    tm.alerts.append(alert)

                tc.methods.append(tm)

            result.classes.append(tc)

        return result


# =============================================================================
# Runtime Error (Dump)
# =============================================================================


@dataclass
class StackFrame:
    """A stack frame from a runtime dump."""
    program: str = ""
    include: str = ""
    line: int = 0
    event: str = ""


@dataclass
class DumpVariable:
    """A variable captured in a runtime dump."""
    name: str = ""
    value: str = ""
    type: str = ""


@dataclass
class RuntimeDump:
    """Summary of a runtime error (short dump)."""
    id: str = ""
    title: str = ""
    category: str = ""
    exception_type: str = ""
    program: str = ""
    include: str = ""
    line: int = 0
    user: str = ""
    client: str = ""
    host: str = ""
    timestamp: str = ""
    uri: str = ""


@dataclass
class DumpDetails(RuntimeDump):
    """Full details of a runtime dump including source and variables."""
    stack_trace: list[StackFrame] = field(default_factory=list)
    variables: list[DumpVariable] = field(default_factory=list)
    source_code: str = ""
    error_details: str = ""
    raw_html: str = ""

    @classmethod
    def from_html(cls, html_text: str, dump_id: str = "") -> DumpDetails:
        """Parse dump details from HTML response (ST22-style)."""
        details = cls(id=dump_id, raw_html=html_text)
        # Extract key fields from HTML
        details.error_details = _extract_html_section(html_text, "Error analysis")
        details.source_code = _extract_html_section(html_text, "Source Code Extract")
        return details


@dataclass
class RuntimeDumpList:
    """List of runtime dumps."""
    dumps: list[RuntimeDump] = field(default_factory=list)

    @classmethod
    def from_xml(cls, xml_text: str) -> RuntimeDumpList:
        result = cls()
        if not xml_text.strip():
            return result
        root = ET.fromstring(xml_text)
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "dump":
                dump = RuntimeDump(
                    id=elem.get("id", ""),
                    title=elem.get("title", ""),
                    category=elem.get("category", ""),
                    exception_type=elem.get("exceptionType", ""),
                    program=elem.get("program", ""),
                    include=elem.get("include", ""),
                    user=elem.get("user", ""),
                    client=elem.get("client", ""),
                    host=elem.get("host", ""),
                    timestamp=elem.get("timestamp", ""),
                    uri=elem.get("uri", ""),
                )
                try:
                    dump.line = int(elem.get("line", "0"))
                except ValueError:
                    pass
                result.dumps.append(dump)
        return result


# =============================================================================
# ABAP Traces
# =============================================================================


@dataclass
class ABAPTrace:
    """An ABAP trace entry."""
    id: str = ""
    title: str = ""
    description: str = ""
    user: str = ""
    start_time: str = ""
    end_time: str = ""
    duration: str = ""
    process_type: str = ""
    object_type: str = ""
    status: str = ""
    uri: str = ""


@dataclass
class TraceEntry:
    """An entry within a trace analysis."""
    program: str = ""
    event: str = ""
    line: int = 0
    gross_time: float = 0.0
    net_time: float = 0.0
    calls: int = 0
    percentage: float = 0.0
    statement: str = ""
    table_name: str = ""
    operation: str = ""
    record_count: int = 0


@dataclass
class TraceAnalysis:
    """Analysis of an ABAP trace."""
    trace_id: str = ""
    tool_type: str = ""
    total_time: float = 0.0
    total_calls: int = 0
    entries: list[TraceEntry] = field(default_factory=list)
    summary: str = ""

    @classmethod
    def from_xml(cls, xml_text: str) -> TraceAnalysis:
        if not xml_text.strip():
            return cls()
        # Parse trace analysis XML response
        root = ET.fromstring(xml_text)
        analysis = cls()
        # Implementation depends on specific XML structure from SAP
        return analysis


@dataclass
class SQLTraceState:
    """SQL trace (ST05) state."""
    active: bool = False
    user: str = ""
    trace_type: str = ""
    start_time: str = ""
    max_records: int = 0
    trace_file: str = ""

    @classmethod
    def from_xml(cls, xml_text: str) -> SQLTraceState:
        if not xml_text.strip():
            return cls()
        root = ET.fromstring(xml_text)
        return cls(
            active=root.get("active", "false").lower() == "true",
            user=root.get("user", ""),
            trace_type=root.get("traceType", ""),
            start_time=root.get("startTime", ""),
        )


@dataclass
class SQLTraceEntry:
    """An entry in the SQL trace directory."""
    id: str = ""
    user: str = ""
    start_time: str = ""
    end_time: str = ""
    trace_type: str = ""
    record_count: int = 0
    size: int = 0
    uri: str = ""


# =============================================================================
# Call Graph / Code Analysis
# =============================================================================


@dataclass
class CallGraphNode:
    """A node in the call graph."""
    uri: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    line: int = 0
    column: int = 0
    children: list[CallGraphNode] = field(default_factory=list)


@dataclass
class CallGraphEdge:
    """An edge in the call graph."""
    caller_uri: str = ""
    caller_name: str = ""
    callee_uri: str = ""
    callee_name: str = ""
    line: int = 0


@dataclass
class CallGraphStats:
    """Statistics for a call graph analysis."""
    total_nodes: int = 0
    total_edges: int = 0
    max_depth: int = 0
    nodes_by_type: dict[str, int] = field(default_factory=dict)
    unique_nodes: int = 0


@dataclass
class ObjectExplorerNode:
    """A node in the object explorer tree."""
    uri: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    children: list[ObjectExplorerNode] = field(default_factory=list)


# =============================================================================
# Transport
# =============================================================================


@dataclass
class TransportTask:
    """A task within a transport request."""
    id: str = ""
    owner: str = ""
    description: str = ""
    status: str = ""


@dataclass
class TransportRequest:
    """A CTS transport request."""
    id: str = ""
    owner: str = ""
    description: str = ""
    status: str = ""
    target: str = ""
    type: str = ""
    tasks: list[TransportTask] = field(default_factory=list)

    @classmethod
    def from_xml(cls, xml_text: str) -> TransportRequest:
        if not xml_text.strip():
            return cls()
        root = ET.fromstring(xml_text)
        tr = cls(
            id=_attr(root, "name") or root.get("trkorr", ""),
            owner=root.get("owner", ""),
            description=root.get("description", "") or _attr(root, "description"),
            status=root.get("status", ""),
            target=root.get("target", ""),
            type=root.get("type", ""),
        )
        return tr

    @classmethod
    def parse_list(cls, xml_text: str) -> list[TransportRequest]:
        if not xml_text.strip():
            return []
        root = ET.fromstring(xml_text)
        transports = []
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag in ("transport", "request"):
                tr = cls(
                    id=elem.get("trkorr", "") or _attr(elem, "name"),
                    owner=elem.get("owner", ""),
                    description=elem.get("description", "") or _attr(elem, "description"),
                    status=elem.get("status", ""),
                    target=elem.get("target", ""),
                    type=elem.get("type", ""),
                )
                transports.append(tr)
        return transports


# =============================================================================
# ATC (ABAP Test Cockpit)
# =============================================================================


@dataclass
class ATCFinding:
    """An ATC finding."""
    uri: str = ""
    location: str = ""
    priority: int = 0
    check_id: str = ""
    check_title: str = ""
    message_title: str = ""
    exemption: str = ""

    @classmethod
    def parse_list(cls, xml_text: str) -> list[ATCFinding]:
        findings: list[ATCFinding] = []
        if not xml_text.strip():
            return findings
        root = ET.fromstring(xml_text)
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "finding":
                finding = cls(
                    uri=elem.get("uri", ""),
                    location=elem.get("location", ""),
                    check_id=elem.get("checkId", ""),
                    check_title=elem.get("checkTitle", ""),
                    message_title=elem.get("messageTitle", ""),
                    exemption=elem.get("exemption", ""),
                )
                try:
                    finding.priority = int(elem.get("priority", "0"))
                except ValueError:
                    pass
                findings.append(finding)
        return findings


# =============================================================================
# XML builders for request bodies
# =============================================================================


def build_activation_xml(objects: list[tuple[str, str, str]]) -> str:
    """Build activation request XML.

    Args:
        objects: List of (uri, adtcore_type, name) tuples.
                 adtcore_type is the ADT sub-type, e.g. "PROG/P", "CLAS/OC".
    """
    entries = ""
    for uri, adt_type, name in objects:
        entries += (
            f'<adtcore:objectReference adtcore:uri="{uri}"'
            f' adtcore:type="{adt_type}" adtcore:name="{name}"/>\n'
        )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<adtcore:objectReferences xmlns:adtcore="http://www.sap.com/adt/core">
{entries}</adtcore:objectReferences>"""


def build_syntax_check_xml(uri: str, source: str = "") -> str:
    """Build syntax check request XML."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<chkrun:checkObjectList xmlns:adtcore="http://www.sap.com/adt/core" xmlns:chkrun="http://www.sap.com/adt/checkrun">
  <chkrun:checkObject adtcore:uri="{uri}" chkrun:version="inactive"/>
</chkrun:checkObjectList>"""


def build_unit_test_xml(uri: str) -> str:
    """Build unit test run request XML."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<aunit:runConfiguration xmlns:aunit="http://www.sap.com/adt/aunit">
  <external>
    <coverage active="false"/>
  </external>
  <options>
    <uriType value="semantic"/>
    <testDetermStrat sameProgram="true" assignedTests="false" publicApi="false"/>
    <riskLevel harmless="true" dangerous="true" critical="true"/>
    <duration short="true" medium="true" long="true"/>
  </options>
  <adtcore:objectSets xmlns:adtcore="http://www.sap.com/adt/core">
    <objectSet kind="inclusive">
      <adtcore:objectReferences>
        <adtcore:objectReference adtcore:uri="{uri}"/>
      </adtcore:objectReferences>
    </objectSet>
  </adtcore:objectSets>
</aunit:runConfiguration>"""


def build_create_object_xml(
    obj_type: str,
    name: str,
    description: str,
    package: str,
    transport: str = "",
    **kwargs: str,
) -> str:
    """Build object creation request XML.

    Uses proper namespace-qualified element names as required by the ADT API
    for each object type.
    """
    # Mapping: obj_type -> (ns_prefix, ns_uri, element_name, adt_type_code)
    _TYPE_META: dict[str, tuple[str, str, str, str]] = {
        "PROG": ("programs", "http://www.sap.com/adt/programs/programs", "abapProgram",       "PROG/P"),
        "CLAS": ("class",    "http://www.sap.com/adt/oo/classes",       "abapClass",          "CLAS/OC"),
        "INTF": ("interface","http://www.sap.com/adt/oo/interfaces",    "abapInterface",      "INTF/OI"),
        "FUGR": ("functions","http://www.sap.com/adt/functions",        "group",              "FUGR/F"),
        "DEVC": ("pak",      "http://www.sap.com/adt/packages",         "package",            "DEVC/K"),
        "TABL": ("blue",     "http://www.sap.com/wbobj/blue",           "blueSource",         "TABL/DT"),
        "DDLS": ("ddl",      "http://www.sap.com/adt/ddic/ddlsources",  "ddlSource",          "DDLS/DF"),
        "DDLX": ("ddlx",     "http://www.sap.com/adt/ddic/ddlxsources", "ddlxSource",         "DDLX/EX"),
        "SRVD": ("srvd",     "http://www.sap.com/adt/ddic/srvdsources", "srvdSource",         "SRVD/SRV"),
        "BDEF": ("bdef",     "http://www.sap.com/adt/bo/behaviordefinitions", "behaviordefinition", "BDEF/BDL"),
        "SRVB": ("srvb",     "http://www.sap.com/adt/ddic/ServiceBindings", "serviceBinding", "SRVB/SVB"),
    }

    # Extra attributes needed on root element for specific object types
    _EXTRA_ATTRS: dict[str, str] = {
        "CLAS": ' class:category="1"',
        "SRVD": ' srvd:srvdSourceType="S"',
    }

    # Extra child elements needed for specific object types
    _EXTRA_ELEMENTS: dict[str, str] = {
    }

    # Build dynamic SRVB elements from kwargs
    if obj_type == "SRVB":
        srvd_name = kwargs.get("service_definition", "")
        binding_version = kwargs.get("binding_version", "V4")
        if srvd_name:
            _EXTRA_ELEMENTS["SRVB"] = (
                f'\n  <srvb:services srvb:name="{srvd_name}">'
                f'<srvb:content srvb:version="0001" srvb:releaseState="NOT_RELEASED">'
                f'<srvb:serviceDefinition adtcore:uri="/sap/bc/adt/ddic/srvd/sources/{srvd_name.lower()}"'
                f' adtcore:type="SRVD/SRV" adtcore:name="{srvd_name}"/>'
                f'</srvb:content></srvb:services>'
                f'\n  <srvb:binding srvb:type="ODATA" srvb:version="{binding_version}" srvb:category="0">'
                f'<srvb:implementation adtcore:name="{name}"/>'
                f'</srvb:binding>'
            )

    meta = _TYPE_META.get(obj_type)
    if meta:
        ns_prefix, ns_uri, element, type_code = meta
        transport_attr = f' adtcore:responsible="{transport}"' if transport else ""
        extra_attr = _EXTRA_ATTRS.get(obj_type, "")
        extra_elem = _EXTRA_ELEMENTS.get(obj_type, "")
        return (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<{ns_prefix}:{element}'
            f' xmlns:{ns_prefix}="{ns_uri}"'
            f' xmlns:adtcore="http://www.sap.com/adt/core"'
            f' adtcore:description="{description}"'
            f' adtcore:name="{name}"'
            f' adtcore:type="{type_code}"'
            f'{extra_attr}'
            f'{transport_attr}>\n'
            f'  <adtcore:packageRef adtcore:name="{package}"/>'
            f'{extra_elem}\n'
            f'</{ns_prefix}:{element}>'
        )

    # Fallback for unknown types
    transport_attr = f' adtcore:responsible="{transport}"' if transport else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<{obj_type} xmlns:adtcore="http://www.sap.com/adt/core"
    adtcore:description="{description}"
    adtcore:name="{name}"
    adtcore:type="{obj_type}"{transport_attr}>
  <adtcore:packageRef adtcore:name="{package}"/>
</{obj_type}>"""


def build_atc_run_xml(uri: str, variant: str = "DEFAULT") -> str:
    """Build ATC check run request XML."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<atc:run xmlns:atc="http://www.sap.com/adt/atc"
         xmlns:adtcore="http://www.sap.com/adt/core">
  <objectSets>
    <objectSet kind="inclusive">
      <adtcore:objectReferences>
        <adtcore:objectReference adtcore:uri="{uri}"/>
      </adtcore:objectReferences>
    </objectSet>
  </objectSets>
</atc:run>"""


# =============================================================================
# Helpers
# =============================================================================


def _get_text_content(elem: ET.Element) -> str:
    """Get all text content from an element and its children."""
    parts = []
    if elem.text:
        parts.append(elem.text.strip())
    for child in elem:
        if child.text:
            parts.append(child.text.strip())
        if child.tail:
            parts.append(child.tail.strip())
    return " ".join(parts)


def _extract_html_section(html_text: str, section_title: str) -> str:
    """Extract a section from an HTML dump page by title."""
    # Simple regex-based extraction
    pattern = rf'{re.escape(section_title)}.*?<pre>(.*?)</pre>'
    match = re.search(pattern, html_text, re.DOTALL | re.IGNORECASE)
    if match:
        return html.unescape(match.group(1).strip())
    return ""
