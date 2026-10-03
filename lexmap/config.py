"""Shared constants and paths for Lexmap."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CORPUS_DIR = RAW / "corpus"
CORPUS_TEXT = CORPUS_DIR / "text"
MANIFEST = CORPUS_DIR / "corpus_manifest.csv"
ADDRESSES = RAW / "data" / "sample_addresses.csv"
SCHEMA = RAW / "schema" / "rule_record.schema.json"
CHANGE_TESTS = RAW / "dev" / "change_tests.json"
SUPPLEMENTARY = ROOT / "data" / "supplementary"
HOUR16 = ROOT / "data" / "hour16"          # organiser mid-event releases (see SUBMISSION_CHECKLIST.md)
CACHE = ROOT / "data" / "cache"
LLM_CACHE = CACHE / "llm"
BUILD = ROOT / "build"            # intermediate artefacts (candidates, reconciled rules)
SUBMISSION = ROOT / "submission"
DOCS = ROOT / "docs"
AUDIT_LOG = SUBMISSION / "audit_log.jsonl"

DEFAULT_AS_OF = "2026-10-01"

CATEGORIES = [
    "rent_increase_limits",
    "just_cause_eviction",
    "security_deposits",
    "application_screening_fees",
    "screening_restrictions",
    "algorithmic_rent_setting",
]
CATEGORY_CODE = {
    "rent_increase_limits": "RENT",
    "just_cause_eviction": "EVICT",
    "security_deposits": "DEP",
    "application_screening_fees": "FEE",
    "screening_restrictions": "SCREEN",
    "algorithmic_rent_setting": "ALG",
}
CATEGORY_LABEL = {
    "rent_increase_limits": "Rent increases",
    "just_cause_eviction": "Just-cause eviction",
    "security_deposits": "Security deposits",
    "application_screening_fees": "Application & screening fees",
    "screening_restrictions": "Screening restrictions",
    "algorithmic_rent_setting": "Algorithmic rent-setting",
}

STATES = {"CA": "California", "NJ": "New Jersey", "MA": "Massachusetts"}
# Canonical jurisdiction strings (schema: state code or "City, ST") -> short code used in rule ids.
JURISDICTION_CODE = {
    "CA": "CA", "NJ": "NJ", "MA": "MA",
    "Los Angeles, CA": "LA",
    "San Francisco, CA": "SF",
    "San Diego, CA": "SD",
    "Berkeley, CA": "BERK",
    "Santa Ana, CA": "SA",
    "Jersey City, NJ": "JC",
    "Hoboken, NJ": "HOB",
    "Newark, NJ": "NWK",
    "Boston, MA": "BOS",
    "Cambridge, MA": "CAM",
}
CITIES = [j for j in JURISDICTION_CODE if "," in j]

# Census "Incorporated Places" NAME -> canonical jurisdiction
CENSUS_PLACE_TO_JURISDICTION = {
    ("CA", "Los Angeles city"): "Los Angeles, CA",
    ("CA", "San Francisco city"): "San Francisco, CA",
    ("CA", "San Diego city"): "San Diego, CA",
    ("CA", "Berkeley city"): "Berkeley, CA",
    ("CA", "Santa Ana city"): "Santa Ana, CA",
    ("NJ", "Jersey City city"): "Jersey City, NJ",
    ("NJ", "Hoboken city"): "Hoboken, NJ",
    ("NJ", "Newark city"): "Newark, NJ",
    ("MA", "Boston city"): "Boston, MA",
    ("MA", "Cambridge city"): "Cambridge, MA",
}

RESULTS = ["applies", "unknown", "superseded", "not_yet_effective", "pending"]

# LLM backend. "claude-cli" uses the locally installed Claude Code CLI (headless, no tools);
# "openrouter" uses OPENROUTER_API_KEY. Override with LEXMAP_LLM_BACKEND.
LLM_BACKEND = os.environ.get("LEXMAP_LLM_BACKEND", "auto")
EXTRACT_MODEL = os.environ.get("LEXMAP_EXTRACT_MODEL", "sonnet")
RECONCILE_MODEL = os.environ.get("LEXMAP_RECONCILE_MODEL", "opus")
OPENROUTER_MODELS = {
    "sonnet": "anthropic/claude-sonnet-5.5",
    "opus": "anthropic/claude-opus-5.5",
}
