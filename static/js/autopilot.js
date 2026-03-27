// --- Initialization ---

// 전역 채널 목록 캐시
window.channelList = [];

async function loadChannels() {
    try {
        const res = await fetch('/api/channels');
        const data = await res.json();
        window.channelList = data.channels || data || [];
        // 싱글모드 폼의 채널 드롭다운도 채움
        const sel = document.getElementById('youtubeChannelId');
        if (sel) {
            const currentVal = sel.value;
            // 기본 옵션 이후 기존 옵션 제거 후 재추가
            while (sel.options.length > 1) sel.remove(1);
            window.channelList.forEach(ch => {
                const opt = document.createElement('option');
                opt.value = ch.id;
                opt.textContent = ch.name;
                sel.appendChild(opt);
            });
            if (currentVal) sel.value = currentVal;
        }
    } catch (e) {
        console.error('Failed to load channels:', e);
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    // 1. Load Presets (Styles & Voices)
    await Promise.all([loadStyles(), loadVoices(), fetchPresets(), loadChannels()]);

    // 2. Load Saved Settings (Global / Default Project)
    // 2. Load Saved Settings (Global / Default Project)
    await Promise.all([loadSavedSettings(), loadSubtitleDefaults()]);

    // 3. Event Listeners
    const startBtn = document.getElementById('startAutopilotBtn');
    if (startBtn) {
        startBtn.addEventListener('click', startAutopilot);
    }

    const sceneRange = document.getElementById('videoSceneCount');
    const sceneVal = document.getElementById('sceneCountVal');
    const allVideoCheck = document.getElementById('allVideoCheck');

    const sceneInline = document.getElementById('sceneCountInline');
    if (sceneRange && sceneVal) {
        sceneRange.addEventListener('input', (e) => {
            if (allVideoCheck && allVideoCheck.checked) return;
            sceneVal.textContent = `${e.target.value} ${i18n.unit_scenes}`;
            if (sceneInline) sceneInline.textContent = e.target.value;
        });
    }

    if (allVideoCheck && sceneRange && sceneVal) {
        allVideoCheck.addEventListener('change', (e) => {
            if (e.target.checked) {
                sceneRange.disabled = true;
                sceneRange.classList.add('opacity-30');
                sceneVal.textContent = `${i18n.label_all_caps} ${i18n.unit_scenes}`;
                sceneVal.classList.replace('bg-pink-500/10', 'bg-pink-500');
                sceneVal.classList.replace('text-pink-400', 'text-white');
                if (sceneInline) sceneInline.textContent = i18n.label_all_caps;
            } else {
                sceneRange.disabled = false;
                sceneRange.classList.remove('opacity-30');
                sceneVal.textContent = `${sceneRange.value} ${i18n.unit_scenes}`;
                sceneVal.classList.replace('bg-pink-500', 'bg-pink-500/10');
                sceneVal.classList.replace('text-white', 'text-pink-400');
                if (sceneInline) sceneInline.textContent = sceneRange.value;
            }
        });
    }

    // [NEW] Check tab parameter - auto switch to batch tab
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('tab') === 'batch') {
        switchTab('batch');
    }

    // [NEW] Check Monitor Mode
    if (urlParams.get('monitor') === 'true' && urlParams.get('project_id')) {
        const pid = urlParams.get('project_id');
        console.log("🔄 Monitoring Project:", pid);
        const startBtn = document.getElementById('startAutopilotBtn');
        if (startBtn) {
            startBtn.disabled = true;
            startBtn.innerText = `${i18n.status_processing_monitor}`;
        }
        pollStatus(pid);
    }

    // [NEW] Start Logs Polling for Batch Mode
    setInterval(pollBatchLogs, 3000);
});


// Styles will be loaded dynamically from API
async function loadStyles() {
    // 1. Visual Styles (fetch from DB)
    const vGrid = document.getElementById('styleSelectorGrid');
    if (vGrid) {
        vGrid.innerHTML = `<div class="col-span-full py-4 text-center text-gray-500 text-[10px]">${i18n.status_loading}</div>`;
        try {
            const res = await fetch('/api/settings/style-presets');
            const data = await res.json();

            vGrid.innerHTML = '';
            Object.entries(data).forEach(([key, val]) => {
                // If customized style has image_url, use it. Otherwise, use default path.
                const imgUrl = (typeof val === 'object' && val.image_url) ? val.image_url : `/static/img/styles/style_${key}.png`;
                const hasInstruction = (typeof val === 'object' && val.gemini_instruction && val.gemini_instruction.trim().length > 0);

                const style = {
                    id: key,
                    name: (typeof val === 'object' && val.name_ko) ? val.name_ko : key,
                    img: imgUrl,
                    hasInstruction: hasInstruction
                };
                const div = createStyleCard(style, 'imageStyle');
                vGrid.appendChild(div);
            });

            // Set default
            const currentImgStyle = document.getElementById('imageStyle').value;
            if (currentImgStyle && data[currentImgStyle]) {
                selectStyle('imageStyle', currentImgStyle);
            } else {
                const firstKey = Object.keys(data)[0];
                if (firstKey) selectStyle('imageStyle', firstKey);
            }
        } catch (e) {
            console.error("Failed to load visual styles:", e);
        }
    }

    // 2. Thumbnail Styles (fetch from DB)
    const tGrid = document.getElementById('thumbnailStyleGrid');
    if (tGrid) {
        tGrid.innerHTML = `<div class="col-span-full py-4 text-center text-gray-500 text-[10px]">${i18n.status_loading}</div>`;
        try {
            const res = await fetch('/api/settings/thumbnail-style-presets');
            const data = await res.json();

            tGrid.innerHTML = '';
            Object.entries(data).forEach(([key, val]) => {
                // Special labels for specific styles; others use their stored name
                const specialLabels = {
                    'japanese_viral': i18n.style_viral
                };

                const imgUrl = (typeof val === 'object' && val.image_url) ? val.image_url : `/static/img/thumbs/${key}.png`;
                const hasInstruction = (typeof val === 'object' && val.gemini_instruction && val.gemini_instruction.trim().length > 0);
                const displayName = specialLabels[key] || (typeof val === 'object' && val.name_ko ? val.name_ko : key);

                const style = {
                    id: key,
                    name: displayName,
                    img: imgUrl,
                    hasInstruction: hasInstruction
                };
                const div = createStyleCard(style, 'thumbnailStyle');
                tGrid.appendChild(div);
            });

            // Set default
            const currentThumbStyle = document.getElementById('thumbnailStyle').value;
            if (currentThumbStyle && data[currentThumbStyle]) {
                selectStyle('thumbnailStyle', currentThumbStyle);
            } else {
                const firstKey = Object.keys(data)[0];
                if (firstKey) selectStyle('thumbnailStyle', firstKey);
            }
        } catch (e) {
            console.error("Failed to load thumbnail styles:", e);
        }
    }
}

