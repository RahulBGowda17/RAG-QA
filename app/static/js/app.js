/**
 * Main application coordinator & tab switcher
 */
document.addEventListener('DOMContentLoaded', () => {
    // Navigation Tabs Switcher
    const navTabs = document.querySelectorAll('.nav-tab');
    const tabPanes = document.querySelectorAll('.tab-pane');

    navTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetId = tab.getAttribute('data-tab');

            navTabs.forEach(t => t.classList.remove('active'));
            tabPanes.forEach(p => p.classList.remove('active'));

            tab.classList.add('active');
            document.getElementById(targetId).classList.add('active');

            if (targetId === 'analytics-view' && window.AnalyticsManager) {
                AnalyticsManager.loadMetrics();
            }
            if (targetId === 'docs-view' && window.DocumentsManager) {
                DocumentsManager.loadDocuments();
            }
        });
    });

    // Initialize modules
    DocumentsManager.init();
    ChatManager.init();
    AnalyticsManager.init();
    EvaluationManager.init();
});
