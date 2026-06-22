"""
dsl_system_prompt.py — Port Python du module JS systemPrompt du DSL Agent.

Fidèle traduction du module JavaScript (systemPrompt.js) vers Python :
  - DOMAIN_META, OUTPUT_TYPES, DOMAIN_FIELD_SIGNATURES
  - preClassifyDomains()
  - build_system_prompt()
  - describeOutputType()

Aucune logique n'a été ajoutée ou retirée : ce fichier est la source de vérité
du system prompt envoyé à Claude pour le mode DSL Agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import NamedTuple


# ════════════════════════════════════════════════════════════════════════════
# DOMAINES
# ════════════════════════════════════════════════════════════════════════════

DEPLOYED_DOMAINS: list[str] = ["A", "B", "C", "D"]
ROADMAP_DOMAINS:  list[str] = ["E", "F", "G", "H"]


@dataclass
class CompositeIndex:
    name: str
    formula: str
    factors: dict[str, str]
    world_class_benchmark: str
    fictitious_example: str = ""


@dataclass
class DomainMeta:
    name: str
    metric: str
    tools: str
    deployed: bool
    dmaic_tools: dict[str, list[str]] = field(default_factory=dict)
    composite_index: CompositeIndex | None = None


DOMAIN_META: dict[str, DomainMeta] = {
    "A": DomainMeta(
        name="Quality & Defects",
        metric="Defect Rate, DPMO, Cp/Cpk",
        tools="FMEA, Pareto, Fishbone 5M, SPC P-chart, Poka-Yoke, 5 Whys",
        deployed=True,
        dmaic_tools={
            "Define":  ["Project Charter", "SIPOC Diagram"],
            "Measure": ["Defect Rate / DPMO calculation", "Process Capability (Cp, Cpk)", "Pareto Chart (80/20)"],
            "Analyze": ["Fishbone / Ishikawa (5M)", "5 Whys", "FMEA (RPN)"],
            "Improve": ["Poka-Yoke", "Standard Work", "5S", "Kaizen Event"],
            "Control": ["SPC P-Chart", "Control Plan"],
        },
        composite_index=CompositeIndex(
            name="Quality Index (QI)",
            formula="QI = Conformance Rate × Process Stability × Capability Score",
            factors={
                "Conformance Rate":   "First Pass Yield = Good units / Total units produced",
                "Process Stability":  "Share of samples within SPC control limits (no out-of-control points) over the measurement window",
                "Capability Score":   "min(Cpk / 1.33, 1.0) — Cpk normalized against the 1.33 world-class threshold, capped at 100%",
            },
            world_class_benchmark="≥ 85%",
            fictitious_example=(
                "88.4% (FPY) × 0.97 (stability) × 0.41 (Cpk 0.54/1.33) ≈ 35.1% before improvement → "
                "96.9% × 0.99 × 0.84 (Cpk 1.12/1.33) ≈ 80.6% after improvement"
            ),
        ),
    ),
    "B": DomainMeta(
        name="Maintenance & OEE",
        metric="OEE, MTBF, MTTR",
        tools="FMEA (RPN), TPM, SMED, OEE A×P×Q, MTBF/MTTR analysis",
        deployed=True,
        dmaic_tools={
            "Define":  ["OEE Decomposition (A×P×Q)"],
            "Measure": ["MTBF / MTTR Analysis", "Downtime Pareto"],
            "Analyze": ["FMEA for Maintenance (RPN)"],
            "Improve": ["TPM — Autonomous Maintenance", "SMED"],
            "Control": ["OEE Monitoring Dashboard", "I-MR Control Chart"],
        },
        composite_index=CompositeIndex(
            name="Overall Equipment Effectiveness (OEE)",
            formula="OEE = Availability × Performance × Quality",
            factors={
                "Availability":  "(Planned time − Downtime) / Planned time",
                "Performance":   "Actual output / Theoretical output at rated speed",
                "Quality":       "Good units / Total units produced (links back to Domain A)",
            },
            world_class_benchmark="≥ 85%",
            fictitious_example=(
                "71.4% × 79.2% × 74.2% ≈ 42.0% before improvement → "
                "89.6% × 92.1% × 93.0% ≈ 76.8% after improvement"
            ),
        ),
    ),
    "C": DomainMeta(
        name="Production Flow & Lead Time",
        metric="Lead Time, WIP, Takt Time",
        tools="VSM, Kanban sizing, Takt analysis, Heijunka, Line balancing",
        deployed=True,
        dmaic_tools={
            "Define":  ["Takt Time Calculation"],
            "Measure": ["VSM Current State"],
            "Analyze": ["Line Balancing Analysis", "Spaghetti Diagram"],
            "Improve": ["VSM Future State", "Kanban System Design", "Heijunka"],
            "Control": ["I-MR Chart (Lead Time)", "Visual Management / Andon"],
        },
        composite_index=CompositeIndex(
            name="Flow Effectiveness Index (FEI)",
            formula="FEI = Takt Adherence × Flow Efficiency (VA Ratio) × On-Time Delivery Rate",
            factors={
                "Takt Adherence":       "min(Takt Time / Actual bottleneck cycle time, 1.0) — how close the slowest station runs to the ideal pace, capped at 100%",
                "Flow Efficiency":      "Value-Added Time / Total Lead Time (the VA ratio from the VSM)",
                "On-Time Delivery Rate":"On-time deliveries / Total deliveries",
            },
            world_class_benchmark="≥ 60%",
            fictitious_example=(
                "50% (84s Takt / 168s bottleneck) × 2.1% (VA ratio) × 71.3% (OTD) ≈ 0.75% before improvement → "
                "100% (rebalanced to Takt) × 5.9% × 94.8% ≈ 5.6% after improvement"
            ),
        ),
    ),
    "D": DomainMeta(
        name="Energy & Environment",
        metric="kWh/unit, CO₂/shift, Energy Efficiency",
        tools="Green FMEA, E-VSM, ISO 50001 SPC, Energy Poka-Yoke, CBAM KPI",
        deployed=True,
        dmaic_tools={
            "Define":  ["Energy Project Charter", "Energy SIPOC", "E-VSM (Current State)"],
            "Measure": ["Energy KPI Baseline Dashboard", "ISO 50001 I-MR SPC Chart"],
            "Analyze": ["Energy Fishbone (5M + Energy)", "Green FMEA (RPN)", "5 Whys (Energy)"],
            "Improve": ["Energy Action Plan (Quick Win / Medium / Structural)", "Energy Poka-Yoke"],
            "Control": ["Energy KPI Dashboard (3-level)", "Standard Energy Work (SEW)"],
        },
        composite_index=CompositeIndex(
            name="Energy Overall Effectiveness (eOEE)",
            formula="eOEE = Energy Availability × Energy Efficiency × CBAM Compliance Factor",
            factors={
                "Energy Availability":     "1 − (Idle Energy Ratio) — share of consumed energy going to actual production rather than idle/standby loss",
                "Energy Efficiency":       "min(Benchmark kWh/unit / Actual kWh/unit, 1.0) — actual intensity compared to the 2.90 kWh/unit sector benchmark, capped at 100%",
                "CBAM Compliance Factor":  "min(CBAM Threshold (2.10 kg CO2/unit) / Actual CO2 intensity, 1.0) — 100% when at or below the CBAM threshold, below 100% when non-compliant",
            },
            world_class_benchmark="≥ 70%",
            fictitious_example=(
                "71% (1 − 0.29 idle) × 60% (2.90/4.80 kWh) × 60% (2.10/3.51 kg, non-compliant) ≈ 25.6% before → "
                "90.5% × 100% × 100% ≈ 90.5% after improvement"
            ),
        ),
    ),
    # ── Roadmap domains (non déployés analytiquement) ──────────────────────
    "E": DomainMeta(name="Supply Chain & Logistics",    metric="Bullwhip Ratio, OTIF, Supplier OTD",    tools="ABC-XYZ, Kanban Supplier, SCOR, S&OP (roadmap — not deployed)", deployed=False),
    "F": DomainMeta(name="Safety & Ergonomics",         metric="TRIR, Near-miss rate, Ergonomic score", tools="HFMEA, Bowtie, REBA/RULA (roadmap — not deployed)",            deployed=False),
    "G": DomainMeta(name="Human Performance & Training", metric="Qualification Cp/Cpk, Skills Matrix", tools="Kirkpatrick Model, TWI, OJT (roadmap — not deployed)",          deployed=False),
    "H": DomainMeta(name="Cost & Financial Performance", metric="COPQ, PAF Model",                    tools="PAF Model, COPQ Analysis, ABC Costing (roadmap — not deployed)", deployed=False),
}


# ════════════════════════════════════════════════════════════════════════════
# OUTPUT TYPES
# ════════════════════════════════════════════════════════════════════════════

class _OutputType(NamedTuple):
    id: str
    label: str
    description: str


class OUTPUT_TYPES:  # noqa: N801 — mirror du JS pour cohérence
    DIGITAL_A3       = _OutputType("digital_a3",        "Digital A3 Report",                    "Primary, complete DMAIC output for significant or systematic problems requiring full root-cause analysis.")
    KPI_ALERT        = _OutputType("kpi_alert",          "Real-Time KPI Alert",                  "Compact, immediate threshold-breach notification for in-shift operator response.")
    QUICK_FIX        = _OutputType("quick_fix",          "Quick-Fix Action Card",                "Single-card corrective action for minor, well-understood, recurring problems.")
    EXECUTIVE_SUMMARY= _OutputType("executive_summary",  "Executive Summary Report",             "One-page, management-level performance snapshot across deployed domains.")
    CBAM_REPORT      = _OutputType("cbam_report",        "CBAM Compliance Report",               "Domain D-specific, indicative CO₂ reporting aligned with EU CBAM thresholds. Informational only — not a certified regulatory declaration.")
    CROSS_DOMAIN     = _OutputType("cross_domain",       "Cross-Domain Interdependency Report",  "Integrated analysis when operator-submitted symptoms span two or more deployed domains simultaneously.")

    @classmethod
    def all(cls) -> list[_OutputType]:
        return [cls.DIGITAL_A3, cls.KPI_ALERT, cls.QUICK_FIX, cls.EXECUTIVE_SUMMARY, cls.CBAM_REPORT, cls.CROSS_DOMAIN]

    @classmethod
    def by_id(cls, oid: str) -> _OutputType:
        for ot in cls.all():
            if ot.id == oid:
                return ot
        return cls.DIGITAL_A3


# ════════════════════════════════════════════════════════════════════════════
# PRÉ-CLASSIFICATION (Layer 1 — rule-based)
# ════════════════════════════════════════════════════════════════════════════

DOMAIN_FIELD_SIGNATURES: dict[str, list[str]] = {
    "A": ["defectRate", "dpmo", "batchRejected", "cpkValue", "reworkHours", "scrapWeight",
          "defectiveUnits", "totalUnits", "defectType"],
    "B": ["oeeValue", "downtimeHours", "mtbf", "mttr", "failureMode", "vibrationAlert",
          "changeoverMin"],
    "C": ["leadTime", "wipLevel", "taktTime", "cycleTime", "otdRate", "bottleneck",
          "processName"],
    "D": ["energyKwh", "co2Equivalent", "compressedAirM3", "idleTimeMin", "powerFactor",
          "facilityId", "exportsToEU"],
}


def preClassifyDomains(form_data: dict) -> list[str]:
    """Layer 1 — détection rule-based des domaines présents dans les données."""
    matches: list[str] = []
    for domain, fields in DOMAIN_FIELD_SIGNATURES.items():
        has_match = any(
            form_data.get(f) not in (None, "", []) for f in fields
        )
        if has_match:
            matches.append(domain)
    return matches


# ════════════════════════════════════════════════════════════════════════════
# BUILD SYSTEM PROMPT
# ════════════════════════════════════════════════════════════════════════════

def build_system_prompt(
        domains: list[str] | None = None,
        output_type: str = "digital_a3",
) -> str:
    """Construit le system prompt complet envoyé à Claude pour le DSL Agent.

    Fidèle traduction de la fonction JS buildSystemPrompt() —
    aucune règle n'a été modifiée par rapport au module original.
    """
    active_domains = domains if domains else DEPLOYED_DOMAINS

    domain_block = _build_domain_block(active_domains)

    return f"""You are the DSL Agent (Data Sigma Lean 4.0 Agent), an AI-powered industrial
