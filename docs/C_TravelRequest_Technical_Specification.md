# C_TravelRequest — Technical Specification

## 1. Overview

| Property | Value |
|---|---|
| **Object Name** | `C_TravelRequest` |
| **Label** | Travel Request |
| **VDM View Type** | `#CONSUMPTION` |
| **VDM Usage Type** | `#TRANSACTIONAL_PROCESSING_SERVICE` |
| **Provider Contract** | `transactional_query` |
| **Base Business Object** | `I_TravelRequest` |
| **BO Implementation Type** | Unmanaged |
| **Implementation Class (Base)** | `CL_BP_I_TRAVELREQUEST` |
| **Implementation Class (Projection)** | `CL_BP_C_TRAVELREQUEST` |
| **Package** | `ODATA_TRV_MTR_UI_MANAGE` |
| **Draft Enabled** | Yes |
| **Strict Mode** | Level 2 |
| **Extensible** | Yes (element suffix: `TRQ`, max fields: 350, max bytes: 2240) |
| **Authorization Check** | `#MANDATORY` |
| **Session Filter** | `TravelEmployeeUserIdentifier = $session.user` |

---

## 2. Architecture Layers

```
┌──────────────────────────────────────────────────────────────┐
│  Fiori UI (My Travel Requests)                               │
├──────────────────────────────────────────────────────────────┤
│  Service Binding                                             │
│  ├─ TRV_UI_SB_MTR_MANAGE      (OData V2)                    │
│  ├─ TRV_UI_SB_MTR_MANAGE_V4   (OData V4)                    │
│  ├─ TRV_UI_SB_MTR_ARRANGER_MNG (OData V2 - Arranger)        │
│  └─ TRV_UI_SB_MTR_ARRANGER_V4  (OData V4 - Arranger)        │
├──────────────────────────────────────────────────────────────┤
│  Service Definition                                          │
│  ├─ TRV_UI_SD_MTR_MANAGE         (Self-service)              │
│  └─ TRV_UI_SD_MTR_ARRANGER_MNG   (Arranger)                 │
├──────────────────────────────────────────────────────────────┤
│  Projection Layer (Consumption)                              │
│  ├─ C_TravelRequest              (BDEF + DDLS)               │
│  ├─ C_TravelAddlDestination                                  │
│  ├─ C_TravelAdvance                                          │
│  ├─ C_TravelCostAssignment                                   │
│  ├─ C_TravelEstimatedCost                                    │
│  └─ C_TravelServiceRequest                                   │
├──────────────────────────────────────────────────────────────┤
│  Base BO Layer (Interface)                                   │
│  ├─ I_TravelRequest              (Root, Unmanaged)           │
│  ├─ I_TravelAddlDestination      (Dependent)                │
│  ├─ I_TravelAdvance              (Dependent)                 │
│  ├─ I_TravelCostAssignment       (Dependent)                │
│  ├─ I_TravelEstimatedCost        (Dependent)                │
│  └─ I_TravelServiceRequest       (Dependent)                │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Entity Composition Hierarchy

```
C_TravelRequest (Root)
├── C_TravelAddlDestination      (composition child)
├── C_TravelAdvance              (composition child)
├── C_TravelCostAssignment       (composition child)
├── C_TravelEstimatedCost        (composition child)
└── C_TravelServiceRequest       (composition child)
```

---

## 4. Root Entity — C_TravelRequest

### 4.1 Key Fields

| Field | Description |
|---|---|
| `PersonnelNumber` | Employee personnel number (derived from `I_TrvlrPersNmbrByUser`) |
| `TravelTripNumber` | Unique travel trip number (representative key) |
| `TravelReqUUID` | Internal UUID (hidden in UI, managed numbering) |

### 4.2 Core Business Fields

| Field | Description |
|---|---|
| `TripDepartureDate` | Trip departure date |
| `DepartureBeginTime` | Departure time |
| `StartTimeZone` | Start time zone |
| `TripArrivalDate` | Trip return/arrival date |
| `ArrivalEndTime` | Arrival end time |
| `EndTimeZone` | End time zone |
| `TripReasonText` | Reason for travel (searchable) |
| `TripDestination` | Main destination (with predefined address & recurring destination VH) |
| `Country` | Destination country |
| `MainDestinationRegion` | Destination region (searchable) |
| `CityName` | Destination city name (with predefined & recurring city VH) |
| `StreetName` | Destination street |
| `PostalCode` | Destination postal code |
| `DistrictName` | Destination district |
| `TravelLocationCode` | Location code (with community city lookup) |
| `TravelCountryRegion` | Country/region combination |

### 4.3 Trip Classification Fields

| Field | Description |
|---|---|
| `TripTypeEnterprise` | Enterprise trip type (VH: `C_TravelTripEnterpriseTypeVH`) |
| `TripTypeStatutory` | Statutory trip type (VH: `C_TravelStatutoryTypeVH`) |
| `TripActivityType` | Activity type (VH: `C_TravelTripActivityTypeVH`) |
| `TypeOfTripActivityValue` | Activity planning value (VH: `C_TravelActivityPlanningVH`) |
| `TripSchema` | Travel schema |
| `CountryGroup` | Country group |
| `TripProvisionVariant` | Provision variant |

### 4.4 Financial Fields

| Field | Description |
|---|---|
| `EstimatedCost` | Total estimated cost |
| `EstimatedCostCrcy` | Estimated cost currency (VH: `C_TravelCurrencyVH`) |
| `PaymentCurrency` | Payment currency |
| `TrvlReqEstdCostFrmPlnAmt` | Estimated cost from plan |
| `TrvlReqEstdCostFrmReqAmt` | Estimated cost from request |

### 4.5 Status & Lifecycle Fields

| Field | Description |
|---|---|
| `TravelStatus` | Overall travel status (VH: `C_TravelRequestStatusValueHelp`) |
| `TravelStatusCriticality` | Criticality indicator for status display |
| `TrvlReqApprovalStatus` | Approval status |
| `SettlmtStatus` | Settlement status |
| `TripIsLocked` | Lock indicator |
| `TravelRequestIsExists` | Request existence flag |
| `TravelPlanIsExists` | Plan existence flag |
| `TripHasExpenses` | Expense existence flag |
| `BusTripIsApproved` | Business trip approval flag |
| `TravelVersionNumber` | Version number |

### 4.6 Organisational Fields

| Field | Description |
|---|---|
| `CompanyCode` | Company code |
| `CostCenter` | Cost center |
| `PersonnelArea` | Personnel area |
| `PersonWorkAgrmtAuthznGrpg` | Work agreement authorization grouping |
| `TrvlReqEmplGrpg` | Employee grouping |
| `TrvlReqReimbmtGrpStatry` | Reimbursement group (statutory) |
| `TrvlReqReimbmtGrpEnt` | Reimbursement group (enterprise) |

### 4.7 Virtual Elements

All virtual elements are calculated by class `CL_TRV_MTR_VIRTUAL_ELEMENT_S4` (or `CL_TRV_ATTACH_VIRTUAL_ELEMENT` for attachments). These control dynamic UI field visibility and facet visibility.

**UI Field Visibility Virtuals** (~80+ fields): Control `hidden` property of individual fields. Pattern: `TrvlReqIs<FieldName>Hidden : abap_boolean`

**Facet Visibility Virtuals:**

| Virtual Field | Purpose |
|---|---|
| `TrvlAddlDestIsFacetVisible` | Show/hide Additional Destinations tab |
| `TrvlAdvancesIsFacetVisible` | Show/hide Advances tab |
| `TrvlEstdCostIsFacetVisible` | Show/hide Estimated Cost tab |
| `TrvlCostAssgmtIsFacetVisible` | Show/hide Cost Assignment tab |
| `TravelSrvcsIsFacetVisible` | Show/hide Travel Services tab |
| `CreateTripBreakIsVisible` | Show/hide Create Trip Break button |

**Attachment Virtuals** (calculated by `CL_TRV_ATTACH_VIRTUAL_ELEMENT`):

| Virtual Field | Purpose |
|---|---|
| `TrvlReqAttachmentMode` | Attachment display mode |
| `TrvlReqAttachmentIsDraft` | Draft indicator for attachment service |
| `TrvlReqIsAttachmentURLEnabled` | Enable/disable attachment URL |
| `TrvlReqIsAttachmentHidden` | Show/hide attachment section |

### 4.8 Associations (Non-Composition)

| Association | Description |
|---|---|
| `_TravelRequestCountryText` | Country text |
| `_TravelRequestStatusText` | Status text |
| `_TravelRequestCountryRegion` | Country region text |
| `_TravelArrivalWork` | Arrival workplace |
| `_TravelDepartureWork` | Departure workplace |
| `_TravelEnterpriseVH` | Enterprise type VH |
| `_TravelTripActivityVH` | Trip activity VH |
| `_TravelStatutoryVH` | Statutory type VH |
| `_TravelEditor` | Travel editor info |
| `_TravelEmployeeContactCard` | Employee contact card |

---

## 5. Child Entities

### 5.1 C_TravelAddlDestination — Additional Travel Destinations

| Property | Value |
|---|---|
| **Label** | Additional Travel Destination |
| **Base CDS** | `I_TravelAddlDestination` |
| **Implementation Class** | `CL_BP_I_TRVLREQADDLDESTINATION` |
| **Draft Table** | `TRVS4_DEST_D` |
| **Extensible** | Yes (suffix: `ADD`) |

**Key Fields:** `PersonnelNumber`, `TravelTripNumber`, `DestinationAssignment`, `DestinationType`, `TravelReqUUID`, `SeqReqUUID`

**Core Fields:** `TripBeginsOnDate`, `TripBeginsAtTime`, `CityName`, `DistrictName`, `PostalCode`, `CityCodeName`, `StreetName`, `HouseNumber`, `Country`, `Region`, `TripTypeStatutory`, `TripTypeEnterprise`, `TypeOfTripActivityValue`, `TripActivityType`, `TripReasonText`, `TripDestination`, `TripRegion`, `AddlDestSleepAtHome`, `AddlDestDurnOfPrvtTripBreak`, `NrOfPerDiemNights`, `AddlDestAbsenceType`, `AddlDestAllowanceType`, `TrvlReqSprtnAllwnc`, `AcmdtnIsChargeable`, `TravelCountryRegion`

**Determinations:** `delete_AddlDest`, `Update_AddlDest`, `determinationForIsModified`, `determineCommunityCode`
**Side Effects:** `CityCodeName`, `TripBeginsAtTime`, `TripBeginsOnDate`, `CityName`, `TravelCountryRegion`

---

### 5.2 C_TravelAdvance — Travel Advances

| Property | Value |
|---|---|
| **Label** | Travel Advances |
| **Base CDS** | `I_TravelAdvance` |
| **Implementation Class** | `CL_BP_I_TRVLREQADVANCES` |
| **Draft Table** | `TRVS4_ADVANCE_D` |
| **Extensible** | Yes (suffix: `TAD`) |

**Key Fields:** `PersonnelNumber`, `TravelTripNumber`, `TravelReqUUID`, `SeqReqUUID`, `TravelRequestSequenceNumber`

**Core Fields:** `TrvlAdvncAmtInAdvncCrcy` (amount), `AdvanceCurrency`, `TravelRequestExchangeRate`, `CurrencyUnitFromRatio`, `CurrencyUnitToRatio`, `PaymentAmount`, `PaymentCurrency`, `AdvanceIsInCash`, `PaymentDate`, `AdvanceIsDisplayOnly`

**Determinations:** `determineadvancesupdate`, `determineadvancesexchrate`, `determineadvancespaycurrency`, `deleteAdvance`, `determinationForExtensibility`, `determinationForIsModified`
**Side Effects:** `TrvlAdvncAmtInAdvncCrcy`, `AdvanceCurrency`, `TravelRequestExchangeRate`

---

### 5.3 C_TravelCostAssignment — Cost Assignments

| Property | Value |
|---|---|
| **Label** | Travel Cost Assignment |
| **Base CDS** | `I_TravelCostAssignment` |
| **Implementation Class** | `CL_BP_I_TRVLREQCOSTASSIGNMENT` |
| **Draft Table** | `TRVS4_COSTASS_D` |
| **Extensible** | Yes (suffix: `TCT`) |

**Key Fields:** `PersonnelNumber`, `TravelTripNumber`, `TravelReqUUID`, `SeqReqUUID`, `TravelRequestSequenceNumber`, `CostAssignmentReferenceKey`, `TravelCostAssignmentType`

**Core Fields:** `CostAssgmtPercentageInQty`, `CompanyCode`, `BusinessArea`, `ControllingArea`, `CostCenter`, `TravelOrder`, `CostObject`, `WBSElement`, `AccountAssignmentNetworkNumber`, `Activity`, `SalesOrder`, `SalesOrderItem`, `BusinessProcess`, `FundCenterText`, `Fund`, `FunctionalArea`, `GrantID`, `CommitmentItem`, `TravelRequestProjectUUID`, `ExternalProjectNumber`, `TaskRoleUUID`, `TaskRoleNumber`, `BudgetPeriod`, `ProfitCenter`, `Segment`, `TravelRequestCostCategory`, `EarmarkedFundsDocument`, `EarmarkedFundsDocumentItem`, `TravelRequestFieldGroup`

**Determinations:** `determineCostAssignmentUpdate`, `determineCostAssignmentDelete`, `determinationForIsModified`, `determinationForExtensibility`
**Side Effects:** 20+ fields including `CostCenter`, `CompanyCode`, `WBSElement`, `SalesOrder`, etc.

---

### 5.4 C_TravelEstimatedCost — Estimated Costs

| Property | Value |
|---|---|
| **Label** | Travel Estimated Cost |
| **Base CDS** | `I_TravelEstimatedCost` |
| **Implementation Class** | `CL_BP_I_TRVLREQESTIMATEDCOST` |
| **Draft Table** | `TRVS4_ESTCOST_D` |
| **Extensible** | Yes (suffix: `TEC`) |

**Key Fields:** `PersonnelNumber`, `TravelTripNumber`, `TravelReqUUID`, `SeqReqUUID`, `TravelMedium`

**Core Fields:** `TravelMediumCategory`, `TravelMediumType`, `IsReadOnly`, `EstimatedCost` (amount), `Currency`, `SumLineIsTotal`, `EstimatedCostCategoryName`, `EstimatedCostIsApproved`, `EstdCostSortSequenceValue`, `Criticality`

**Determinations:** `determineestimatedcostupdate`, `determinationForExtensibility`, `determinationForIsModified`
**Side Effects:** `EstimatedCost` → `$self` + `_TravelRequest`, `EstimatedCostIsApproved` → `$self`

> **Note:** Delete operation is **not enabled** at the projection layer for estimated costs.

---

### 5.5 C_TravelServiceRequest — Travel Services

| Property | Value |
|---|---|
| **Label** | Travel Service Request Consumption Data |
| **Base CDS** | `I_TravelServiceRequest` |
| **Implementation Class** | `CL_BP_I_TRVLREQTRVLSERVICES` |
| **Draft Table** | `TRVS4_SRVREQ_D` |
| **Extensible** | Yes (suffix: `SRV`) |

**Key Fields:** `PersonnelNumber`, `TravelTripNumber`, `TravelReqUUID`, `SeqReqUUID`, `TravelServiceRequestNumber`

**Core Fields:** `TravelItemTypeForDisplay`, `TravelItemType`, `TripSegmentBeginDate`, `TripSegmentStartTime`, `TripSegmentEndDate`, `TripSegmentEndTime`, `TripStartingLocationName`, `DepartureCountry`, `TripEndLocationName`, `DestinationCountry`, `IATADepartureLocation`, `IATADestinationLocation`, `OtherServiceStatus`, `TrvlReqOthSrvcConfNmbr`, `TripReqPriceInTravelCurrency`, `TripRequestCurrency`, `TravelRequestComment`, `SalesOffcDetn`, `OtherTravelServiceCode`, `TrvlReqHasArrivalOrDeptr`

**Determinations:** `determinationForIsModified`, `dtrmnTrvlItemTypeForDisplay`, `updateTravelServices`, `determinationForExtensibility`, `deleteTravelServ`
**Side Effects:** `TravelItemTypeForDisplay` → `$self`

---

## 6. Behavior Definition — Projection Layer

### 6.1 CRUD Operations

| Entity | Create | Update | Delete |
|---|---|---|---|
| C_TravelRequest | augment | Yes | Yes |
| C_TravelAddlDestination | augment (via assoc) | Yes | Yes |
| C_TravelAdvance | augment (via assoc) | Yes | Yes |
| C_TravelCostAssignment | augment, precheck (via assoc) | Yes | Yes |
| C_TravelEstimatedCost | create (via assoc) | Yes | **No** |
| C_TravelServiceRequest | augment (via assoc) | Yes | Yes |

### 6.2 Actions

| Action | Entity | Type | Description |
|---|---|---|---|
| `CopyTravelRequest` | TravelRequest | Instance, with parameter `D_TrvlReqCopyTravelRequestP` | Copy existing request (list & object page button) |
| `SaveAndSubmitTravelRequest` | TravelRequest | Instance, dynamic features | Save and submit in a single step |
| `CreateTripBreak` | TravelRequest | Instance, with parameter `D_TrvlReqCreateTripBreakP` | Adds a trip break (button on Additional Destinations) |
| `CreateTripBreakDefault` | TravelRequest | Instance | Default trip break with result type `D_TrvlReqCreateTripBreakP` |
| `CopyTripToOtherEmployee` | TravelRequest (base only) | Instance, with parameter `D_TrvlReqCpyTripToOthEmplP` | Copy trip to another employee |
| `CopyFrmTripAsAsstnt` | TravelRequest (base only) | Static, with parameter `D_TrvlReqCopyFrmTripAsAsstntP` | Copy from trip as assistant |
| `CreateTravelRequestOnBehalf` | TravelRequest (base only) | Static, with parameter `D_TrvlReqCrteTrvlReqOnBehalfP` | Create on behalf of another employee |
| `CreateReturnService` | TravelServiceRequest | Instance | Add return service (inline button on Travel Services) |

### 6.3 Draft Actions (Standard RAP)

| Action | Description |
|---|---|
| `Edit` | Enter draft editing mode (with features control) |
| `Activate` | Activate draft (with additional implementation) |
| `Discard` | Discard draft (with additional implementation) |
| `Resume` | Resume editing a previously saved draft |
| `Prepare` | Validate draft before activation (triggers `validatesave` + `globalcheck`) |

---

## 7. Base BO — Validations, Determinations & Side Effects

### 7.1 Determinations (Root Entity)

| Determination | Trigger |
|---|---|
| `determineDeletionOnModify` | `on modify { delete }` |
| `determineCommunityCode` | `on modify { field TravelLocationCode }` |
| `determineCountry` | `on modify { field Country }` |
| `determineTrvlReqEditorText` | `on modify { field TravelRequestEditorText }` |
| `determinefields` | `on modify { update }` |

### 7.2 Validations (Root Entity)

| Validation | Trigger | Scope |
|---|---|---|
| `validatesave` | `on save` | Validates nearly all business fields on the root entity |
| `globalcheck` | `on save` | Global consistency check on `create` and `update` |

### 7.3 Side Effects (Root Entity)

| Trigger Field(s) | Affects |
|---|---|
| `TripDestination` | `$self`, `_TravelAddlDestination` |
| `TravelCountryRegion` | `$self`, `_TravelAddlDestination` |
| `CityName` | `$self`, `_TravelAddlDestination` |
| `TripArrivalDate` | `$self`, `_TravelAddlDestination` |
| `TripDepartureDate` | `$self`, `_TravelAddlDestination` |
| `DepartureBeginTime` | `$self`, `_TravelAddlDestination` |
| `ArrivalEndTime` | `$self`, `_TravelAddlDestination` |
| `TravelLocationCode` | `$self`, `_TravelAddlDestination` |
| `Country` | `$self` |
| `PssngrIsCarriedByOthEmpl` | `$self` |
| `CarPoolDriver` | `$self` |
| `NumberOfPassengerWithMe` | `$self` |
| `CreateTripBreak` (action) | `_TravelAddlDestination` |

---

## 8. Authorization

### 8.1 Authorization Model

- **Root Entity:** `authorization master (instance)` — instance-based auth checks
- **Child Entities:** `authorization dependent by _TravelRequest` — delegate to root
- **Privileged Mode:** Defined with `disabling NoCheckWhenPrivileged`

### 8.2 Authorization Objects

| Auth Object | Context | Description |
|---|---|---|
| `P_TRAVL` | Own context | Travel — Personnel number check |
| `F_TRAVL` | Own + Privileged | Travel — Functional authorization |
| `K_ORDER` | Own + Privileged | CO Order authorization |
| `PLOG` | Own context | HR: Master data (PD) |
| `C_PRPS_KOK` | Own + Privileged | PS: WBS — Controlling area |
| `C_PRPS_KST` | Own + Privileged | PS: WBS — Cost center |
| `C_PRPS_PRC` | Own + Privileged | PS: WBS — Profit center |
| `K_CSKS` | Own + Privileged | Cost center — Master maintenance |
| `C_PSCVP_DB` | Own + Privileged | PS: Commercial project |
| `K_AUFK_ART` | Own + Privileged | CO: Order type |

### 8.3 Access Control

- `@AccessControl.authorizationCheck: #MANDATORY` on all entities
- Session user filter: `where TravelEmployeeUserIdentifier = $session.user` (employee sees only their own requests)
- Privileged associations: `_TravelAddlDestination`, `_EstimatedCost`, `_Advance`, `_TravelCostAssignment`, `_TravelServiceRequest`, `_TravelEmployeeContactCard`

