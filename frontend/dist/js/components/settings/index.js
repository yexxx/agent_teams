/**
 * components/settings/index.js
 * Settings modal shell and tab routing.
 */
import { bindModelProfileHandlers, loadModelProfilesPanel } from './modelProfiles.js';
import {
    bindNotificationSettingsHandlers,
    loadNotificationSettingsPanel,
} from './notifications.js';
import { bindSystemStatusHandlers, loadMcpStatusPanel, loadSkillsStatusPanel } from './systemStatus.js';

let settingsModal = null;
let currentTab = 'model';
let initialized = false;

export function initSettings() {
    if (initialized) return;
    createModal();
    setupEventListeners();
    initialized = true;
}

function createModal() {
    settingsModal = document.createElement('div');
    settingsModal.id = 'settings-modal';
    settingsModal.className = 'modal';
    settingsModal.innerHTML = `
        <div class="modal-content settings-modal-content">
            <div class="modal-header">
                <h2>Settings</h2>
                <button class="close-btn" id="settings-close">&times;</button>
            </div>
            <div class="settings-tabs">
                <button class="settings-tab active" data-tab="model">Model Profiles</button>
                <button class="settings-tab" data-tab="notifications">Notifications</button>
                <button class="settings-tab" data-tab="mcp">MCP Config</button>
                <button class="settings-tab" data-tab="skills">Skills</button>
            </div>
            <div class="settings-body">
                <div class="settings-panel" id="model-panel">
                    <div class="settings-section">
                        <div class="section-header">
                            <h3>Model Profiles</h3>
                        </div>
                        <div class="profiles-list" id="profiles-list"></div>
                        <div class="profile-editor" id="profile-editor" style="display:none;">
                            <h4 id="profile-editor-title">Add Profile</h4>
                            <div class="form-group">
                                <label>Profile Name:</label>
                                <input type="text" id="profile-name" placeholder="e.g., default, kimi">
                            </div>
                            <div class="form-group">
                                <label>Model:</label>
                                <input type="text" id="profile-model" placeholder="e.g., gpt-4o, kimi-k2.5">
                            </div>
                            <div class="form-group">
                                <label>Base URL:</label>
                                <input type="text" id="profile-base-url" placeholder="e.g., https://api.openai.com/v1">
                            </div>
                            <div class="form-group">
                                <label>API Key:</label>
                                <input type="password" id="profile-api-key" placeholder="sk-...">
                            </div>
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Temperature:</label>
                                    <input type="number" id="profile-temperature" value="0.7" step="0.1" min="0" max="2">
                                </div>
                                <div class="form-group">
                                    <label>Top P:</label>
                                    <input type="number" id="profile-top-p" value="1.0" step="0.1" min="0" max="1">
                                </div>
                                <div class="form-group">
                                    <label>Max Tokens:</label>
                                    <input type="number" id="profile-max-tokens" value="4096" min="1">
                                </div>
                            </div>
                            <div class="form-actions">
                                <button class="primary-btn" id="save-profile-btn">Save</button>
                                <button class="secondary-btn" id="test-profile-btn" type="button">Test Connection</button>
                                <button class="secondary-btn" id="cancel-profile-btn">Cancel</button>
                            </div>
                            <div class="profile-probe-status" id="profile-probe-status" style="display:none;"></div>
                        </div>
                        <button class="primary-btn" id="add-profile-btn" style="margin-top:10px;">+ Add Profile</button>
                    </div>
                </div>
                <div class="settings-panel" id="mcp-panel" style="display:none;">
                    <div class="settings-section">
                        <div class="section-header">
                            <h3>MCP Servers</h3>
                            <button class="primary-btn" id="reload-mcp-btn">Reload</button>
                        </div>
                        <div class="status-info" id="mcp-status"></div>
                    </div>
                </div>
                <div class="settings-panel" id="notifications-panel" style="display:none;">
                    <div class="settings-section">
                        <div class="section-header">
                            <h3>Notifications</h3>
                        </div>
                        <div class="status-info notifications-panel-body">
                            <p class="notifications-help">
                                Configure when notifications should be sent, and through which channel.
                                A notification is delivered only when <strong>Enabled</strong> is on and at least one channel is selected.
                            </p>
                            <div class="notification-grid">
                                <div class="notification-row" data-notif-type="tool_approval_requested">
                                    <div class="notification-row-main">
                                        <div class="notification-row-title">Tool approval requested</div>
                                        <div class="notification-row-desc">When an agent asks for tool approval.</div>
                                    </div>
                                    <label class="notification-toggle">
                                        <input type="checkbox" id="notif-tool_approval_requested-enabled">
                                        <span>Enabled</span>
                                    </label>
                                    <label class="notification-toggle">
                                        <input type="checkbox" id="notif-tool_approval_requested-browser">
                                        <span>Browser</span>
                                    </label>
                                    <label class="notification-toggle">
                                        <input type="checkbox" id="notif-tool_approval_requested-toast">
                                        <span>Toast</span>
                                    </label>
                                </div>

                                <div class="notification-row" data-notif-type="run_completed">
                                    <div class="notification-row-main">
                                        <div class="notification-row-title">Run completed</div>
                                        <div class="notification-row-desc">When a run finishes successfully.</div>
                                    </div>
                                    <label class="notification-toggle">
                                        <input type="checkbox" id="notif-run_completed-enabled">
                                        <span>Enabled</span>
                                    </label>
                                    <label class="notification-toggle">
                                        <input type="checkbox" id="notif-run_completed-browser">
                                        <span>Browser</span>
                                    </label>
                                    <label class="notification-toggle">
                                        <input type="checkbox" id="notif-run_completed-toast">
                                        <span>Toast</span>
                                    </label>
                                </div>

                                <div class="notification-row" data-notif-type="run_failed">
                                    <div class="notification-row-main">
                                        <div class="notification-row-title">Run failed</div>
                                        <div class="notification-row-desc">When a run exits due to an error.</div>
                                    </div>
                                    <label class="notification-toggle">
                                        <input type="checkbox" id="notif-run_failed-enabled">
                                        <span>Enabled</span>
                                    </label>
                                    <label class="notification-toggle">
                                        <input type="checkbox" id="notif-run_failed-browser">
                                        <span>Browser</span>
                                    </label>
                                    <label class="notification-toggle">
                                        <input type="checkbox" id="notif-run_failed-toast">
                                        <span>Toast</span>
                                    </label>
                                </div>

                                <div class="notification-row" data-notif-type="run_stopped">
                                    <div class="notification-row-main">
                                        <div class="notification-row-title">Run stopped</div>
                                        <div class="notification-row-desc">When a run is stopped by user action.</div>
                                    </div>
                                    <label class="notification-toggle">
                                        <input type="checkbox" id="notif-run_stopped-enabled">
                                        <span>Enabled</span>
                                    </label>
                                    <label class="notification-toggle">
                                        <input type="checkbox" id="notif-run_stopped-browser">
                                        <span>Browser</span>
                                    </label>
                                    <label class="notification-toggle">
                                        <input type="checkbox" id="notif-run_stopped-toast">
                                        <span>Toast</span>
                                    </label>
                                </div>
                            </div>
                            <div class="notifications-actions">
                                <button class="primary-btn" id="save-notifications-btn">Save Notifications</button>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="settings-panel" id="skills-panel" style="display:none;">
                    <div class="settings-section">
                        <div class="section-header">
                            <h3>Skills</h3>
                            <button class="primary-btn" id="reload-skills-btn">Reload</button>
                        </div>
                        <div class="status-info" id="skills-status"></div>
                    </div>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(settingsModal);
}

function setupEventListeners() {
    const closeBtn = document.getElementById('settings-close');
    if (closeBtn) {
        closeBtn.onclick = closeSettings;
    }

    settingsModal.onclick = (e) => {
        if (e.target === settingsModal) {
            closeSettings();
        }
    };

    document.querySelectorAll('.settings-tab').forEach(tab => {
        tab.onclick = () => {
            currentTab = tab.dataset.tab;
            document.querySelectorAll('.settings-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            showPanel(currentTab);
        };
    });

    bindModelProfileHandlers();
    bindNotificationSettingsHandlers();
    bindSystemStatusHandlers();
}

async function showPanel(tab) {
    document.querySelectorAll('.settings-panel').forEach(p => p.style.display = 'none');
    document.getElementById(`${tab}-panel`).style.display = 'block';

    if (tab === 'model') {
        await loadModelProfilesPanel();
    } else if (tab === 'notifications') {
        await loadNotificationSettingsPanel();
    } else if (tab === 'mcp') {
        await loadMcpStatusPanel();
    } else if (tab === 'skills') {
        await loadSkillsStatusPanel();
    }
}

export function openSettings() {
    if (!initialized) initSettings();
    settingsModal.style.display = 'flex';
    showPanel(currentTab);
}

export function closeSettings() {
    if (!settingsModal) return;
    settingsModal.style.display = 'none';
}

window.openSettings = openSettings;
