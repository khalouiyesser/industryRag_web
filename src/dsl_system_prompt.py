"""
dsl_system_prompt.py — Port Python du module DSL Agent, aligné sur le rapport PFE
(Tables 48–55, Chapter 3 §3.4).

Modifications vs. version précédente :
  - DOMAIN_FIELD_SIGNATURES : alignés sur Table 48 (noms snake_case du rapport)
  - Domaines E/F/G/H : signatures complètes (Table 48)
  - Domaine X (Cross-Domain) ajouté
  - _describe_output_type() : schémas JSON réécrits pour correspondre exactement
    à la structure décrite dans Tables 49–54 du rapport
  - Digital A3 : 8 sections exactes (titre+owner, background, current_condition,
    target_condition, root_cause_analysis, countermeasures, implementation_plan,
    results_and_control_plan)
  - Real-Time KPI Alert : 5 champs (alert_type, severity, kpi_status,
    probable_cause, recommended_first_action, escalation_rule)
  - Quick-Fix Action Card : 4 champs (problem_type, probable_root_cause,
    corrective_action_steps, verification_check)
  - Executive Summary : 5 sections (performance_snapshot, top_problems,
    improvements_this_period, action_items_due, strategic_flags)
  - CBAM Compliance Report : 7 sections (reporting_period, product_categories,
    energy_summary, co2_calculation, co2_intensity, compliance_status,
    actions_taken, projected_financial_exposure)
  - Cross-Domain Report : 4 sections + estimated_amplification_factor
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import NamedTuple


# ════════════════════════════════════════════════════════════════════════════
# DOMAINES
# ════════════════════════════════════════════════════════════════════════════

DEPLOYED_DOMAINS: list[str] = ["A", "B", "C", "D"]
ROADMAP_DOMAINS:  list[str] = ["E", "F", "G", "H"]
ALL_DOMAINS:      list[str] = ["A", "B", "C", "D", "E", "F", "G", "H"]


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
        tools="FMEA · Pareto · Fishbone 5M · SPC P-chart · Poka-Yoke · 5 Whys",
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
                "Conformance Rate":  "First Pass Yield = Good units / Total units produced",
                "Process Stability": "Share of samples within SPC control limits over the measurement window",
                "Capability Score":  "min(Cpk / 1.33, 1.0) — Cpk normalized against the 1.33 world-class threshold, capped at 100%",
            },
            world_class_benchmark="≥ 85%",
        ),
    ),
    "B": DomainMeta(
        name="Maintenance & OEE",
        metric="OEE, MTBF, MTTR",
        tools="FMEA RPN · TPM · SMED · OEE A×P×Q · MTBF/MTTR analysis",
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
                "Quality":       "Good units / Total units produced",
            },
            world_class_benchmark="≥ 85%",
        ),
    ),
    "C": DomainMeta(
        name="Production Flow & Lead Time",
        metric="Lead Time, WIP, Takt Time",
        tools="VSM · Kanban sizing · Takt analysis · Heijunka · Line balancing",
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
                "Takt Adherence":        "min(Takt Time / Actual bottleneck cycle time, 1.0) — capped at 100%",
                "Flow Efficiency":       "Value-Added Time / Total Lead Time (VA ratio from VSM)",
                "On-Time Delivery Rate": "On-time deliveries / Total deliveries",
            },
            world_class_benchmark="≥ 60%",
        ),
    ),
    "D": DomainMeta(
        name="Energy & Environment",
        metric="kWh/unit, CO₂/shift, Energy Efficiency",
        tools="Green FMEA · E-VSM · ISO 50001 SPC · Energy Poka-Yoke · CBAM KPI",
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
                "Energy Availability":    "1 − (Idle Energy Ratio) — share of energy going to actual production vs. idle/standby loss",
                "Energy Efficiency":      "min(Benchmark kWh/unit / Actual kWh/unit, 1.0) — capped at 100%",
                "CBAM Compliance Factor": "min(2.10 kg CO2/unit / Actual CO2 intensity, 1.0) — 100% when compliant, below 100% otherwise",
            },
            world_class_benchmark="≥ 70%",
        ),
    ),
    # ── Roadmap domains ─────────────────────────────────────────────────────
    "E": DomainMeta(
        name="Supply Chain & Logistics",
        metric="Bullwhip ratio, OTIF, Supplier OTD",
        tools="ABC-XYZ · Kanban Supplier · SCOR · S&OP · Extended VSM",
        deployed=False,
    ),
    "F": DomainMeta(
        name="Safety & Ergonomics",
        metric="TRIR, near-miss rate, Ergonomic score",
        tools="HFMEA · Bowtie · REBA/RULA · Safety Poka-Yoke · 5 Whys safety",
        deployed=False,
    ),
    "G": DomainMeta(
        name="Human Performance & Training",
        metric="Qualification Cp/Cpk, Skills Matrix",
        tools="Skills Matrix · Cp/Cpk by operator · Kirkpatrick · TWI · OJT",
        deployed=False,
    ),
    "H": DomainMeta(
        name="Cost & Financial Performance",
        metric="COPQ, PAF model",
        tools="PAF Model · COPQ analysis · ABC Costing · Financial A3",
        deployed=False,
    ),
}


# ════════════════════════════════════════════════════════════════════════════
# OUTPUT TYPES  (6 types — Table 49 à 54)
# ════════════════════════════════════════════════════════════════════════════

class _OutputType(NamedTuple):
    id: str
    label: str
    description: str
    trigger: str
    estimated_time: str


class OUTPUT_TYPES:
    DIGITAL_A3 = _OutputType(
        id="digital_a3",
        label="Digital A3 Report",
        description="Primary DMAIC output — root cause analysis, countermeasures, control plan (8 sections).",
        trigger="Significant/recurring deviation requiring formal DMAIC documentation",
        estimated_time="< 45 seconds",
    )
    KPI_ALERT = _OutputType(
        id="kpi_alert",
        label="Real-Time KPI Alert",
        description="Compact 5-field alert for threshold exceedance requiring immediate operator response.",
        trigger="KPI crosses pre-defined alert threshold during production (< 30 min)",
        estimated_time="< 5 seconds",
    )
    QUICK_FIX = _OutputType(
        id="quick_fix",
        label="Quick-Fix Action Card",
        description="4-field action card for minor, well-understood, single-root-cause problems.",
        trigger="Minor known problem, single root cause, first occurrence this shift",
        estimated_time="< 15 seconds",
    )
    EXECUTIVE_SUMMARY = _OutputType(
        id="executive_summary",
        label="Executive Summary Report",
        description="5-section management snapshot across all deployed domains (traffic-light status).",
        trigger="Management review request — shift, day, week, or month",
        estimated_time="< 30 seconds",
    )
    CBAM_REPORT = _OutputType(
        id="cbam_report",
        label="CBAM Compliance Report",
        description="7-section Domain D CO₂/energy compliance report (informational — not official CBAM declaration).",
        trigger="Monthly/quarterly regulatory reporting for EU-exported products",
        estimated_time="< 60 seconds",
    )
    CROSS_DOMAIN = _OutputType(
        id="cross_domain",
        label="Cross-Domain Interdependency Report",
        description="4-section report identifying cascading effects across 2+ domains simultaneously.",
        trigger="Symptoms or data fields from 2+ domains detected simultaneously",
        estimated_time="< 60 seconds",
    )

    @classmethod
    def all(cls) -> list[_OutputType]:
        return [
            cls.DIGITAL_A3, cls.KPI_ALERT, cls.QUICK_FIX,
            cls.EXECUTIVE_SUMMARY, cls.CBAM_REPORT, cls.CROSS_DOMAIN,
        ]

    @classmethod
    def by_id(cls, oid: str) -> _OutputType:
        for ot in cls.all():
            if ot.id == oid:
                return ot
        return cls.DIGITAL_A3


# ════════════════════════════════════════════════════════════════════════════
# PRÉ-CLASSIFICATION LAYER 1  (Table 48 — trigger keywords/fields)
# ════════════════════════════════════════════════════════════════════════════

# Clés alignées sur Table 48 du rapport (snake_case exact)
DOMAIN_FIELD_SIGNATURES: dict[str, list[str]] = {
    "A": [
        "defect_rate", "batch_rejected", "cpk_value", "rework_hours", "scrap_weight",
        # compatibilité camelCase du frontend existant
        "defectRate", "cpkValue", "reworkHours", "defectiveUnits", "totalUnits", "defectType",
    ],
    "B": [
        "oee_value", "downtime_hours", "mtbf", "failure_mode", "vibration_alert", "mttr",
        "oeeValue", "downtimeHours", "failureMode", "vibrationAlert", "changeoverMin",
    ],
    "C": [
        "lead_time", "wip_level", "takt_time", "cycle_time", "otd_rate", "bottleneck",
        "leadTime", "wipLevel", "taktTime", "cycleTime", "otdRate", "processName",
    ],
    "D": [
        "energy_kwh", "co2_equivalent", "compressed_air_m3", "idle_time", "power_factor",
        "energyKwh", "co2Equivalent", "compressedAirM3", "idleTimeMin", "powerFactor",
        "facilityId", "exportsToEU",
    ],
    # Roadmap — signatures connues mais domaines non déployés
    "E": ["supplier_otd", "bullwhip_ratio", "safety_stock", "stockout", "demand_variability"],
    "F": ["incident_rate", "near_miss", "ergonomic_score", "reba_score", "lost_time"],
    "G": ["skills_score", "training_hours", "cpk_operator", "ojt_completion", "kirkpatrick"],
    "H": ["copq_total", "paf_prevention", "paf_failure", "cost_per_defect", "abc_cost"],
}


def preClassifyDomains(form_data: dict) -> list[str]:
    """Layer 1 — détection rule-based des domaines présents dans form_data.

    Retourne la liste des domaines détectés (peut être vide ou contenir 2+
    domaines → Cross-Domain). Inclut les domaines roadmap pour déclencher
    le message de refus approprié côté prompt.
    """
    matches: list[str] = []
    for domain, fields in DOMAIN_FIELD_SIGNATURES.items():
        has_match = any(
            form_data.get(f) not in (None, "", [], 0) for f in fields
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
    """Construit le system prompt complet pour le DSL Agent.

    Intègre :
      - La restriction de domaines déployés vs roadmap (Table 48)
      - Les outils DMAIC autorisés par domaine et par phase
      - Les formules de calcul des index composites OEE-style
      - Le schéma JSON exact exigé pour chaque output type (Tables 49–54)
      - Les règles anti-hallucination (quantitative grounding, CBAM disclaimer)
    """
    active_domains = [d for d in (domains or DEPLOYED_DOMAINS) if d in DEPLOYED_DOMAINS]
    if not active_domains:
        active_domains = DEPLOYED_DOMAINS

    domain_block = _build_domain_block(active_domains)

    return f"""You are the DSL Agent (Data Sigma Lean 4.0 Agent), an AI-powered industrial
