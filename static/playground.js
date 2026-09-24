(function () {
  "use strict";

  function $(id) {
    return document.getElementById(id);
  }

  let lastResult = null;

  function num(id) {
    return Number($(id).value) || 0;
  }

  function assess() {
    const checks = [
      ["Identity", $("identity").checked],
      ["Authority", $("authority").checked],
      ["Provenance", $("provenance").checked],
      ["Deterministic policy", $("policy").checked],
      ["Reliability threshold", num("reliability") >= num("target")],
      ["No critical failures", num("critical") === 0],
      ["Review escalation", $("degraded").checked],
      ["Dependency visibility", $("deps").checked],
      ["Runtime control", $("runtime").checked]
    ];

    const failed = checks.filter(function (x) {
      return !x[1];
    });

    const passed = checks.length - failed.length;
    const score = passed / checks.length;

    let state = "ASSURED";

    if (failed.length > 0) {
      state =
        score >= 0.72 && num("critical") === 0
          ? "DEGRADED"
          : "BLOCKED";
    }

    const findings = [];

    if (failed.length) {
      findings.push({
        id: "F-001",
        severity: state === "BLOCKED" ? "critical" : "high",
        title: "Assurance controls failed",
        detail:
          failed.length +
          " of " +
          checks.length +
          " controls failed under the supplied posture.",
        remediation:
          "Resolve failed controls and rerun before unconditional release."
      });
    }

    if (num("toolfail") > 0) {
      findings.push({
        id: "F-002",
        severity: num("toolfail") >= 3 ? "high" : "medium",
        title: "Tool execution failures",
        detail:
          num("toolfail") +
          " tool failure(s) across " +
          num("runs").toLocaleString() +
          " runs.",
        remediation:
          "Exercise timeout, invalid-argument, permission and partial-execution paths."
      });
    }

    if (num("policyfail") > 0) {
      findings.push({
        id: "F-003",
        severity: "critical",
        title: "Policy violations observed",
        detail:
          num("policyfail") +
          " policy violation(s) supplied to the assessment.",
        remediation:
          "Bind the violated policy to the action boundary and require deterministic enforcement."
      });
    }

    if (num("recovery") < 95) {
      findings.push({
        id: "F-004",
        severity: "high",
        title: "Recovery below target",
        detail:
          "Observed recovery rate is " + num("recovery").toFixed(1) + "%.",
        remediation:
          "Test safe termination and human escalation under dependency and tool failure."
      });
    }

    if (num("depinc") > 0) {
      findings.push({
        id: "F-005",
        severity: "medium",
        title: "Dependency impact requires review",
        detail:
          num("depinc") + " dependency incident(s) supplied.",
        remediation:
          "Map incidents to affected systems and invalidate assurance when material dependencies change."
      });
    }

    const result = {
      workflow: {
        name: $("workflow").value.trim() || "Reference AI workflow",
        version: $("version").value.trim() || "unversioned",
        environment: $("environment").value
      },
      assessment: {
        score: Number(score.toFixed(4)),
        percentage: Number((score * 100).toFixed(1)),
        passed: passed,
        total: checks.length,
        state: state,
        test_runs: Math.max(1, num("runs")),
        tool_failures: Math.max(0, num("toolfail")),
        policy_violations: Math.max(0, num("policyfail")),
        recovery_rate: num("recovery") / 100,
        dependency_incidents: Math.max(0, num("depinc"))
      },
      findings: findings,
      evidence: checks.map(function (x, i) {
        return {
          evidence_id: "EV-" + String(i + 1).padStart(3, "0"),
          control: x[0],
          status: x[1] ? "PASS" : "FAIL",
          observation: x[1]
            ? "Control satisfied."
            : "Control failed under supplied posture.",
          provenance: "AAI deterministic reference benchmark"
        };
      }),
      release_decision: {
        action:
          state === "ASSURED"
            ? "ALLOW"
            : state === "DEGRADED"
              ? "REVIEW"
              : "DENY",
        rationale:
          state === "ASSURED"
            ? "All reference controls passed."
            : "Material assurance conditions require review before unconditional release."
      }
    };

    return result;
  }

  function render(result) {
    lastResult = result;

    const a = result.assessment;
    const d = result.release_decision;

    $("workflowTitle").textContent =
      result.workflow.name + " - " + result.workflow.version;

    $("workflowMeta").textContent =
      result.workflow.environment +
      " - " +
      a.passed +
      "/" +
      a.total +
      " controls - " +
      a.percentage +
      "%";

    const decision = $("decision");
    decision.textContent = d.action;
    decision.className = "decision " + d.action.toLowerCase();

    $("summaryStats").innerHTML =
      '<div class="stat"><b>' + a.percentage + '%</b><div class="label">Score</div></div>' +
      '<div class="stat"><b>' + result.evidence.length + '</b><div class="label">Evidence</div></div>' +
      '<div class="stat"><b>' + result.findings.length + '</b><div class="label">Findings</div></div>' +
      '<div class="stat"><b>' + a.test_runs.toLocaleString() + '</b><div class="label">Runs</div></div>';

    $("findings").innerHTML = result.findings.length
      ? result.findings.map(function (f) {
          return (
            '<div class="finding">' +
            '<strong>' + f.id + ' - ' + f.title + '</strong>' +
            '<span class="sev ' + f.severity + '">' + f.severity + '</span>' +
            '<p>' + f.detail + '</p>' +
            '<p><b>Remediation:</b> ' + f.remediation + '</p>' +
            '</div>'
          );
        }).join("")
      : '<div class="card"><h3>No findings</h3><p>The supplied reference posture produced no findings.</p></div>';

    $("evidenceBody").innerHTML = result.evidence.map(function (e) {
      return (
        "<tr>" +
        "<td>" + e.evidence_id + "</td>" +
        "<td>" + e.control + "</td>" +
        '<td class="' + (e.status === "PASS" ? "pass" : "critical") + '">' + e.status + "</td>" +
        "<td>" + e.observation + "</td>" +
        "</tr>"
      );
    }).join("");

    $("decisionBody").innerHTML =
      '<div class="card">' +
      '<div class="eyebrow">Release action</div>' +
      '<h2 class="decision-heading">' + d.action + "</h2>" +
      "<p>" + d.rationale + "</p>" +
      "</div>";

    $("json").textContent = JSON.stringify(result, null, 2);
  }

  async function runAssessment() {
    const button = $("run");
    button.disabled = true;
    button.textContent = "Generating report...";
    try {
      const traces = [{
        trace_id: "reference-001",
        timestamp: new Date().toISOString(),
        action: "reference_action",
        tool: "reference-tool",
        status: "ok"
      }];
      const body = {
        system: {
          system_id: $("workflow").value.trim() || "reference-ai-workflow",
          version: $("version").value.trim() || "1.0.0",
          environment: $("environment").value
        },
        contract: {
          allowed_actions: ["reference_action"],
          tools: ["reference-tool"],
          data_classes: [],
          permissions: $("authority").checked ? ["read"] : ["read", "write"],
          least_privilege: $("identity").checked && $("authority").checked,
          egress_controls: $("provenance").checked,
          dependency_attestation: $("deps").checked,
          adversarial_testing: $("policy").checked,
          change_reassessment: $("runtime").checked,
          safe_fallback: $("degraded").checked
        },
        traces,
        changes: $("depinc").value > 0 ? ["reference-dependency-change"] : [],
        policies: $("policy").checked ? [{id:"reference-policy", status:"active"}] : []
      };
      const response = await fetch("/api/assurance/report", {
        method: "POST",
        headers: {"content-type":"application/json"},
        body: JSON.stringify(body)
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || result.detail || "Assessment failed");
      render(result);
      document.querySelectorAll(".pane").forEach(p => p.classList.remove("active"));
      $("pane-findings").classList.add("active");
      document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t.dataset.tab === "findings"));
    } catch (error) {
      console.error("AAI assessment error:", error);
      $("findings").innerHTML = '<div class="card"><h3>Assessment error</h3><p>' + String(error.message || error) + '</p></div>';
    } finally {
      button.disabled = false;
      button.textContent = "Run assessment";
    }
  }

  function exportJSON() {
    if (!lastResult) {
      runAssessment();
    }

    const blob = new Blob(
      [JSON.stringify(lastResult, null, 2)],
      { type: "application/json" }
    );

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = "aai-assurance-report.json";
    document.body.appendChild(link);
    link.click();
    link.remove();

    setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 1000);
  }

  function scenario(type) {
    if (type === "strong") {
      $("reliability").value = 98;
      $("critical").value = 0;
      $("toolfail").value = 0;
      $("policyfail").value = 0;
      $("recovery").value = 99;
      $("depinc").value = 0;
    }

    if (type === "tool") {
      $("reliability").value = 96;
      $("critical").value = 0;
      $("toolfail").value = 4;
      $("policyfail").value = 0;
      $("recovery").value = 94;
      $("depinc").value = 1;
    }

    if (type === "policy") {
      $("reliability").value = 97;
      $("critical").value = 1;
      $("toolfail").value = 1;
      $("policyfail").value = 2;
      $("recovery").value = 91;
      $("depinc").value = 0;
    }

    if (type === "regression") {
      $("reliability").value = 93;
      $("critical").value = 0;
      $("toolfail").value = 2;
      $("policyfail").value = 0;
      $("recovery").value = 92;
      $("depinc").value = 2;
    }

    runAssessment();
  }

  function init() {
    $("run").addEventListener("click", runAssessment);
    $("download").addEventListener("click", exportJSON);

    document.querySelectorAll(".tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        document.querySelectorAll(".tab").forEach(function (x) {
          x.classList.toggle("active", x === tab);
        });

        document.querySelectorAll(".pane").forEach(function (pane) {
          pane.classList.toggle(
            "active",
            pane.id === "pane-" + tab.dataset.tab
          );
        });
      });
    });

    document.querySelectorAll("[data-s]").forEach(function (button) {
      button.addEventListener("click", function () {
        scenario(button.dataset.s);
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
