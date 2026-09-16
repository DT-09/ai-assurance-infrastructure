const state = {
    apiKey: sessionStorage.getItem("aai_api_key") || "",
    assets: [],
    selected: null,
    trust: {},
    evidence: {},
    loading: false
};

const $ = (id) => document.getElementById(id);

function toast(message) {
    const el = $("toast");
    if (!el) return;
    el.textContent = message;
    el.classList.add("show");
    setTimeout(() => el.classList.remove("show"), 2400);
}

function esc(value) {
    return String(value ?? "").replace(
        /[&<>"']/g,
        (m) => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        }[m])
    );
}

function stateBadge(value) {
    const normalized = String(value || "").toUpperCase();

    if (normalized === "ASSURED") {
        return '<span class="badge ASSURED">ASSURED</span>';
    }

    if (normalized === "DEGRADED") {
        return '<span class="badge DEGRADED">DEGRADED</span>';
    }

    if (normalized === "BLOCKED") {
        return '<span class="badge BLOCKED">BLOCKED</span>';
    }

    if (normalized === "OPERATIONAL" || normalized === "READY" || normalized === "ENFORCED") {
        return '<span class="badge ASSURED">' + esc(normalized) + "</span>";
    }

    return '<span class="badge">' + esc(value || "UNKNOWN") + "</span>";
}

function setText(id, value) {
    const el = $(id);
    if (el) el.textContent = value;
}

function setHTML(id, value) {
    const el = $(id);
    if (el) el.innerHTML = value;
}

function setLoading(id, text = "Loading…") {
    const el = $(id);
    if (el) el.textContent = text;
}

async function api(path, options = {}) {
    const headers = { ...(options.headers || {}) };

    if (state.apiKey) {
        headers["X-API-Key"] = state.apiKey;
    }

    const response = await fetch(path, {
        ...options,
        headers
    });

    let data = null;

    try {
        data = await response.json();
    } catch {
        data = null;
    }

    if (!response.ok) {
        throw new Error(
            data?.detail ||
            data?.message ||
            `Request failed (${response.status})`
        );
    }

    return data;
}

function setView(view) {
    document.querySelectorAll(".view").forEach((element) => {
        element.classList.remove("active");
    });

    const target = $(`view-${view}`);

    if (target) {
        target.classList.add("active");
    }

    document.querySelectorAll("nav button").forEach((button) => {
        button.classList.toggle("active", button.dataset.view === view);
    });

    setText(
        "crumb",
        "Control Plane / " +
        view.replace(/^./, (character) => character.toUpperCase())
    );

    if (view === "overview") {
        loadOverview();
    }

    if (view === "assets") {
        loadAssets();
    }

    if (view === "graph") {
        loadGraph();
    }

    if (view === "protocol") {
        loadProtocol();
    }

    if (view === "evidence") {
        loadEvidence();
    }

    if (view === "assurance") {
        loadTrust();
    }
}

document.querySelectorAll("nav button").forEach((button) => {
    button.onclick = () => setView(button.dataset.view);
});

document.querySelectorAll("[data-action]").forEach((button) => {
    button.onclick = () => {
        const action = button.dataset.action;

        if (action === "save-key") {
            saveKey();
        }

        if (action === "clear-key") {
            clearKey();
        }

        if (action === "refresh") {
            refreshAll();
        }
    };
});

async function init() {
    setText("serviceStatus", "Checking…");

    try {
        const health = await api("/api/health");

        setText("version", "v" + (health.version || "—"));

        const readiness = await api("/api/readiness");

        setText(
            "serviceStatus",
            readiness.status === "ready"
                ? "Operational"
                : "Degraded"
        );

        updatePlatformStatus(readiness);
    } catch (error) {
        setText("serviceStatus", "Unavailable");
        updatePlatformStatus(null, error.message);
    }

    if (state.apiKey) {
        const keyInput = $("apiKey");

        if (keyInput) {
            keyInput.value = state.apiKey;
        }

        setText("keyStatus", "Workspace credential loaded.");
    }

    await loadProtocol();

    if (state.apiKey) {
        await refreshAll();
    } else {
        showDisconnectedState();
    }
}

async function refreshAll() {
    await Promise.allSettled([
        loadAssets(),
        loadOverview(),
        loadGraph(),
        loadProtocol()
    ]);
}

function showDisconnectedState() {
    setText("metricAssets", "—");
    setText("metricState", "—");
    setText("metricEvidence", "—");

    setHTML(
        "assetCards",
        '<div class="asset-card">' +
            "<h3>Connect workspace</h3>" +
            "<p>Add an API key under Workspace to load registered AI systems.</p>" +
        "</div>"
    );

    setText("trustHeadline", "Workspace not connected");
    setText(
        "trustReasons",
        "Connect a workspace credential to retrieve assurance state."
    );
}

