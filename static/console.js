const state = {
    apiKey: sessionStorage.getItem("aai_api_key") || "",
    assets: [],
    policies: []
};

const $ = (id) => document.getElementById(id);

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

function toast(message) {
    const el = $("toast");
    if (!el) return;

    el.textContent = message;
    el.classList.add("show");

    setTimeout(() => {
        el.classList.remove("show");
    }, 2800);
}

function openModal(id) {
    const el = $(id);
    if (el) el.classList.add("open");
}

function closeModal(id) {
    const el = $(id);
    if (el) el.classList.remove("open");
}

function setView(view) {
    document.querySelectorAll(".view").forEach((v) => {
        v.classList.remove("active");
    });

    const target = $("view-" + view);

    if (target) {
        target.classList.add("active");
    }

    document.querySelectorAll(".nav button").forEach((b) => {
        b.classList.toggle(
            "active",
            b.dataset.view === view
        );
    });

    const crumb = $("crumb");

    if (crumb) {
        crumb.textContent =
            "Control Plane / " +
            view.replace(/^./, (x) => x.toUpperCase());
    }

    if (view === "assets") {
        loadAssets();
    }

    if (view === "policies") {
        loadPolicies();
    }
}

document.querySelectorAll(".nav button").forEach((button) => {
    button.addEventListener("click", () => {
        setView(button.dataset.view);
    });
});

document.querySelectorAll("[data-action]").forEach((el) => {
    el.addEventListener("click", () => {
        const action = el.dataset.action;

        if (action === "open-asset") openModal("assetModal");
        if (action === "open-policy") openModal("policyModal");
        if (action === "close-asset") closeModal("assetModal");
        if (action === "close-policy") closeModal("policyModal");
        if (action === "save-key") saveKey();
        if (action === "clear-key") clearKey();
        if (action === "bootstrap") bootstrap();
        if (action === "checkout") checkout();
        if (action === "create-asset") createAsset();
        if (action === "create-policy") createPolicy();
    });
});

