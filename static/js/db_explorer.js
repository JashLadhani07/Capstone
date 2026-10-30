async function loadDatabase() {
    const container = document.getElementById("db-list");
    if (!container) return;

    try {
        const data = await apiRequest("/api/v1/all");
        const files = data.files || [];

        if (!files.length) {
            container.innerHTML = `<p class="loading-cell">No processed JSON files found in storage.</p>`;
            return;
        }

        container.innerHTML = files.map(file => `
            <div class="review-item">
                <div style="display: flex; flex-direction: column; gap: 4px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span class="status-label" style="font-size: 8px;">${escapeHTML(file.category)}</span>
                        <h4 style="margin: 0;">${escapeHTML(file.title)}</h4>
                    </div>
                    <p style="font-size: 10px; color: var(--muted);">ID: ${escapeHTML(file.id)}</p>
                </div>
                <div class="review-actions">
                    <button class="view-details" onclick="showToast('File path: ${file.path}')">Info</button>
                </div>
            </div>
        `).join("");

    } catch (error) {
        container.innerHTML = `<p class="loading-cell">Error loading database: ${error.message}</p>`;
    }
}

document.addEventListener("DOMContentLoaded", loadDatabase);
