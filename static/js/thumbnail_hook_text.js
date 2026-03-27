// AI 썸네일 후킹 문구 생성 함수들

// [NEW] AI 후킹 문구 생성
async function generateHookTexts(buttonId = 'hookTextBtn') {
    const projectId = getCurrentProject();
    if (!projectId) {
        Utils.showToast('프로젝트를 먼저 선택하세요', 'warning');
        return;
    }

    const btn = document.getElementById(buttonId);
    if (btn) Utils.setLoading(btn, true, '생성 중...');

    try {
        const style = document.getElementById('thumbnailStyle').value;
        const title = document.getElementById('videoTitle')?.value?.trim() || '';
        const lang = (typeof detectLanguageFromTitle === 'function')
            ? detectLanguageFromTitle(title)
            : (window.targetLang || 'ko');

        const response = await fetch('/api/thumbnail/generate-text', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project_id: parseInt(projectId),
                thumbnail_style: style,
                target_language: lang
            })
        });

        const result = await response.json();

        if (result.status === 'ok') {
            displayHookTexts(result.texts, result.reasoning);

            // 모든 문구를 캔버스 레이어로 자동 적용
            if (result.texts && result.texts.length > 0) {
                const textsToApply = result.texts.slice(0, 3);
                const _pos = ['row3', 'row4', 'row5'];
                const _colors = ['#FFFFFF', '#FFFF00', '#00D4FF'];
                textLayers = textsToApply.map((text, i) => ({
                    text: text,
                    position: _pos[i] || 'row5',
                    x_offset: 0,
                    y_offset: 0,
                    font_family: 'Recipekorea',
                    font_size: 89,
                    color: _colors[i] || '#FFFFFF',
                    stroke_color: '#000000',
                    stroke_width: 8,
                    bg_color: null
                }));

                if (typeof renderLayers === 'function') renderLayers();
                if (typeof drawPreview === 'function') drawPreview();
            }

            Utils.showToast('후킹 문구 3종이 사전 배치되었습니다!', 'success');
        } else {
            Utils.showToast('생성 실패: ' + result.error, 'error');
        }

    } catch (e) {
        console.error('Hook text generation error:', e);
        Utils.showToast('오류: ' + e.message, 'error');
    } finally {
        Utils.setLoading(btn, false);
    }
}

// [NEW] 생성된 문구 표시
function displayHookTexts(texts, reasoning) {
    const section = document.getElementById('hookTextsSection');
    const list = document.getElementById('hookTextsList');
    const reasoningEl = document.getElementById('hookReasoning');

    if (!section || !list) {
        console.error('Hook texts UI elements not found');
        return;
    }

    section.classList.remove('hidden');

    // 문구 버튼 생성
    list.innerHTML = texts.map((text, i) => `
        <button 
            onclick="applyHookText('${text.replace(/'/g, "\\'")}', ${i})" 
            class="px-3 py-2 bg-white dark:bg-gray-700 border-2 border-blue-300 dark:border-blue-600 rounded-lg hover:bg-blue-100 dark:hover:bg-blue-800 transition text-sm font-bold text-gray-800 dark:text-white shadow-sm hover:shadow-md"
            title="클릭하여 적용"
        >
            ${i === 0 ? '⭐ ' : ''}${text}
        </button>
    `).join('');

    // 선택 이유 표시
    if (reasoning && reasoningEl) {
        reasoningEl.textContent = `💡 ${reasoning}`;
    }

    // 스크롤
    section.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// [NEW] 문구 적용
function applyHookText(text, index = 0) {
    if (typeof textLayers === 'undefined') {
        console.error('textLayers not defined');
        return;
    }

    // 지정된 인덱스에 레이어가 없으면 생성
    while (textLayers.length <= index) {
        startNewLayer();
    }

    const currentStyle = document.getElementById('thumbnailStyle').value || 'face';

    // 스타일별 텍스트 설정 (색상, 테두리, 폰트)
    const styleConfigs = {
        'face': { color: '#ffffff', stroke_color: '#000000', stroke_width: 8, font_family: 'Recipekorea' },
        'text': { color: '#ffff00', stroke_color: '#000000', stroke_width: 10, font_family: 'GmarketSansBold' },
        'contrast': { color: '#ffffff', stroke_color: '#ff0000', stroke_width: 8, font_family: 'GmarketSansBold' },
        'mystery': { color: '#adff2f', stroke_color: '#000000', stroke_width: 6, font_family: 'GmarketSansMedium' },
        'minimal': { color: '#000000', stroke_color: '#ffffff', stroke_width: 2, font_family: 'NanumGothic' },
        'dramatic': { color: '#ff0000', stroke_color: '#000000', stroke_width: 10, font_family: 'Recipekorea' },
        'japanese_viral': { color: '#00ff00', stroke_color: '#000000', stroke_width: 8, font_family: 'GmarketSansBold' },
        'ghibli': { color: '#ffffff', stroke_color: '#4a4a4a', stroke_width: 4, font_family: 'NanumPen' },
        'wimpy': { color: '#000000', stroke_color: 'transparent', stroke_width: 0, font_family: 'NanumPen' }
    };

    const config = styleConfigs[currentStyle] || styleConfigs['face'];

    // 해당 인덱스 레이어에 적용
    const layer = textLayers[index];
    layer.text = text;

    if (config) {
        layer.color = index === 1 ? '#ffff00' : config.color; // 중앙 문구는 노란색 강조 유지
        layer.stroke_color = config.stroke_color;
        layer.stroke_width = config.stroke_width;
        layer.font_family = config.font_family;

        // 위치 자동 조정
        if (index === 0) layer.position = 'row3';
        else if (index === 1) layer.position = 'row4';
        else layer.position = 'row5';
    }

    // UI 업데이트
    if (typeof renderLayers === 'function') renderLayers();
    if (typeof drawPreview === 'function') drawPreview();

    Utils.showToast(`${index + 1}번 문구 업데이트됨`, 'success');
}

function startNewLayer() {
    if (typeof addLayer === 'function') {
        addLayer();
    } else {
        textLayers.push({
            text: '새 텍스트',
            position: 'center',
            x_offset: 0,
            y_offset: 0,
            font_family: 'Recipekorea',
            font_size: 72,
            color: '#FFFFFF',
            stroke_color: '#000000',
            stroke_width: 5
        });
    }
}