function createStyleCard(style, inputId) {
    const div = document.createElement('div');
    div.className = `cursor-pointer relative group rounded-xl overflow-hidden border-2 border-transparent hover:border-purple-500 transition-all bg-gray-800 aspect-video style-card-${inputId}`;
    div.dataset.value = style.id;
    div.onclick = () => selectStyle(inputId, style.id);

    // Filter name for display (remove paths if any)
    const displayName = style.name.split('/').pop().replace(/_/g, ' ');

    div.innerHTML = `
        <img src="${style.img}" class="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" alt="${style.name}" 
            onerror="this.style.display='none'; this.parentElement.innerHTML='<div class=\\'flex flex-col items-center justify-center h-full p-2 text-center\\'><div class=\\'text-2xl mb-1\\'>🎨</div><div class=\\'text-[10px] text-white font-bold leading-tight truncate w-full\\'>${displayName}</div></div>';">
        <div class="absolute bottom-0 inset-x-0 bg-black/60 p-1.5 text-center transition-transform translate-y-0">
            <span class="text-[10px] text-white font-medium block truncate">${displayName}</span>
        </div>
        ${style.hasInstruction ? `
        <div class="absolute top-1.5 left-1.5 bg-purple-600/90 text-white rounded-md px-1 py-0.5 text-[8px] font-bold flex items-center gap-0.5 shadow-lg">
            <span>🧠</span><span>GROUNDED</span>
        </div>
        ` : ''}
        <div class="absolute top-2 right-2 bg-purple-600 rounded-full p-1 opacity-0 check-icon transition-opacity shadow-lg">
            <svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"></path></svg>
        </div>
    `;
    return div;
}

function selectStyle(inputId, val) {
    const input = document.getElementById(inputId);
    if (!input) return;
    input.value = val;

    // Visual Update
    const container = inputId === 'imageStyle' ? document.getElementById('styleSelectorGrid') : document.getElementById('thumbnailStyleGrid');
    if (!container) return;

    // Remove active state from all siblings
    container.querySelectorAll('div[data-value]').forEach(el => {
        el.classList.remove('border-purple-500', 'ring-2', 'ring-purple-500/50');
        el.classList.add('border-transparent');
        el.querySelector('.check-icon')?.classList.add('opacity-0');
    });

    // Add active state to selected
    const selected = container.querySelector(`div[data-value="${val}"]`);
    if (selected) {
        selected.classList.remove('border-transparent');
        selected.classList.add('border-purple-500', 'ring-2', 'ring-purple-500/50');
        selected.querySelector('.check-icon')?.classList.remove('opacity-0');
    }
}

// [NEW] Mode Selection
function setMode(mode) {
    const input = document.getElementById('appMode');
    if (!input) return;
    input.value = mode;

    // Visual update
    const btnLong = document.getElementById('modeLongform');
    const btnShort = document.getElementById('modeShorts');

    if (mode === 'longform') {
        btnLong.classList.add('bg-purple-600', 'text-white', 'font-bold');
        btnLong.classList.remove('text-gray-500');
        btnShort.classList.remove('bg-purple-600', 'text-white', 'font-bold');
        btnShort.classList.add('text-gray-500');

        const durLabel = document.querySelector('#targetDuration + span');
        if (durLabel) durLabel.innerText = i18n.unit_min_short;
        const durInput = document.getElementById('targetDuration');
        if (durInput && durInput.value == 60) durInput.value = 10;

        const commerceToggle = document.getElementById('commerceModeToggle');
        if (commerceToggle) commerceToggle.classList.add('hidden');
        setCreationMode('default');
    } else {
        btnShort.classList.add('bg-purple-600', 'text-white', 'font-bold');
        btnShort.classList.remove('text-gray-500');
        btnLong.classList.remove('bg-purple-600', 'text-white', 'font-bold');
        btnLong.classList.add('text-gray-500');

        const durLabel = document.querySelector('#targetDuration + span');
        if (durLabel) durLabel.innerText = i18n.unit_sec_short;
        const durInput = document.getElementById('targetDuration');
        if (durInput) durInput.value = 60;

        const commerceToggle = document.getElementById('commerceModeToggle');
        if (commerceToggle) commerceToggle.classList.remove('hidden');

        // Ensure creation mode is synced
        setCreationMode(document.getElementById('creationMode')?.value || 'default');
    }
}

// [NEW] Creation Mode Selection (Standard vs TopView Commerce)
function setCreationMode(mode) {
    const input = document.getElementById('creationMode');
    if (!input) return;
    input.value = mode;

    const btnDefault = document.getElementById('modeDefault');
    const btnCommerce = document.getElementById('modeCommerce');

    const topicContainer = document.getElementById('topicInputContainer');
    const productContainer = document.getElementById('productUrlContainer');

    if (mode === 'default') {
        // Normal Mode
        btnDefault.classList.add('bg-cyan-600', 'text-white', 'font-bold');
        btnDefault.classList.remove('text-cyan-400');
        btnCommerce.classList.remove('bg-cyan-600', 'text-white', 'font-bold');
        btnCommerce.classList.add('text-cyan-400');

        if (topicContainer) topicContainer.classList.remove('hidden');
        if (productContainer) productContainer.classList.add('hidden');
    } else {
        // Commerce Mode (TopView)
        btnCommerce.classList.add('bg-cyan-600', 'text-white', 'font-bold');
        btnCommerce.classList.remove('text-cyan-400');
        btnDefault.classList.remove('bg-cyan-600', 'text-white', 'font-bold');
        btnDefault.classList.add('text-cyan-400');

        if (topicContainer) topicContainer.classList.add('hidden');
        if (productContainer) productContainer.classList.remove('hidden');
    }
}

// [NEW] Motion Method Selection
function setMotionMethod(val) {
    document.getElementById('motionMethod').value = val;
    document.querySelectorAll('.motion-method-btn').forEach(btn => {
        if (btn.getAttribute('data-value') === val) {
            btn.classList.add('bg-purple-600', 'text-white', 'font-bold', 'shadow-sm');
            btn.classList.remove('bg-gray-800', 'text-gray-400');
        } else {
            btn.classList.remove('bg-purple-600', 'text-white', 'font-bold', 'shadow-sm');
            btn.classList.add('bg-gray-800', 'text-gray-400');
        }
    });

    // 만약 slowmo/extend 면 안내 문구 등 추가 가능
}

