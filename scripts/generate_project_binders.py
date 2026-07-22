from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "project-records" / "print"
HASH_MANIFEST = ROOT / "docs" / "project-records" / "BINDER_SHA256SUMS.txt"
LOGO = ROOT / "assets" / "branding" / "logos" / "fxd-logo-approved-dark-1600x900.png"
VOLUME_1_NAME = "FXD_Engineering_Binder_Volume_1_Milestones_01-25_Final.pdf"
VOLUME_2_NAME = "FXD_Engineering_Binder_Volume_2_Milestones_26-31_Final.pdf"
COMBINED_NAME = "FXD_Engineering_Binder_Complete_Milestones_01-31_Final.pdf"
FIXED_PDF_DATE = "D:20000101000000+00'00'"

MILESTONES = [
    (1, "Establish the Runnable Technical Baseline", "#2", "Created the dependency-free geometry proof, explicit millimetre units, transforms, intersection and clearance checks, deterministic neutral serialization, CI entry points, and the first CAD-neutral architecture boundary.", "Baseline geometry and unit tests passed; the proof deliberately used bounded review geometry rather than claiming production B-Rep behavior.", "No STEP parser, real topology, production fixture geometry, certification, or production release."),
    (2, "Import STEP Assemblies into a Normalized Product Model", "#3", "Added immutable CAD-neutral assembly hierarchy, repeated instances, nested transforms, units, bounds, topology summaries, source hashing, and explicit import failures.", "Hierarchy, transform, unit, repeated-instance, source-hash, and failure-path coverage passed.", "The normalized model did not modify source CAD or claim a full ISO 10303 implementation."),
    (3, "Build the Engineering-Annotation Workflow", "#4", "Created source-bound annotations for build orientation, loading direction, process, quantity, critical characteristics, locating permissions, forbidden contacts, weld joints, shop constraints, and visible assumptions.", "Deterministic round-trip, source binding, reference validation, and explicit-unknown behavior passed.", "Annotations describe manufacturing intent; they do not prove or approve a fixture."),
    (4, "Generate Baseplate, Supports, Stops, and Locator Primitives", "#5", "Generated traceable parameterized baseplates, supports, stops, pin envelopes, and locator primitives with initial overlap, forbidden-contact, missing-intent, and trapped-part findings.", "Primitive identity, parameter, overlap, forbidden-contact, missing-intent, and trapped-part coverage passed.", "Proof primitives only; no complete structure, structural adequacy, or production-ready geometry."),
    (5, "Create and Rank Complete Fixture Concepts", "#6", "Produced deterministic alternatives for minimum cost, fast loading, and high repeatability with locating/clamping rationale, warnings, score components, and copy-on-write corrections.", "Concept generation, ranking, score decomposition, rationale, alternatives, and correction behavior passed.", "Relative engineering ranking only; not supplier quotation, process certification, or production approval."),
    (6, "Model Weld, Operator, and Robot Access", "#7", "Added weld-approach, manual-tool, robot, operator, loading, and unloading envelopes with deterministic obstruction findings and visible uncertainty.", "Envelope generation, obstruction findings, incomplete-evidence handling, and traceability passed.", "No robot path planning, ergonomic certification, or weld-process approval."),
    (7, "Add Standard Clamp and Tooling Libraries", "#8", "Implemented vendor-neutral clamp, pin, and rest contracts and deterministic selection using force, stroke, mounting, envelope, licensing, and review limitations.", "Library identity, suitability, force/stroke, mounting, envelope, fallback, and licensing metadata passed.", "Review data only; not certified supplier selection or commercial-CAD equivalence."),
    (8, "Export a Fabrication-Ready Review Package", "#9", "Added deterministic review-package export with STEP-shaped proof geometry, DXF profiles, BOM, setup instructions, manifest, validation findings, units, revision, and engineering-review labels.", "Package determinism, manifest linkage, units, revision identity, and review-status coverage passed.", "Review package only; proof outputs were not released production drawings."),
    (9, "Capture Engineer Corrections and Reusable Knowledge", "#10", "Added attributable copy-on-write corrections, local private storage, sanitized training export, decision gating, and protections against silently promoting preferences into universal rules.", "Correction attribution, revision, privacy, sanitized export, and promotion-gating coverage passed.", "No autonomous engineering-rule rewriting."),
    (10, "Add CAD-Specific Connectors", "#11", "Established optional thin CAD connectors around the neutral model, including neutral STEP translation, review-package export, conservative SOLIDWORKS probing, and approval-gated destructive operations.", "Connector routing, capability probing, neutral handoff, failure behavior, and approval gates passed.", "The engineering core remained independent of SOLIDWORKS and every single CAD vendor."),
    (11, "Integrate a Real Geometry Kernel", "#12", "Integrated pinned cadquery-ocp behind the CAD-neutral kernel boundary with real STEP import/export, XCAF hierarchy, topology, stable references, Booleans, distance, clearance, malformed-input handling, source immutability, and licensing records.", "Real-kernel import, topology, references, Booleans, distance, clearance, malformed input, source immutability, and licensing passed; superseded PR #13 was not controlling evidence.", "Kernel capability does not certify fixture geometry or manufacturing readiness."),
    (12, "Complete the Deterministic Locating and Constraint Solver", "#14", "Implemented six-degree-of-freedom locating analysis using contact points, normals, roles, rigid-body constraint rows, rank analysis, and physical DOF classification.", "Rank, DOF classification, invalid-reference, redundancy, underconstraint, and recommendation-blocking coverage passed.", "Rigid-body locating analysis only; no elastic deformation, complete tolerance stack, or structural simulation."),
    (13, "Complete Weld-Fixture Engineering Rules", "#15", "Added deterministic weld-process reasoning for process, direction, sequence, heat input, distortion, tack, release, support placement, and clamp-force direction with traceable rule identities.", "Clamp direction, tack/release, sequence, evidence, and rule-traceability coverage passed.", "No thermal FEA, weld-quality certification, or WPS approval."),
    (14, "Establish the Manufacturing-Aware Geometry Foundation", "#16/#17/#19/#22", "Added manufacturing method, material, thickness, fit, clearance, allowance, interface, and operation metadata; deterministic cut-operation planning; source binding; feature-order validation; and STEP/DXF parity.", "STEP/DXF parity, wrong source hash, reordered features, malformed outputs, substitution, and pinned-OCP acceptance infrastructure passed.", "Foundation closure did not itself claim application-grade visual acceptance; that was completed under Milestone 17."),
    (15, "Build the Full Deterministic Validation Pipeline", "#21", "Unified geometry, locating, access, tooling, tolerance, and manufacturing evidence into a versioned ValidationResult that gates export and fails closed for missing, invalid, mismatched, unitless, unsupported, or empty evidence.", "Identity matching, evidence digest, intended interfaces, unrelated collisions, locating/clamp adequacy, provisional findings, and export blocking passed.", "Validation supports qualified review; it is not certification."),
    (16, "Build the First Serious Visual Engineering Application", "#24", "Added a local engineering application for STEP import, rotatable review, layers, assumptions, findings, corrections, approval decisions, and neutral project save/reload with stale and invalid approval blocking.", "Annotation preservation, immutable source identity, evidence persistence, tamper detection, unsafe approval blocking, edit revocation, and unknown-feature rejection passed.", "Initial display used normalized review geometry; production-quality B-Rep display followed in Milestone 17."),
    (17, "Prove and Expose Real-Kernel Geometry", "#28", "Exposed real product and fixture B-Rep geometry with tessellation, selectable faces/edges, sections, feature findings, collision highlighting, wireframe, transparency, layers, regeneration, and reconstruction from embedded STEP.", "Python 3.12, pinned OCP 7.9.3.1.1, and 85 repository tests passed with Boolean, clearance, section, tessellation, and visual acceptance.", "Real visual geometry remained engineering-review evidence, not automatic production approval."),
    (18, "Build the Edit-Regenerate-Revalidate Workflow", "#29", "Implemented move, resize, suppress, replace, restore, and parameter edits as revisioned commands that regenerate geometry, rerun validation, revoke stale approval, preserve history, compare revisions, and fail closed for unsupported edits.", "Recorded acceptance included 88 passed/4 skipped and later repaired merge evidence referenced 91 passing tests; revision and approval-revocation paths passed.", "Only explicitly supported engineering edits are allowed; source CAD remains immutable."),
    (19, "Deepen Weld-Fixture and Automation Workflow", "#39", "Added editable weld, tack, clamp, release, loading, and unloading sequences; heat, distortion, spatter, and restricted zones; and shared torch, hand, operator, robot, cobot, load, and unload envelopes.", "Pinned-OCP acceptance and workflow regressions passed with findings linked to workflow objects, collided geometry, and authoritative validation.", "No thermal simulation, force simulation, weld-quality certification, or robot kinematic planning."),
    (20, "Harden Projects, Packaging, and Release Operations", "#40", "Added project-v2 compatibility, atomic saves, autosave/recovery, diagnostics, isolated preferences, gated fabrication export, reproducible install/update, synthetic performance evidence, release manifests, sensitive-path rejection, and signing procedure.", "Kernel acceptance, migration, autosave/recovery, preferences, large-assembly performance, manifest safety, sensitive-path rejection, and repository validation passed.", "A controlled release procedure is not itself a production-approved release."),
    (21, "Generate Complete Fixture Structures", "#43", "Added deterministic baseplate and welded-frame structures with connected members, load paths, sizing assumptions, evidence, and fail-closed findings integrated into concepts, regeneration, validation, persistence, and review.", "9 focused structural tests and 110 full-suite tests passed; backlog, schema, compilation, secret scan, and real OCP proof passed.", "No structural certification, final fabrication geometry, thermal simulation, robot planning, safety certification, or production approval."),
    (22, "Optimize Locator, Support, Stop, and Clamp Placement", "#44", "Added datum-candidate ranking and editable placement contracts composing the six-DOF solver, access findings, tooling, weld intent, and structures while preserving alternatives, confidence, assumptions, digests, and evidence.", "10 focused placement tests and 121 full-suite tests passed; compilation, backlog, schema, secret scan, and OCP proof passed.", "No final B-Rep tooling, structural/thermal simulation, robot motion planning, safety certification, or production approval."),
    (23, "Produce Manufacturing-Ready Fixture Geometry", "#45", "Added stable manufacturing-component contracts for real OCP/B-Rep fixture solids, deterministic per-component STEP and planar DXF exports, and source/component/connectivity/hole/fit/mount/interface validation.", "7 focused tests and 128 full-suite tests passed; compileall, backlog, schema, OCP proof, secret scan, STEP reimport, topology, byte determinism, and DXF checks passed.", "Engineering-review exports only; no final drawings, complete tolerance stack, structural/safety certification, vendor approval, or production release."),
    (24, "Generate Fixture Drawings and Documentation", "#46", "Generated typed assembly, exploded, component, purchased-reference, and evidence-backed detail sheets with dimensions, annotations, hole tables, BOM, revision blocks, findings, deterministic PDF, manifest, and drawing BOM.", "8 focused tests and 137 full-suite tests passed; compileall, schema, backlog, secret scan, and OCP proof passed; a representative PDF had 22 pages and explicit review-only labels.", "Qualified drawing review remained required; no production approval or certification."),
    (25, "Optimize Cost, Volume, and Manufacturability", "#47", "Added deterministic cost, volume, manufacturability, alternative, recommendation, and evidence contracts with explicit material, process, engineering, programming, build, commissioning, maintenance, and replacement assumptions.", "7 focused optimization tests and 147 full-suite tests passed; compile, schema, backlog, secret scan, and OCP proof passed; scenarios covered 1, 25, 250, and 1000 units.", "Engineering estimate only; not supplier quotation, certified material takeoff, production budget, safety approval, or production release."),
    (26, "Complete the Local Engineering Workbench", "#48", "Repaired OCCT one-based triangle indexing and added persistent VTK actors, shaded defaults, navigation, diagnostics, XCAF color preservation, and honest real-geometry fallback.", "5 focused workbench tests and 154 full-suite tests passed; kernel proof, backlog, compileall, diff checks, and controlled STEP evidence passed.", "Render benchmarks were not visible-GUI FPS claims; engineering review only."),
    (27, "Unify the FXD Engineering Workbench", "#49", "Replaced the launched Tk shell with a PySide6 workbench and supervised native VTK worker, adding engineering tree, properties/findings, layers, review decisions, renderer controls, diagnostics, benchmarks, selection, and visibility.", "15 focused tests and 164 full-suite tests passed; CI contract, full CI, OCP proof, compileall, backlog, schema, diff checks, and Windows acceptance passed.", "Windows child-window embedding is not cross-platform acceptance; provisional evidence cannot be labeled real source geometry."),
    (28, "Expose the Interactive Fixture Engineering Workflow", "#50", "Exposed process intent, exact OCP face annotations, private tooling metadata, deterministic background analysis, concept comparison, supported corrections, revision restoration, findings review, persistence, and gated evidence export.", "34 focused workflow/workbench tests and 190 full-suite tests passed; compileall, schema, backlog, CI, secret scan, OCP proof, and Windows acceptance passed.", "Concept evidence remained visibly provisional; no paid runtime AI, supplier scraping, thermal simulation, robot planning, safety certification, or production approval."),
    (29, "Implement the Desktop UI and Branding System", "#51", "Integrated UI and Branding Kit v1.1 with design tokens, palette, QSS, approved assets, semantic widgets, source identity, workflow rail, renderer health, validation/approval gates, responsive docks, and layout persistence.", "30 focused branding/workbench tests and 201 full-suite tests passed; compileall, schema, backlog, launcher, secret scan, OCP proof, full CI, and branding-manifest verification passed.", "Branding does not alter engineering rules, source identity, validation, or approval authority."),
    (30, "Generate Real Fixture Geometry and Tack/Location Workflows", "#52", "Added deterministic real OCP fixture-construction evidence for full-weld, tack/location, assembly, inspection, checking, rework, automation, and combined fixture purposes with lifecycle, Cleco, holes, tabs, poka-yoke, BOM, nest, sequence, authority, validation, comparison, authoring, and schema-v4 persistence.", "16 focused tests and 224 full-suite tests passed; compileall, backlog, schema, OCP proof, full CI, and Windows real-geometry evidence passed.", "No structural adequacy, clamp-force calculation, thermal simulation, robot planning, automated nesting, safety certification, weld-procedure approval, or production release."),
    (31, "AI Fixture Engineer and Guided Validation", "#53", "Added the provider-neutral fxd-fixture-proposal-v1 contract, environment-only adapter, deterministic baseline, output quarantine, proposal workflow, intent confirmation, audited recommendations, evidence highlights, guided validation/correction routing, provenance, staleness, tooling evidence, and schema-v5 persistence.", "17 AI-core, 45 Qt/workbench, 14 persistence/export, 36 orientation/interactive/kernel, and 278 full-suite tests passed; compileall, diff, launcher, CI, hosted OCP acceptance, OCP proof, and Windows walkthrough passed.", "AI never approves fixtures; deterministic validation and human approval remain authoritative and fail closed."),
]

