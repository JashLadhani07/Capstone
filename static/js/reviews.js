
async function loadReviews() {
    const container = document.getElementById("review-list");
    if (!container) return;

    try {
        const data = await apiRequest("/review/queue");
        const queue = data.queue || [];

        document.getElementById("review-pending").textContent = data.total_pending ?? 0;
        document.getElementById("review-approved").textContent = data.total_approved ?? 0;
        document.getElementById("review-rejected").textContent = data.total_rejected ?? 0;

        if (!queue.length) {
            container.innerHTML = `<p class="loading-cell">No pending reviews.</p>`;
            return;
        }

        container.innerHTML = queue.map(item => `
            <div class="review-item">
                <div>
                    <h4>${escapeHTML(item.nct_id || item.signal_id || item.queue_id || "Review item")}</h4>
                    <p>${escapeHTML(item.summary || item.signal_summary || "No summary available.")}</p>
                </div>
                <div class="review-actions">
                    <button class="approve" data-id="${escapeHTML(item.queue_id)}" data-decision="approve">Approve</button>
                    <button class="reject" data-id="${escapeHTML(item.queue_id)}" data-decision="reject">Reject</button>
                </div>
            </div>
        `).join("");

    } catch (error) {
        container.textContent = `Unable to load review queue: ${error.message}`;
    }
}

document.getElementById("review-list")?.addEventListener("click", async event => {
    const button = event.target.closest("button[data-decision]");
    if (!button) return;

    const queueId = button.dataset.id;
    const decision = button.dataset.decision;

    if (!queueId || queueId === "undefined") {
        showToast("Review item does not contain a queue ID.");
        return;
    }

    let rejectionReason = "";

    if (decision === "reject") {
        rejectionReason = prompt("Enter a rejection reason:");
        if (rejectionReason === null) return;
    }

    button.disabled = true;

    try {
        await apiRequest(`/review/${encodeURIComponent(queueId)}`, {
            method: "PATCH",
            body: JSON.stringify({
                decision,
                reviewer: "analyst",
                rejection_reason: rejectionReason
            })
        });

        showToast(`Review ${decision}d successfully.`);
        await loadReviews();

    } catch (error) {
        showToast(`Review failed: ${error.message}`);
        button.disabled = false;
    }
});

document.addEventListener("DOMContentLoaded", loadReviews);