function setVideoEngine(val) {
    document.getElementById('videoEngine').value = val;
    document.querySelectorAll('.video-engine-btn').forEach(btn => {
        if (btn.getAttribute('data-value') === val) {
            btn.classList.add('bg-purple-600', 'text-white', 'font-bold', 'shadow-sm');
            btn.classList.remove('bg-gray-800', 'text-gray-400');
        } else {
            btn.classList.remove('bg-purple-600', 'text-white', 'font-bold', 'shadow-sm');
            btn.classList.add('bg-gray-800', 'text-gray-400');
        }
    });
}

function toggleScheduleInput() {
    const privacy = document.getElementById('uploadPrivacy')?.value;
    const container = document.getElementById('scheduleInputContainer');
    if (!container) return;

    if (privacy === 'scheduled') {
        container.classList.remove('hidden');
        // Default: Tomorrow this time
        const input = document.getElementById('uploadScheduleAt');
        if (input && !input.value) {
            const tomorrow = new Date();
            tomorrow.setDate(tomorrow.getDate() + 1);
            tomorrow.setMinutes(tomorrow.getMinutes() - tomorrow.getTimezoneOffset());
            input.value = tomorrow.toISOString().slice(0, 16);
        }
    } else {
        container.classList.add('hidden');
    }
}



async function loadVoices() {
    const providerSelect = document.getElementById('providerSelect');
    const voiceSelect = document.getElementById('voiceSelect');
    const scriptSelect = document.getElementById('scriptStyleSelect');

    if (!providerSelect || !voiceSelect) return;

    // Load Script Styles if select exists
    if (scriptSelect) {
        try {
            const res = await fetch('/api/settings/script-style-presets');
            const data = await res.json();

            // Keep current value if possible
            const currentVal = scriptSelect.value;
            scriptSelect.innerHTML = '';

            Object.keys(data).forEach(key => {
                const opt = document.createElement('option');
                opt.value = key;
                opt.innerText = key;
                scriptSelect.appendChild(opt);
            });

            if (data[currentVal]) scriptSelect.value = currentVal;
            else if (Object.keys(data).length > 0) scriptSelect.value = Object.keys(data)[0];

        } catch (e) {
            console.error("Failed to load script styles:", e);
        }
    }

    // Provider Change Event
    providerSelect.onchange = async () => {
        const provider = providerSelect.value;
        voiceSelect.innerHTML = `<option>${i18n.status_loading}</option>`;
        await fetchVoices(provider);
    };

    // Initial fetch
    await fetchVoices(providerSelect.value);
}

async function fetchVoices(provider) {
    const voiceSelect = document.getElementById('voiceSelect');
    if (!voiceSelect) return;

    voiceSelect.innerHTML = `<option>${i18n.status_loading}</option>`;
    console.log("[Autopilot] Fetching voices for provider:", provider);

    try {
        // For non-API providers, use static lists
        if (provider === 'gemini') {
            voiceSelect.innerHTML = '';
            ['Puck', 'Charon', 'Kore', 'Fenrir', 'Aoede'].forEach(name => {
                const opt = document.createElement('option');
                opt.value = name;
                opt.innerText = `Gemini - ${name}`;
                voiceSelect.appendChild(opt);
            });
            return;
        }

        if (provider === 'google_cloud') {
            voiceSelect.innerHTML = '';
            [
                { id: 'ko-KR-Neural2-A', name: 'G-Neural2 A(여)' },
                { id: 'ko-KR-Neural2-C', name: 'G-Neural2 C(남)' },
                { id: 'ko-KR-Standard-A', name: 'G-Std A(여)' }
            ].forEach(v => {
                const opt = document.createElement('option');
                opt.value = v.id;
                opt.innerText = v.name;
                voiceSelect.appendChild(opt);
            });
            return;
        }

        if (provider === 'openai') {
            voiceSelect.innerHTML = '';
            ['alloy', 'echo', 'shimmer', 'nova', 'onyx', 'fable'].forEach(name => {
                const opt = document.createElement('option');
                opt.value = name;
                opt.innerText = `OpenAI - ${name}`;
                voiceSelect.appendChild(opt);
            });
            return;
        }

        // ElevenLabs - fetch from API
        const res = await fetch('/api/tts/voices');
        const data = await res.json();
        voiceSelect.innerHTML = '';

        console.log("[Autopilot] API returned voices:", data.voices?.length || 0);

        const voices = (data.voices || []).filter(v => v.provider === provider || (!v.provider && provider === 'elevenlabs'));

        if (voices.length === 0) {
            voiceSelect.innerHTML = `<option value="">${i18n.status_no_voices_available}</option>`;
            return;
        }

        voices.forEach(v => {
            const opt = document.createElement('option');
            opt.value = v.voice_id || v.id;
            opt.innerText = v.name;
            voiceSelect.appendChild(opt);
        });

        console.log("[Autopilot] Loaded", voices.length, "voices for", provider);

    } catch (e) {
        console.error("Voice load error:", e);
        voiceSelect.innerHTML = `<option value="">${i18n.status_error_loading_voices}</option>`;
    }
}