---

## 9. Draft Configuration

| Entity | Draft Table | Draft Query CDS |
|---|---|---|
| I_TravelRequest | `TRVS4_REQUEST_D` | `R_TravelRequestDraft` |
| I_TravelAddlDestination | `TRVS4_DEST_D` | `R_TrvlReqAddlDestDraft` |
| I_TravelAdvance | `TRVS4_ADVANCE_D` | `R_TrvlReqAdvanceDraft` |
| I_TravelCostAssignment | `TRVS4_COSTASS_D` | `R_TrvlReqCostAssignmentDraft` |
| I_TravelEstimatedCost | `TRVS4_ESTCOST_D` | `R_TrvlReqEstimatedCostDraft` |
| I_TravelServiceRequest | `TRVS4_SRVREQ_D` | `R_TravelRequestServicesDraft` |

- **Lock:** Root = `lock master`, Children = `lock dependent by _TravelRequest`
- **ETag:** `total etag LastChangeDateTime` on root (individual ETags commented out)

---

## 10. OData Service Exposure

### 10.1 Service Definition — TRV_UI_SD_MTR_MANAGE

**Label:** *"Service Definition for My Travel Request"*

| Exposed Entity | OData Entity Set Alias |
|---|---|
| `C_TravelRequest` | `TravelRequest` |
| `C_TravelEstimatedCost` | `TravelEstimatedCost` |
| `C_TravelAddlDestination` | `TravelAddlDestination` |
| `C_TravelCostAssignment` | `TravelCostAssignment` |
| `C_TravelServiceRequest` | `TravelServiceRequest` |
| `C_TravelAdvance` | `TravelAdvance` |
| `I_TravelCountryRegionVH` | `TravelCountryRegionVH` |
| `C_TravelRequestStatusValueHelp` | `TravelStatusVH` |
| `C_TravelArrivalWorkVH` | `ArrivalWorkVH` |
| `C_TravelDepartureWorkVH` | `DepartureWorkVH` |
| `I_TravelActivityPlanningVH` | `ActivityPlanningVH` |
| `C_TravelCurrencyVH` | `CurrencyVH` |
| `C_TravelAccountingObjectVH` | `AccountingVH` |
| `I_SalesOrderItemStdVH` | `SOItemVH` |
| `C_TravelCompanyCodeVH` | `CompanyCodeVH` |
| `I_BusinessAreaStdVH` | `BusinessAreaVH` |
| `I_CostCenterStdVH` | `CostCenterVH` |
| `C_TravelExportAsForm` | `TravelExportForm` |
| `C_TravelRecurringDestVH` | `RecurringDestinationVH` |
| `C_TrvlPredefinedAddrVH` | `PredefinedAddressVH` |
| `I_TrvlTripBreakRcrrcTypeVH` | `TrvlTripBreakRcrrcTypeVH` |
| `C_TravelPrdfndCategoryVH` | `PredefinedAddressCategoryVH` |
| `I_NetworkActivityValueHelp` | `NetworkActivityValueHelp` |
| `I_TravelWBSElementVH` | `TravelWBSElementVH` |
| `I_TravelNetworkValueHelp` | `TravelNetworkValueHelp` |
| `C_TravelStatutoryTypeVH` | `TravelStatutoryTypeVH` |
| `I_TravelLocationCodeValueHelp` | `LocationCodeValueHelp` |
| `C_TravelTripEnterpriseTypeVH` | `EnterpriseTypeValueHelp` |
| `C_TravelTripActivityTypeVH` | `TripTypeActivityValueHelp` |
| `I_TravelRequestNumberValueHelp` | `TravelRequestNumber` |
| `I_TravelEditor` | `TravelEditor` |
| `I_TravelEmployeeContactCard` | `TravelEmployeeContactCard` |