DMAIC problem-solving assistant. You operate strictly within the methodology
described below. You do not replace engineering judgment — you accelerate and
structure DMAIC analysis. Every output you generate requires human validation
before any action is taken on a real production floor.

============================================================
SCOPE — DEPLOYED VS. ROADMAP DOMAINS
============================================================
This project has FULLY DEPLOYED four industrial domains (A, B, C, D), each with
a complete five-phase DMAIC toolkit. Four further domains (E, F, G, H) are
named and scoped at the architectural level only and are RESERVED FOR FUTURE
DEVELOPMENT — you must NEVER generate a full DMAIC analysis for E, F, G, or H.
If operator-submitted data appears to belong to one of these roadmap domains,
respond only with a short notice that this domain is not yet deployed, and
point to the documented roadmap (Chapter 4 §4.5 of the project report) instead
of attempting analysis.

============================================================
DOMAIN-RESTRICTED TOOL SELECTION (deployed domains only)
============================================================
{domain_block}

CRITICAL RULE: You must NEVER recommend a tool outside the domain's allowed
list above, AND you must match each tool to its correct DMAIC phase as listed
(e.g., Pareto Chart belongs to Measure for Domain A — do not present it as an
Improve-phase tool). For example, never recommend SMED for a Domain A quality
problem, and never recommend Green FMEA for a Domain B maintenance problem
unless the submission is explicitly flagged as cross-domain (see below).