async function loadSavedSettings() {
    try {
        const res = await fetch('/api/settings');
        const data = await res.json();

        if (data) {
            log("⚙️ Loaded Saved Settings");

            if (data.app_mode) {
                setMode(data.app_mode);
                // 설정된 모드가 고정이면 반대쪽 버튼 숨김
                const btnLong = document.getElementById('modeLongform');
                const btnShort = document.getElementById('modeShorts');
                if (data.app_mode === 'longform' && btnShort) {
                    btnShort.style.display = 'none';
                } else if (data.app_mode === 'shorts' && btnLong) {
                    btnLong.style.display = 'none';
                }
            }


            // 1. TTS Settings
            if (data.voice_provider) {
                const pSelect = document.getElementById('providerSelect');
                if (pSelect) {
                    pSelect.value = data.voice_provider;
                    // Wait for voices to load before setting voice_id
                    await fetchVoices(data.voice_provider);
                }
            } else {
                // Default fetch
                await fetchVoices(document.getElementById('providerSelect').value);
            }

            // [FIX] Support both voice_id and voice_name
            const savedVoiceId = data.voice_id || data.voice_name;
            console.log("[Autopilot] Trying to select voice:", savedVoiceId);

            if (savedVoiceId) {
                const vSelect = document.getElementById('voiceSelect');
                if (vSelect) {
                    vSelect.value = savedVoiceId;

                    // If exact match failed (value is empty or first option), try to find by partial match
                    if (!vSelect.value || vSelect.selectedIndex === 0) {
                        console.log("[Autopilot] Exact match failed, trying partial match...");
                        const options = Array.from(vSelect.options);
                        const match = options.find(opt =>
                            opt.value === savedVoiceId ||
                            opt.textContent.toLowerCase().includes(savedVoiceId.toLowerCase())
                        );
                        if (match) {
                            vSelect.value = match.value;
                            console.log("[Autopilot] Partial match found:", match.value);
                        }
                    }

                    console.log("[Autopilot] Voice selected:", vSelect.value);
                }
            }

            // 2. Image Style
            if (data.image_style) {
                selectStyle('imageStyle', data.image_style);
            } else {
                selectStyle('imageStyle', 'realistic'); // Default
            }

            // 3. Thumbnail Style
            console.log("[Autopilot] Loaded thumbnail_style from settings:", data.thumbnail_style);
            if (data.thumbnail_style) {
                selectStyle('thumbnailStyle', data.thumbnail_style);
                console.log("[Autopilot] Applied thumbnail style:", data.thumbnail_style);
            } else if (data.image_style) {
                // Intelligent fallback: Sync with Image Style
                const mapped = mapImageToThumb(data.image_style);
                selectStyle('thumbnailStyle', mapped);
                console.log("[Autopilot] Fallback thumbnail style from image_style:", mapped);
            } else {
                selectStyle('thumbnailStyle', 'face'); // Default
                console.log("[Autopilot] Using default thumbnail style: face");
            }

            // 4. Script Style
            if (data.script_style) {
                const sSelect = document.getElementById('scriptStyleSelect');
                if (sSelect) sSelect.value = data.script_style;
            }
            
            // [NEW] Ethnicity
            if (data.char_ethnicity) {
                const ethSelect = document.getElementById('charEthnicity');
                if (ethSelect) ethSelect.value = data.char_ethnicity;
            }

            // [NEW] Duration
            if (data.duration_seconds) {
                const minutes = Math.round(data.duration_seconds / 60);
                const durInput = document.getElementById('targetDuration');
                if (durInput && minutes > 0) {
                    durInput.value = minutes;
                    console.log("[Autopilot] Loaded duration:", minutes, "min");
                }
            }

            // 5. Last Topic (Global)
            if (data.last_topic) {
                const topicInput = document.getElementById('topicInput');
                if (topicInput && !topicInput.value) {
                    topicInput.value = data.last_topic;
                }
            }

            // 6. Duration (Global)
            if (data.duration_seconds) {
                window.loadedDurationSeconds = data.duration_seconds;
                // Estimate scenes: 1 min ~ 1 scene (minimum 3)
                let estScenes = Math.floor(data.duration_seconds / 60);
                if (estScenes < 1) estScenes = 1;
                if (estScenes > 20) estScenes = 20;

                const range = document.getElementById('videoSceneCount');
                if (range) {
                    range.value = estScenes;
                    const sceneValEl = document.getElementById('sceneCountVal');
                    if (sceneValEl) sceneValEl.innerText = estScenes + ` ${i18n.unit_scenes}`;
                    const sceneInlineEl = document.getElementById('sceneCountInline');
                    if (sceneInlineEl) sceneInlineEl.textContent = estScenes;
                }
            }

            // [NEW] Upload Settings
            if (data.upload_privacy) {
                const privacySelect = document.getElementById('uploadPrivacy');
                if (privacySelect) {
                    privacySelect.value = data.upload_privacy;
                    toggleScheduleInput();
                }
            }
            if (data.upload_schedule_at) {
                const scheduleInput = document.getElementById('uploadScheduleAt');
                if (scheduleInput) {
                    scheduleInput.value = data.upload_schedule_at;
                }
            }
            if (data.youtube_channel_id) {
                const channelSelect = document.getElementById('youtubeChannelId');
                if (channelSelect) {
                    channelSelect.value = data.youtube_channel_id;
                }
            }
            if (data.use_character_analysis !== undefined) {
                const charAnalysisCheck = document.getElementById('useCharacterAnalysis');
                if (charAnalysisCheck) {
                    charAnalysisCheck.checked = data.use_character_analysis === '1' || data.use_character_analysis === true;
                }
            }

            // [SYNC] Video Engine from Global Settings
            if (data.video_engine) {
                setVideoEngine(data.video_engine);
            }
        }
    } catch (e) {
        console.error("Settings load fail:", e);
        // Fallback: Load voices anyway
        await fetchVoices(document.getElementById('providerSelect').value);
    }
}

function mapImageToThumb(imgStyle) {
    const map = {
        'realistic': 'face',
        'anime': 'ghibli',
        'cinematic': 'dramatic',
        'minimal': 'minimal',
        'k_webtoon': 'k_manhwa',
    };
    return map[imgStyle] || 'face';
}

