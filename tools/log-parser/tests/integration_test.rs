//! Integration tests for the log-parser library.
//!
//! Uses realistic Jenkins console output fixtures to validate
//! end-to-end parsing behaviour.

use log_parser::{
    parser::{parse_log, Severity},
    report::{OutputFormat, Report},
};

// ── Fixtures ────────────────────────────────────────────────────────────

const SUCCESSFUL_BUILD: &str = r#"
[Pipeline] Start of Pipeline
[Pipeline] (Checkout)
Checking out https://github.com/example/app.git
[Pipeline] (Build)
Running maven build...
[INFO] Building app 1.0.0
[INFO] Tests run: 42, Failures: 0, Errors: 0, Skipped: 2
[Pipeline] (Deploy)
Deploying to staging environment
Finished: 3.5 minutes
"#;

const FAILED_BUILD: &str = r#"
[Pipeline] Start of Pipeline
[Pipeline] (Checkout)
Checking out repository
[Pipeline] (Build)
[ERROR] Failed to execute goal: compilation failure
[ERROR] src/main/java/App.java:42: error: cannot find symbol
BUILD FAILED
[Pipeline] (Test)
Tests run: 10, Failures: 3, Errors: 1, Skipped: 0
Total time: 120 seconds
"#;

const BUILD_WITH_WARNINGS: &str = r#"
[Pipeline] (Build)
[WARNING] Deprecated API usage in module core
[WARN] Unused import: java.util.List
[INFO] Tests run: 20, Failures: 0, Errors: 0, Skipped: 1
Finished: 45 seconds
"#;

const EXCEPTION_LOG: &str = r#"
[Pipeline] (Test)
Exception in thread "main" java.lang.NullPointerException
    at com.example.Service.process(Service.java:88)
    at com.example.Main.main(Main.java:12)
"#;

// ── Tests ────────────────────────────────────────────────────────────────

#[test]
fn successful_build_has_no_errors() {
    let parsed = parse_log(SUCCESSFUL_BUILD);
    assert_eq!(parsed.error_count(), 0, "successful build should have no errors");
}

#[test]
fn successful_build_extracts_test_summary() {
    let parsed = parse_log(SUCCESSFUL_BUILD);
    let ts = parsed.test_summary.expect("test summary should be present");
    assert_eq!(ts.total, 42);
    assert_eq!(ts.failures, 0);
    assert_eq!(ts.skipped, 2);
    assert_eq!(ts.passed(), 40);
}

#[test]
fn successful_build_extracts_duration() {
    let parsed = parse_log(SUCCESSFUL_BUILD);
    let duration = parsed.build_duration_seconds.expect("duration should be present");
    assert!(
        (duration - 210.0).abs() < 1.0,
        "expected ~210s (3.5 min), got {}",
        duration
    );
}

#[test]
fn successful_build_extracts_stages() {
    let parsed = parse_log(SUCCESSFUL_BUILD);
    assert!(parsed.stages.contains(&"Checkout".to_string()));
    assert!(parsed.stages.contains(&"Build".to_string()));
    assert!(parsed.stages.contains(&"Deploy".to_string()));
}

#[test]
fn failed_build_detects_errors() {
    let parsed = parse_log(FAILED_BUILD);
    assert!(parsed.error_count() > 0, "failed build should have errors");
}

#[test]
fn failed_build_extracts_test_failures() {
    let parsed = parse_log(FAILED_BUILD);
    let ts = parsed.test_summary.expect("test summary should be present");
    assert_eq!(ts.failures, 3);
    assert_eq!(ts.errors, 1);
    assert_eq!(ts.total, 10);
}

#[test]
fn failed_build_extracts_duration_in_seconds() {
    let parsed = parse_log(FAILED_BUILD);
    let duration = parsed.build_duration_seconds.expect("duration should be present");
    assert!(
        (duration - 120.0).abs() < 1.0,
        "expected 120s, got {}",
        duration
    );
}

#[test]
fn warnings_are_classified_correctly() {
    let parsed = parse_log(BUILD_WITH_WARNINGS);
    assert_eq!(parsed.error_count(), 0);
    assert!(parsed.warning_count() >= 2, "should have at least 2 warnings");
    let all_warnings = parsed
        .entries
        .iter()
        .all(|e| e.severity == Severity::Warning);
    assert!(all_warnings, "all entries should be warnings");
}

#[test]
fn java_exception_is_classified_as_error() {
    let parsed = parse_log(EXCEPTION_LOG);
    assert!(parsed.error_count() > 0, "NullPointerException should be an error");
}

#[test]
fn report_has_failures_is_true_for_failed_build() {
    let parsed = parse_log(FAILED_BUILD);
    let report = Report::new(parsed);
    assert!(report.has_failures());
}

#[test]
fn report_has_failures_is_false_for_successful_build() {
    let parsed = parse_log(SUCCESSFUL_BUILD);
    let report = Report::new(parsed);
    assert!(!report.has_failures());
}

#[test]
fn json_output_is_valid_json() {
    let parsed = parse_log(FAILED_BUILD);
    let report = Report::new(parsed);
    // Capture stdout by testing serialisation directly
    let json = serde_json::to_string(&report.log);
    assert!(json.is_ok(), "JSON serialisation should succeed");
    let val: serde_json::Value = serde_json::from_str(&json.unwrap()).unwrap();
    assert!(val.is_object());
    assert!(val["entries"].is_array());
}

#[test]
fn empty_log_produces_empty_result() {
    let parsed = parse_log("");
    assert_eq!(parsed.error_count(), 0);
    assert_eq!(parsed.warning_count(), 0);
    assert!(parsed.test_summary.is_none());
    assert!(parsed.build_duration_seconds.is_none());
}
