// UI Feature Toggles for Settings Page

// Load UI toggles from localStorage
function loadUIToggles() {
    const showMusicGen = localStorage.getItem('showMusicGenPage') !== 'false'; // default: true (shown)
    const checkbox = document.getElementById('showMusicGenPage');
    if (checkbox) {
        checkbox.checked = showMusicGen;
    }
}

// Toggle Music Generation Page visibility
function toggleMusicGenPage(show) {
    localStorage.setItem('showMusicGenPage', show);
    Utils.showToast(show ? '배경음악 페이지가 표시됩니다' : '배경음악 페이지가 숨겨집니다', 'success');

    // Update sidebar immediately
    updateSidebarVisibility();
}

// Update sidebar menu visibility based on toggles
function updateSidebarVisibility() {
    const showMusicGen = localStorage.getItem('showMusicGenPage') !== 'false';
    const musicGenLink = document.querySelector('a[href="/music-gen"]');

    if (musicGenLink) {
        if (showMusicGen) {
            musicGenLink.parentElement.classList.remove('hidden');
        } else {
            musicGenLink.parentElement.classList.add('hidden');
        }
    }
}

// Initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        if (window.location.pathname === '/settings') {
            loadUIToggles();
        }
        updateSidebarVisibility();
    });
} else {
    if (window.location.pathname === '/settings') {
        loadUIToggles();
    }
    updateSidebarVisibility();
}