function log(msg) {
    const area = document.getElementById('modalConsoleLogs');
    const oldArea = document.getElementById('consoleLogs');

    const target = area || oldArea;
    if (!target) return;

    let icon = "⚙️";
    if (msg.includes("✅")) icon = "✅";
    if (msg.includes("❌")) icon = "❌";
    if (msg.includes("🚀")) icon = "🚀";
    if (msg.includes("🎬")) icon = "🎬";
    if (msg.includes("🎙️")) icon = "🎙️";
    if (msg.includes("🏁")) icon = "🏁";
    if (msg.includes("Status:")) icon = "⚡";
    if (msg.includes("Anal")) icon = "📊";
    if (msg.includes("Script")) icon = "📝";
    if (msg.includes("Asset")) icon = "🎨";
    if (msg.includes("Thumb")) icon = "🖼️";
    if (msg.includes("Render")) icon = "🎞️";

    // Clean up msg - removing common status icons if present (using a safer approach)
    const cleanMsg = msg.replace(/[^\x00-\x7F가-힣]/g, "").trim();

    const div = document.createElement('div');
    const time = new Date().toLocaleTimeString('ko-KR', { hour12: true, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    div.className = `log-item text-gray-400 text-[10px] border-b border-gray-800/20 py-1.5 flex gap-2 items-start`;
    div.innerHTML = `
        <span class="opacity-30 shrink-0 font-mono">[${time}]</span> 
        <span class="shrink-0 scale-75 origin-top">${icon}</span>
        <span class="flex-1 leading-normal">${cleanMsg}</span>
    `;

    target.appendChild(div);
    target.scrollTop = target.scrollHeight;

    const statusText = document.getElementById('modalStatusText');
    if (statusText && msg.includes('Status:')) {
        const stage = msg.split('Status:')[1].trim();
        statusText.innerText = getFriendlyStatus(stage);
    }
}

function clearLogs() {
    const area = document.getElementById('modalConsoleLogs');
    if (area) area.innerHTML = '<div class="text-gray-700 italic border-b border-gray-800/20 pb-1">Logs cleared.</div>';
}

function openAutopilotModal(topic = "") {
    const modal = document.getElementById('autopilotModal');
    if (modal) {
        modal.classList.remove('hidden');
        document.getElementById('modalTopicTitle').innerText = topic ? `(${topic})` : "";
        document.getElementById('modalProgressPercent').innerText = "0%";
        document.getElementById('modalProgressBar').style.width = "0%";
        document.getElementById('modalStatusText').innerText = i18n.status_preparing;
        document.getElementById('modalDoneBtn').classList.add('hidden');
    }
}

function closeAutopilotModal() {
    const modal = document.getElementById('autopilotModal');
    if (modal) {
        if (isProcessing) {
            if (!confirm(i18n.confirm_close_modal_keep_task)) return;
        }
        modal.classList.add('hidden');
    }
}

function getFriendlyStatus(status) {
    const map = {
        'created': '워크플로우 초기화 중...',
        'analyzing': '유튜브 데이터 분석 중...',
        'analyzed': '데이터 분석 완료',
        'planning': '대본 기획 구성 중...',
        'planned': '기획안 확정 완료',
        'scripting': 'AI 대본 작성 중...',
        'scripted': '대본 초안 완성',
        'generating_assets': 'AI 비주얼 에셋 생성 중 (이미지/영상)...',
        'generating_thumbnail': '맞춤형 썸네일 제작 중...',
        'rendering': '최종 영상 합성 및 렌더링 중...',
        'done': '모든 제작이 완료되었습니다! ✨',
        'error': '처리 중 오류가 발생했습니다.'
    };
    return map[status] || status;
}

function getProgressValue(status) {
    const map = {
        'created': 5,
        'analyzing': 15,
        'analyzed': 25,
        'planning': 35,
        'planned': 45,
        'scripting': 55,
        'scripted': 65,
        'generating_assets': 75,
        'generating_thumbnail': 85,
        'rendering': 95,
        'done': 100,
        'error': 0
    };
    return map[status] ?? 10;
}

// --- Autopilot Logic ---

let isProcessing = false;

function getAutopilotConfig() {
    const topicInput = document.getElementById('topicInput');
    const topic = topicInput ? topicInput.value.trim() : '';

    const creationMode = document.getElementById('creationMode')?.value || 'default';
    const productUrl = document.getElementById('productUrlInput')?.value.trim() || '';

    if (creationMode === 'default' && !topic) {
        alert("Please enter a topic keyword.");
        topicInput.focus();
        return null;
    }

    if (creationMode === 'commerce' && !productUrl) {
        alert(i18n.alert_enter_product_url);
        document.getElementById('productUrlInput').focus();
        return null;
    }

    const config = {
        keyword: creationMode === 'commerce' ? `[Commerce] ${productUrl}` : topic,
        topic: topic,
        mode: document.getElementById('appMode')?.value || 'longform',
        image_style: document.getElementById('imageStyle').value,
        thumbnail_style: document.getElementById('thumbnailStyle').value,
        video_scene_count: parseInt(document.getElementById('videoSceneCount').value || 0),
        all_video: document.getElementById('allVideoCheck')?.checked || false,
        video_engine: document.getElementById('videoEngine')?.value || 'wan',
        motion_method: document.getElementById('motionMethod').value || 'standard',
        char_ethnicity: document.getElementById('charEthnicity')?.value || 'East Asian heritage, Polished porcelain skin',
        script_style: document.getElementById('scriptStyleSelect').value,
        voice_provider: document.getElementById('providerSelect').value,
        voice_id: document.getElementById('voiceSelect').value,
        duration_seconds: (function () {
            const val = parseInt(document.getElementById('targetDuration').value);
            const m = document.getElementById('appMode')?.value || 'longform';
            if (m === 'shorts') return val || 60;
            return (val || 10) * 60;
        })(),
        subtitle_settings: window.currentSubtitleSettings || null,
        preset_id: document.getElementById('presetSelect') ? (parseInt(document.getElementById('presetSelect').value) || null) : null,
        upload_privacy: document.getElementById('uploadPrivacy')?.value || 'private',
        upload_schedule_at: document.getElementById('uploadScheduleAt')?.value || null,
        youtube_channel_id: document.getElementById('youtubeChannelId')?.value ? parseInt(document.getElementById('youtubeChannelId').value) : null,
        creation_mode: creationMode,
        product_url: productUrl,
        use_character_analysis: document.getElementById('useCharacterAnalysis')?.checked || false
    };
    return config;
}

async function startAutopilot() {
    if (isProcessing) return;

    const config = getAutopilotConfig();
    if (!config) return;

    const topic = config.keyword;
    const startBtn = document.getElementById('btnStartProduction');

    // UI Loading State (Popup Trigger)
    isProcessing = true;
    openAutopilotModal(topic);

    log(`🎬 Mode: ${config.mode} | Style: ${config.image_style}`);
    log(`🎙️ Voice: ${config.voice_provider} / ${config.voice_id}`);

    try {
        const res = await fetch('/api/autopilot/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        const data = await res.json();

        if (data.status === 'ok') {
            log("✅ Workflow started. Project ID: " + data.project_id);
            // 오토파일럿이 생성한 새 프로젝트를 현재 프로젝트로 설정
            if (typeof setCurrentProject === 'function') {
                setCurrentProject(data.project_id);
            } else {
                localStorage.setItem('currentProjectId', data.project_id);
            }
            pollStatus(data.project_id);
        } else {
            throw new Error(data.error || "Failed to start");
        }
    } catch (e) {
        log("❌ FAIL: " + e.message);
        isProcessing = false;
        if (startBtn) {
            startBtn.disabled = false;
            startBtn.innerHTML = '<span>제작 시작하기</span> ⚡';
        }
    }
}

async function addToQueue() {
    if (isProcessing) return;

    const config = getAutopilotConfig();
    if (!config) return;

    config.is_queued = true; // Mark as queued

    const btn = document.getElementById('btnAddToQueue');
    const oldHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span>⏳</span> ${i18n.status_processing}`;

    try {
        const res = await fetch('/api/autopilot/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        const data = await res.json();

        if (data.status === 'ok') {
            Utils.showToast(data.message || i18n.status_added_to_queue, "success");
            refreshQueue(); // Update badge and list
        } else {

            throw new Error(data.error || "Failed to add to queue");
        }
    } catch (e) {
        console.error(e);
        alert(e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = oldHtml;
    }
}

async function updateQueueItemChannel(projectId, channelId, selectEl) {
    const prevValue = selectEl.dataset.prevValue ?? selectEl.value;
    selectEl.dataset.prevValue = channelId;
    try {
        const res = await fetch(`/api/queue/${projectId}/channel`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ youtube_channel_id: channelId ? parseInt(channelId) : null })
        });
        const data = await res.json();
        if (data.status === 'ok') {
            const chName = channelId
                ? (window.channelList.find(c => c.id == channelId)?.name || '채널')
                : '기본 채널';
            Utils.showToast(`채널 변경: ${chName}`, "success");
        } else {
            throw new Error(data.detail || data.error || '변경 실패');
        }
    } catch (e) {
        console.error(e);
        selectEl.value = prevValue;
        Utils.showToast(`채널 변경 실패: ${e.message}`, "error");
    }
}


function pollStatus(projectId) {
    const interval = setInterval(async () => {
        try {
            const res = await fetch(`/api/projects/${projectId}/full`);
            if (!res.ok) throw new Error("Status check failed");
            const data = await res.json();

            const status = data.project?.status || "processing";

            // Update UI Progress
            const progress = getProgressValue(status);
            const pBar = document.getElementById('modalProgressBar');
            const pPercent = document.getElementById('modalProgressPercent');
            const statusText = document.getElementById('modalStatusText');

            if (pBar) pBar.style.width = `${progress}%`;
            if (pPercent) pPercent.innerText = `${progress}%`;
            if (statusText) statusText.innerText = getFriendlyStatus(status);

            // Log Update (Throttle logs to same status)
            const logContainer = document.getElementById('modalConsoleLogs');
            const lastLog = logContainer ? logContainer.lastElementChild : null;

            if (lastLog && lastLog.textContent.includes("Status:")) {
                const time = new Date().toLocaleTimeString('ko-KR', { hour12: true, hour: '2-digit', minute: '2-digit', second: '2-digit' });
                lastLog.innerHTML = `<span class="opacity-30 shrink-0">[${time}]</span> <span class="flex-1">... Background Check Status: <span class="text-purple-400 font-bold">${status}</span></span>`;
            } else {
                log(`... Status: ${status}`);
            }

            if (status === 'done') {
                clearInterval(interval);
                isProcessing = false;
                log(`🏁 ${i18n.status_done_redirecting}`);

                const doneBtn = document.getElementById('modalDoneBtn');
                if (doneBtn) doneBtn.classList.remove('hidden');

                const startBtn = document.getElementById('startAutopilotBtn');
                if (startBtn) {
                    startBtn.innerText = "✅ Result Rendered";
                    startBtn.disabled = false;
                }

                // Auto redirect after 3s
                setTimeout(() => {
                    window.location.href = '/video-gen';
                }, 3000);

            } else if (status === 'error') {
                clearInterval(interval);
                isProcessing = false;
                log(`❌ ${i18n.status_error_occurred_check_logs}`);

                const startBtn = document.getElementById('startAutopilotBtn');
                if (startBtn) {
                    startBtn.disabled = false;
                    startBtn.innerHTML = '<span>제작 시작하기</span> ⚡';
                }
            }
        } catch (e) {
            console.error("Poll error:", e);
        }
    }, 5000);
}

/* =========================================
   [NEW] Batch Mode Logic
   ========================================= */

function switchTab(mode) {
    const single = document.getElementById('singleMode');
    const batch = document.getElementById('batchMode');
    const tabSingle = document.getElementById('tabSingle');
    const tabBatch = document.getElementById('tabBatch');

    if (mode === 'single') {
        single.classList.remove('hidden');
        batch.classList.add('hidden');
        tabSingle.classList.add('border-purple-500', 'text-purple-400');
        tabSingle.classList.remove('border-transparent', 'text-gray-400');
        tabBatch.classList.remove('border-purple-500', 'text-purple-400');
        tabBatch.classList.add('border-transparent', 'text-gray-400');
    } else {
        single.classList.add('hidden');
        batch.classList.remove('hidden');
        tabBatch.classList.add('border-purple-500', 'text-purple-400');
        tabBatch.classList.remove('border-transparent', 'text-gray-400');
        tabSingle.classList.remove('border-purple-500', 'text-purple-400');
        tabSingle.classList.add('border-transparent', 'text-gray-400');
        refreshQueue();
    }
}

async function refreshQueue() {
    const list = document.getElementById('queueList');
    const badge = document.getElementById('queueBadge');
    const countEl = document.getElementById('queueCount');

    list.innerHTML = `<div class="text-center py-12 text-gray-500"><div class="loader-sm mx-auto mb-2"></div>${i18n.status_loading}</div>`;

    try {
        const res = await fetch('/api/autopilot/queue');
        const data = await res.json();

        const projects = data.projects || [];
        const count = data.count || 0;

        if (badge) {
            badge.innerText = count;
            badge.classList.remove('hidden');
        }
        if (countEl) countEl.innerText = count;

        const btnStart = document.getElementById('btnStartBatch');

        if (count === 0) {
            list.innerHTML = `<div class="text-center py-12 text-gray-500">${i18n.status_no_queued_projects}<br><span class="text-xs">${i18n.helper_add_from_plan}</span></div>`;
            if (btnStart) btnStart.disabled = true;
            return;
        }

        if (btnStart) btnStart.disabled = false;

        // 채널 드롭다운 옵션 HTML 생성
        const channelOptions = [
            `<option value="">기본 채널</option>`,
            ...window.channelList.map(ch =>
                `<option value="${ch.id}">${ch.name}</option>`
            )
        ].join('');

        list.innerHTML = projects.map((p, idx) => {
            const chId = p.youtube_channel_id || '';
            const chName = p.channel_name || '기본 채널';
            return `
            <div class="flex items-center justify-between p-4 bg-gray-800/50 rounded-xl border border-gray-700/50 hover:bg-gray-800 transition-all">
                <div class="flex items-center gap-4">
                    <div class="flex flex-col items-center">
                        <span class="text-gray-600 font-mono text-xs mb-1">SEQ</span>
                        <span class="text-purple-400 font-bold bg-purple-500/10 px-2 py-0.5 rounded text-sm">${idx + 1}</span>
                    </div>
                    <div>
                        <h4 class="font-bold text-white text-base mb-1">${p.topic || i18n.label_no_title}</h4>
                        <p class="text-xs text-gray-400 flex items-center gap-2">
                            <span>ID: ${p.id}</span>
                            <span class="text-gray-600">|</span>
                            <span>${new Date(p.created_at).toLocaleString()}</span>
                            ${p.status === 'queued' ? `<span class="text-yellow-500 bg-yellow-500/10 px-1.5 py-0.5 rounded ml-2">${i18n.status_queued}</span>` : ''}
                        </p>
                    </div>
                </div>
                <div class="flex items-center gap-3">
                    <div class="flex flex-col items-end gap-1">
                        <span class="text-[9px] text-gray-500">업로드 채널</span>
                        <select
                            onchange="updateQueueItemChannel(${p.id}, this.value, this)"
                            class="bg-gray-700 border border-gray-600 text-white text-[11px] rounded-lg px-2 py-1 focus:ring-1 focus:ring-purple-500/50 outline-none min-w-[120px]"
                        >
                            ${channelOptions.replace(`value="${chId}"`, `value="${chId}" selected`)}
                        </select>
                    </div>
                    <button onclick="deleteFromQueue(${p.id})" class="text-xs text-red-500 bg-red-500/10 px-3 py-1.5 rounded hover:bg-red-500 hover:text-white transition-all ml-2">${i18n.btn_delete}</button>
                </div>
            </div>
        `}).join('');

    } catch (e) {
        console.error(e);
        list.innerHTML = `<div class="text-center py-12 text-red-500">${i18n.status_failed_to_load_list}</div>`;
    }
}

async function startBatch() {
    if (!confirm(i18n.confirm_start_batch)) return;

    const btn = document.getElementById('btnStartBatch');
    btn.disabled = true;
    btn.innerHTML = `<span>⏳</span> ${i18n.status_requesting_start}`;

    try {
        const res = await fetch('/api/queue/start', { method: 'POST' });
        const data = await res.json();

        if (data.status === 'success' || data.status === 'started') {
            Utils.showToast(`${i18n.status_batch_started} 🚀`, "success");
            btn.innerHTML = `<span class="loader-sm border-white"></span> ${i18n.status_processing}`;

            const logArea = document.getElementById('batchConsoleLogs');
            logArea.innerHTML = `<div class="text-yellow-400 p-2">✅ ${i18n.status_batch_started_check_queue}</div>`;

            // Start Polling Queue Count to show progress
            const interval = setInterval(async () => {
                await refreshQueue();
                const countText = document.getElementById('queueCount')?.innerText || "0";
                if (countText === "0") {
                    clearInterval(interval);
                    btn.disabled = false;
                    btn.innerHTML = `<span>▶️</span> ${i18n.btn_start_batch}`;
                    logArea.innerHTML += `<div class="text-green-400 p-2">🏁 ${i18n.status_all_tasks_done}</div>`;
                    Utils.showToast(`${i18n.status_all_tasks_done}!`, "success");
                }
            }, 5000);

        }
    } catch (e) {
        alert("실패: " + e.message);
        btn.disabled = false;
        btn.innerHTML = `<span>▶️</span> ${i18n.btn_start_batch}`;
    }
}

async function deleteFromQueue(pid) {
    if (!confirm(i18n.confirm_remove_from_queue)) return;
    try {
        const res = await fetch(`/api/projects/${pid}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: 'planning' })
        });
        refreshQueue();
        Utils.showToast(i18n.status_removed_from_queue, "info");
    } catch (e) { console.error(e); }
}