async function loadOverview() {
    if (!state.apiKey) {
        showDisconnectedState();
        return;
    }

    try {
        const assetsResponse = await api("/v1/control/assets");
        const assets = assetsResponse.assets || [];

        state.assets = assets;

        setText("metricAssets", assets.length);

        let assured = 0;
        let degraded = 0;
        let blocked = 0;

        const trustResults = await Promise.allSettled(
            assets.map((asset) =>
                api(`/v1/control/assets/${asset.id}/trust`)
            )
        );

        trustResults.forEach((result) => {
            if (result.status !== "fulfilled") return;

            const trust = result.value;
            const currentState = String(trust.state || "").toUpperCase();

            if (currentState === "ASSURED") assured++;
            if (currentState === "DEGRADED") degraded++;
            if (currentState === "BLOCKED") blocked++;
        });

        const totalTrustStates = assured + degraded + blocked;

        if (totalTrustStates === 0) {
            setText("metricState", "No state");
        } else if (blocked > 0) {
            setText("metricState", `${blocked} BLOCKED`);
        } else if (degraded > 0) {
            setText("metricState", `${degraded} DEGRADED`);
        } else {
            setText("metricState", `${assured} ASSURED`);
        }

        if (assets.length) {
            const evidenceResults = await Promise.allSettled(
                assets.map((asset) =>
                    api(`/v1/control/assets/${asset.id}/evidence`)
                )
            );

            let evidenceCount = 0;

            evidenceResults.forEach((result) => {
                if (result.status !== "fulfilled") return;
                evidenceCount += (result.value.evidence || []).length;
            });

            setText("metricEvidence", evidenceCount);
        } else {
            setText("metricEvidence", "0");
        }

        renderAssetCards(assets, trustResults);
    } catch (error) {
        toast(error.message);
        setText("metricAssets", "—");
        setText("metricState", "Unavailable");
        setText("metricEvidence", "—");
    }
}

async function loadAssets() {
    if (!state.apiKey) {
        showDisconnectedState();
        return;
    }

    try {
        const data = await api("/v1/control/assets");

        state.assets = data.assets || [];

        setText("metricAssets", state.assets.length);

        const trustResults = await Promise.allSettled(
            state.assets.map((asset) =>
                api(`/v1/control/assets/${asset.id}/trust`)
            )
        );

        renderAssetCards(state.assets, trustResults);
    } catch (error) {
        toast(error.message);

        setHTML(
            "assetCards",
            '<div class="asset-card">' +
                "<h3>Unable to load assets</h3>" +
                `<p>${esc(error.message)}</p>` +
            "</div>"
        );
    }
}

function renderAssetCards(assets, trustResults = []) {
    if (!assets.length) {
        setHTML(
            "assetCards",
            '<div class="asset-card">' +
                "<h3>No assets registered</h3>" +
                "<p>Register an AI system through the control API.</p>" +
            "</div>"
        );
        return;
    }

    setHTML(
        "assetCards",
        assets.map((asset, index) => {
            const result = trustResults[index];

            let trustState = "UNKNOWN";

            if (result?.status === "fulfilled") {
                trustState = result.value?.state || "UNKNOWN";
            }

            return `
                <article class="asset-card" onclick="selectAsset('${esc(asset.id)}')">
                    <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start">
                        <div>
                            <h3>${esc(asset.name)}</h3>
                            <p>
                                ${esc(asset.asset_type)} ·
                                ${esc(asset.environment)} ·
                                ${esc(asset.criticality)}
                            </p>
                        </div>
                        ${stateBadge(trustState)}
                    </div>

                    <span class="badge">${esc(asset.id)}</span>
                </article>
            `;
        }).join("")
    );
}

async function selectAsset(id) {
    state.selected = id;

    setView("assurance");

    await Promise.allSettled([
        loadTrust(),
        loadEvidence()
    ]);
}

async function loadTrust() {
    if (!state.selected) {
        setText("trustHeadline", "Select an AI asset");
        setText(
            "trustReasons",
            "Choose an asset from AI Assets to inspect its current assurance state."
        );
        return;
    }

    try {
        const trust = await api(
            `/v1/control/assets/${state.selected}/trust`
        );

        state.trust = trust;

        const score =
            typeof trust.score === "number"
                ? Math.round(trust.score * 100)
                : null;

        setText("metricState", trust.state || "UNKNOWN");
        setText("trustHeadline", trust.state || "UNKNOWN");

        if (score !== null) {
            setText("trustRing", `${score}%`);
        } else {
            setText("trustRing", "—");
        }

        setText(
            "trustReasons",
            Array.isArray(trust.reasons)
                ? trust.reasons.join(" ")
                : "Current trust state retrieved from the assurance engine."
        );

        setHTML(
            "trustTable",
            `
            <tr>
                <td>Reliability</td>
                <td>${esc(trust.reliability ?? "—")}</td>
                <td>
                    ${
                        typeof trust.reliability === "number"
                            ? Math.round(trust.reliability * 100) + "%"
                            : "—"
                    }
                </td>
            </tr>
            <tr>
                <td>Evidence</td>
                <td>${esc(trust.evidence_state ?? "—")}</td>
                <td>—</td>
            </tr>
            <tr>
                <td>Dependencies</td>
                <td>${esc(trust.dependency_state ?? "—")}</td>
                <td>—</td>
            </tr>
            <tr>
                <td>Policy</td>
                <td>${esc(trust.policy_state ?? "—")}</td>
                <td>—</td>
            </tr>
            <tr>
                <td>Epoch</td>
                <td>Persistent</td>
                <td>${esc(trust.epoch ?? "—")}</td>
            </tr>
            `
        );
    } catch (error) {
        setText("trustHeadline", "No trust state");
        setText("trustRing", "—");
        setText("trustReasons", error.message);

        setHTML(
            "trustTable",
            `
            <tr>
                <td colspan="3" class="empty">
                    No computed assurance state is available for this asset.
                </td>
            </tr>
            `
        );
    }
}

