async function loadInsights() {
    const statsMap = {
        "stat-sponsors": "total_sponsors",
        "stat-studies": "total_studies_indexed",
        "stat-missing": "global_missing_results",
        "stat-cred": "average_credibility"
    };

    try {
        const data = await apiRequest("/insights/summary");

        if (data.error) {
            throw new Error(data.error);
        }

        // Update stats
        const stats = data.stats || {};
        for (const [id, key] of Object.entries(statsMap)) {
            const el = document.getElementById(id);
            if (el) {
                const val = stats[key];
                el.textContent = typeof val === 'number' ? val.toLocaleString() : val;
                if (id === "stat-cred") {
                    el.textContent = (val * 100).toFixed(1) + "%";
                }
            }
        }

        // Update high risk list
        const riskList = document.getElementById("risk-list");
        const risks = data.top_risks || [];

        if (!risks.length) {
            riskList.innerHTML = `<p class="loading-cell">No high-risk sponsors identified.</p>`;
            return;
        }

        riskList.innerHTML = risks.map(s => `
            <div class="review-item">
                <div style="display: flex; flex-direction: column; gap: 4px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span class="status-label" style="background: #ff6b6b; color: white;">HIGH RISK</span>
                        <h4 style="margin: 0;">${escapeHTML(s.sponsor)}</h4>
                    </div>
                    <p style="font-size: 11px; color: var(--muted);">
                        Credibility: <strong>${(s.credibility_score * 100).toFixed(1)}%</strong> |
                        Broken Promises: <strong>${s.broken_promises}</strong>
                    </p>
                </div>
                <div class="review-actions">
                    <button class="view-details" onclick="showToast('Viewing profile for ${s.sponsor}')">Analyze →</button>
                </div>
            </div>
        `).join("");

    } catch (error) {
        document.getElementById("risk-list").innerHTML = `<p class="loading-cell">Error loading insights: ${error.message}</p>`;
    }
}

document.addEventListener("DOMContentLoaded", loadInsights);
