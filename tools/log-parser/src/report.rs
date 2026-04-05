//! Report formatting — renders a [`ParsedLog`] as human-readable text
//! or machine-readable JSON.

use crate::parser::{ParsedLog, Severity};
use serde_json;

/// Output format for the report.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OutputFormat {
    Text,
    Json,
}

/// Wraps a [`ParsedLog`] and provides rendering methods.
pub struct Report {
    pub log: ParsedLog,
}

impl Report {
    pub fn new(log: ParsedLog) -> Self {
        Self { log }
    }

    /// Returns true if any ERROR-level entries were found.
    pub fn has_failures(&self) -> bool {
        self.log.error_count() > 0
    }

    /// Print the report in the requested format.
    pub fn print(&self, format: OutputFormat) {
        match format {
            OutputFormat::Json => self.print_json(),
            OutputFormat::Text => self.print_text(),
        }
    }

    fn print_text(&self) {
        println!("\n=== Jenkins Build Log Analysis ===");
        println!(
            "Errors: {}  |  Warnings: {}  |  Stages: {}",
            self.log.error_count(),
            self.log.warning_count(),
            self.log.stages.len()
        );

        if let Some(d) = self.log.build_duration_seconds {
            println!("Build duration: {:.1}s", d);
        }

        if let Some(ts) = &self.log.test_summary {
            println!(
                "Tests: {} total | {} passed | {} failed | {} errors | {} skipped",
                ts.total,
                ts.passed(),
                ts.failures,
                ts.errors,
                ts.skipped
            );
        }

        if !self.log.stages.is_empty() {
            println!("\nPipeline stages:");
            for stage in &self.log.stages {
                println!("  → {}", stage);
            }
        }

        let errors: Vec<_> = self
            .log
            .entries
            .iter()
            .filter(|e| e.severity == Severity::Error)
            .collect();

        if !errors.is_empty() {
            println!("\nFailures ({}):", errors.len());
            for e in &errors {
                let stage_label = e
                    .stage
                    .as_deref()
                    .map(|s| format!(" [{}]", s))
                    .unwrap_or_default();
                println!("  L{}{}: {}", e.line_number, stage_label, e.message);
            }
        } else {
            println!("\n✅ No failures detected");
        }

        let warnings: Vec<_> = self
            .log
            .entries
            .iter()
            .filter(|e| e.severity == Severity::Warning)
            .collect();

        if !warnings.is_empty() {
            println!("\nWarnings ({}):", warnings.len());
            for w in warnings.iter().take(10) {
                println!("  L{}: {}", w.line_number, w.message);
            }
            if warnings.len() > 10 {
                println!("  ... and {} more", warnings.len() - 10);
            }
        }
    }

    fn print_json(&self) {
        match serde_json::to_string_pretty(&self.log) {
            Ok(json) => println!("{}", json),
            Err(e) => eprintln!("error serialising report: {}", e),
        }
    }
}
