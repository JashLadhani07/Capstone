
async function loadSignals() {
    const tbody = document.getElementById("signals-table");
    if (!tbody) return;

    const agent = document.getElementById("agent-filter")?.value || "";
    const type = document.getElementById("type-filter")?.value || "";

    const params = new URLSearchParams({ limit: "100" });
    if (agent) params.set("agent", agent);
    if (type) params.set("signal_type", type);

    try {
        const response = await apiRequest(`/signals?${params}`);
        const signals = Array.isArray(response) ? response : response.signals || [];

        if (!signals.length) {
            tbody.innerHTML = `<tr><td colspan="5" class="loading-cell">No matching signals found.</td></tr>`;
            return;
        }

        tbody.innerHTML = signals.map(signal => `
            <tr>
                <td>${escapeHTML(signal.nct_id || "—")}</td>
                <td>${escapeHTML(formatLabel(signal.agent))}</td>
                <td>${escapeHTML(formatLabel(signal.signal_type))}</td>
                <td class="signal-summary">${escapeHTML(signal.summary || "—")}</td>
                <td><a class="signal-link" href="/signals/${encodeURIComponent(signal.signal_id)}">Inspect →</a></td>
            </tr>
        `).join("");

        const search = document.getElementById("signal-search");
        search?.addEventListener("input", () => {
            const query = search.value.toLowerCase();
            tbody.querySelectorAll("tr").forEach(row => {
                row.hidden = !row.textContent.toLowerCase().includes(query);
            });
        });

    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="5" class="loading-cell">Could not load signals: ${escapeHTML(error.message)}</td></tr>`;
    }
}

async function loadSignalDetail() {
    const container = document.getElementById("signal-detail");
    if (!container) return;

    const signalId = location.pathname.split("/").pop();

    try {
        const signal = await apiRequest(`/signals/${encodeURIComponent(signalId)}`);

        const fields = [
            ["Signal ID", signal.signal_id],
            ["Clinical Trial", signal.nct_id],
            ["Agent", formatLabel(signal.agent)],
            ["Signal Type", formatLabel(signal.signal_type)],
            ["Status", formatLabel(signal.status)]
        ];

        container.innerHTML = `
            <div class="detail-grid">
                ${fields.map(([label, value]) => `
                    <div class="detail-field">
                        <span>${escapeHTML(label)}</span>
                        <strong>${escapeHTML(value || "—")}</strong>
                    </div>
                `).join("")}
                <div class="detail-field detail-summary">
                    <span>Signal Summary</span>
                    ${escapeHTML(signal.summary || "No summary available.")}
                </div>
            </div>
        `;
    } catch (error) {
        container.textContent = `Unable to load signal: ${error.message}`;
    }
}

document.getElementById("filter-signals")?.addEventListener("click", loadSignals);
document.addEventListener("DOMContentLoaded", () => {
    loadSignals();
    loadSignalDetail();
});
