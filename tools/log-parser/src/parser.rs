//! Log parsing engine.
//!
//! Processes raw Jenkins console text line by line and extracts
//! structured log entries categorised by severity.

use chrono::{DateTime, Utc};
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::sync::OnceLock;

// ── Regex patterns ──────────────────────────────────────────────────────────

fn re_error() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(r"(?i)(\bERROR\b|\bFAILED\b|\bFAILURE\b|Build failed|FATAL|Exception in thread|java\.lang\.[A-Z]\w+Exception|\bFAIL\b)").unwrap()
    })
}

fn re_warning() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(?i)(\bWARN(ING)?\b|\bDEPRECATED\b)").unwrap())
}

fn re_test_result() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)")
            .unwrap()
    })
}

fn re_duration() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(r"(?i)(?:Finished|Total time):[^\d]*(\d+(?:\.\d+)?)\s*(min(?:ute)?s?|s(?:econds?)?)").unwrap()
    })
}

fn re_stage() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"\[Pipeline\]\s+(?:stage\s+)?\(([^)]+)\)").unwrap())
}

// ── Types ────────────────────────────────────────────────────────────────

/// Severity level of a log entry.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Severity {
    Error,
    Warning,
    Info,
}

/// A single parsed log line with metadata.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogEntry {
    pub line_number: usize,
    pub severity: Severity,
    pub message: String,
    pub stage: Option<String>,
}

/// Aggregated test results extracted from a Jenkins Surefire/JUnit block.
#[derive(Debug, Default, Clone, Serialize, Deserialize)]
pub struct TestSummary {
    pub total: u32,
    pub failures: u32,
    pub errors: u32,
    pub skipped: u32,
}

impl TestSummary {
    pub fn passed(&self) -> u32 {
        self.total.saturating_sub(self.failures + self.errors + self.skipped)
    }
}

/// The complete structured result of parsing a Jenkins log.
#[derive(Debug, Serialize, Deserialize)]
pub struct ParsedLog {
    pub entries: Vec<LogEntry>,
    pub test_summary: Option<TestSummary>,
    pub build_duration_seconds: Option<f64>,
    pub stages: Vec<String>,
    pub parsed_at: DateTime<Utc>,
}

impl ParsedLog {
    pub fn error_count(&self) -> usize {
        self.entries
            .iter()
            .filter(|e| e.severity == Severity::Error)
            .count()
    }

    pub fn warning_count(&self) -> usize {
        self.entries
            .iter()
            .filter(|e| e.severity == Severity::Warning)
            .count()
    }
}

// ── Parser ─────────────────────────────────────────────────────────────────

/// Parse raw Jenkins console log text into a [`ParsedLog`].
pub fn parse_log(raw: &str) -> ParsedLog {
    let mut entries: Vec<LogEntry> = Vec::new();
    let mut test_summary: Option<TestSummary> = None;
    let mut build_duration_seconds: Option<f64> = None;
    let mut stages: Vec<String> = Vec::new();
    let mut current_stage: Option<String> = None;

    for (idx, line) in raw.lines().enumerate() {
        let line_number = idx + 1;

        // Track pipeline stages
        if let Some(cap) = re_stage().captures(line) {
            let stage_name = cap[1].trim().to_string();
            if !stages.contains(&stage_name) {
                stages.push(stage_name.clone());
            }
            current_stage = Some(stage_name);
        }

        // Extract test summary (last one wins if multiple)
        if let Some(cap) = re_test_result().captures(line) {
            let summary = TestSummary {
                total: cap[1].parse().unwrap_or(0),
                failures: cap[2].parse().unwrap_or(0),
                errors: cap[3].parse().unwrap_or(0),
                skipped: cap[4].parse().unwrap_or(0),
            };
            test_summary = Some(summary);
        }

        // Extract build duration
        if let Some(cap) = re_duration().captures(line) {
            let value: f64 = cap[1].parse().unwrap_or(0.0);
            let unit = cap[2].to_lowercase();
            let seconds = if unit.starts_with('m') {
                value * 60.0
            } else {
                value
            };
            build_duration_seconds = Some(seconds);
        }

        // Classify line severity
        let severity = if re_error().is_match(line) {
            Some(Severity::Error)
        } else if re_warning().is_match(line) {
            Some(Severity::Warning)
        } else {
            None
        };

        if let Some(sev) = severity {
            entries.push(LogEntry {
                line_number,
                severity: sev,
                message: line.trim().to_string(),
                stage: current_stage.clone(),
            });
        }
    }

    ParsedLog {
        entries,
        test_summary,
        build_duration_seconds,
        stages,
        parsed_at: Utc::now(),
    }
}