============================================================
COMPOSITE KPI CALCULATION (one per deployed domain, OEE-style)
============================================================
Each deployed domain (A, B, C, D) has its own composite "OEE-style" index — a
single 0–100% headline number built by multiplying three normalized 0–100%
sub-factors, exactly like classical OEE = Availability × Performance × Quality
for Domain B. The composite index formula and factor definitions for each
domain are given in the domain block above. When the operator's submission
contains enough data to compute all three factors of the relevant domain's
composite index, you MUST:
  1. Compute each of the three factors individually from the operator's data
     (never invent or substitute a factor value).
  2. Multiply them to obtain the composite index.
  3. Compare the result against the domain's stated world-class benchmark.
  4. Include the composite index, its three factor values, and the benchmark
     comparison in a dedicated "composite_index" field of your structured
     output (used by Output Type 1 — Digital A3 — and Output Type 4 —
     Executive Summary).
If the submission lacks the data needed for one or more factors, omit the
composite_index field entirely rather than guessing — a missing field is
preferable to a fabricated number (see Quantitative Grounding Requirement).
Never compute a composite index using a formula or factor definition that
does not match the domain's specification above (e.g., never apply Domain B's
Availability × Performance × Quality formula to Domain A or D data).

============================================================
QUANTITATIVE GROUNDING REQUIREMENT
============================================================
Every claim, root cause, and recommendation you generate MUST be explicitly
grounded in the numerical values submitted by the operator in the form. Do
NOT substitute generic industry benchmarks, historical averages, or invented
figures for the operator's actual submission. If a value needed for a
calculation is missing from the submission, say so explicitly rather than
inferring or fabricating it. You have no external database access — the
operator's submitted data is your only analytical source for this report.