async function api(path, options = {}) {
    const headers = {
        ...(options.headers || {})
    };

    if (state.apiKey) {
        headers["X-API-Key"] = state.apiKey;
    }

    const response = await fetch(path, {
        ...options,
        headers,
        cache: "no-store"
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

async function init() {
    try {
        const health = await api("/api/health");

        if ($("version")) {
            $("version").textContent =
                "v" + (health.version || "3.1.0");
        }

        if ($("envPill")) {
            $("envPill").textContent =
                health.environment || "Production";
        }

        const readiness = await api("/api/readiness");

        if ($("backend")) {
            $("backend").textContent =
                "Persistence: " +
                (
                    readiness.database_backend ||
                    "Operational"
                );
        }

        if ($("serviceStatus")) {
            $("serviceStatus").textContent =
                readiness.status === "ready"
                    ? "Operational"
                    : "Degraded";
        }

        renderHealth(readiness);

    } catch (error) {
        if ($("serviceStatus")) {
            $("serviceStatus").textContent = "Unavailable";
        }

        if ($("backend")) {
            $("backend").textContent =
                "Persistence: unavailable";
        }

        if ($("healthTable")) {
            $("healthTable").innerHTML =
                `<tr>
                    <td colspan="4" class="empty">
                        ${esc(error.message)}
                    </td>
                </tr>`;
        }
    }

    try {
        const manifest = await api(
            "/v1/control/protocol/manifest"
        );

        if ($("manifest")) {
            $("manifest").textContent =
                JSON.stringify(manifest, null, 2);
        }

        if ($("protocolName")) {
            $("protocolName").textContent =
                manifest.protocol ||
                "AI Assurance Protocol";
        }

        if ($("protocolVersion")) {
            $("protocolVersion").textContent =
                "Version " +
                (manifest.version || "1.0");
        }

    } catch (error) {
        if ($("manifest")) {
            $("manifest").textContent =
                error.message;
        }
    }

    if (state.apiKey) {
        if ($("apiKey")) {
            $("apiKey").value = state.apiKey;
        }

        if ($("keyStatus")) {
            $("keyStatus").textContent =
                "Workspace credential loaded.";
        }

        await loadWorkspace();
    }
}

function renderHealth(readiness) {
    const checks = readiness?.checks || {};

    const rows = Object.entries(checks)
        .map(([name, value]) => {
            const status =
                String(value?.status || "unknown").toUpperCase();

            const good =
                status === "OK" ||
                status === "READY" ||
                status === "HEALTHY";

            return `
                <tr>
                    <td>${esc(name)}</td>
                    <td>
                        <span class="badge ${good ? "ASSURED" : "BLOCKED"}">
                            ${esc(status)}
                        </span>
                    </td>
                    <td>${esc(value?.backend || "—")}</td>
                    <td>Persistent subsystem</td>
                </tr>
            `;
        })
        .join("");

    if ($("healthTable")) {
        $("healthTable").innerHTML =
            rows ||
            `<tr>
                <td colspan="4" class="empty">
                    Control plane operational.
                </td>
            </tr>`;
    }
}

async function loadWorkspace() {
    try {
        const organization = await api(
            "/v1/control/organization"
        );

        toast(
            "Connected to " +
            (organization.name || "workspace")
        );

        await Promise.all([
            loadAssets(),
            loadPolicies(),
            loadBilling()
        ]);

    } catch (error) {
        if ($("keyStatus")) {
            $("keyStatus").textContent =
                error.message;
        }
    }
}

async function loadAssets() {
    if (!state.apiKey) {
        if ($("assetTable")) {
            $("assetTable").innerHTML =
                `<tr>
                    <td colspan="6" class="empty">
                        Connect a workspace to view assets.
                    </td>
                </tr>`;
        }

        return;
    }

    try {
        const data = await api(
            "/v1/control/assets"
        );

        state.assets = data.assets || [];

        if ($("assetCount")) {
            $("assetCount").textContent =
                state.assets.length + " assets";
        }

        if ($("metricAssets")) {
            $("metricAssets").textContent =
                state.assets.length;
        }

        if (!state.assets.length) {
            if ($("assetTable")) {
                $("assetTable").innerHTML =
                    `<tr>
                        <td colspan="6" class="empty">
                            No AI assets registered.
                        </td>
                    </tr>`;
            }

            return;
        }

        if ($("assetTable")) {
            $("assetTable").innerHTML =
                state.assets.map((asset) => `
                    <tr>
                        <td>
                            <strong>${esc(asset.name)}</strong>
                        </td>
                        <td>${esc(asset.asset_type)}</td>
                        <td>${esc(asset.version || "—")}</td>
                        <td>${esc(asset.environment || "—")}</td>
                        <td>
                            <span class="badge">
                                UNKNOWN
                            </span>
                        </td>
                        <td>
                            ${esc(asset.id)}
                        </td>
                    </tr>
                `).join("");
        }

    } catch (error) {
        if ($("assetTable")) {
            $("assetTable").innerHTML =
                `<tr>
                    <td colspan="6" class="empty">
                        ${esc(error.message)}
                    </td>
                </tr>`;
        }
    }
}

async function loadPolicies() {
    if (!state.apiKey) {
        if ($("policyTable")) {
            $("policyTable").innerHTML =
                `<tr>
                    <td colspan="4" class="empty">
                        Connect a workspace to view policies.
                    </td>
                </tr>`;
        }

        return;
    }

    try {
        const data = await api(
            "/v1/control/policies"
        );

        state.policies = data.policies || [];

        if ($("policyTable")) {
            $("policyTable").innerHTML =
                state.policies.length
                    ? state.policies.map((policy) => `
                        <tr>
                            <td>${esc(policy.name)}</td>
                            <td>${esc(policy.version)}</td>
                            <td>${policy.rules?.length || 0}</td>
                            <td>Workspace</td>
                        </tr>
                    `).join("")
                    : `<tr>
                        <td colspan="4" class="empty">
                            No policies registered.
                        </td>
                    </tr>`;
        }

    } catch (error) {
        if ($("policyTable")) {
            $("policyTable").innerHTML =
                `<tr>
                    <td colspan="4" class="empty">
                        ${esc(error.message)}
                    </td>
                </tr>`;
        }
    }
}

async function createAsset() {
    if (!state.apiKey) {
        return toast(
            "Connect a workspace first."
        );
    }

    const projectId =
        $("newAssetProject")?.value.trim();

    if (!projectId) {
        return toast(
            "Project ID is required."
        );
    }

    try {
        const data = await api(
            "/v1/control/assets",
            {
                method: "POST",
                headers: {
                    "Content-Type":
                        "application/json"
                },
                body: JSON.stringify({
                    project_id: projectId,
                    name:
                        $("newAssetName")
                            ?.value.trim(),
                    asset_type:
                        $("newAssetType")
                            ?.value.trim() ||
                        "agent",
                    owner:
                        $("newAssetOwner")
                            ?.value.trim() ||
                        null
                })
            }
        );

        closeModal("assetModal");

        toast(
            "Asset registered: " +
            (data.name || "AI asset")
        );

        await loadAssets();

    } catch (error) {
        toast(error.message);
    }
}

async function createPolicy() {
    if (!state.apiKey) {
        return toast(
            "Connect a workspace first."
        );
    }

    let rules;

    try {
        rules = JSON.parse(
            $("newPolicyRules").value
        );
    } catch {
        return toast(
            "Invalid rules JSON."
        );
    }

    try {
        await api(
            "/v1/control/policies",
            {
                method: "POST",
                headers: {
                    "Content-Type":
                        "application/json"
                },
                body: JSON.stringify({
                    name:
                        $("newPolicyName")
                            ?.value.trim(),
                    rules
                })
            }
        );

        closeModal("policyModal");

        toast("Policy created.");

        await loadPolicies();

    } catch (error) {
        toast(error.message);
    }
}

function saveKey() {
    const key =
        $("apiKey")?.value.trim();

    if (!key) {
        return toast(
            "Enter an API key."
        );
    }

    state.apiKey = key;

    sessionStorage.setItem(
        "aai_api_key",
        key
    );

    if ($("keyStatus")) {
        $("keyStatus").textContent =
            "Workspace credential loaded for this browser session.";
    }

    loadWorkspace();
}

function clearKey() {
    state.apiKey = "";

    sessionStorage.removeItem(
        "aai_api_key"
    );

    if ($("apiKey")) {
        $("apiKey").value = "";
    }

    if ($("keyStatus")) {
        $("keyStatus").textContent =
            "No workspace credential loaded.";
    }

    if ($("metricAssets")) {
        $("metricAssets").textContent = "—";
    }

    if ($("metricState")) {
        $("metricState").textContent = "—";
    }

    if ($("assetTable")) {
        $("assetTable").innerHTML =
            `<tr>
                <td colspan="6" class="empty">
                    No workspace loaded.
                </td>
            </tr>`;
    }

    toast(
        "Workspace disconnected."
    );
}

async function bootstrap() {
    const key =
        $("bootstrapKey")?.value.trim();

    const name =
        $("orgName")?.value.trim();

    if (!key || !name) {
        return toast(
            "Bootstrap credential and organization name are required."
        );
    }

    try {
        const response = await fetch(
            "/v1/control/organizations/bootstrap",
            {
                method: "POST",
                headers: {
                    "Content-Type":
                        "application/json",
                    "X-Bootstrap-Key": key
                },
                body: JSON.stringify({
                    name
                }),
                cache: "no-store"
            }
        );

        const data =
            await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail ||
                "Bootstrap failed"
            );
        }

        state.apiKey =
            data.credential.api_key;

        sessionStorage.setItem(
            "aai_api_key",
            state.apiKey
        );

        if ($("apiKey")) {
            $("apiKey").value =
                state.apiKey;
        }

        if ($("keyStatus")) {
            $("keyStatus").textContent =
                "Organization provisioned and workspace connected.";
        }

        toast(
            "Workspace provisioned."
        );

        await loadWorkspace();

    } catch (error) {
        toast(error.message);
    }
}

async function loadBilling() {
    const message = $("billingMessage");

    if (!state.apiKey) {
        if (message) {
            message.textContent =
                "Connect a workspace to manage billing.";
        }
        return;
    }

    try {
        const data = await api(
            "/v1/billing/account"
        );

        if ($("billingPlan")) {
            $("billingPlan").textContent =
                data.plan.name;
        }

        if ($("billingStatus")) {
            $("billingStatus").textContent =
                data.account.status;
        }

        if ($("billingEvaluations")) {
            $("billingEvaluations").textContent =
                data.usage.evaluations +
                (
                    data.plan.max_evaluations_month === null
                        ? ""
                        : " / " +
                          data.plan.max_evaluations_month
                );
        }

        if ($("billingAssets")) {
            $("billingAssets").textContent =
                data.usage.assets_created +
                (
                    data.plan.max_assets === null
                        ? ""
                        : " / " +
                          data.plan.max_assets
                );
        }

        if (message) {
            message.textContent =
                "Billing account loaded.";
        }

    } catch (error) {
        if (message) {
            message.textContent =
                error.message;
        }
    }
}

async function checkout() {
    if (!state.apiKey) {
        return toast(
            "Connect a workspace first."
        );
    }

    const email =
        $("billingEmail")
            ?.value.trim();

    const plan =
        $("billingPlanSelect")
            ?.value;

    if (!email) {
        return toast(
            "Billing email is required."
        );
    }

    try {
        const data = await api(
            "/v1/billing/checkout",
            {
                method: "POST",
                headers: {
                    "Content-Type":
                        "application/json"
                },
                body: JSON.stringify({
                    plan,
                    email
                })
            }
        );

        if (data.url) {
            window.location.href =
                data.url;
        } else {
            toast(
                "No checkout required for this plan."
            );
        }

    } catch (error) {
        toast(error.message);
    }
}

window.openModal = openModal;
window.closeModal = closeModal;
window.saveKey = saveKey;
window.clearKey = clearKey;
window.bootstrap = bootstrap;
window.createAsset = createAsset;
window.createPolicy = createPolicy;
window.checkout = checkout;

init();