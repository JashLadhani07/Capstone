
const analysisForm = document.getElementById("analysis-form");

analysisForm?.addEventListener("submit", async event => {
    event.preventDefault();

    const button = document.getElementById("run-analysis");
    const message = document.getElementById("analysis-message");
    const result = document.getElementById("analysis-result");

    const task = document.getElementById("task").value.trim();
    const nctIds = document.getElementById("nct-ids").value
        .split(",")
        .map(id => id.trim())
        .filter(Boolean);

    const maxStudies = Number(document.getElementById("max-studies").value);

    if (!task || maxStudies < 1 || maxStudies > 100) {
        message.textContent = "Enter a valid objective and study limit.";
        message.className = "form-message error";
        return;
    }

    button.disabled = true;
    button.textContent = "Running Analysis...";
    message.textContent = "MOSAIC is processing your investigation. Please wait.";
    message.className = "form-message";
    result.hidden = true;

    try {
        const data = await apiRequest("/analyze", {
            method: "POST",
            body: JSON.stringify({
                task,
                nct_ids: nctIds,
                max_studies: maxStudies
            })
        });

        document.getElementById("result-run-id").textContent = data.run_id ?? "—";
        document.getElementById("result-signals").textContent = data.total_signals ?? "—";
        document.getElementById("result-reviews").textContent = data.signals_requiring_review ?? "—";
        document.getElementById("result-duration").textContent =
            data.duration_seconds != null ? `${data.duration_seconds}s` : "—";

        document.getElementById("result-brief").textContent =
            data.final_brief || "No final brief was returned.";

        result.hidden = false;
        message.textContent = "Analysis completed successfully.";
        message.className = "form-message success";

    } catch (error) {
        message.textContent = `Analysis failed: ${error.message}`;
        message.className = "form-message error";
    } finally {
        button.disabled = false;
        button.textContent = "✳ Run Analysis";
    }
});
