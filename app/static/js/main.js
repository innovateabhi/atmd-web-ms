// Initialize Lucide icons on DOM ready
document.addEventListener('DOMContentLoaded', function () {
    if (window.lucide) {
        lucide.createIcons();
    }
});

// Helper for formatting millisecond durations
function formatMs(val) {
    if (val === null || val === undefined || isNaN(val)) return 'N/A';
    return Number(val).toFixed(1) + ' ms';
}

// Global Toast or Banner utility
function showBanner(message, type = 'info') {
    const alertBox = document.createElement('div');
    alertBox.className = `alert alert-${type} alert-dismissible fade show shadow-sm`;
    alertBox.role = 'alert';
    alertBox.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    const container = document.querySelector('.content-container');
    if (container) {
        container.insertBefore(alertBox, container.firstChild);
        setTimeout(() => {
            alertBox.classList.remove('show');
            setTimeout(() => alertBox.remove(), 200);
        }, 5000);
    }
}
