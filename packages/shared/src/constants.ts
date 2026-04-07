// SAP operation codes (single-character, matches VSP safety system)
export const OPERATION_CODES = {
  READ: "R",
  SEARCH: "S",
  QUERY: "Q",
  FREE_SQL: "F",
  CREATE: "C",
  UPDATE: "U",
  DELETE: "D",
  ACTIVATE: "A",
  TEST: "T",
  LOCK: "L",
  INTELLIGENCE: "I",
  WORKFLOW: "W",
  TRANSPORT: "X",
  DEBUG: "B",
  INSTALL: "N",
} as const;

export const WRITE_OPS = new Set(["C", "U", "D", "A", "L", "W", "F"]);

// Tool category metadata for UI rendering
export const TOOL_CATEGORIES = {
  read: { label: "Read", icon: "BookOpen", color: "#60a5fa" },
  search: { label: "Search", icon: "Search", color: "#a78bfa" },
  crud: { label: "Edit", icon: "Pencil", color: "#f59e0b" },
  system: { label: "System", icon: "Server", color: "#6b7280" },
  devtools: { label: "Dev Tools", icon: "Wrench", color: "#10b981" },
  transport: { label: "Transport", icon: "Truck", color: "#f97316" },
  diagnostics: { label: "Diagnostics", icon: "Activity", color: "#ef4444" },
  codeintel: { label: "Code Intel", icon: "Lightbulb", color: "#eab308" },
  analysis: { label: "Analysis", icon: "GitBranch", color: "#8b5cf6" },
  debug: { label: "Debug", icon: "Bug", color: "#dc2626" },
  report: { label: "Reports", icon: "FileText", color: "#0ea5e9" },
  git: { label: "Git", icon: "GitCommit", color: "#f97316" },
  ui5: { label: "UI5/BSP", icon: "Globe", color: "#06b6d4" },
  amdp: { label: "AMDP", icon: "Database", color: "#7c3aed" },
  install: { label: "Install", icon: "Download", color: "#22c55e" },
} as const;

// Map tool names to their categories (for UI rendering decisions)
export const TOOL_TO_CATEGORY: Record<string, string> = {
  // Read
  GetSource: "read", GetClassInclude: "read", GetClassInfo: "read",
  GetPackage: "read", GetTable: "read", GetTableContents: "read",
  RunQuery: "read", GetFunctionGroup: "read", GetMessages: "read",
  GetCDSDependencies: "read", GetProgram: "read", GetClass: "read",
  GetInterface: "read", GetFunction: "read", GetInclude: "read",
  GetStructure: "read", GetTransaction: "read", GetTypeInfo: "read",
  // Search
  SearchObject: "search", GrepObject: "search", GrepPackage: "search",
  // CRUD
  LockObject: "crud", UnlockObject: "crud", CreateObject: "crud",
  CreatePackage: "crud", CreateTable: "crud", DeleteObject: "crud",
  WriteSource: "crud", EditSource: "crud", CompareSource: "crud",
  CloneObject: "crud",
  // System
  GetConnectionInfo: "system", GetFeatures: "system", GetAbapHelp: "system",
  GetSystemInfo: "system", GetInstalledComponents: "system", GetServiceBinding: "system",
  // DevTools
  SyntaxCheck: "devtools", Activate: "devtools", ActivateList: "devtools",
  ActivatePackage: "devtools", GetInactiveObjects: "devtools",
  RunUnitTests: "devtools", RunATCCheck: "devtools", GetATCCustomizing: "devtools",
  PrettyPrint: "devtools", GetPrettyPrinterSettings: "devtools",
  SetPrettyPrinterSettings: "devtools",
  // Transport
  ListTransports: "transport", GetTransport: "transport",
  CreateTransport: "transport", ReleaseTransport: "transport",
  DeleteTransport: "transport", AddToTransport: "transport",
  // Diagnostics
  ListDumps: "diagnostics", GetDump: "diagnostics", ListTraces: "diagnostics",
  GetTrace: "diagnostics", GetTraceAnalysis: "diagnostics",
  GetSQLTraceState: "diagnostics", SetSQLTraceState: "diagnostics",
  ListSQLTraces: "diagnostics",
  // CodeIntel
  FindDefinition: "codeintel", FindReferences: "codeintel",
  CodeCompletion: "codeintel", GetTypeHierarchy: "codeintel",
  GetClassComponents: "codeintel", GetUsageLocations: "codeintel",
  // Analysis
  GetCallGraph: "analysis", GetObjectStructure: "analysis",
  GetCallersOf: "analysis", GetCalleesOf: "analysis",
  AnalyzeCallGraph: "analysis", GetObjectExplorer: "analysis",
  // Debug
  SetBreakpoint: "debug", GetBreakpoints: "debug", DeleteBreakpoint: "debug",
  DeleteAllBreakpoints: "debug", DebuggerListen: "debug",
  DebuggerStep: "debug", DebuggerGetStack: "debug",
  DebuggerGetVariables: "debug", DebuggerSetVariable: "debug",
  DebuggerGetSource: "debug", DebuggerDetach: "debug",
  // Report
  RunReport: "report", RunReportAsync: "report", GetAsyncResult: "report",
  GetVariants: "report", GetReportOutput: "report", RFCCall: "report",
  // Git
  GitListRepos: "git", GitGetRepo: "git", GitExport: "git",
  GitPull: "git", GitStage: "git", GitPush: "git", GitLink: "git",
  // UI5
  UI5ListApps: "ui5", UI5GetApp: "ui5", UI5GetFileContent: "ui5",
  UI5UploadFile: "ui5", UI5DeleteFile: "ui5", UI5CreateApp: "ui5",
  // AMDP
  AMDPGetProcedures: "amdp", AMDPGetSource: "amdp",
  AMDPDebuggerStart: "amdp", AMDPDebuggerResume: "amdp",
  AMDPDebuggerStep: "amdp", AMDPDebuggerGetVariables: "amdp",
  AMDPDebuggerStop: "amdp", AMDPSetBreakpoint: "amdp",
  // Install
  InstallZADTVSP: "install", InstallAbapGit: "install",
  ListDependencies: "install", GetServerVersion: "install",
};

// Default safety config for new systems
export const DEFAULT_SAFETY_CONFIG = {
  readOnly: false,
  blockFreeSql: false,
  allowedOps: "RSQI", // read-only by default
  disallowedOps: "",
  allowedPackages: [],
  allowTransportableEdits: false,
};

// Default feature config  
export const DEFAULT_FEATURE_CONFIG = {
  abapgit: "auto" as const,
  rap: "auto" as const,
  amdp: "auto" as const,
  ui5: "auto" as const,
  transport: "auto" as const,
};

// System colors palette
export const SYSTEM_COLORS = [
  "#3b82f6", // blue
  "#10b981", // emerald
  "#f59e0b", // amber
  "#ef4444", // red
  "#8b5cf6", // violet
  "#06b6d4", // cyan
  "#ec4899", // pink
  "#f97316", // orange
];
