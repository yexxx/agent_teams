/**
 * components/settings/modelProfiles.js
 * Model profile tab logic.
 */
import {
    deleteModelProfile,
    fetchModelProfiles,
    probeModelConnection,
    reloadModelConfig,
    saveModelProfile,
} from '../../core/api.js';
import { errorToPayload, logError } from '../../utils/logger.js';

let profiles = {};
let editingProfile = null;
let profileProbeStates = {};
let draftProbeState = null;

export function bindModelProfileHandlers() {
    const addProfileBtn = document.getElementById('add-profile-btn');
    if (addProfileBtn) {
        addProfileBtn.onclick = handleAddProfile;
    }

    const saveProfileBtn = document.getElementById('save-profile-btn');
    if (saveProfileBtn) {
        saveProfileBtn.onclick = handleSaveProfile;
    }

    const testProfileBtn = document.getElementById('test-profile-btn');
    if (testProfileBtn) {
        testProfileBtn.onclick = handleTestDraftProfile;
    }

    const cancelProfileBtn = document.getElementById('cancel-profile-btn');
    if (cancelProfileBtn) {
        cancelProfileBtn.onclick = handleCancelProfile;
    }
}

export async function loadModelProfilesPanel() {
    try {
        profiles = await fetchModelProfiles();
        renderProfiles();
        renderDraftProbeState();
    } catch (e) {
        logError(
            'frontend.model_profiles.load_failed',
            'Failed to load model profiles',
            errorToPayload(e),
        );
    }
}

function renderProfiles() {
    const listEl = document.getElementById('profiles-list');
    showProfilesList();

    if (Object.keys(profiles).length === 0) {
        listEl.innerHTML = '<p class="empty-message">No profiles configured. Click "Add Profile" to create one.</p>';
        return;
    }

    let html = '<div class="profile-cards">';
    for (const [name, profile] of Object.entries(profiles)) {
        const probeState = profileProbeStates[name] || null;
        const testButtonLabel = probeState?.status === 'probing' ? 'Testing...' : 'Test';
        html += `
            <div class="profile-card">
                <div class="profile-card-header">
                    <h4>${escapeHtml(name)}</h4>
                    <div class="profile-card-actions">
                        <button class="icon-btn profile-card-test-btn" data-name="${escapeHtml(name)}" title="Test Connection" ${probeState?.status === 'probing' ? 'disabled' : ''}>${testButtonLabel}</button>
                        <button class="icon-btn edit-profile-btn" data-name="${escapeHtml(name)}" title="Edit">Edit</button>
                        <button class="icon-btn delete-profile-btn" data-name="${escapeHtml(name)}" title="Delete">Delete</button>
                    </div>
                </div>
                <div class="profile-card-body">
                    <p><strong>Model:</strong> ${escapeHtml(profile.model || '-')}</p>
                    <p><strong>Base URL:</strong> ${escapeHtml(profile.base_url || '-')}</p>
                    <p><strong>API Key:</strong> ${profile.has_api_key ? '********' : 'Not set'}</p>
                    <p><strong>Temperature:</strong> ${escapeHtml(String(profile.temperature ?? '-'))}</p>
                </div>
                ${renderProbeStatusMarkup(probeState)}
            </div>
        `;
    }
    html += '</div>';
    listEl.innerHTML = html;

    listEl.querySelectorAll('.profile-card-test-btn').forEach(btn => {
        btn.onclick = () => handleTestProfile(btn.dataset.name);
    });
    listEl.querySelectorAll('.edit-profile-btn').forEach(btn => {
        btn.onclick = () => handleEditProfile(btn.dataset.name);
    });
    listEl.querySelectorAll('.delete-profile-btn').forEach(btn => {
        btn.onclick = () => handleDeleteProfile(btn.dataset.name);
    });
}

function handleAddProfile() {
    editingProfile = null;
    draftProbeState = null;
    const apiKeyInput = document.getElementById('profile-api-key');
    document.getElementById('profile-editor-title').textContent = 'Add Profile';
    document.getElementById('profile-name').value = '';
    document.getElementById('profile-name').disabled = false;
    document.getElementById('profile-model').value = '';
    document.getElementById('profile-base-url').value = '';
    apiKeyInput.value = '';
    apiKeyInput.placeholder = '';
    document.getElementById('profile-temperature').value = '0.7';
    document.getElementById('profile-top-p').value = '1.0';
    document.getElementById('profile-max-tokens').value = '4096';

    showProfileEditor();
    renderDraftProbeState();
    document.getElementById('profile-name').focus();
}

function handleEditProfile(name) {
    const profile = profiles[name];
    if (!profile) return;

    editingProfile = name;
    draftProbeState = null;
    const apiKeyInput = document.getElementById('profile-api-key');
    document.getElementById('profile-editor-title').textContent = `Edit Profile: ${name}`;
    document.getElementById('profile-name').value = name;
    document.getElementById('profile-name').disabled = true;
    document.getElementById('profile-model').value = profile.model || '';
    document.getElementById('profile-base-url').value = profile.base_url || '';
    apiKeyInput.value = '';
    apiKeyInput.placeholder = profile.has_api_key ? 'Leave blank to keep current API key' : '';
    document.getElementById('profile-temperature').value = profile.temperature || 0.7;
    document.getElementById('profile-top-p').value = profile.top_p || 1.0;
    document.getElementById('profile-max-tokens').value = profile.max_tokens || 4096;

    showProfileEditor();
    renderDraftProbeState();
}

function handleCancelProfile() {
    showProfilesList();
    editingProfile = null;
    draftProbeState = null;
    renderDraftProbeState();
}