async function pollBatchLogs() {
    const logArea = document.getElementById('batchConsoleLogs');
    const batchMode = document.getElementById('batchMode');
    if (!logArea || !batchMode || batchMode.classList.contains('hidden')) return;

    try {
        const res = await fetch('/api/queue/logs');
        const data = await res.json();
        const logs = data.logs || [];
        
        if (logs.length > 0) {
            // Only update if changed
            const newContent = logs.map(line => `<div>${line.trim()}</div>`).join('');
            if (logArea.innerHTML !== newContent) {
                logArea.innerHTML = newContent;
                logArea.scrollTop = logArea.scrollHeight;
            }
        }
    } catch (e) {
        console.error("Log fetch failed:", e);
    }
}


async function loadSubtitleDefaults() {
    const panel = document.getElementById('subtitlePreviewPanel');
    if (!panel) return;

    try {
        const res = await fetch('/api/settings/subtitle/defaults');
        const data = await res.json();
        const s = data.settings || {};

        // [NEW] Cache for Preset Saving & Start Payload
        window.currentSubtitleSettings = s;
        renderSubtitlePreview(s);

        if (data.status === 'ok') {
            // Already rendered by renderSubtitlePreview(s)
        } else {
            panel.innerHTML = `<div class="col-span-2 text-red-400 text-xs">${i18n.status_load_failed}</div>`;
        }
    } catch (e) {
        console.error(e);
        panel.innerHTML = `<div class="col-span-2 text-red-400 text-xs">${i18n.status_connection_error}</div>`;
    }
}