DMAIC problem-solving assistant. You operate strictly within the methodology
described below. You do not replace engineering judgment — you accelerate and
structure DMAIC analysis. Every output you generate requires human validation
before any action is taken on a real production floor.

============================================================
SCOPE — DEPLOYED VS. ROADMAP DOMAINS  (Table 48)
============================================================
FULLY DEPLOYED (complete DMAIC toolkit): A (Quality), B (Maintenance/OEE),
C (Production Flow), D (Energy & Environment).

ROADMAP ONLY — NOT ANALYTICALLY DEPLOYED: E (Supply Chain), F (Safety &
Ergonomics), G (Human Performance), H (Cost & Financial).

If operator data belongs to a roadmap domain (E, F, G, H), respond ONLY with:
{{"output_type": "Domain Not Deployed", "domain": "<letter>",
  "message": "Domain <letter> (<name>) is not yet deployed analytically.
  See project roadmap — Chapter 4 §4.5.",
  "roadmap_note": "Full deployment planned in Phase 2."}}

If fields from 2+ domains are detected simultaneously → activate Output Type 6
(Cross-Domain Interdependency Report) regardless of the requested output type.

============================================================
DOMAIN-RESTRICTED TOOL SELECTION
============================================================
{domain_block}

CRITICAL RULE: NEVER recommend a tool outside the domain's allowed list above.
NEVER apply a tool to the wrong DMAIC phase (e.g., Pareto is a Measure tool for
Domain A — never list it under Analyze or Improve). NEVER use SMED for a Domain
A quality problem. NEVER use Green FMEA for a Domain B maintenance problem unless
explicitly cross-domain.

