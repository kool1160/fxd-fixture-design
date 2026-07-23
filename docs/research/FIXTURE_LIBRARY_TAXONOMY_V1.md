# FXD Fixture Library Taxonomy v1

## Status

Research taxonomy only. It does not authorize runtime implementation or assign
a future milestone.

## Classification rule

Every item has:

- one `category`, describing what kind of library content it is; and
- exactly one `authority_level`, describing what evidence it may provide.

Category and authority are intentionally separate. For example, a purchased
clamp category can be metadata-only, provisional, exact private, or
supplier-authorized exact.

## Category A: FXD standard parametric primitives

Required primitive families:

- support pads;
- locator pins, including round and relieved intent;
- hard stops;
- rest buttons;
- risers;
- clamp brackets;
- gussets;
- base rails;
- baseplates;
- mounting feet;
- bridge members;
- replaceable locator blocks;
- generic review clamps;
- wear components; and
- shim components.

Each primitive needs a feature definition, units, manufacturing intent, stable
interfaces, configurable variants, revision history, and deterministic
validation participation.

## Category B: Shop-standard packs

Configurable fields include:

- available materials;
- plate thicknesses;
- tube, angle, channel, and rail sizes;
- standard hole and slot sizes;
- fasteners;
- tab-and-slot clearances;
- kerf and process allowances;
- clamp preferences;
- support and locator styles;
- finish conventions;
- markings;
- reusable-versus-recut preferences; and
- cost and production-volume preferences.

These are attributed inputs. They are never universal rules. Merge precedence
is FXD defaults, organization, shop, machine/process, project, then explicit
engineer decision. The result retains every contributing record.

## Category C: Private purchased tooling

Tooling classes include:

- commercial clamps;
- pins and bushings;
- cylinders;
- grippers;
- vises;
- pallets;
- positioners;
- torch heads;
- robot or cobot end effectors;
- sensors;
- probes; and
- inspection equipment.

Public FXD data may store category metadata and source links. Exact CAD is
customer- or supplier-controlled and may be used only under an authorized local
policy. FXD does not download, scrape, or redistribute tooling CAD.

## Category D: User-created reusable components

Reusable private component families include:

- clamp stands;
- locator towers;
- adjustable supports;
- tubing-frame corners;
- tab-and-slot risers;
- rail sections;
- sensor brackets;
- removable nests;
- modular station assemblies; and
- inspection stands.

Reuse transfers feature and interface intent, not prior placement approval,
validation, or production acceptance.

## Category E: Fixture-family templates

The reference corpus includes:

1. flat-base weld fixture;
2. tack and location fixture;
3. multi-station weld fixture;
4. assembly fixture;
5. inspection fixture;
6. profile-check fixture;
7. go/no-go gauge;
8. rework fixture;
9. machining and workholding setup;
10. product nest; and
11. combined build-and-check tooling.

Templates are bounded starting structures. Their authority is
`fixture_family_template`; they cannot participate as completed fixture
geometry or release evidence.

## Category F: Process-context assets

Process-context classes include:

- torch envelopes or heads;
- robot and cobot wrists;
- simple reach envelopes;
- tables;
- positioners;
- pallets;
- vises;
- machine envelopes;
- spindle and tool envelopes;
- operator hand, arm, and body envelopes;
- guarding;
- keep-out zones;
- maintenance and service zones; and
- inspection probes and scanners.

Only context required by the selected process pack should be loaded. A
profile-check fixture does not need a robot model; a workholding review may
need a machine envelope; a weld fixture may need torch, operator, table, or
positioner context.

## Category G: Private benchmark references

Private benchmark references describe annotated, owner-controlled examples.
They do not contain or publish the linked assets. The public repository contains
only the schema and synthetic examples.

## Public engineering knowledge

Public knowledge records include:

- engineering principles;
- fixture patterns;
- component applications;
- failure modes;
- abstract human acceptance; and
- abstract human rejection.

They are advisory precedent. They cannot authorize geometry, supplier claims,
shop standards, deterministic passes, or production release.

## Functional taxonomy

### Location and support

- primary support;
- secondary locator;
- tertiary stop;
- hole locator;
- relieved locator;
- adjustable locator;
- auxiliary support;
- clamp reaction support;
- wear contact; and
- shimmed datum contact.

### Force application

- manual clamp;
- powered clamp;
- gripper;
- vise;
- hold-down;
- side clamp;
- swing or retracting clamp; and
- temporary fit-up clamp.

### Structure and mounting

- baseplate;
- rail;
- crossmember;
- bridge;
- riser;
- tower;
- bracket;
- gusset;
- foot;
- pallet interface; and
- table-grid interface.

### Process and inspection

- torch tip or envelope;
- robot TCP;
- probe point;
- sensor field;
- tool or spindle envelope;
- load direction;
- unload direction; and
- maintenance access.

## Manufacturing-form taxonomy

- laser-cut plate;
- formed plate;
- machined block;
- tube;
- angle;
- channel;
- rail;
- weldment;
- purchased component;
- printed prototype where separately approved;
- wear insert;
- shim; and
- reference-only geometry.

## State taxonomy

Items may declare:

- fixed;
- open;
- closed;
- extended;
- retracted;
- loading;
- locating;
- clamping;
- process;
- inspection;
- release;
- unloading;
- changeover;
- cleaning; and
- maintenance.

A validation record cites the exact states it covers.

## Replacement taxonomy

Replacement is classified as:

- exact revision successor;
- same mounting and same functional interfaces;
- same mounting but changed function;
- placement-preserving with stale validation;
- geometry-only visual substitute;
- metadata-only substitute;
- incompatible; or
- unknown pending engineer review.

Similar envelope size is never sufficient compatibility evidence.