// [NEW] Render Subtitle Preview (Helper)
function renderSubtitlePreview(s) {
    const panel = document.getElementById('subtitlePreviewPanel');
    if (!panel) return;

    // Logic extracted from above for reuse
    const fontName = s.subtitle_font || 'N/A';
    const size = s.subtitle_font_size ? `${s.subtitle_font_size}%` : 'N/A';
    const color = s.subtitle_color || 'N/A';
    const opacity = s.subtitle_bg_opacity !== undefined ? s.subtitle_bg_opacity : 'N/A';
    const stroke = s.subtitle_stroke_width > 0 ? `${s.subtitle_stroke_width}px` : 'None';
    const lineSpace = s.subtitle_line_spacing || '0.1';

    panel.innerHTML = `
        <div class="flex flex-col">
            <span class="text-xs text-gray-500">폰트 (Font)</span>
            <span class="font-bold text-white">${fontName}</span>
        </div>
        <div class="flex flex-col">
            <span class="text-xs text-gray-500">크기 (Size)</span>
            <span class="font-bold text-white">${size}</span>
        </div>
        <div class="flex flex-col">
            <span class="text-xs text-gray-500">색상 (Color)</span>
            <div class="flex items-center gap-2">
                <div class="w-3 h-3 rounded-full border border-gray-600" style="background-color: ${color}"></div>
                <span class="font-bold text-white">${color}</span>
            </div>
        </div>
        <div class="flex flex-col">
            <span class="text-xs text-gray-500">테두리 (Stroke)</span>
            <span class="font-bold text-white">${stroke}</span>
        </div>
        <div class="flex flex-col">
            <span class="text-xs text-gray-500">배경 투명도 (Opacity)</span>
            <span class="font-bold text-white">${opacity}</span>
        </div>
        <div class="flex flex-col">
            <span class="text-xs text-gray-500">줄 간격 (Spacing)</span>
            <span class="font-bold text-white">${lineSpace}</span>
        </div>
    `;
}

