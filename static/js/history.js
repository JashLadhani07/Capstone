async function loadAgentRules() {
    const container = document.getElementById("rules-container");
    if (!container) return;

    const agents = [
        "missing_results_agent",
        "broken_promises_agent",
        "track_record_agent",
        "pattern_finder_agent",
        "side_effect_agent",
        "timeline_agent"
    ];

    try {
        let allRulesHtml = "";

        for (const agent of agents) {
            const data = await apiRequest(`/memory/procedures/${agent}`);
            const rules = data.procedures || [];

            allRulesHtml += `
                <div class="rules-agent-section">
                    <div class="rules-agent-header">
                        <h4>${agent.replace(/_/g, ' ').toUpperCase()}</h4>
                        <span class="rules-count">${rules.length} Rules</span>
                    </div>
                    <div class="rules-grid">
                        ${rules.map(rule => `
                            <div class="rule-card ${rule.rule_type === 'learned' ? 'learned' : ''}">
                                <span class="rule-type">${escapeHTML(rule.rule_type || 'default')}</span>
                                <p class="rule-text">${escapeHTML(rule.rule || rule.text || rule.description || 'No rule text available')}</p>
                            </div>
                        `).join("")}
                    </div>
                </div>
            `;
        }

        container.innerHTML = allRulesHtml;

    } catch (error) {
        container.innerHTML = `<p class="loading-cell">Unable to load agent rules: ${error.message}</p>`;
    }
}

document.addEventListener("DOMContentLoaded", loadAgentRules);
