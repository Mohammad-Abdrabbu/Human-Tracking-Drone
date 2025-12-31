
const DEFAULTS = {
    local: {
        api: 'http://127.0.0.1:8000',
        ws: 'ws://127.0.0.1:8000',
        video: 'http://localhost:8001/video'
    },
    cloud: {
        api: 'https://sahtd-backend.onrender.com',
        ws: 'wss://sahtd-backend.onrender.com',
        video: '' // Video on cloud requires ngrok dynamic URL, leaving empty for now
    }
};

export const getStoredConfig = () => {
    // 1. Check for manual Mode override
    const mode = localStorage.getItem('sahtd_mode');

    if (mode === 'cloud') {
        return {
            apiBaseUrl: DEFAULTS.cloud.api,
            wsBaseUrl: DEFAULTS.cloud.ws,
            videoUrl: DEFAULTS.cloud.video,
            mode: 'cloud'
        };
    }

    // 2. Default to Local
    return {
        apiBaseUrl: DEFAULTS.local.api,
        wsBaseUrl: DEFAULTS.local.ws,
        videoUrl: DEFAULTS.local.video,
        mode: 'local'
    };
};

export const toggleEnvironment = () => {
    const current = localStorage.getItem('sahtd_mode');
    const newMode = current === 'cloud' ? 'local' : 'cloud';
    localStorage.setItem('sahtd_mode', newMode);
    window.location.reload();
};

const currentConfig = getStoredConfig();

export const API_BASE_URL = currentConfig.apiBaseUrl;
export const WS_BASE_URL = currentConfig.wsBaseUrl;
export const VIDEO_URL = currentConfig.videoUrl;
export const APP_MODE = currentConfig.mode;
