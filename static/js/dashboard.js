
async function loadDashboard() {
    const status = document.getElementById("backend-status");
    const description = document.getElementById("backend-description");

    const results = await Promise.allSettled([
        apiRequest("/health"),
        apiRequest("/review/queue"),
        apiRequest("/memory/episodes?limit=1"),
        apiRequest("/signals?limit=5")
    ]);

    const [healthResult, reviewsResult, episodesResult, signalsResult] = results;

    // Check whether the API itself is responding.
    if (healthResult.status === "fulfilled") {
        const health = healthResult.value;

        const healthy = health.status === "healthy";

        status.textContent = healthy ? "Connected" : "Degraded";
        status.style.color = healthy ? "var(--green)" : "#edaa55";

        description.textContent = healthy
            ? "MOSAIC API is responding"
            : "API is responding, but some storage services may be unavailable";

        document.getElementById("total-signals").textContent =
            health.details?.signals_count ?? "—";

        document.getElementById("memory-episodes").textContent =
            health.details?.episodes_count ?? "—";

    } else {
        status.textContent = "Disconnected";
        status.style.color = "#ed8b8b";
        description.textContent = "Could not reach MOSAIC API";

        console.error("Health check failed:", healthResult.reason);
    }

    // Load pending reviews independently.
    if (reviewsResult.status === "fulfilled") {
        document.getElementById("pending-reviews").textContent =
            reviewsResult.value.total_pending ?? "—";
    } else {
        document.getElementById("pending-reviews").textContent = "—";
        console.error("Review queue failed:", reviewsResult.reason);
    }

    // Check episodic memory independently.
    if (episodesResult.status === "rejected") {
        console.error("Episodic memory request failed:", episodesResult.reason);
    }

    // Load recent signals independently.
    const tbody = document.getElementById("recent-signals");

    if (signalsResult.status === "fulfilled") {
        const response = signalsResult.value;
        const rows = Array.isArray(response)
            ? response
            : response.signals || [];

        if (!rows.length) {
            tbody.innerHTML =
                `<tr><td colspan="4" class="loading-cell">No signals available.</td></tr>`;
        } else {
            tbody.innerHTML = rows.map(signal => `
                <tr>
                    <td><span class="signal-id">${escapeHTML(signal.nct_id || "—")}</span></td>
                    <td>${escapeHTML(formatLabel(signal.agent))}</td>
                    <td>${escapeHTML(formatLabel(signal.signal_type))}</td>
                    <td>${escapeHTML(formatLabel(signal.status || "Detected"))}</td>
                </tr>
            `).join("");
        }
    } else {
        tbody.innerHTML =
            `<tr><td colspan="4" class="loading-cell">Could not load signals.</td></tr>`;

        console.error("Signals request failed:", signalsResult.reason);
    }
}

document.addEventListener("DOMContentLoaded", loadDashboard);
