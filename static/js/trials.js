async function loadTrials() {
    const container = document.getElementById("trials-list");
    if (!container) return;

    try {
        const data = await apiRequest("/api/v1/trials/all");

        const studies = data.studies || [];
        const papers = data.papers || [];

        if (!studies.length && !papers.length) {
            container.innerHTML = `<p class="loading-cell">No local data found in storage.</p>`;
            return;
        }

        let html = `<div class="trials-tabs">
            <button class="tab-btn active" data-tab="studies">Studies (${studies.length})</button>
            <button class="tab-btn" data-tab="papers">Papers (${papers.length})</button>
        </div>`;

        html += `<div id="trials-grid" class="trials-grid"></div>`;
        container.innerHTML = html;

        const grid = document.getElementById("trials-grid");

        function renderList(list, type) {
            grid.innerHTML = list.map(item => {
                if (type === "STUDY") {
                    return `
                        <div class="trial-card">
                            <div class="trial-header">
                                <span class="trial-id">${escapeHTML(item.id)}</span>
                                <span class="trial-status ${item.status.toLowerCase().replace(/\s+/g, '-')}">${escapeHTML(item.status)}</span>
                            </div>
                            <div class="trial-body">
                                <h4 class="trial-title">${escapeHTML(item.title)}</h4>
                                <p class="trial-sponsor">Sponsor: ${escapeHTML(item.sponsor)}</p>
                                <p class="trial-summary">${escapeHTML(item.summary.substring(0, 180))}...</p>
                                <div class="trial-meta">
                                    <span class="meta-tag">Phase ${escapeHTML(item.phase)}</span>
                                </div>
                            </div>
                            <div class="trial-footer">
                                <a href="/analysis" class="secondary-button" style="font-size: 10px; padding: 5px 10px;">Analyze →</a>
                            </div>
                        </div>
                    `;
                } else {
                    return `
                        <div class="trial-card">
                            <div class="trial-header">
                                <span class="trial-id">${escapeHTML(item.id)}</span>
                                <span class="trial-type">PAPER</span>
                            </div>
                            <div class="trial-body">
                                <h4 class="trial-title">${escapeHTML(item.title)}</h4>
                                <p class="trial-sponsor">Journal: ${escapeHTML(item.journal)} (${escapeHTML(item.year)})</p>
                                <p class="trial-summary">${escapeHTML(item.summary.substring(0, 180))}...</p>
                            </div>
                            <div class="trial-footer">
                                <a href="/analysis" class="secondary-button" style="font-size: 10px; padding: 5px 10px;">Analyze →</a>
                            </div>
                        </div>
                    `;
                }
            }).join("");
        }

        renderList(studies, "STUDY");

        document.querySelectorAll(".tab-btn").forEach(btn => {
            btn.addEventListener("click", (e) => {
                document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
                e.target.classList.add("active");

                if (e.target.dataset.tab === "studies") {
                    renderList(studies, "STUDY");
                } else {
                    renderList(papers, "PAPER");
                }
            });
        });

    } catch (error) {
        container.innerHTML = `<p class="loading-cell">Error loading database: ${error.message}</p>`;
    }
}

document.addEventListener("DOMContentLoaded", loadTrials);