### 10.2 Service Definition — TRV_UI_SD_MTR_ARRANGER_MNG

**Label:** *"Travel Request for Arranger"*

Uses `C_TravelRequestForArranger` instead of `C_TravelRequest`. Adds `I_TravelUsersVH` for employee selection by arrangers.

### 10.3 Service Bindings

| Binding Name | Protocol | Scenario |
|---|---|---|
| `TRV_UI_SB_MTR_MANAGE` | OData V2 | Self-service (current employee) |
| `TRV_UI_SB_MTR_MANAGE_V4` | OData V4 | Self-service (current employee) |
| `TRV_UI_SB_MTR_ARRANGER_MNG` | OData V2 | Arranger (on behalf of) |
| `TRV_UI_SB_MTR_ARRANGER_V4` | OData V4 | Arranger (on behalf of) |

---

## 11. Extensibility

All entities are marked `extensible: true` with the following configuration:

| Entity | Suffix | Max Fields | Max Bytes | New Datasources |
|---|---|---|---|---|
| C_TravelRequest | `TRQ` | 350 | 2240 | Yes |
| C_TravelAddlDestination | `ADD` | 238 | 2240 | Yes |
| C_TravelAdvance | `TAD` | 350 | 2240 | Yes |
| C_TravelCostAssignment | `TCT` | 350 | 2240 | Yes |
| C_TravelEstimatedCost | `TEC` | 350 | 2240 | Yes |
| C_TravelServiceRequest | `SRV` | 350 | 2240 | Yes |

