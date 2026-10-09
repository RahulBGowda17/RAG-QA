/**
 * Evaluation and ablation benchmarking logic
 */
const EvaluationManager = {
    init() {
        const btn = document.getElementById('btn-run-eval');
        btn.addEventListener('click', () => this.runEvaluation());
    },

    async runEvaluation() {
        const spinner = document.getElementById('eval-spinner');
        const tbody = document.getElementById('eval-tbody');
        const btn = document.getElementById('btn-run-eval');

        spinner.style.display = 'block';
        btn.disabled = true;

        try {
            const res = await API.runEvaluation();
            spinner.style.display = 'none';
            btn.disabled = false;

            if (res.success && res.report) {
                const bms = res.report.benchmarks;
                tbody.innerHTML = bms.map(b => `
                    <tr>
                        <td><strong>${b.pipeline_name}</strong></td>
                        <td><span class="status-badge badge-high">${(b.hit_rate * 100).toFixed(1)}%</span></td>
                        <td>${b.mrr.toFixed(3)}</td>
                        <td>${(b.faithfulness * 100).toFixed(1)}%</td>
                        <td><span class="status-badge badge-med">${((b.answer_relevance || b.hit_rate) * 100).toFixed(1)}%</span></td>
                        <td>${b.latency_sec.toFixed(4)}s</td>
                    </tr>
                `).join('');

                const insights = res.report.research_insights;
                if (insights) {
                    document.getElementById('rq-insights').innerHTML = `
                        <div class="rq-item"><strong>RQ1 (Dense vs. Hybrid):</strong> ${insights.RQ1_hybrid_vs_dense}</div>
                        <div class="rq-item"><strong>RQ2 (CrossEncoder Reranker):</strong> ${insights.RQ2_reranker_impact}</div>
                        <div class="rq-item"><strong>RQ3 (Query Rewriting):</strong> ${insights.RQ3_rewriting_impact}</div>
                        <div class="rq-item"><strong>RQ4 (Verification Layer):</strong> ${insights.RQ4_verification}</div>
                        <div class="rq-item"><strong>RQ5 (Latency Budget):</strong> ${insights.RQ5_latency_tradeoff}</div>
                    `;
                }
            } else {
                tbody.innerHTML = `<tr><td colspan="5" class="text-center" style="color:var(--danger);">${res.error || 'Evaluation failed'}</td></tr>`;
            }
        } catch (err) {
            spinner.style.display = 'none';
            btn.disabled = false;
            tbody.innerHTML = `<tr><td colspan="5" class="text-center" style="color:var(--danger);">Error executing evaluation: ${err.message}</td></tr>`;
        }
    }
};
