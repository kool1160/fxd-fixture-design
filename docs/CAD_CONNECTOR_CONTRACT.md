# FXD CAD connector contract

Milestone 10 establishes the optional connector boundary. A connector may
translate a vendor document into FXD's immutable `ProductModel` or consume a
neutral review package. Vendor objects, COM handles, SDK types, and vendor
business rules must not cross into `fxd_geometry`'s engineering core.

The dependency-free `NeutralStepConnector` is the reference implementation and
keeps the standalone workflow available without a CAD installation. Connector
failures are wrapped as `ConnectorError`; they do not modify source bytes or
replace the neutral model.

## SOLIDWORKS Connected/Makers probe

`probe_solidworks()` is intentionally read-only. On non-Windows hosts it
reports `unsupported`. On Windows it reports `not_detected` unless an operator
sets `FXD_SOLIDWORKS_VERSION`, and then reports `unknown`. The environment
variable is evidence supplied by the operator, not proof of installation,
edition, API availability, compatibility, or license rights. The probe does
not start SOLIDWORKS, inspect customer files, call COM, or import an SDK.

An approved Windows test may later add a thin adapter, but it must document
the exact Connected/Makers edition, API access, authentication, redistribution
terms, and failure behavior. No vendor SDK or binary is bundled by this
milestone.

## Operation policy

Read/import and neutral review-package export are safe connector operations.
Mutation of a vendor document is not implemented. Any future operation named
`mutate_vendor_document` or `save_into_vendor_document` must call
`require_destructive_approval()` and receive explicit human approval. FXD does
not treat connector output as certified, validated, or production-approved.

The next connector implementation should be tested against synthetic or
legally shareable geometry only, with a Windows installation and vendor terms
approved before SDK or COM work begins.