async function loadEvidence() {
    if (!state.selected) {
        setText("metricEvidence", "—");
        return;
    }

    try {
        const data = await api(
            `/v1/control/assets/${state.selected}/evidence`
        );

        const evidence = data.evidence || [];

        setText("metricEvidence", evidence.length);

        setHTML(
            "evidenceTable",
            evidence.length
                ? evidence.map((item) => `
                    <tr>
                        <td>${esc(item.id)}</td>
                        <td>${esc(item.evidence_type)}</td>
                        <td>${esc(item.result)}</td>
                        <td>${esc(item.source)}</td>
                        <td class="mono">
                            ${esc(
                                String(item.provenance_hash || "").slice(0, 18)
                            )}…
                        </td>
                    </tr>
                `).join("")
                : '<tr><td colspan="5" class="empty">No evidence recorded.</td></tr>'
        );
    } catch (error) {
        setHTML(
            "evidenceTable",
            `
            <tr>
                <td colspan="5" class="empty">
                    Unable to load evidence.
                </td>
            </tr>
            `
        );
    }
}

async function loadGraph() {
    if (!state.apiKey) {
        setText("graphSummary", "Connect workspace");
        return;
    }

    try {
        const graph = await api("/v1/control/graph");

        const nodes = graph.nodes || [];
        const edges = graph.edges || [];

        setText(
            "graphSummary",
            `${nodes.length} nodes · ${edges.length} relationships`
        );

        setHTML(
            "graphNodes",
            nodes.length
                ? nodes.map((node) => `
                    <div class="node">
                        <b>${esc(node.label)}</b>
                        <span>${esc(node.id)}</span>
                    </div>
                `).join("")
                : '<div class="empty">No dependency relationships registered.</div>'
        );
    } catch (error) {
        setText("graphSummary", "Unavailable");
        setHTML(
            "graphNodes",
            `<div class="empty">${esc(error.message)}</div>`
        );
    }
}

async function loadProtocol() {
    try {
        const manifest = await api(
            "/v1/control/protocol/manifest"
        );

        setText(
            "manifest",
            JSON.stringify(manifest, null, 2)
        );
    } catch (error) {
        setText("manifest", error.message);
    }
}

function updatePlatformStatus(readiness, errorMessage = "") {
    const status = readiness?.status || "unavailable";
    const checks = readiness?.checks || {};

    const mappings = {
        database: "databaseStatus",
        audit_chain: "auditStatus",
        outbox: "outboxStatus",
        runtime_control: "runtimeStatus"
    };

    Object.entries(mappings).forEach(([key, elementId]) => {
        const check = checks[key];

        if (check) {
            setText(
                elementId,
                check.status === "ok"
                    ? "Operational"
                    : String(check.status)
            );
        } else if (errorMessage) {
            setText(elementId, "Unavailable");
        }
    });

    const platformMessage =
        status === "ready"
            ? "All control-plane health checks operational."
            : errorMessage || "Control-plane readiness degraded.";

    setText("platformStatus", platformMessage);
}

async function saveKey() {
    const input = $("apiKey");

    if (!input) return;

    const key = input.value.trim();

    if (!key) {
        toast("Enter an API key.");
        return;
    }

    state.apiKey = key;

    sessionStorage.setItem(
        "aai_api_key",
        key
    );

    setText(
        "keyStatus",
        "Workspace credential loaded."
    );

    toast("Workspace connected.");

    await refreshAll();
}

function clearKey() {
    state.apiKey = "";
    state.selected = null;

    sessionStorage.removeItem("aai_api_key");

    const input = $("apiKey");

    if (input) {
        input.value = "";
    }

    setText(
        "keyStatus",
        "No workspace credential loaded."
    );

    showDisconnectedState();

    toast("Workspace disconnected.");
}

async function demoDecision(decision) {
    if (!state.selected) {
        toast("Select an asset first.");
        return;
    }

    try {
        const result = await api(
            "/v1/control/decisions",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    asset_id: state.selected,
                    action: "execute",
                    context: {
                        ui_request: decision
                    }
                })
            }
        );

        setText(
            "decisionOutput",
            JSON.stringify(result, null, 2)
        );
    } catch (error) {
        toast(error.message);
    }
}

window.selectAsset = selectAsset;
window.demoDecision = demoDecision;

init();