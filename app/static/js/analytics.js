/**
 * Analytics and Chart.js integration
 */
let evidenceChartInstance = null;
let queryVolumeChartInstance = null;

const AnalyticsManager = {
    async init() {
        document.getElementById('btn-refresh-analytics').addEventListener('click', () => {
            this.loadMetrics();
        });
        await this.loadMetrics();
    },

    async loadMetrics() {
        try {
            const res = await API.getAnalytics();
            if (!res.success) return;
            const m = res.metrics;

            document.getElementById('metric-docs').innerText = m.total_documents;
            document.getElementById('metric-chunks').innerText = m.total_chunks;
            document.getElementById('metric-queries').innerText = m.total_queries;
            document.getElementById('metric-ret-lat').innerText = m.avg_retrieval_latency + 's';
            document.getElementById('metric-gen-lat').innerText = m.avg_generation_latency + 's';

            this.renderEvidenceChart(m.evidence_status_distribution || {});
            this.renderVolumeChart(m.daily_volume || []);
        } catch (e) {
            console.error('Analytics load error:', e);
        }
    },

    renderEvidenceChart(dist) {
        const ctx = document.getElementById('chart-evidence-dist');
        if (!ctx) return;

        const labels = Object.keys(dist);
        const data = Object.values(dist);

        if (evidenceChartInstance) {
            evidenceChartInstance.destroy();
        }

        if (labels.length === 0) {
            labels.push('No queries yet');
            data.push(1);
        }

        evidenceChartInstance = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: ['#10b981', '#6366f1', '#f59e0b', '#ef4444', '#64748b']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { color: '#94a3b8' } }
                }
            }
        });
    },

    renderVolumeChart(daily) {
        const ctx = document.getElementById('chart-daily-queries');
        if (!ctx) return;

        const labels = daily.map(d => d.query_date);
        const data = daily.map(d => d.query_count);

        if (queryVolumeChartInstance) {
            queryVolumeChartInstance.destroy();
        }

        queryVolumeChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels.length ? labels : ['Today'],
                datasets: [{
                    label: 'Queries',
                    data: data.length ? data : [0],
                    borderColor: '#38bdf8',
                    backgroundColor: 'rgba(56, 189, 248, 0.1)',
                    fill: true,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { ticks: { color: '#94a3b8' }, grid: { color: '#334155' } },
                    y: { ticks: { color: '#94a3b8' }, grid: { color: '#334155' } }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }
};
