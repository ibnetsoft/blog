(function () {
    const state = {
        campaigns: [],
        runs: [],
        approvals: [],
        autoRefreshEnabled: true,
        refreshTimer: null,
    };

    const aiModelOptions = {
        gemini: [
            { value: "gemini-3.5-flash", label: "Gemini 3.5 Flash" },
            { value: "gemini-3.1-pro-preview", label: "Gemini 3.1 Pro Preview" },
            { value: "gemini-3-flash-preview", label: "Gemini 3 Flash Preview" },
        ],
        openai: [
            { value: "gpt-5.5", label: "GPT-5.5" },
            { value: "gpt-5.4", label: "GPT-5.4" },
            { value: "gpt-5.4-mini", label: "GPT-5.4 Mini" },
        ],
        anthropic: [
            { value: "claude-fable-5", label: "Claude Fable 5" },
            { value: "claude-opus-4-8", label: "Claude Opus 4.8" },
            { value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
        ],
    };

    function toast(message, type = "success") {
        if (window.Utils && typeof window.Utils.showToast === "function") {
            window.Utils.showToast(message, type);
            return;
        }
        window.alert(message);
    }

    async function jsonFetch(url, options = {}) {
        const response = await fetch(url, {
            headers: { "Content-Type": "application/json" },
            ...options,
        });
        return response.json();
    }

    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function nl2br(value) {
        return escapeHtml(value).replace(/\n/g, "<br>");
    }

    function openPreview(title, meta, bodyHtml) {
        document.getElementById("previewTitle").textContent = title || "Details";
        document.getElementById("previewMeta").textContent = meta || "";
        document.getElementById("previewBody").innerHTML = bodyHtml || "";
        document.getElementById("openclawPreviewModal").classList.remove("hidden");
    }

    function closePreview() {
        document.getElementById("openclawPreviewModal").classList.add("hidden");
    }

    function targetRowHTML(item = {}) {
        const platform = item.platform || "wordpress";
        const language = item.language || "ko";
        const targetId = item.target_id || platform;
        return `
            <div class="grid grid-cols-1 gap-3 rounded-2xl bg-white/80 p-3 shadow-sm dark:bg-gray-950/40 md:grid-cols-[1fr_1fr_1.2fr_auto]">
                <select class="oc-platform rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-900 dark:text-white">
                    <option value="wordpress" ${platform === "wordpress" ? "selected" : ""}>wordpress</option>
                    <option value="blogger" ${platform === "blogger" ? "selected" : ""}>blogger</option>
                    <option value="facebook" ${platform === "facebook" ? "selected" : ""}>facebook</option>
                    <option value="instagram" ${platform === "instagram" ? "selected" : ""}>instagram</option>
                    <option value="tiktok" ${platform === "tiktok" ? "selected" : ""}>tiktok</option>
                </select>
                <select class="oc-language rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-900 dark:text-white">
                    <option value="ko" ${language === "ko" ? "selected" : ""}>ko</option>
                    <option value="en" ${language === "en" ? "selected" : ""}>en</option>
                    <option value="ja" ${language === "ja" ? "selected" : ""}>ja</option>
                </select>
                <input class="oc-target-id rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-900 dark:text-white" value="${escapeHtml(targetId)}" placeholder="target_id">
                <button class="oc-remove-target rounded-xl bg-rose-500 px-3 py-2 text-xs font-black text-white transition hover:bg-rose-600">Remove</button>
            </div>
        `;
    }

    function collectTargets() {
        return [...document.querySelectorAll("#platformTargets > div")]
            .map((row) => ({
                platform: row.querySelector(".oc-platform").value,
                language: row.querySelector(".oc-language").value,
                target_id: row.querySelector(".oc-target-id").value.trim() || row.querySelector(".oc-platform").value,
            }))
            .filter((item) => item.target_id);
    }

    function addTargetRow(item = {}) {
        const container = document.getElementById("platformTargets");
        const wrapper = document.createElement("div");
        wrapper.innerHTML = targetRowHTML(item);
        const row = wrapper.firstElementChild;
        row.querySelector(".oc-remove-target").addEventListener("click", () => row.remove());
        row.querySelector(".oc-platform").addEventListener("change", (event) => {
            const input = row.querySelector(".oc-target-id");
            if (!input.value.trim()) input.value = event.target.value;
        });
        container.appendChild(row);
    }

    function renderAiModels(provider = "gemini", selectedModel = "") {
        const select = document.getElementById("campaignAiModel");
        if (!select) return;
        const options = aiModelOptions[provider] || aiModelOptions.gemini;
        select.innerHTML = options.map((item) => `<option value="${escapeHtml(item.value)}" ${item.value === selectedModel ? "selected" : ""}>${escapeHtml(item.label)}</option>`).join("");
        if (!selectedModel && options.length) {
            select.value = options[0].value;
        }
    }

    function statusBadge(status) {
        const map = {
            completed: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
            partial: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
            waiting_approval: "bg-cyan-100 text-cyan-700 dark:bg-cyan-500/15 dark:text-cyan-300",
            running: "bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300",
            retry_publish: "bg-violet-100 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300",
            failed: "bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300",
            active: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
            paused: "bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200",
        };
        return map[status] || "bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-200";
    }

    async function loadSummary() {
        const data = await jsonFetch("/api/openclaw/dashboard/summary");
        if (data.status !== "ok") return;
        const summary = data.summary || {};
        document.getElementById("summaryCampaignCount").textContent = summary.campaign_count || 0;
        document.getElementById("summaryActiveCampaigns").textContent = summary.active_campaign_count || 0;
        document.getElementById("summaryPendingApprovals").textContent = summary.pending_approval_count || 0;
        document.getElementById("summaryActionableCount").textContent = summary.actionable_count || 0;
        document.getElementById("summaryCompletedCount").textContent = summary.completed_count || 0;
        document.getElementById("summaryPartialCount").textContent = summary.partial_count || 0;
        document.getElementById("summaryFailedCount").textContent = summary.failed_count || 0;
        const latestAt = summary.latest_run_at ? `${summary.latest_run_status || "run"} @ ${summary.latest_run_at}` : "No runs yet";
        const latestRunEl = document.getElementById("summaryLatestRun");
        if (latestRunEl) {
            latestRunEl.textContent = latestAt;
        }
    }

    async function loadCampaigns() {
        const data = await jsonFetch("/api/openclaw/campaigns");
        if (data.status !== "ok") return;
        state.campaigns = data.campaigns || [];
        renderCampaigns();
    }

    function renderCampaigns() {
        const el = document.getElementById("campaignList");
        if (!state.campaigns.length) {
            el.innerHTML = `<div class="rounded-2xl bg-gray-50 p-4 text-sm text-gray-500 dark:bg-gray-900 dark:text-gray-400">No campaigns yet.</div>`;
            return;
        }

        el.innerHTML = state.campaigns.map((campaign) => `
            <div class="rounded-2xl border border-gray-200 p-4 dark:border-gray-700">
                <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                        <div class="flex items-center gap-2">
                            <h3 class="text-base font-black text-gray-900 dark:text-white">${escapeHtml(campaign.name)}</h3>
                            <span class="rounded-full px-2 py-1 text-[11px] font-black ${statusBadge(campaign.is_active ? "active" : "paused")}">${campaign.is_active ? "active" : "paused"}</span>
                        </div>
                        <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">Category: ${escapeHtml(campaign.category || "-")} · Approval: ${escapeHtml(campaign.approval_mode || "auto")} · Time: ${escapeHtml(campaign.schedule_time || "-")}</p>
                        <p class="mt-1 text-xs text-cyan-500 dark:text-cyan-300">OpenClaw AI: ${escapeHtml(campaign.ai_provider || "gemini")} / ${escapeHtml(campaign.ai_model || "gemini-3.5-flash")}</p>
                        <p class="mt-1 text-xs text-gray-400 dark:text-gray-500">Targets: ${(campaign.platforms_json || []).map((item) => `${item.platform}/${item.language}/${item.target_id}`).join(", ") || "-"}</p>
                    </div>
                    <div class="flex flex-wrap gap-2">
                        <button data-run-id="${campaign.id}" class="oc-run rounded-xl bg-cyan-500 px-3 py-2 text-xs font-black text-white transition hover:bg-cyan-600">Run now</button>
                        <button data-toggle-id="${campaign.id}" class="oc-toggle rounded-xl border border-gray-200 px-3 py-2 text-xs font-black text-gray-700 transition hover:bg-gray-100 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700">${campaign.is_active ? "Pause" : "Activate"}</button>
                    </div>
                </div>
            </div>
        `).join("");

        el.querySelectorAll(".oc-run").forEach((button) => {
            button.addEventListener("click", async () => {
                button.disabled = true;
                const campaignId = button.getAttribute("data-run-id");
                const result = await jsonFetch(`/api/openclaw/campaigns/${campaignId}/run`, { method: "POST" });
                button.disabled = false;
                if (result.status === "ok") {
                    toast(`Campaign started. run_id=${result.run_id}`, "success");
                    await Promise.all([loadRuns(), loadApprovals(), loadSummary()]);
                } else {
                    toast(result.error || "Campaign run failed", "error");
                }
            });
        });

        el.querySelectorAll(".oc-toggle").forEach((button) => {
            button.addEventListener("click", async () => {
                const campaignId = button.getAttribute("data-toggle-id");
                const result = await jsonFetch(`/api/openclaw/campaigns/${campaignId}/toggle`, { method: "POST" });
                if (result.status === "ok") {
                    await Promise.all([loadCampaigns(), loadSummary()]);
                } else {
                    toast(result.error || "Status update failed", "error");
                }
            });
        });
    }

    async function loadRuns() {
        const data = await jsonFetch("/api/openclaw/runs?limit=20");
        if (data.status !== "ok") return;
        state.runs = data.runs || [];
        renderRuns();
    }

    async function showRunDetails(runId) {
        const data = await jsonFetch(`/api/openclaw/runs/${runId}`);
        if (data.status !== "ok") {
            toast(data.error || "Failed to load run details", "error");
            return;
        }

        const run = data.run || {};
        const variants = data.variants || [];
        const tasks = data.tasks || [];
        const approvals = data.approvals || [];

        const body = `
            <div class="space-y-5">
                <div class="rounded-2xl bg-gray-50 p-4 dark:bg-gray-900">
                    <div><strong>Status:</strong> ${escapeHtml(run.status || "-")}</div>
                    <div><strong>Stage:</strong> ${escapeHtml(run.current_stage || "-")}</div>
                    <div><strong>Topic:</strong> ${escapeHtml(run.topic || "-")}</div>
                    <div><strong>Error:</strong> ${escapeHtml(run.error_message || "-")}</div>
                </div>
                <div>
                    <h4 class="mb-2 text-sm font-black">Variants</h4>
                    <div class="space-y-2">
                        ${variants.map((variant) => `
                            <div class="rounded-2xl border border-gray-200 p-3 dark:border-gray-700">
                                <div class="font-bold">${escapeHtml(variant.title || "(untitled)")}</div>
                                <div class="mt-1 text-xs text-gray-500 dark:text-gray-400">${escapeHtml(variant.platform)} / ${escapeHtml(variant.language)} / ${escapeHtml(variant.publish_status)}</div>
                                <div class="mt-2 text-xs text-gray-500 dark:text-gray-400">score=${escapeHtml(variant.quality_score || "-")} url=${escapeHtml(variant.publish_url || "-")}</div>
                            </div>
                        `).join("") || `<div class="text-sm text-gray-500 dark:text-gray-400">No variants.</div>`}
                    </div>
                </div>
                <div>
                    <h4 class="mb-2 text-sm font-black">Tasks</h4>
                    <div class="space-y-2">
                        ${tasks.map((task) => `
                            <div class="rounded-2xl border border-gray-200 p-3 text-xs dark:border-gray-700">
                                <div><strong>${escapeHtml(task.task_type)}</strong> · ${escapeHtml(task.status)}</div>
                                <div class="mt-1 text-gray-500 dark:text-gray-400">${escapeHtml(task.target_id || "-")} ${task.error_message ? "· " + escapeHtml(task.error_message) : ""}</div>
                            </div>
                        `).join("") || `<div class="text-sm text-gray-500 dark:text-gray-400">No tasks.</div>`}
                    </div>
                </div>
                <div>
                    <h4 class="mb-2 text-sm font-black">Approvals</h4>
                    <div class="space-y-2">
                        ${approvals.map((item) => `
                            <div class="rounded-2xl border border-gray-200 p-3 text-xs dark:border-gray-700">
                                <div><strong>${escapeHtml(item.status)}</strong> · ${escapeHtml(item.target_id || "-")}</div>
                                <div class="mt-1 text-gray-500 dark:text-gray-400">${escapeHtml(item.review_note || "-")}</div>
                            </div>
                        `).join("") || `<div class="text-sm text-gray-500 dark:text-gray-400">No approvals.</div>`}
                    </div>
                </div>
            </div>
        `;
        openPreview(`Run #${runId}`, `campaign_id=${run.campaign_id || "-"} · created_at=${run.created_at || "-"}`, body);
    }

    function renderRuns() {
        const el = document.getElementById("runList");
        if (!state.runs.length) {
            el.innerHTML = `<div class="rounded-2xl bg-gray-50 p-4 text-sm text-gray-500 dark:bg-gray-900 dark:text-gray-400">No runs yet.</div>`;
            return;
        }

        el.innerHTML = state.runs.map((run) => `
            <div class="rounded-2xl border border-gray-200 p-4 dark:border-gray-700">
                <div class="flex items-start justify-between gap-3">
                    <div>
                        <div class="flex items-center gap-2">
                            <h3 class="text-sm font-black text-gray-900 dark:text-white">Run #${run.id}</h3>
                            <span class="rounded-full px-2 py-1 text-[11px] font-black ${statusBadge(run.status)}">${escapeHtml(run.status)}</span>
                        </div>
                        <p class="mt-2 text-sm text-gray-600 dark:text-gray-300">${escapeHtml(run.topic || "Topic not generated yet")}</p>
                        <p class="mt-1 text-xs text-gray-400 dark:text-gray-500">campaign_id=${run.campaign_id} · stage=${escapeHtml(run.current_stage || "-")} · created_at=${escapeHtml(run.created_at || "-")}</p>
                    </div>
                    <div class="flex flex-wrap gap-2">
                        <button data-view-run-id="${run.id}" class="oc-view-run rounded-xl border border-gray-200 px-3 py-2 text-xs font-black text-gray-700 transition hover:bg-gray-100 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700">Details</button>
                        ${(run.status === "failed" || run.status === "partial") ? `<button data-retry-run-id="${run.id}" class="oc-retry-run rounded-xl bg-violet-500 px-3 py-2 text-xs font-black text-white transition hover:bg-violet-600">Retry</button>` : ""}
                    </div>
                </div>
            </div>
        `).join("");

        el.querySelectorAll(".oc-view-run").forEach((button) => {
            button.addEventListener("click", () => showRunDetails(button.getAttribute("data-view-run-id")));
        });

        el.querySelectorAll(".oc-retry-run").forEach((button) => {
            button.addEventListener("click", async () => {
                const runId = button.getAttribute("data-retry-run-id");
                const result = await jsonFetch(`/api/openclaw/runs/${runId}/retry`, { method: "POST" });
                if (result.status === "ok") {
                    toast(`Retry started for run_id=${runId}`, "success");
                    await Promise.all([loadRuns(), loadApprovals(), loadSummary()]);
                } else {
                    toast(result.error || "Retry failed", "error");
                }
            });
        });
    }

    async function loadApprovals() {
        const data = await jsonFetch("/api/openclaw/approvals?status=pending");
        if (data.status !== "ok") return;
        state.approvals = data.approvals || [];
        renderApprovals();
    }

    async function reloadDashboard() {
        await Promise.all([loadSummary(), loadCampaigns(), loadRuns(), loadApprovals()]);
    }

    async function retryFailedRuns() {
        const button = document.getElementById("btnRetryFailedRuns");
        if (button) button.disabled = true;
        try {
            const result = await jsonFetch("/api/openclaw/runs/retry-failed?limit=10", { method: "POST" });
            if (result.status === "ok") {
                toast(`Retry queued for ${result.processed || 0} failed runs`, "success");
                await reloadDashboard();
            } else {
                toast(result.error || "Bulk retry failed", "error");
            }
        } finally {
            if (button) button.disabled = false;
        }
    }

    function setAutoRefresh(enabled) {
        state.autoRefreshEnabled = enabled;
        const button = document.getElementById("btnAutoRefresh");
        if (button) {
            button.textContent = enabled ? "Auto refresh: ON" : "Auto refresh: OFF";
        }
        if (state.refreshTimer) {
            clearInterval(state.refreshTimer);
            state.refreshTimer = null;
        }
        if (enabled) {
            state.refreshTimer = setInterval(() => {
                reloadDashboard().catch(() => {});
            }, 30000);
        }
    }

    function renderApprovals() {
        const el = document.getElementById("approvalList");
        if (!state.approvals.length) {
            el.innerHTML = `<div class="rounded-2xl bg-gray-50 p-4 text-sm text-gray-500 dark:bg-gray-900 dark:text-gray-400">No pending approvals.</div>`;
            return;
        }

        el.innerHTML = state.approvals.map((item) => `
            <div class="rounded-2xl border border-gray-200 p-4 dark:border-gray-700">
                <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                        <div class="text-sm font-black text-gray-900 dark:text-white">${escapeHtml(item.title || "(untitled)")}</div>
                        <div class="mt-1 text-xs text-gray-400 dark:text-gray-500">run_id=${item.run_id} · target_id=${escapeHtml(item.target_id)}</div>
                        <p class="mt-2 line-clamp-3 text-sm text-gray-600 dark:text-gray-300">${escapeHtml(item.summary || "No summary")}</p>
                    </div>
                    <div class="flex flex-wrap gap-2">
                        <button data-preview-id="${item.id}" class="oc-preview rounded-xl border border-gray-200 px-3 py-2 text-xs font-black text-gray-700 transition hover:bg-gray-100 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700">Preview</button>
                        <button data-approve-id="${item.id}" class="oc-approve rounded-xl bg-emerald-500 px-3 py-2 text-xs font-black text-white transition hover:bg-emerald-600">Approve</button>
                        <button data-reject-id="${item.id}" class="oc-reject rounded-xl bg-rose-500 px-3 py-2 text-xs font-black text-white transition hover:bg-rose-600">Reject</button>
                    </div>
                </div>
            </div>
        `).join("");

        el.querySelectorAll(".oc-preview").forEach((button) => {
            button.addEventListener("click", () => {
                const approvalId = button.getAttribute("data-preview-id");
                const item = state.approvals.find((approval) => String(approval.id) === String(approvalId));
                if (!item) return;
                const body = `
                    <div class="space-y-4">
                        <div class="rounded-2xl bg-gray-50 p-4 dark:bg-gray-900">
                            <div><strong>Summary</strong></div>
                            <div class="mt-2">${nl2br(item.summary || "No summary")}</div>
                        </div>
                        <div class="rounded-2xl border border-gray-200 p-4 dark:border-gray-700">
                            ${item.content_html || "<div class='text-sm text-gray-500 dark:text-gray-400'>No content</div>"}
                        </div>
                    </div>
                `;
                openPreview(item.title || "Approval preview", `run_id=${item.run_id} · target_id=${item.target_id}`, body);
            });
        });

        el.querySelectorAll(".oc-approve").forEach((button) => {
            button.addEventListener("click", async () => {
                const approvalId = button.getAttribute("data-approve-id");
                const result = await jsonFetch(`/api/openclaw/approvals/${approvalId}/approve`, {
                    method: "POST",
                    body: JSON.stringify({ reviewer: "dashboard", note: "Approved from OpenClaw dashboard" }),
                });
                if (result.status === "ok") {
                    toast("Approval processed", "success");
                    closePreview();
                    await Promise.all([loadApprovals(), loadRuns(), loadSummary()]);
                } else {
                    toast(result.error || "Approval failed", "error");
                }
            });
        });

        el.querySelectorAll(".oc-reject").forEach((button) => {
            button.addEventListener("click", async () => {
                const approvalId = button.getAttribute("data-reject-id");
                const result = await jsonFetch(`/api/openclaw/approvals/${approvalId}/reject`, {
                    method: "POST",
                    body: JSON.stringify({ reviewer: "dashboard", note: "Rejected from OpenClaw dashboard" }),
                });
                if (result.status === "ok") {
                    toast("Rejection processed", "success");
                    closePreview();
                    await Promise.all([loadApprovals(), loadRuns(), loadSummary()]);
                } else {
                    toast(result.error || "Reject failed", "error");
                }
            });
        });
    }

    async function createCampaign() {
        const payload = {
            name: document.getElementById("campaignName").value.trim(),
            category: document.getElementById("campaignCategory").value.trim() || "IT",
            default_language: document.getElementById("campaignLanguage").value,
            ai_provider: document.getElementById("campaignAiProvider").value,
            ai_model: document.getElementById("campaignAiModel").value,
            approval_mode: document.getElementById("campaignApprovalMode").value,
            schedule_time: document.getElementById("campaignScheduleTime").value || "09:00",
            quality_min_score: parseInt(document.getElementById("campaignQualityMinScore").value, 10) || 82,
            platforms: collectTargets(),
        };

        if (!payload.name) {
            toast("Enter a campaign name.", "error");
            return;
        }
        if (!payload.platforms.length) {
            toast("Add at least one target platform.", "error");
            return;
        }

        const result = await jsonFetch("/api/openclaw/campaigns", {
            method: "POST",
            body: JSON.stringify(payload),
        });
        if (result.status === "ok") {
            toast("Campaign created.", "success");
            document.getElementById("campaignName").value = "";
            await Promise.all([loadCampaigns(), loadSummary()]);
        } else {
            toast(result.error || "Campaign creation failed", "error");
        }
    }

    function bindEvents() {
        document.getElementById("btnAddTarget").addEventListener("click", () => addTargetRow());
        document.getElementById("btnCreateCampaign").addEventListener("click", createCampaign);
        document.getElementById("btnRefreshSummary").addEventListener("click", loadSummary);
        document.getElementById("btnRefreshCampaigns").addEventListener("click", loadCampaigns);
        document.getElementById("btnRefreshRuns").addEventListener("click", loadRuns);
        const retryButton = document.getElementById("btnRetryFailedRuns");
        if (retryButton) {
            retryButton.addEventListener("click", retryFailedRuns);
        }
        const autoRefreshButton = document.getElementById("btnAutoRefresh");
        if (autoRefreshButton) {
            autoRefreshButton.addEventListener("click", () => setAutoRefresh(!state.autoRefreshEnabled));
        }
        document.getElementById("btnClosePreview").addEventListener("click", closePreview);
        document.getElementById("campaignAiProvider").addEventListener("change", (event) => {
            renderAiModels(event.target.value);
        });
        document.getElementById("openclawPreviewModal").addEventListener("click", (event) => {
            if (event.target.id === "openclawPreviewModal") {
                closePreview();
            }
        });
    }

    async function bootstrap() {
        addTargetRow({ platform: "wordpress", language: "ko", target_id: "wordpress" });
        renderAiModels("gemini", "gemini-3.5-flash");
        bindEvents();
        setAutoRefresh(true);
        await reloadDashboard();
    }

    document.addEventListener("DOMContentLoaded", bootstrap);
})();