NAVY = colors.HexColor("#111827")
BLUE = colors.HexColor("#1878B8")
MID = colors.HexColor("#5B6775")
GRID = colors.HexColor("#B7C4CF")
WHITE = colors.white
BLACK = colors.HexColor("#111111")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="BodyDense", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.5, leading=10.7, textColor=BLACK, spaceAfter=4))
styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.1, leading=8.8, textColor=BLACK))
styles.add(ParagraphStyle(name="MetaLabel", parent=styles["BodyDense"], fontName="Helvetica-Bold", textColor=WHITE))
styles.add(ParagraphStyle(name="SectionBar", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=14, leading=16, textColor=WHITE, backColor=NAVY, leftIndent=7, rightIndent=7, spaceBefore=8, spaceAfter=8))
styles.add(ParagraphStyle(name="H2Blue", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11.2, leading=13.5, textColor=BLUE, spaceBefore=5, spaceAfter=3, keepWithNext=True))
styles.add(ParagraphStyle(name="MilestoneTitle", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=15.5, leading=18, textColor=NAVY, spaceAfter=5))
styles.add(ParagraphStyle(name="CoverTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=22, leading=26, textColor=NAVY, alignment=TA_CENTER, spaceAfter=7))
styles.add(ParagraphStyle(name="CoverSub", parent=styles["BodyText"], fontName="Helvetica", fontSize=10, leading=12, textColor=MID, alignment=TA_CENTER, spaceAfter=5))
styles.add(ParagraphStyle(name="Callout", parent=styles["BodyText"], fontName="Helvetica-BoldOblique", fontSize=10, leading=13, textColor=BLUE, alignment=TA_CENTER, spaceBefore=7, spaceAfter=7))
styles.add(ParagraphStyle(name="Tracker", parent=styles["BodyText"], fontName="Helvetica", fontSize=6.2, leading=7.4, textColor=BLACK))
styles.add(ParagraphStyle(name="TrackerHead", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=6.3, leading=7.4, textColor=WHITE, alignment=TA_CENTER))
styles.add(ParagraphStyle(name="BulletDense", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.3, leading=10.3, leftIndent=11, firstLineIndent=-7, spaceAfter=2))


class OutlineDocTemplate(SimpleDocTemplate):
    """Create stable PDF outline entries from governed heading styles."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._outline_index = 0

    def afterFlowable(self, flowable):
        super().afterFlowable(flowable)
        if not isinstance(flowable, Paragraph):
            return
        levels = {"SectionBar": 0, "MilestoneTitle": 1}
        level = levels.get(flowable.style.name)
        if level is None:
            return
        title = flowable.getPlainText()
        key = f"fxd-outline-{self._outline_index:03d}"
        self._outline_index += 1
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(title, key, level=level, closed=False)


def invariant_canvas(*args, **kwargs):
    """Return a ReportLab canvas with stable dates and document identifiers."""

    kwargs["invariant"] = 1
    kwargs["pageCompression"] = 1
    return Canvas(*args, **kwargs)


def header_footer(volume: str, milestone_range: str):
    def draw(canvas, doc):
        canvas.saveState()
        width, height = letter
        canvas.setStrokeColor(colors.HexColor("#7DB3D5"))
        canvas.setLineWidth(0.6)
        canvas.line(0.65 * inch, height - 0.48 * inch, width - 0.65 * inch, height - 0.48 * inch)
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(MID)
        canvas.drawCentredString(width / 2, height - 0.38 * inch, f"Christopher Hilton | FXD - Intelligent Industrial Fixture Design | Engineering Binder {volume}")
        canvas.drawCentredString(width / 2, 0.35 * inch, f"FXD Engineering Binder | Milestones {milestone_range} | Page {doc.page}")
        canvas.restoreState()
    return draw


def cover_story(volume: str, milestone_range: str, subtitle: str):
    story = [Spacer(1, 0.1 * inch)]
    if LOGO.exists():
        story += [Image(str(LOGO), width=6.5 * inch, height=2.25 * inch), Spacer(1, 0.08 * inch)]
    story += [Paragraph("FXD Engineering Project Binder", styles["CoverTitle"]), Paragraph(f"{volume} - Milestones {milestone_range}", styles["CoverTitle"]), Paragraph(subtitle, styles["CoverSub"])]
    meta = [
        ["Project", "FXD - Intelligent Industrial Fixture Design"],
        ["Repository", "kool1160/fxd-fixture-design"],
        ["Document Class", "Engineering development history / professional project binder"],
        ["Volume Status", f"Closed audited record through Milestone {milestone_range.split('-')[-1]}"],
        ["Audit Basis", "Merged pull requests, tests, CI, project law, architecture, decision, and project records"],
        ["Runtime Changes", "None - documentation only"],
    ]
    table = Table([[Paragraph(a, styles["MetaLabel"]), Paragraph(b, styles["BodyDense"])] for a, b in meta], colWidths=[1.45 * inch, 5.0 * inch])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), NAVY), ("TEXTCOLOR", (0, 0), (0, -1), WHITE), ("GRID", (0, 0), (-1, -1), 0.5, GRID), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story += [Spacer(1, 0.1 * inch), table, Paragraph("AI proposes. Engineering validates.", styles["Callout"]), Paragraph("The software should think like an experienced fixture engineer.", styles["Callout"]), PageBreak()]
    return story


def tracker(records):
    rows = [[Paragraph(x, styles["TrackerHead"]) for x in ["M", "Milestone", "Status / PR", "Scope Summary", "Testing / Evidence", "Boundary"]]]
    for n, title, pr, scope, tests, limits in records:
        rows.append([Paragraph(str(n), styles["Tracker"]), Paragraph(title, styles["Tracker"]), Paragraph(f"Complete<br/>{pr}", styles["Tracker"]), Paragraph(scope, styles["Tracker"]), Paragraph(tests, styles["Tracker"]), Paragraph(limits, styles["Tracker"])])
    table = LongTable(rows, colWidths=[0.28 * inch, 1.05 * inch, 0.72 * inch, 1.78 * inch, 1.78 * inch, 1.03 * inch], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), WHITE), ("GRID", (0, 0), (-1, -1), 0.35, GRID), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, colors.HexColor("#F6F9FB")])]))
    return table


def detailed_records(records):
    story = []
    for index, (n, title, pr, scope, tests, limits) in enumerate(records):
        evidence = Table([[Paragraph("<b>Status</b>", styles["Small"]), Paragraph("Complete", styles["Small"]), Paragraph("<b>Controlling PR</b>", styles["Small"]), Paragraph(pr, styles["Small"])]], colWidths=[0.62 * inch, 0.85 * inch, 0.9 * inch, 1.2 * inch])
        evidence.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), NAVY), ("TEXTCOLOR", (0, 0), (0, 0), WHITE), ("BACKGROUND", (2, 0), (2, 0), NAVY), ("TEXTCOLOR", (2, 0), (2, 0), WHITE), ("GRID", (0, 0), (-1, -1), 0.4, GRID), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        story += [KeepTogether([Paragraph(f"Milestone {n:02d} - {title}", styles["MilestoneTitle"]), evidence, Spacer(1, 4)]), Paragraph("Engineering scope and significance", styles["H2Blue"]), Paragraph(scope, styles["BodyDense"]), Paragraph("Validation and source evidence", styles["H2Blue"]), Paragraph(tests, styles["BodyDense"]), Paragraph("Known limitations and protected boundaries", styles["H2Blue"]), Paragraph(limits, styles["BodyDense"]), Paragraph("Completion record", styles["H2Blue"]), Paragraph(f"Milestone {n:02d} is recorded as Complete because its controlling implementation was merged through PR {pr}. The original pull request, commit history, CI evidence, test records, and qualified engineering review remain authoritative.", styles["BodyDense"]), HRFlowable(width="100%", thickness=0.6, color=GRID, spaceBefore=5, spaceAfter=7)]
        if index % 2 == 1 and index != len(records) - 1:
            story.append(PageBreak())
    return story


def make_volume(output_dir: Path, filename: str, volume: str, milestone_range: str, records, summary: str, closeout: str, handoff: str):
    output_dir.mkdir(parents=True, exist_ok=True)
    story = cover_story(volume, milestone_range, "Audited engineering record based on the approved documentation-recovery structure")
    story += [Paragraph("1. Executive Summary", styles["SectionBar"]), Paragraph(summary, styles["BodyDense"]), Paragraph("Governing principles", styles["H2Blue"])]
    for principle in ["Source customer CAD remains immutable.", "Deterministic geometry, mathematics, and engineering rules remain authoritative.", "AI is advisory and may not approve a fixture.", "Every recommendation and validation result must remain explainable and traceable.", "Manufacturing practicality and qualified human approval remain mandatory."]:
        story.append(Paragraph("- " + principle, styles["BulletDense"]))
    story += [Paragraph("2. Master Milestone Recovery Tracker", styles["SectionBar"]), Paragraph("Exact historical test counts are reported only when the controlling repository evidence states them.", styles["BodyDense"]), tracker(records), PageBreak(), Paragraph("3. Detailed Milestone Records", styles["SectionBar"])]
    story += detailed_records(records)
    story += [PageBreak(), Paragraph("4. Evidence and Validation Record", styles["SectionBar"]), Paragraph("Controlling evidence consists of merged pull requests, commit history, automated and hosted validation, real-kernel proof, Windows visual evidence where applicable, architecture decisions, project records, roadmap records, and explicit human-review boundaries. Exact missing historical values are not invented.", styles["BodyDense"]), Paragraph("5. Documentation Correction Note", styles["SectionBar"]), Paragraph("This audited edition replaces the earlier under-filled print layout. It restores dense milestone tracking, engineering scope, validation evidence, limitations, closeout, and content-driven pagination while preserving repository history as the source of truth.", styles["BodyDense"]), Paragraph("6. Volume Closeout", styles["SectionBar"]), Paragraph(closeout, styles["BodyDense"]), Paragraph("7. Controlled Handoff", styles["SectionBar"]), Paragraph(handoff, styles["BodyDense"]), Paragraph("8. Future Documentation Rule", styles["SectionBar"])]
    for rule in ["Planning -> Implementation -> Testing -> Documentation.", "Never mark an open or unmerged milestone complete.", "Update controlled binder batches while evidence is fresh.", "Record PR, validation evidence, limitations, and the next handoff.", "Pass results, not noise; never reconstruct missing facts by guessing."]:
        story.append(Paragraph("- " + rule, styles["BulletDense"]))
    path = output_dir / filename
    doc = OutlineDocTemplate(
        str(path),
        pagesize=letter,
        rightMargin=0.58 * inch,
        leftMargin=0.58 * inch,
        topMargin=0.62 * inch,
        bottomMargin=0.55 * inch,
        title=f"FXD Engineering Binder {volume} - Milestones {milestone_range}",
        author="Christopher Hilton",
        subject="Audited FXD engineering history through Milestone 31",
        creator="FXD deterministic binder generator",
    )
    doc.build(
        story,
        onFirstPage=header_footer(volume, milestone_range),
        onLaterPages=header_footer(volume, milestone_range),
        canvasmaker=invariant_canvas,
    )
    return path


def combine(paths, output):
    writer = PdfWriter()
    for path, title in paths:
        writer.append(path, outline_item=title, import_outline=True)
    writer.add_metadata(
        {
            "/Title": "FXD Engineering Binder - Complete Milestones 01-31",
            "/Author": "Christopher Hilton",
            "/Subject": "Audited FXD engineering history through Milestone 31",
            "/Creator": "FXD deterministic binder generator",
            "/Producer": "pypdf 6.14.2",
            "/CreationDate": FIXED_PDF_DATE,
            "/ModDate": FIXED_PDF_DATE,
        }
    )
    writer.generate_file_identifiers()
    with output.open("wb") as handle:
        writer.write(handle)
    return output


def digest_lines(paths):
    return [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}" for path in paths]


def write_hashes(paths, manifest=HASH_MANIFEST):
    manifest.write_text("\n".join(digest_lines(paths)) + "\n", encoding="utf-8")


def outline_titles(reader):
    titles = []

    def visit(items):
        for item in items:
            if isinstance(item, list):
                visit(item)
            else:
                titles.append(str(item.title))

    visit(reader.outline)
    return titles


def expected_volume_outline(records):
    return [
        "1. Executive Summary",
        "2. Master Milestone Recovery Tracker",
        "3. Detailed Milestone Records",
        *[f"Milestone {number:02d} - {title}" for number, title, *_ in records],
        "4. Evidence and Validation Record",
        "5. Documentation Correction Note",
        "6. Volume Closeout",
        "7. Controlled Handoff",
        "8. Future Documentation Rule",
    ]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def preflight_pdf(path, expected_outline):
    reader = PdfReader(path)
    require(not reader.is_encrypted, f"encrypted PDF: {path}")
    require(bool(reader.pages), f"empty PDF: {path}")
    require(all(float(page.mediabox.width) == 612 and float(page.mediabox.height) == 792 for page in reader.pages), f"non-letter page: {path}")
    require(all((page.extract_text() or "").strip() for page in reader.pages), f"non-searchable page: {path}")
    require(all(not page.get("/Annots") for page in reader.pages), f"page annotations present: {path}")
    require("/AcroForm" not in reader.trailer["/Root"], f"interactive form present: {path}")
    require(outline_titles(reader) == expected_outline, f"outline mismatch: {path}")
    require(bool(reader.trailer.get("/ID")), f"missing document identifier: {path}")
    return reader


def build_binders(output_dir):
    vol1 = make_volume(output_dir, VOLUME_1_NAME, "Volume 1", "01-25", MILESTONES[:25], "Volume 1 records FXD's progression from a dependency-free geometry proof into a CAD-neutral digital fixture engineer with real STEP/OCP geometry, deterministic locating and weld-fixture rules, explainable concept generation, validation gates, visual engineering review, controlled edits, complete fixture structures, manufacturing geometry, drawings, and cost/volume/manufacturability analysis.", "Volume 1 closes at Milestone 25 because the first complete deterministic engineering foundation was established: imported assemblies could be interpreted, annotated, fixtured, validated, represented as manufacturing components, documented, and compared economically while preserving source-CAD immutability and human approval.", "Volume 2 begins at Milestone 26 and records the transition from the deterministic foundation into the local engineering workbench, unified application, interactive workflow, branding, real fixture-build workflows, and guided AI assistance.")
    vol2 = make_volume(output_dir, VOLUME_2_NAME, "Volume 2", "26-31", MILESTONES[25:], "Volume 2 records the transformation of FXD from a completed deterministic fixture-engineering foundation into a serious local engineering application with real STEP viewing, a unified PySide6/VTK workbench, interactive engineering workflows, controlled branding, real fixture-construction geometry, and the advisory AI Fixture Engineer with guided validation.", "Volume 2 closes at Milestone 31. FXD now has a professional Windows engineering workbench, real source-geometry review, interactive intent and correction workflows, deterministic real fixture-build geometry, governed persistence, and an advisory AI proposal layer subordinate to validation and human authority.", "Work after Milestone 31 belongs to a later binder volume or addendum. Its current status is governed outside this retrospective binder by the authoritative milestone registry and active GitHub issue.")
    combined = combine(
        [
            (vol1, "Volume 1 - Milestones 01-25"),
            (vol2, "Volume 2 - Milestones 26-31"),
        ],
        output_dir / COMBINED_NAME,
    )
    preflight_pdf(vol1, expected_volume_outline(MILESTONES[:25]))
    preflight_pdf(vol2, expected_volume_outline(MILESTONES[25:]))
    preflight_pdf(
        combined,
        [
            "Volume 1 - Milestones 01-25",
            *expected_volume_outline(MILESTONES[:25]),
            "Volume 2 - Milestones 26-31",
            *expected_volume_outline(MILESTONES[25:]),
        ],
    )
    return (vol1, vol2, combined)


def publish_reproducible_binders(output_dir=OUTPUT, manifest=HASH_MANIFEST):
    with TemporaryDirectory(prefix="fxd-binder-a-") as first_dir, TemporaryDirectory(prefix="fxd-binder-b-") as second_dir:
        first = build_binders(Path(first_dir))
        second = build_binders(Path(second_dir))
        for first_path, second_path in zip(first, second, strict=True):
            require(first_path.read_bytes() == second_path.read_bytes(), f"non-deterministic PDF bytes: {first_path.name}")
        output_dir.mkdir(parents=True, exist_ok=True)
        published = tuple(output_dir / path.name for path in first)
        for source, destination in zip(first, published, strict=True):
            shutil.copyfile(source, destination)
    write_hashes(published, manifest)
    return published


def main():
    paths = publish_reproducible_binders()
    for path in paths:
        reader = PdfReader(path)
        print(f"generated {path.relative_to(ROOT)}: {len(reader.pages)} pages, {path.stat().st_size} bytes")
    print("verified byte-identical output from two independent builds")


if __name__ == "__main__":
    main()