// [NEW] Preset Functions
async function fetchPresets() {
    const select = document.getElementById('presetSelect');
    if (!select) return;

    try {
        const res = await fetch('/api/autopilot/presets');
        const data = await res.json();

        select.innerHTML = `-- ${i18n.preset_custom} --`;
        if (data.presets) {
            data.presets.forEach(p => {
                const opt = document.createElement('option');
                opt.value = p.id;
                opt.innerText = p.name;
                select.appendChild(opt);
            });
        }

    } catch (e) { console.error("Fetch presets error:", e); }
}

async function loadPreset(presetId) {
    if (!presetId) {
        document.getElementById('btnDeletePreset').classList.add('hidden');
        document.getElementById('newPresetName').value = ""; // Clear name
        return;
    }

    document.getElementById('btnDeletePreset').classList.remove('hidden');

    const select = document.getElementById('presetSelect');
    const selectedOption = select.options[select.selectedIndex];
    const presetName = selectedOption ? selectedOption.innerText : "";
    document.getElementById('newPresetName').value = presetName;

    try {
        const res = await fetch('/api/autopilot/presets');
        const data = await res.json();
        const preset = data.presets.find(p => p.id == presetId);

        if (preset && preset.settings) {
            applyPresetSettings(preset.settings);
            Utils.showToast(`${i18n.status_preset_loaded_prefix} '${preset.name}' ${i18n.status_preset_loaded_suffix}`, 'success');
        }
    } catch (e) {
        console.error(e);
        Utils.showToast(i18n.status_failed_to_load_preset, 'error');
    }
}

function applyPresetSettings(s) {
    // [NEW] Mode
    if (s.mode) {
        setMode(s.mode);
    }

    // [NEW] Creation Mode (Normal/Commerce)
    if (s.creation_mode) {
        setCreationMode(s.creation_mode);
        if (s.product_url) {
            document.getElementById('productUrlInput').value = s.product_url;
        } else {
            document.getElementById('productUrlInput').value = "";
        }
    } else {
        setCreationMode('default');
    }

    // 1. Image Style
    if (s.image_style) selectStyle('imageStyle', s.image_style);
    if (s.visual_style) selectStyle('imageStyle', s.visual_style); // Fallback for old presets

    if (s.thumbnail_style) selectStyle('thumbnailStyle', s.thumbnail_style);

    // 2. Video
    if (s.video_scene_count !== undefined) {
        document.getElementById('videoSceneCount').value = s.video_scene_count;
        document.getElementById('sceneCountVal').innerText = s.video_scene_count + ` ${i18n.unit_scenes}`;
    }

    // [NEW] All Video Toggle
    if (s.all_video !== undefined) {
        const check = document.getElementById('allVideoCheck');
        if (check) {
            check.checked = s.all_video;
            check.dispatchEvent(new Event('change')); // Trigger visual update
        }
    }

    // [NEW] Motion Method
    if (s.motion_method) {
        setMotionMethod(s.motion_method);
    }
    if (s.duration_seconds) {
        const durInput = document.getElementById('targetDuration');
        if (durInput) {
            if (s.mode === 'shorts') {
                durInput.value = s.duration_seconds;
            } else {
                durInput.value = Math.round(s.duration_seconds / 60);
            }
        }
    }

    // 3. Script
    if (s.script_style) {
        document.getElementById('scriptStyleSelect').value = s.script_style;
    }

    // 4. Voice
    if (s.voice_provider) {
        document.getElementById('providerSelect').value = s.voice_provider;
        // Trigger change? No, manually update voice
        // We need to wait for voice fetch? 
        // This is tricky. Simplified for now.
    }

    // 5. Subtitles (Most Important)
    if (s.subtitle_settings) {
        window.currentSubtitleSettings = s.subtitle_settings;
        renderSubtitlePreview(s.subtitle_settings);
    }

    // [NEW] Upload Options
    if (s.upload_privacy) {
        const privacySelect = document.getElementById('uploadPrivacy');
        if (privacySelect) {
            privacySelect.value = s.upload_privacy;
            toggleScheduleInput();
        }
    }
    if (s.upload_schedule_at) {
        const scheduleAt = document.getElementById('uploadScheduleAt');
        if (scheduleAt) scheduleAt.value = s.upload_schedule_at;
    }
    if (s.youtube_channel_id) {
        const channelSelect = document.getElementById('youtubeChannelId');
        if (channelSelect) channelSelect.value = s.youtube_channel_id;
    }
}

async function saveCurrentPreset() {
    const nameInput = document.getElementById('newPresetName');
    const name = nameInput.value.trim();
    if (!name) return alert(i18n.alert_enter_preset_name);

    const currentSettings = {
        name: name,
        settings: {
            mode: document.getElementById('appMode')?.value || 'longform',
            image_style: document.getElementById('imageStyle').value,
            thumbnail_style: document.getElementById('thumbnailStyle').value,
            video_scene_count: parseInt(document.getElementById('videoSceneCount').value || 0),
            all_video: document.getElementById('allVideoCheck')?.checked || false,
            motion_method: document.getElementById('motionMethod')?.value || 'standard',
            script_style: document.getElementById('scriptStyleSelect').value,
            voice_provider: document.getElementById('providerSelect').value,
            voice_id: document.getElementById('voiceSelect').value,
            target_duration: parseInt(document.getElementById('targetDuration').value || 10),
            subtitle_settings: window.currentSubtitleSettings || null,
            upload_privacy: document.getElementById('uploadPrivacy')?.value || 'private',
            upload_schedule_at: document.getElementById('uploadScheduleAt')?.value || null,
            youtube_channel_id: document.getElementById('youtubeChannelId')?.value ? parseInt(document.getElementById('youtubeChannelId').value) : null
        }
    };

    try {
        const res = await fetch('/api/autopilot/presets', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentSettings)
        });
        const data = await res.json();
        if (data.status === 'ok') {
            Utils.showToast(i18n.status_preset_saved, "success");
            fetchPresets(); // refresh list
        } else {
            alert("Error: " + data.error);
        }
    } catch (e) {
        console.error(e);
    }
}

async function deleteCurrentPreset() {
    const select = document.getElementById('presetSelect');
    const pid = select.value;
    if (!pid) return;

    const name = select.options[select.selectedIndex].innerText;
    if (!confirm(`'${name}' ${i18n.confirm_delete_preset}`)) return;

    try {
        const res = await fetch(`/api/autopilot/presets/${pid}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.status === 'ok') {
            Utils.showToast(i18n.status_preset_deleted, "success");
            fetchPresets();
            document.getElementById('btnDeletePreset').classList.add('hidden');
            document.getElementById('newPresetName').value = "";
        } else {
            alert("삭제 실패: " + data.error);
        }
    } catch (e) { console.error(e); }
}