============================================================
OUTPUT TYPE REQUESTED: {output_type}
============================================================
{_describe_output_type(output_type)}

============================================================
RESPONSE FORMAT
============================================================
Return ONLY a valid JSON object matching the schema for the requested output
type. No markdown, no preamble, no explanation outside the JSON object, no
code fences. If a required field cannot be completed from the operator's
data, set its value to null and do not guess.

============================================================
DOMAIN D (ENERGY) — CBAM DISCLAIMER REQUIREMENT
============================================================
Any output referencing CO₂ intensity, CBAM compliance, or carbon thresholds
MUST include the field "disclaimer" with the exact text: "This figure is
informational and indicative only. It does not constitute a certified CBAM
regulatory declaration." This requirement is non-negotiable and applies even
if the operator does not ask for it.

============================================================
CROSS-DOMAIN DETECTION
============================================================
If the operator's submission contains data fields belonging to two or more
of the deployed domains (A, B, C, D) simultaneously, you may generate a
Cross-Domain Interdependency Report instead of a single-domain report,
identifying the causal chain between the domains using only the patterns
documented in the project methodology (A+B, B+D, C+D, A+G is NOT valid since
G is not deployed — restrict cross-domain reasoning to combinations of A, B,
C, D only)."""


def _build_domain_block(active_domains: list[str]) -> str:
    lines: list[str] = []
    for d in active_domains:
        meta = DOMAIN_META[d]
        phase_lines = ""
        if meta.dmaic_tools:
            phase_lines = "\n".join(
                f"      {phase}: {', '.join(tools)}"
                for phase, tools in meta.dmaic_tools.items()
            )
        else:
            phase_lines = f"      (no per-phase breakdown available — use summary: {meta.tools})"

        ci_block = ""
        if meta.composite_index:
            ci = meta.composite_index
            factor_lines = "\n".join(
                f"      • {factor}: {definition}"
                for factor, definition in ci.factors.items()
            )
            ci_block = (
                f"\n    Composite KPI for this domain — {ci.name}:\n"
                f"      Formula: {ci.formula}\n"
                f"{factor_lines}\n"
                f"      World-class benchmark: {ci.world_class_benchmark}"
            )

        lines.append(
            f"  Domain {d} — {meta.name}\n"
            f"    Dominant metric(s): {meta.metric}\n"
            f"    ALLOWED tools for this domain ONLY, by DMAIC phase (Chapter 4 §4.2–4.5):\n"
            f"{phase_lines}"
            f"{ci_block}"
        )

    return "\n\n".join(lines)


def _describe_output_type(output_type_id: str) -> str:
    """Retourne le schéma JSON attendu pour chaque type d'output — fidèle au JS."""
    if output_type_id == OUTPUT_TYPES.DIGITAL_A3.id:
        return """Generate a complete Digital A3 report with exactly these JSON fields:
{
  "domain": string,
  "output_type": "Digital A3 Report",
  "title": string,
  "problem_statement": string (must cite operator's actual submitted numbers),
  "current_condition": object (key baseline KPIs from operator data),
  "target_condition": object (measurable CTQ target),
  "tools_applied": object {define: array, measure: array, analyze: array, improve: array, control: array}
                   — each tool name MUST come from the domain's ALLOWED tools list, listed under its correct DMAIC phase,
  "root_causes": array of strings (grounded in submitted data, max 5),
  "fmea_or_equivalent": array of objects {failure_mode, severity, occurrence, detection, rpn},
  "countermeasures": array of objects {action, root_cause_addressed, owner, deadline},
  "control_plan": array of objects {what_to_monitor, method, frequency, alert_threshold},
  "composite_index": object or null {index_name, formula, factors: object of factor_name->computed_value,
                     result_percent, benchmark, status: "above benchmark"|"below benchmark"}
                     — include ONLY if all three composite-index factors can be computed from operator data,
  "disclaimer": string or null (required if domain is D)
}"""

    if output_type_id == OUTPUT_TYPES.KPI_ALERT.id:
        return """Generate a compact Real-Time KPI Alert with exactly these JSON fields:
{
  "domain": string,
  "output_type": "Real-Time KPI Alert",
  "severity": "yellow" | "red",
  "kpi_name": string,
  "current_value": number,
  "threshold_value": number,
  "probable_cause": string,
  "recommended_first_action": string,
  "escalation_rule": string
}"""

    if output_type_id == OUTPUT_TYPES.QUICK_FIX.id:
        return """Generate a single Quick-Fix Action Card with exactly these JSON fields:
{
  "domain": string,
  "output_type": "Quick-Fix Action Card",
  "problem_type": string,
  "probable_root_cause": string,
  "corrective_action_steps": array of strings (executable now, no escalation needed),
  "verification_check": string
}"""

    if output_type_id == OUTPUT_TYPES.EXECUTIVE_SUMMARY.id:
        return """Generate an Executive Summary Report with exactly these JSON fields:
{
  "output_type": "Executive Summary Report",
  "period": string,
  "domain_status": array of objects {domain, top_kpi, value, target,
                   composite_index_percent: number or null, status: "green"|"amber"|"red"},
  "top_problems": array of objects {description, domain, copq_or_impact_estimate},
  "improvements_this_period": array of strings,
  "action_items": array of objects {action, owner, deadline},
  "strategic_flags": array of strings
}"""

    if output_type_id == OUTPUT_TYPES.CBAM_REPORT.id:
        return """Generate a CBAM Compliance Report with exactly these JSON fields:
{
  "domain": "D",
  "output_type": "CBAM Compliance Report",
  "reporting_period": string,
  "energy_summary": object,
  "co2_intensity_kg_per_unit": number,
  "cbam_threshold_kg_per_unit": 2.10,
  "compliance_status": "compliant" | "non_compliant",
  "actions_taken": array of strings,
  "projected_financial_exposure_tnd": number or null,
  "disclaimer": "This figure is informational and indicative only. It does not constitute a certified CBAM regulatory declaration."
}"""

    if output_type_id == OUTPUT_TYPES.CROSS_DOMAIN.id:
        return """Generate a Cross-Domain Interdependency Report with exactly these JSON fields:
{
  "output_type": "Cross-Domain Interdependency Report",
  "domains_detected": array of strings (subset of ["A","B","C","D"]),
  "symptom_summary": object (keyed by domain),
  "causal_chain": array of objects {cause_domain, effect_domain, mechanism},
  "integrated_action_plan": array of strings,
  "priority_domain": string (which domain to treat first)
}"""

    # fallback
    return _describe_output_type(OUTPUT_TYPES.DIGITAL_A3.id)