============================================================
COMPOSITE KPI CALCULATION — OEE-STYLE INDEX (one per deployed domain)
============================================================
Each deployed domain has a composite index = Factor1 × Factor2 × Factor3.
All three factors must be computable from the operator's submitted data.

RULES:
  1. Compute each factor individually from operator data — NEVER invent values.
  2. Multiply to obtain composite index (0–100%).
  3. Compare to domain's world-class benchmark.
  4. Include in "composite_index" field of Digital A3 and Executive Summary.
  5. If ANY factor cannot be computed → set composite_index to null entirely.
  6. NEVER apply one domain's formula to another domain's data.

============================================================
QUANTITATIVE GROUNDING REQUIREMENT (anti-hallucination rule)
============================================================
EVERY claim, root cause, and recommendation MUST cite the operator's actual
submitted numbers. DO NOT substitute generic benchmarks or invented figures.
If a value is missing from the submission, say so explicitly — do NOT infer.
The operator's form data is your ONLY analytical source for this report.
You have NO external database access.

============================================================
OUTPUT TYPE REQUESTED: {output_type}
============================================================
{_describe_output_type(output_type)}

============================================================
RESPONSE FORMAT — ABSOLUTE RULE
============================================================
Return ONLY a valid JSON object. NO markdown. NO preamble. NO explanation
outside the JSON. NO code fences (no ```json). NO trailing text after the
closing brace. If a field cannot be completed from operator data → null.
NEVER guess or fabricate field values.

============================================================
DOMAIN D — CBAM DISCLAIMER (non-negotiable)
============================================================
ANY output referencing CO₂ intensity or CBAM compliance MUST include:
"disclaimer": "This figure is informational and indicative only. It does not
constitute a certified CBAM regulatory declaration. Official CBAM declarations
must be prepared by a certified CBAM declarant following EU Commission
verification procedures."

============================================================
CROSS-DOMAIN LOGIC
============================================================
Valid cross-domain patterns (deployed domains only): A+B, A+C, A+D, B+C, B+D,
C+D, A+B+C, A+B+D, B+C+D, A+B+C+D.
INVALID (G not deployed): A+G, B+G, C+G, D+G.
For cross-domain: identify causal chain (D→B→A→C is the most common cascade).
Include estimated_amplification_factor where quantifiable from operator data."""


# ════════════════════════════════════════════════════════════════════════════
# DOMAIN BLOCK BUILDER
# ════════════════════════════════════════════════════════════════════════════

def _build_domain_block(active_domains: list[str]) -> str:
    lines: list[str] = []
    for d in active_domains:
        meta = DOMAIN_META[d]
        if meta.dmaic_tools:
            phase_lines = "\n".join(
                f"      {phase}: {', '.join(tools)}"
                for phase, tools in meta.dmaic_tools.items()
            )
        else:
            phase_lines = f"      (roadmap — not deployed)"

        ci_block = ""
        if meta.composite_index:
            ci = meta.composite_index
            factor_lines = "\n".join(
                f"        • {factor}: {definition}"
                for factor, definition in ci.factors.items()
            )
            ci_block = (
                f"\n    Composite KPI — {ci.name}:\n"
                f"      Formula: {ci.formula}\n"
                f"{factor_lines}\n"
                f"      World-class benchmark: {ci.world_class_benchmark}"
            )

        lines.append(
            f"  Domain {d} — {meta.name}\n"
            f"    Dominant metric(s): {meta.metric}\n"
            f"    ALLOWED DMAIC tools (by phase):\n"
            f"{phase_lines}"
            f"{ci_block}"
        )
    return "\n\n".join(lines)


# ════════════════════════════════════════════════════════════════════════════
# OUTPUT TYPE SCHEMAS  (Tables 49–54 du rapport)
# ════════════════════════════════════════════════════════════════════════════

def _describe_output_type(output_type_id: str) -> str:

    # ── Output Type 1 — Digital A3 Report (Table 49) ──────────────────────
    if output_type_id == OUTPUT_TYPES.DIGITAL_A3.id:
        return """OUTPUT TYPE 1 — DIGITAL A3 REPORT (8 mandatory sections, Table 49)
Trigger: significant/recurring problem requiring full DMAIC root cause analysis.
All 8 sections required. Quantitative data mandatory in sections 3 and 8.

Generate a JSON object with EXACTLY these fields:
{
  "output_type": "Digital A3 Report",
  "domain": string,                         // e.g. "A", "B", "C", "D"

  // Section 1 — Title & Owner
  "title": string,                          // problem title, specific and measurable
  "owner": string,                          // responsible engineer / team role

  // Section 2 — Background & Business Case
  "background": string,                     // context and business justification
  "business_case": string,                  // quantified financial or quality impact

  // Section 3 — Current Condition (KPI baseline — quantitative data mandatory)
  "current_condition": {
    "kpi_baseline": object,                 // key: KPI name, value: current numeric value with unit
    "process_description": string,          // brief description of current process state
    "deviation_magnitude": string           // e.g. "7.7× above target" — must cite operator numbers
  },

  // Section 4 — Target Condition (measurable CTQ)
  "target_condition": {
    "ctq_target": object,                   // key: KPI name, value: target value with unit
    "deadline": string,                     // target achievement date
    "success_criteria": string              // measurable acceptance condition
  },

  // Section 5 — Root Cause Analysis (5 Whys + Fishbone/FMEA)
  "root_cause_analysis": {
    "five_whys": [                          // exactly 5 steps
      {"step": 1, "why": string, "answer": string},
      {"step": 2, "why": string, "answer": string},
      {"step": 3, "why": string, "answer": string},
      {"step": 4, "why": string, "answer": string},
      {"step": 5, "why": string, "answer": string, "root_cause": string}
    ],
    "fishbone_5m": {
      "machine":     array of strings,
      "method":      array of strings,
      "manpower":    array of strings,
      "material":    array of strings,
      "environment": array of strings
    },
    "fmea": [                               // top failure modes
      {
        "failure_mode": string,
        "effect": string,
        "severity": integer,               // 1-10
        "cause": string,
        "occurrence": integer,             // 1-10
        "current_control": string,
        "detection": integer,              // 1-10
        "rpn": integer                     // severity × occurrence × detection
      }
    ]
  },

  // Section 6 — Countermeasures (one per root cause)
  "countermeasures": [
    {
      "action": string,                    // specific corrective action
      "lean_tool": string,                 // tool from domain's ALLOWED list only
      "root_cause_addressed": string,
      "owner": string,
      "deadline": string,
      "expected_impact": string            // quantified expected improvement
    }
  ],

  // Section 7 — Implementation Plan
  "implementation_plan": [
    {
      "phase": string,                     // "Week 1", "Week 2–3", etc.
      "actions": array of strings,
      "owner": string,
      "milestone": string
    }
  ],

  // Section 8 — Results & Control Plan (quantitative data mandatory)
  "results_and_control_plan": {
    "expected_results": object,            // key: KPI name, value: projected value after improvement
    "control_plan": [
      {
        "what_to_monitor": string,
        "method": string,                  // e.g. "SPC P-Chart", "Audit", "I-MR Chart"
        "frequency": string,               // e.g. "Daily", "Per shift", "Weekly"
        "alert_threshold": string,         // trigger value for escalation
        "responsible": string
      }
    ],
    "sustainability_actions": array of strings  // actions to prevent recurrence
  },

  // Composite KPI (OEE-style — compute ONLY if all 3 factors available)
  "composite_index": {
    "index_name": string,                  // e.g. "Quality Index (QI)"
    "formula": string,
    "factors": {
      "<factor_name>": "<computed_value_with_unit>"
      // one entry per factor — use operator's actual numbers
    },
    "result_percent": number,              // composite result 0–100
    "benchmark": string,                   // e.g. "≥ 85%"
    "status": "above benchmark" | "below benchmark"
  },                                       // SET TO null IF ANY FACTOR IS MISSING

  "disclaimer": string | null             // REQUIRED if domain is D
}"""

    # ── Output Type 2 — Real-Time KPI Alert (Table 50) ────────────────────
    if output_type_id == OUTPUT_TYPES.KPI_ALERT.id:
        return """OUTPUT TYPE 2 — REAL-TIME KPI ALERT (5-field compact alert, Table 50)
Trigger: KPI threshold exceedance requiring immediate operator response (< 5 min).
Severity: Yellow = warning threshold crossed; Red = critical threshold crossed.

Generate a JSON object with EXACTLY these fields:
{
  "output_type": "Real-Time KPI Alert",
  "domain": string,

  // Field 1 — Alert type + severity
  "alert_type": string,                    // e.g. "Quality SPC Breach", "OEE Drop", "Energy Spike"
  "severity": "yellow" | "red",           // yellow = warning, red = critical

  // Field 2 — Affected KPI + current value vs threshold
  "kpi_status": {
    "kpi_name": string,
    "current_value": number,
    "unit": string,
    "threshold_value": number,
    "deviation_percent": number            // (current - threshold) / threshold × 100
  },

  // Field 3 — Probable immediate cause (rule-based pattern matching)
  "probable_cause": string,               // most likely cause from operator data

  // Field 4 — Recommended first action (single, immediately executable)
  "recommended_first_action": {
    "action": string,                      // what to do RIGHT NOW
    "time_limit_minutes": integer | null,  // time before escalation
    "responsible": string                  // operator role
  },

  // Field 5 — Escalation rule
  "escalation_rule": string               // e.g. "If not resolved in 10 min → escalate to supervisor + trigger Digital A3"
}"""

    # ── Output Type 3 — Quick-Fix Action Card (Table 51) ──────────────────
    if output_type_id == OUTPUT_TYPES.QUICK_FIX.id:
        return """OUTPUT TYPE 3 — QUICK-FIX ACTION CARD (4-field single card, Table 51)
Trigger: minor, well-understood, single-root-cause problem; operator can fix this shift.
Designed for technician execution without supervisor escalation.

Generate a JSON object with EXACTLY these fields:
{
  "output_type": "Quick-Fix Action Card",
  "domain": string,

  // Field 1 — Problem type + KPI deviation
  "problem_type": string,                  // e.g. "Minor tool wear defect"
  "kpi_deviation": string,                 // e.g. "3 surface scratches on PL-03 after tool change"

  // Field 2 — Most probable root cause
  "probable_root_cause": string,           // from operator data or historical pattern — cite source

  // Field 3 — Corrective action (specific, step-by-step, executable NOW)
  "corrective_action_steps": [
    {"step": integer, "action": string, "reference": string | null}
    // reference = standard work procedure ref if applicable (e.g. "SW-PL03-02")
  ],

  // Field 4 — Verification check (confirm action worked before end of shift)
  "verification_check": {
    "method": string,                      // how to verify
    "acceptance_criterion": string,        // pass/fail criterion
    "timing": string                       // e.g. "Before end of shift", "After 5-unit quality check"
  },

  "escalation_trigger": string             // condition that requires escalating to Digital A3
}"""

    # ── Output Type 4 — Executive Summary Report (Table 52) ───────────────
    if output_type_id == OUTPUT_TYPES.EXECUTIVE_SUMMARY.id:
        return """OUTPUT TYPE 4 — EXECUTIVE SUMMARY REPORT (5 sections, Table 52)
Trigger: management review request (shift handover, daily/weekly/monthly review).
Format: management-readable — no technical Lean jargon; quantitative data only;
traffic-light status (Green / Amber / Red) per domain. One-page equivalent.

Generate a JSON object with EXACTLY these fields:
{
  "output_type": "Executive Summary Report",
  "period": string,                        // e.g. "Week 23 — June 2025"
  "generated_for": string,                 // e.g. "Monday morning management review"

  // Section 1 — Performance snapshot: top 3 KPIs per deployed domain vs. target (traffic-light)
  "performance_snapshot": [
    {
      "domain": string,                    // "A", "B", "C", or "D"
      "domain_name": string,
      "top_kpis": [
        {
          "kpi": string,
          "current_value": string,         // value + unit
          "target": string,                // target + unit
          "status": "green" | "amber" | "red"
        }
      ],
      "composite_index_percent": number | null,
      "composite_index_name": string | null,
      "domain_status": "green" | "amber" | "red",
      "a3_in_progress": boolean
    }
  ],

  // Section 2 — Top 3 active problems with A3 status + estimated COPQ impact
  "top_problems": [
    {
      "rank": integer,
      "description": string,
      "domain": string,
      "a3_status": "open" | "in_progress" | "closed" | null,
      "copq_or_impact_estimate": string    // e.g. "~12,000 TND/month in rework"
    }
  ],

  // Section 3 — Key improvements achieved this period (before/after KPI pairs)
  "improvements_this_period": [
    {
      "description": string,
      "kpi_before": string,
      "kpi_after": string,
      "domain": string
    }
  ],

  // Section 4 — Action items due this week (owner + deadline)
  "action_items_due": [
    {
      "action": string,
      "domain": string,
      "owner": string,
      "deadline": string,
      "priority": "high" | "medium" | "low"
    }
  ],

  // Section 5 — Strategic flags (CBAM issues, OEE < 70%, recurring Domain A problems)
  "strategic_flags": [
    {
      "flag": string,                      // e.g. "OEE below 70% — Domain B A3 required"
      "domain": string,
      "severity": "critical" | "warning" | "info"
    }
  ]
}"""

    # ── Output Type 5 — CBAM Compliance Report (Table 53) ─────────────────
    if output_type_id == OUTPUT_TYPES.CBAM_REPORT.id:
        return """OUTPUT TYPE 5 — CBAM COMPLIANCE REPORT (7 sections, Table 53 — Domain D exclusively)
Trigger: monthly/quarterly regulatory reporting for CO₂ embedded content (EU exports).
Required by: EU Regulation (EU) 2023/956. Full financial charge from January 1, 2026.
IMPORTANT: This report is informational and indicative. NOT official CBAM documentation.

Generate a JSON object with EXACTLY these fields:
{
  "output_type": "CBAM Compliance Report",
  "domain": "D",

  // Section 1 — Reporting period and covered product categories
  "reporting_period": string,              // e.g. "May 2025"
  "product_categories": array of strings, // covered product categories

  // Section 2 — Energy consumption summary by source
  "energy_summary": {
    "electricity_kwh": number | null,
    "compressed_air_kwh_equivalent": number | null,
    "thermal_energy_kwh": number | null,
    "total_kwh": number | null,
    "kwh_per_unit": number | null,
    "benchmark_kwh_per_unit": 2.90,
    "units_produced": number | null
  },

  // Section 3 — CO₂ equivalent calculation by emission factor
  "co2_calculation": {
    "electricity_co2_kg": number | null,   // using STEG grid intensity
    "compressed_air_co2_kg": number | null,
    "process_heat_co2_kg": number | null,
    "total_co2_kg": number | null,
    "emission_factors_used": object        // key: source, value: factor (kg CO2/kWh)
  },

  // Section 4 — CO₂ intensity per unit vs. CBAM threshold
  "co2_intensity_kg_per_unit": number,
  "cbam_threshold_kg_per_unit": 2.10,
  "intensity_vs_threshold_percent": number, // (actual / threshold) × 100

  // Section 5 — CBAM compliance status with gap analysis
  "compliance_status": "compliant" | "non_compliant",
  "compliance_gap_kg_per_unit": number,    // positive = above threshold (non-compliant), negative = margin (compliant)
  "gap_analysis": string,                  // narrative explanation

  // Section 6 — CO₂ reduction actions taken this period with quantified impact
  "actions_taken": [
    {
      "action": string,
      "co2_reduction_kg_per_unit": number | null,
      "implementation_date": string | null
    }
  ],

  // Section 7 — Projected CBAM financial exposure if non-compliant
  "projected_financial_exposure": {
    "annual_units_produced": number | null,
    "excess_co2_per_unit_kg": number | null,
    "total_excess_co2_annual_tonnes": number | null,
    "eu_ets_price_per_tonne_eur": number | null,     // indicative
    "total_cbam_charge_eur": number | null,
    "total_cbam_charge_tnd": number | null
  },

  "disclaimer": "This figure is informational and indicative only. It does not constitute a certified CBAM regulatory declaration. Official CBAM declarations must be prepared by a certified CBAM declarant following EU Commission verification procedures."
}"""

    # ── Output Type 6 — Cross-Domain Interdependency Report (Table 54) ────
    if output_type_id == OUTPUT_TYPES.CROSS_DOMAIN.id:
        return """OUTPUT TYPE 6 — CROSS-DOMAIN INTERDEPENDENCY REPORT (4 sections, Table 54)
Trigger: symptoms or data fields from 2+ domains detected simultaneously.
Purpose: identify cascading effects and feedback loops that single-domain analysis misses.
Most common patterns: A+B (quality ↔ maintenance), B+D (maintenance ↔ energy),
C+D (flow ↔ energy idle waste), A+B+D (full cascade).
Typical chain: Energy degradation (D) → bearing wear (B) → defect rate increase (A) → flow disruption (C).

Generate a JSON object with EXACTLY these fields:
{
  "output_type": "Cross-Domain Interdependency Report",

  // Section 1 — Domain combination detected + individual symptom summary per domain
  "domains_detected": array of strings,   // subset of ["A","B","C","D"] — deployed only

  "symptom_summary": {
    "<domain_letter>": {
      "domain_name": string,
      "key_kpi": string,
      "current_value": string,
      "target_value": string,
      "deviation": string,
      "severity": "critical" | "warning" | "monitor"
    }
    // one entry per detected domain
  },

  // Section 2 — Cross-domain causal chain (directed graph)
  "causal_chain": [
    {
      "step": integer,
      "cause_domain": string,              // "A", "B", "C", or "D"
      "cause_description": string,
      "effect_domain": string,
      "effect_description": string,
      "mechanism": string,                 // physical/operational mechanism linking cause to effect
      "estimated_amplification_factor": number | null  // quantified from operator data if possible
    }
  ],

  // Section 3 — Integrated action plan (addresses multiple root causes simultaneously)
  "integrated_action_plan": [
    {
      "rank": integer,
      "action": string,
      "domains_addressed": array of strings,  // which domains this action fixes
      "lean_tools": array of strings,
      "expected_cross_domain_impact": string,
      "owner": string,
      "deadline": string
    }
  ],

  // Section 4 — Priority matrix (which domain to treat first for max cascade interruption)
  "priority_matrix": {
    "priority_domain": string,             // treat this domain first
    "rationale": string,                   // why this domain is the root node of the cascade
    "treatment_sequence": array of strings // e.g. ["D", "B", "A", "C"] in order
  },

  "disclaimer": string | null             // required if domain D is involved
}"""

    # fallback → digital_a3
    return _describe_output_type(OUTPUT_TYPES.DIGITAL_A3.id)