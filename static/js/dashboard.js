
async function loadDashboard() {
    const status = document.getElementById("backend-status");
    const description = document.getElementById("backend-description");

    try {
        const [health, reviews, episodes, signals] = await Promise.all([
            apiRequest("/health"),
            apiRequest("/review/queue"),
            apiRequest("/memory/episodes?limit=1"),
            apiRequest("/signals?limit=5")
        ]);

        status.textContent = "Connected";
        status.style.color = "var(--green)";
        description.textContent = "MOSAIC API is responding";

        document.getElementById("total-signals").textContent =
            health.details?.signals_count ?? "—";

        document.getElementById("pending-reviews").textContent =
            reviews.total_pending ?? "—";

        document.getElementById("memory-episodes").textContent =
            health.details?.episodes_count ?? "—";

        const rows = Array.isArray(signals) ? signals : signals.signals || [];
        const tbody = document.getElementById("recent-signals");

        if (!rows.length) {
            tbody.innerHTML = `<tr><td colspan="4" class="loading-cell">No signals available.</td></tr>`;
            return;
        }

        tbody.innerHTML = rows.map(signal => `
            <tr>
                <td><span class="signal-id">${escapeHTML(signal.nct_id || "—")}</span></td>
                <td>${escapeHTML(formatLabel(signal.agent))}</td>
                <td>${escapeHTML(formatLabel(signal.signal_type))}</td>
                <td>${escapeHTML(formatLabel(signal.status || "Detected"))}</td>
            </tr>
        `).join("");

    } catch (error) {
        status.textContent = "Disconnected";
        status.style.color = "#ed8b8b";
        description.textContent = "Could not connect to MOSAIC API";

        document.getElementById("recent-signals").innerHTML =
            `<tr><td colspan="4" class="loading-cell">Unable to load signals. Check the API connection.</td></tr>`;

        console.error("Dashboard loading error:", error);
    }
}

document.addEventListener("DOMContentLoaded", loadDashboard);
