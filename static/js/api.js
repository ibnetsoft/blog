/**
 * 피카디리스튜디오 API 클라이언트
 */

const API = {
    // YouTube API
    youtube: {
        async search(query, options = {}) {
            const response = await fetch('/api/youtube/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query,
                    max_results: options.maxResults || 10,
                    order: options.order || 'relevance',
                    published_after: options.publishedAfter || null,
                    video_duration: options.videoDuration || null
                })
            });
            return response.json();
        },

        async getVideo(videoId) {
            const response = await fetch(`/api/youtube/videos/${videoId}`);
            return response.json();
        },

        async getComments(videoId, maxResults = 100) {
            const response = await fetch(`/api/youtube/comments/${videoId}?max_results=${maxResults}`);
            return response.json();
        },

        async getChannel(channelId) {
            const response = await fetch(`/api/youtube/channel/${channelId}`);
            return response.json();
        }
    },

    // Gemini API
    gemini: {
        async generate(prompt, options = {}) {
            const response = await fetch('/api/gemini/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prompt,
                    temperature: options.temperature || 0.7,
                    max_tokens: options.maxTokens || 8192
                })
            });
            return response.json();
        },

        async analyzeComments(video) {
            const response = await fetch('/api/gemini/analyze-comments', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    video_id: video.id,
                    title: video.snippet.title,
                    channel_title: video.snippet.channelTitle,
                    description: video.snippet.description || "",
                    tags: video.snippet.tags || [],
                    view_count: parseInt(video.statistics.viewCount) || 0,
                    like_count: parseInt(video.statistics.likeCount) || 0,
                    comment_count: parseInt(video.statistics.commentCount) || 0,
                    published_at: video.snippet.publishedAt,
                    thumbnail_url: video.snippet.thumbnails.high?.url || video.snippet.thumbnails.default.url,
                    transcript: video.transcript || null
                })
            });
            return response.json();
        }
    },

    // TTS API
    tts: {
        async generate(text, options = {}) {
            const response = await fetch('/api/tts/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text,
                    voice_id: options.voiceId || null,
                    provider: options.provider || 'elevenlabs',
                    language: options.language || 'ko', // 언어 전달
                    speed: options.speed || 1.0, // 속도 전달
                    project_id: options.projectId || null
                })
            });
            return response.json();
        },

        async getVoices() {
            const response = await fetch('/api/tts/voices');
            return response.json();
        }
    },

    // 이미지 API
    // 이미지 API
    image: {
        async generatePrompts(script, style = 'realistic', count = 5, characterReference = null, projectId = null) {
            const response = await fetch('/api/image/generate-prompts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    script,
                    style,
                    count,
                    character_reference: characterReference,
                    project_id: projectId ? parseInt(projectId) : null
                })
            });
            return response.json();
        },

        async generate(prompt, projectId, sceneNumber, style = 'realistic', aspectRatio = '16:9') {
            const response = await fetch('/api/image/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prompt,
                    project_id: projectId,
                    scene_number: sceneNumber,
                    style,
                    aspect_ratio: aspectRatio
                })
            });
            return response.json();
        },

        // 썸네일 생성 (이미지 + 텍스트 합성)
        async generateThumbnail(prompt, text, options = {}) {
            const body = {
                prompt,
                text,
                text_position: options.textPosition || options.position || 'center',
                text_color: options.textColor || options.color || '#FFFFFF',
                font_size: options.fontSize || 72,
                language: options.language || 'ko',
                background_path: options.background_path || null, // 배경 이미지 경로
                aspect_ratio: options.aspectRatio || '16:9' // [NEW] Aspect Ratio
            };

            if (options.text_layers) {
                // 데이터 타입 안전 변환 (서버 유효성 검사 통과용)
                body.text_layers = options.text_layers.map(layer => ({
                    ...layer,
                    font_size: parseInt(layer.font_size, 10),
                    x_offset: parseInt(layer.x_offset || 0, 10),
                    y_offset: parseInt(layer.y_offset || 0, 10),
                    stroke_width: parseInt(layer.stroke_width || 0, 10)
                }));
            }
            if (options.shape_layers) {
                body.shape_layers = options.shape_layers.map(shape => ({
                    ...shape,
                    x: parseInt(shape.x, 10),
                    y: parseInt(shape.y, 10),
                    width: parseInt(shape.width, 10),
                    height: parseInt(shape.height, 10),
                    opacity: parseFloat(shape.opacity),
                    opacity_end: shape.opacity_end !== null && shape.opacity_end !== undefined ? parseFloat(shape.opacity_end) : null
                }));
            }

            const response = await fetch('/api/image/generate-thumbnail', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            return response.json();
        },

        // 썸네일 배경만 생성
        async generateThumbnailBackground(prompt, aspectRatio = '16:9', style = null, projectId = null) {
            const response = await fetch('/api/image/generate-thumbnail-background', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prompt,
                    aspect_ratio: aspectRatio,
                    thumbnail_style: style,
                    project_id: projectId ? parseInt(projectId) : null
                })
            });
            return response.json();
        },

        // 캐릭터 이미지 분석 (Consistency)
        async analyzeCharacter(formData) {
            const response = await fetch('/api/image/analyze-character', {
                method: 'POST',
                body: formData // Form Data (multipart)
            });
            return response.json();
        }
    },

    // 영상 API
    video: {
        async createSlideshow(images, audioUrl = null, durationPerImage = 5.0) {
            const response = await fetch('/api/video/create-slideshow', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    images,
                    audio_url: audioUrl,
                    duration_per_image: durationPerImage
                })
            });
            return response.json();
        },

        async search(script, style, query = null) {
            const response = await fetch('/api/video/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ script, style, query })
            });
            return response.json();
        },

        async generateVeo(prompt, model = "veo-3.1-generate-preview") {
            const response = await fetch('/api/video/generate-veo', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt, model })
            });
            return response.json();
        }
    },

    // 프로젝트 API
    project: {
        // 프로젝트 목록
        async list() {
            const response = await fetch('/api/projects');
            return response.json();
        },

        // 프로젝트 생성
        async create(name, topic = null, target_language = 'ko') {
            const response = await fetch('/api/projects', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, topic, target_language })
            });
            return response.json();
        },

        // 프로젝트 조회
        async get(projectId) {
            const response = await fetch(`/api/projects/${projectId}`);
            return response.json();
        },

        // 프로젝트 전체 데이터 조회
        async getFull(projectId) {
            const response = await fetch(`/api/projects/${projectId}/full?t=${new Date().getTime()}`);
            return response.json();
        },

        // 프로젝트 영상 렌더링
        async render(projectId, options = {}) {
            const response = await fetch(`/api/projects/${projectId}/render`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project_id: parseInt(projectId),
                    use_subtitles: options.useSubtitles ?? true,
                    resolution: options.resolution || "720p"
                })
            });
            return response.json();
        },

        // 프로젝트 업데이트
        async update(projectId, data) {
            const response = await fetch(`/api/projects/${projectId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            return response.json();
        },
        async updateSetting(id, key, value) {
            const response = await fetch(`/api/projects/${id}/setting`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key, value })
            });
            return response.json();
        },
        // 프로젝트 삭제
        async delete(projectId) {
            const response = await fetch(`/api/projects/${projectId}`, {
                method: 'DELETE'
            });
            return response.json();
        },

        // 분석 결과 저장/조회
        async saveAnalysis(projectId, videoData, analysisResult) {
            const response = await fetch(`/api/projects/${projectId}/analysis`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ video_data: videoData, analysis_result: analysisResult })
            });
            return response.json();
        },

        async getAnalysis(projectId) {
            const response = await fetch(`/api/projects/${projectId}/analysis`);
            return response.json();
        },

        // 대본 구조 저장/조회
        async saveScriptStructure(projectId, structure) {
            const response = await fetch(`/api/projects/${projectId}/script-structure`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(structure)
            });
            return response.json();
        },

        async getScriptStructure(projectId) {
            const response = await fetch(`/api/projects/${projectId}/script-structure`);
            return response.json();
        },

        // 대본 저장/조회
        async saveScript(projectId, fullScript, wordCount, estimatedDuration) {
            const response = await fetch(`/api/projects/${projectId}/script`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    full_script: fullScript,
                    word_count: wordCount,
                    estimated_duration: estimatedDuration
                })
            });
            return response.json();
        },

        async getScript(projectId) {
            const response = await fetch(`/api/projects/${projectId}/script`);
            return response.json();
        },

        // 이미지 프롬프트 저장/조회
        async saveImagePrompts(projectId, prompts) {
            const response = await fetch(`/api/projects/${projectId}/image-prompts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompts })
            });
            return response.json();
        },

        async getImagePrompts(projectId) {
            const response = await fetch(`/api/projects/${projectId}/image-prompts`);
            return response.json();
        },

        // 메타데이터 저장/조회
        async saveMetadata(projectId, titles, description, tags, hashtags) {
            const response = await fetch(`/api/projects/${projectId}/metadata`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ titles, description, tags, hashtags })
            });
            return response.json();
        },

        async getMetadata(projectId) {
            const response = await fetch(`/api/projects/${projectId}/metadata`);
            return response.json();
        },

        // 썸네일 저장/조회
        async saveThumbnails(projectId, ideas, texts) {
            const response = await fetch(`/api/projects/${projectId}/thumbnails`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ideas, texts })
            });
            return response.json();
        },

        async getThumbnails(projectId) {
            const response = await fetch(`/api/projects/${projectId}/thumbnails`);
            return response.json();
        },

        // 쇼츠 저장/조회
        async saveShorts(projectId, shortsData) {
            const response = await fetch(`/api/projects/${projectId}/shorts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ shorts_data: shortsData })
            });
            return response.json();
        },

        async getShorts(projectId) {
            const response = await fetch(`/api/projects/${projectId}/shorts`);
            return response.json();
        },

        // ===== 프로젝트 핵심 설정 (10가지 요소) =====
        async saveSettings(projectId, settings) {
            const response = await fetch(`/api/projects/${projectId}/settings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
            return response.json();
        },

        async getSettings(projectId) {
            const response = await fetch(`/api/projects/${projectId}/settings`);
            return response.json();
        },

        async updateSetting(projectId, key, value) {
            const response = await fetch(`/api/projects/${projectId}/settings/${key}?value=${encodeURIComponent(value)}`, {
                method: 'PATCH'
            });
            return response.json();
        },

        // All settings bulk update
        async updateSettings(projectId, settings) {
            return this.saveSettings(projectId, settings);
        }
    },



    // 상태 확인
    async health() {
        const response = await fetch('/api/health');
        return response.json();
    },

    // API 키 관리
    apiKeys: {
        async get() {
            const response = await fetch('/api/settings/api-keys');
            return response.json();
        },

        async save(keys) {
            const response = await fetch('/api/settings/api-keys', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(keys)
            });
            return response.json();
        }
    }
};

// 현재 프로젝트 ID 관리
window.currentProjectId = localStorage.getItem('currentProjectId') || null;

window.setCurrentProject = function (projectId) {
    window.currentProjectId = projectId;
    localStorage.setItem('currentProjectId', projectId);
    // 프로젝트 변경 이벤트 발생
    window.dispatchEvent(new CustomEvent('projectChanged', { detail: { projectId } }));
};

window.getCurrentProject = function () {
    return window.currentProjectId;
};

// 전역 사용
window.API = API;