async function handleSaveProfile() {
    const name = document.getElementById('profile-name').value.trim();
    const model = document.getElementById('profile-model').value.trim();
    const baseUrl = document.getElementById('profile-base-url').value.trim();
    const apiKey = document.getElementById('profile-api-key').value.trim();
    const temperature = parseFloat(document.getElementById('profile-temperature').value) || 0.7;
    const topP = parseFloat(document.getElementById('profile-top-p').value) || 1.0;
    const maxTokens = parseInt(document.getElementById('profile-max-tokens').value) || 4096;

    if (!name) {
        alert('Profile name is required');
        return;
    }

    if (!editingProfile && !apiKey) {
        alert('API key is required for a new profile');
        return;
    }

    const profile = {
        model: model,
        base_url: baseUrl,
        temperature: temperature,
        top_p: topP,
        max_tokens: maxTokens,
    };

    if (apiKey) {
        profile.api_key = apiKey;
    }

    try {
        await saveModelProfile(name, profile);
        await reloadModelConfig();
        draftProbeState = null;
        renderDraftProbeState();
        alert('Profile saved and reloaded!');
        await loadModelProfilesPanel();
    } catch (e) {
        alert(`Failed to save: ${e.message}`);
    }
}

async function handleTestProfile(name) {
    if (!name) {
        return;
    }

    profileProbeStates[name] = {
        status: 'probing',
        message: 'Testing connection...',
    };
    renderProfiles();

    try {
        const result = await probeModelConnection({ profile_name: name });
        profileProbeStates[name] = buildProbeState(result);
    } catch (e) {
        profileProbeStates[name] = {
            status: 'failed',
            message: `Probe failed: ${e.message}`,
        };
    }

    renderProfiles();
}

async function handleTestDraftProfile() {
    const payload = buildDraftProbePayload();
    if (!payload) {
        return;
    }

    draftProbeState = {
        status: 'probing',
        message: 'Testing connection...',
    };
    renderDraftProbeState();

    try {
        const result = await probeModelConnection(payload);
        draftProbeState = buildProbeState(result);
    } catch (e) {
        draftProbeState = {
            status: 'failed',
            message: `Probe failed: ${e.message}`,
        };
    }

    renderDraftProbeState();
}

async function handleDeleteProfile(name) {
    if (!confirm(`Are you sure you want to delete profile "${name}"?`)) {
        return;
    }

    try {
        await deleteModelProfile(name);
        await reloadModelConfig();
        delete profileProbeStates[name];
        alert('Profile deleted and reloaded!');
        await loadModelProfilesPanel();
    } catch (e) {
        alert(`Failed to delete: ${e.message}`);
    }
}

function buildDraftProbePayload() {
    const model = document.getElementById('profile-model').value.trim();
    const baseUrl = document.getElementById('profile-base-url').value.trim();
    const apiKey = document.getElementById('profile-api-key').value.trim();
    const temperature = parseFloat(document.getElementById('profile-temperature').value) || 0.7;
    const topP = parseFloat(document.getElementById('profile-top-p').value) || 1.0;
    const maxTokens = parseInt(document.getElementById('profile-max-tokens').value) || 4096;

    if (!model || !baseUrl || (!apiKey && !editingProfile)) {
        draftProbeState = {
            status: 'failed',
            message: 'Model, base URL, and API key are required before testing a new profile.',
        };
        renderDraftProbeState();
        return null;
    }

    const override = {
        model: model,
        base_url: baseUrl,
        temperature: temperature,
        top_p: topP,
        max_tokens: maxTokens,
    };

    if (apiKey) {
        override.api_key = apiKey;
    }

    const payload = { override };
    if (editingProfile) {
        payload.profile_name = editingProfile;
    }
    return payload;
}

function buildProbeState(result) {
    if (result.ok) {
        const usageText = result.token_usage ? ` · ${result.token_usage.total_tokens} tokens` : '';
        return {
            status: 'success',
            message: `Connected in ${result.latency_ms}ms${usageText}`,
        };
    }

    const reason = result.error_message || result.error_code || 'Unknown error';
    return {
        status: 'failed',
        message: `Connection failed: ${reason}`,
    };
}

function renderDraftProbeState() {
    const statusEl = document.getElementById('profile-probe-status');
    const testBtn = document.getElementById('test-profile-btn');
    if (!statusEl || !testBtn) {
        return;
    }

    if (!draftProbeState) {
        statusEl.style.display = 'none';
        statusEl.textContent = '';
        statusEl.className = 'profile-probe-status';
        testBtn.disabled = false;
        testBtn.textContent = 'Test Connection';
        return;
    }

    statusEl.style.display = 'block';
    statusEl.textContent = draftProbeState.message;
    statusEl.className = `profile-probe-status probe-status probe-status-${draftProbeState.status}`;
    testBtn.disabled = draftProbeState.status === 'probing';
    testBtn.textContent = draftProbeState.status === 'probing' ? 'Testing...' : 'Test Connection';
}

function showProfilesList() {
    document.getElementById('profile-editor').style.display = 'none';
    document.getElementById('profiles-list').style.display = 'block';
    document.getElementById('add-profile-btn').style.display = 'block';
}

function showProfileEditor() {
    document.getElementById('profiles-list').style.display = 'none';
    document.getElementById('add-profile-btn').style.display = 'none';
    document.getElementById('profile-editor').style.display = 'block';
}

function renderProbeStatusMarkup(state) {
    if (!state) {
        return '';
    }
    return `<div class="probe-status probe-status-${state.status}">${escapeHtml(state.message)}</div>`;
}

function escapeHtml(value) {
    return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}
