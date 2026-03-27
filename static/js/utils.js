/**
 * 피카디리스튜디오 유틸리티 함수
 */

const Utils = {
    // 숫자 포맷팅
    formatNumber(num) {
        if (!num) return '0';
        num = parseInt(num);
        if (num >= 100000000) return (num / 100000000).toFixed(1) + '억';
        if (num >= 10000) return (num / 10000).toFixed(1) + '만';
        if (num >= 1000) return (num / 1000).toFixed(1) + '천';
        return num.toLocaleString();
    },

    // 날짜 포맷팅
    formatDate(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diff = now - date;
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));

        if (days === 0) return '오늘';
        if (days === 1) return '어제';
        if (days < 7) return `${days}일 전`;
        if (days < 30) return `${Math.floor(days / 7)}주 전`;
        if (days < 365) return `${Math.floor(days / 30)}달 전`;
        return `${Math.floor(days / 365)}년 전`;
    },

    // 시간 파싱 (ISO 8601)
    parseDuration(duration) {
        const match = duration.match(/PT(\d+H)?(\d+M)?(\d+S)?/);
        const hours = parseInt(match[1]) || 0;
        const minutes = parseInt(match[2]) || 0;
        const seconds = parseInt(match[3]) || 0;
        return hours * 3600 + minutes * 60 + seconds;
    },

    // 시간 포맷팅
    formatDuration(seconds) {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = seconds % 60;

        if (h > 0) {
            return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
        }
        return `${m}:${s.toString().padStart(2, '0')}`;
    },

    // 바이럴 스코어 계산
    calculateViralScore(video) {
        const views = parseInt(video.statistics?.viewCount || 0);
        const likes = parseInt(video.statistics?.likeCount || 0);
        const comments = parseInt(video.statistics?.commentCount || 0);
        const publishedAt = new Date(video.snippet?.publishedAt);
        const daysSincePublished = Math.max(1, (Date.now() - publishedAt) / (1000 * 60 * 60 * 24));

        // 일별 조회수
        const viewsPerDay = views / daysSincePublished;

        // 참여율
        const engagementRate = views > 0 ? (likes + comments) / views : 0;

        // 스코어 계산
        let score = 0;
        score += Math.min(40, viewsPerDay / 1000 * 10);
        score += Math.min(30, engagementRate * 1000);
        score += Math.min(20, Math.log10(views + 1) * 3);
        score += daysSincePublished < 7 ? 10 : daysSincePublished < 30 ? 5 : 0;

        return Math.min(100, Math.round(score));
    },

    // 클립보드 복사
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (e) {
            console.error('복사 실패:', e);
            return false;
        }
    },

    // 파일 다운로드
    downloadFile(content, filename, type = 'text/plain') {
        const blob = new Blob([content], { type });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    },

    // 로컬 스토리지 헬퍼
    storage: {
        get(key, defaultValue = null) {
            try {
                const item = localStorage.getItem(key);
                return item ? JSON.parse(item) : defaultValue;
            } catch {
                return defaultValue;
            }
        },

        set(key, value) {
            try {
                localStorage.setItem(key, JSON.stringify(value));
                return true;
            } catch {
                return false;
            }
        },

        remove(key) {
            localStorage.removeItem(key);
        }
    },

    // 알림 토스트
    showToast(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = `toast-notification fixed right-4 px-6 py-3 rounded-lg shadow-lg z-50 transition-all transform translate-x-full opacity-0`;

        const colors = {
            info: 'bg-blue-500 text-white',
            success: 'bg-green-500 text-white',
            warning: 'bg-yellow-500 text-white',
            error: 'bg-red-500 text-white'
        };

        toast.className += ` ${colors[type] || colors.info}`;
        toast.textContent = message;

        // 기존 토스트들의 위치 계산
        const existingToasts = document.querySelectorAll('.toast-notification');
        let bottomPosition = 16; // 기본 bottom: 1rem (16px)

        existingToasts.forEach(existingToast => {
            const rect = existingToast.getBoundingClientRect();
            const currentBottom = parseInt(existingToast.style.bottom) || 16;
            const toastHeight = rect.height;
            const gap = 8; // 토스트 간 간격

            if (currentBottom + toastHeight + gap > bottomPosition) {
                bottomPosition = currentBottom + toastHeight + gap;
            }
        });

        toast.style.bottom = `${bottomPosition}px`;
        document.body.appendChild(toast);

        // 애니메이션
        requestAnimationFrame(() => {
            toast.classList.remove('translate-x-full', 'opacity-0');
        });

        setTimeout(() => {
            toast.classList.add('translate-x-full', 'opacity-0');
            setTimeout(() => {
                toast.remove();
                // 토스트 제거 후 남은 토스트들 위치 재조정
                Utils.repositionToasts();
            }, 300);
        }, duration);
    },

    // 토스트 위치 재조정 (내부 사용)
    repositionToasts() {
        const existingToasts = Array.from(document.querySelectorAll('.toast-notification'));
        existingToasts.sort((a, b) => {
            const bottomA = parseInt(a.style.bottom) || 16;
            const bottomB = parseInt(b.style.bottom) || 16;
            return bottomA - bottomB;
        });

        let currentBottom = 16;
        const gap = 8;

        existingToasts.forEach(toast => {
            toast.style.bottom = `${currentBottom}px`;
            currentBottom += toast.getBoundingClientRect().height + gap;
        });
    },

    // 로딩 상태 표시
    setLoading(button, loading, loadingText = '처리 중...') {
        if (loading) {
            button.disabled = true;
            if (!button.dataset.originalText) {
                button.dataset.originalText = button.innerHTML;
            }
            button.innerHTML = `<span class="loader"></span><span>${loadingText}</span>`;
        } else {
            button.disabled = false;
            button.innerHTML = button.dataset.originalText || button.innerHTML;
        }
    },

    // 디바운스
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
};

// 전역 사용
window.Utils = Utils;
