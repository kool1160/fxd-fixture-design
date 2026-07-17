# FXD Product Direction

## What FXD is

FXD is an intelligent industrial fixture-design platform. It begins with weld fixturing for sheet-metal products and fabricated assemblies, but its architecture must support other manufacturing fixture classes later.

The defining workflow is:

> Give FXD the product assembly and manufacturing intent; receive practical, editable fixture concepts that understand locating, clamping, access, loading, welding, manufacturability, and removal.

## Who it serves

Initial users are manufacturing engineers, fixture designers, weld engineers, toolmakers, fabrication shops, and integrators working with:

- laser-cut sheet and plate
- formed sheet-metal parts
- tube, angle, channel, and structural members
- manual MIG/TIG welding
- cobot and robotic welding
- low-volume through repeat-production fixtures

## The problem

Existing automated fixture tools commonly create contour-matched skeletons or cradles. Those can be expensive, difficult to edit, awkward to load, hostile to weld access, and disconnected from how a real fixture locates individual components.

FXD must reason about the manufacturing job, not only the outer shape of the finished solid.

## Product differentiators

- understands assembly components rather than treating the weldment as one anonymous body
- separates locating from clamping
- reasons about six degrees of freedom and intentional floating directions
- considers torch, operator, robot, tack, and unload access
- prefers standard and laser-cut construction before unnecessary machining
- produces several tradeoff-driven concepts instead of pretending one answer is universally best
- exposes assumptions and lets the engineer correct them
- creates reusable manufacturing knowledge from corrections

## Initial product boundary

The first useful release targets flat-base weld fixtures for fabricated sheet, plate, and structural components using supports, pins, stops, laser-cut risers, tab-and-slot construction, and standard clamps.

It will not initially promise:

- universal fixturing for every geometry or process
- certified thermal-distortion prediction
- structural certification of the fixture
- automatic production release
- complete robot offline programming
- replacement of a full CAD system
- unattended changes to customer CAD

## Product architecture direction

FXD should be a standalone application with a CAD-neutral engineering core. STEP is the first neutral input/output. CAD connectors are optional thin adapters added after the core workflow works.

The core product must remain useful to users of SOLIDWORKS, Inventor, Creo, Fusion, Onshape, CATIA, NX, and other systems through neutral formats.

## AI boundary

AI may interpret instructions, propose plans, rank concepts, explain tradeoffs, and help classify ambiguous geometry. Deterministic geometry and manufacturing rules must own safety-critical constraints, dimensions, collision results, and export decisions.

## Commercial direction

FXD may become commercial software, but the current repository is an early public development scaffold with no open-source license. Do not add billing, public accounts, or SaaS infrastructure until the local engineering product proves value.

## Future runtime AI boundary

The base local FXD product must remain useful without paid AI calls. Future AI
capacity may use included usage and explicit add-on analysis packages, with
replaceable runtime providers. Routine explanation may use a balanced model
and difficult interpretation may use a higher-reasoning model, but customers
must never be led to believe unbounded inference is free. Structured evidence,
assumptions, and deterministic results remain the authority; provider-specific
AI code does not belong in the engineering kernel.

## Supplier and private tooling direction

FXD may recommend an exact commercial component for customer approval. Without
an authorized supplier integration, FXD may provide the official source link,
but the customer downloads CAD under the supplier's terms and imports it into
their private tooling library. FXD may then place and validate that exact local
geometry. Built-in supplier catalogs require licensing, permission, an approved
feed, API, or partnership. FXD does not scrape supplier sites or redistribute
unauthorized catalog geometry.