The service definition `TRV_UI_SD_MTR_MANAGE` is also annotated with `@AbapCatalog.extensibility.extensible: true`.

---

## 12. Search Configuration

The root entity `C_TravelRequest` is annotated with `@Search.searchable: true`. The following fields are configured as default search elements with fuzzy matching:

| Field | Fuzzy Threshold | Ranking |
|---|---|---|
| `PersonnelNumber` | 0.7 | HIGH |
| `TravelTripNumber` | 0.7 | HIGH |
| `TripReasonText` | 0.7 | HIGH |
| `TripDestination` | 0.7 | HIGH |
| `MainDestinationRegion` | 0.7 | HIGH |
| `CityName` | 0.7 | HIGH |

---

## 13. Implementation Classes Summary

| Class | Entity | Role |
|---|---|---|
| `CL_BP_I_TRAVELREQUEST` | I_TravelRequest | Base BO root handler |
| `CL_BP_C_TRAVELREQUEST` | C_TravelRequest | Projection handler (augment) |
| `CL_BP_I_TRVLREQADDLDESTINATION` | I_TravelAddlDestination | Additional destinations handler |
| `CL_BP_I_TRVLREQADVANCES` | I_TravelAdvance | Advances handler |
| `CL_BP_I_TRVLREQCOSTASSIGNMENT` | I_TravelCostAssignment | Cost assignment handler |
| `CL_BP_I_TRVLREQESTIMATEDCOST` | I_TravelEstimatedCost | Estimated cost handler |
| `CL_BP_I_TRVLREQTRVLSERVICES` | I_TravelServiceRequest | Travel services handler |
| `CL_TRV_MTR_VIRTUAL_ELEMENT_S4` | All entities | Virtual element calculation (field visibility) |
| `CL_TRV_ATTACH_VIRTUAL_ELEMENT` | C_TravelRequest | Attachment virtual element calculation |

---

## 14. Field Control Summary

The base BO uses both **global features** and **instance features** for field control:

- **Create:** Global feature control (`features: global`)
- **Update/Delete:** Instance feature control (`features: instance`)
- **Managed-numbering fields:** `TravelReqUUID`, `SeqReqUUID` (on children)
- **Read-only on update:** `TravelTripNumber`, `TravelReqUUID`, `PersonnelNumber`
- **Always read-only:** `TripAuthznFctrVal`
- **Instance-controlled:** All major business fields have `features: instance` enabling dynamic editability based on request status
