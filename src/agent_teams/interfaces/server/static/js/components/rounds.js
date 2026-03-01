/**
 * components/rounds.js
 * Renders session rounds (sidebar list + main area coordinator view).
 * Historical messages use the unified messageRenderer.
 */
import { els } from '../utils/dom.js';
import { sysLog } from '../utils/logger.js';
import { state } from '../core/state.js';
import { fetchSessionRounds } from '../core/api.js';
import { renderNativeDAG } from './workflow.js';
import { setRoundsMode, setSessionMode } from './sidebar.js';
import { renderHistoricalMessageList } from './messageRenderer.js';
import { clearAllPanels } from './agentPanel.js';
import { parseMarkdown } from '../utils/markdown.js';

export let currentRounds = [];
export let currentRound = null;

export async function loadSessionRounds(sessionId) {
    try {
        const rounds = await fetchSessionRounds(sessionId);
        currentRounds = rounds || [];
        renderRoundsListInSidebar(currentRounds);
        // Show first (most recent) round
        if (currentRounds.length > 0) {
            renderRoundContent(currentRounds[0]);
            updateWorkflowState(currentRounds[0].workflows?.length ?? 0, currentRounds[0]);
        } else {
            renderRoundContent(null);
            updateWorkflowState(0, null);
        }
    } catch (e) {
        console.error('Failed loading rounds', e);
    }
}

/**
 * Create an immediate "live round" entry in the sidebar and switch to a
 * streaming view in the main area.  Called right after the user hits Send
 * so they see the new round instantly, before any SSE events arrive.
 */
export function createLiveRound(intentText) {
    const liveRound = {
        run_id: '__live__',
        created_at: new Date().toISOString(),
        intent: intentText,
        coordinator_messages: [],
        workflows: [],
    };

    // Prepend to the rounds array
    currentRounds = [liveRound, ...currentRounds];
    currentRound = liveRound;

    renderRoundsListInSidebar(currentRounds);

    // Clear main area and show the live header
    const container = els.chatMessages;
    if (container) {
        container.innerHTML = '';
        const headerEl = document.createElement('div');
        headerEl.className = 'round-detail-header';
        headerEl.innerHTML = `
            <div class="round-detail-label">Round ${currentRounds.length === 1 ? 1 : 1} <span class="live-badge">LIVE</span></div>
            <div class="round-detail-time">${new Date().toLocaleString()}</div>
            <div class="round-detail-intent">
                <span class="intent-label">Intent:</span>
                <span class="intent-text">${_esc(intentText)}</span>
            </div>`;
        container.appendChild(headerEl);
    }

    // Show the execution graph panel (collapsed initially)
    if (els.workflowPanel) {
        els.workflowPanel.style.display = 'flex';
        const canvas = document.getElementById('workflow-canvas');
        if (canvas) canvas.innerHTML = '<div class="panel-empty">等待 Coordinator 创建 workflow graph…</div>';
    }
    if (els.workflowCollapsed) els.workflowCollapsed.style.display = 'none';
}

// ─── Sidebar round list ──────────────────────────────────────────────────────

function renderRoundsListInSidebar(rounds) {
    if (!els.roundsList) return;
    els.roundsList.innerHTML = '';

    const header = document.createElement('div');
    header.className = 'rounds-header';
    header.textContent = 'Rounds';
    els.roundsList.appendChild(header);

    rounds.forEach((round, index) => {
        const item = document.createElement('div');
        item.className = 'round-item';
        if (currentRound?.run_id === round.run_id) item.classList.add('active');
        item.onclick = () => selectRound(round);

        const dot = document.createElement('span');
        dot.className = 'round-item-dot';

        const label = round.run_id === '__live__'
            ? `🔴 Round ${index + 1}: ${round.intent || '…'}`
            : `Round ${index + 1}: ${round.intent || 'No intent'}`;

        const text = document.createElement('span');
        text.className = 'round-item-text';
        text.textContent = label;

        item.appendChild(dot);
        item.appendChild(text);
        els.roundsList.appendChild(item);
    });
}

export function selectRound(round) {
    currentRound = round;

    document.querySelectorAll('.round-item').forEach((el, idx) => {
        el.classList.toggle('active', currentRounds[idx]?.run_id === round.run_id);
    });

    // Clear agent panels when switching rounds
    clearAllPanels();
    state.instanceRoleMap = {};

    renderRoundContent(round);
    updateWorkflowState(round.workflows?.length ?? 0, round);
}

function renderRoundContent(round) {
    const container = els.chatMessages;
    if (!container) return;
    container.innerHTML = '';

    if (!round) {
        container.innerHTML = `
            <div class="system-intro">
                <div class="intro-icon">🛸</div>
                <h1>Welcome to Agent Teams</h1>
                <p>Select a session or create a new one to begin.</p>
            </div>`;
        return;
    }

    // Round header
    const time = new Date(round.created_at).toLocaleString();
    const idx = currentRounds.indexOf(round);
    const headerEl = document.createElement('div');
    headerEl.className = 'round-detail-header';
    headerEl.innerHTML = `
        <div class="round-detail-label">Round ${idx + 1}</div>
        <div class="round-detail-time">${time}</div>
        <div class="round-detail-intent">
            <span class="intent-label">Intent:</span>
            <span class="intent-text">${_esc(round.intent || 'No intent')}</span>
        </div>`;
    container.appendChild(headerEl);

    // Coordinator messages — use unified renderer
    if (round.coordinator_messages?.length > 0) {
        renderHistoricalMessageList(container, round.coordinator_messages);
    }

    container.scrollTop = container.scrollHeight;
}

function updateWorkflowState(workflowCount, round) {
    if (!els.workflowCount || !els.workflowCollapsed || !els.workflowPanel) return;
    els.workflowCount.textContent = workflowCount;

    if (workflowCount > 0) {
        els.workflowPanel.style.display = 'flex';
        els.workflowCollapsed.style.display = 'none';
        if (round?.workflows?.length > 0) {
            renderNativeDAG(round.workflows[round.workflows.length - 1]);
        }
    } else {
        els.workflowCollapsed.style.display = 'none';
        els.workflowPanel.style.display = 'none';
    }
}

export function toggleWorkflow() {
    if (!els.workflowPanel || !els.workflowCollapsed) return;
    const isHidden = els.workflowPanel.style.display === 'none' || els.workflowPanel.style.display === '';
    if (isHidden) {
        els.workflowPanel.style.display = 'flex';
        els.workflowCollapsed.style.display = 'none';
        if (currentRound?.workflows?.length > 0) {
            renderNativeDAG(currentRound.workflows[currentRound.workflows.length - 1]);
        }
    } else {
        els.workflowPanel.style.display = 'none';
        els.workflowCollapsed.style.display = 'block';
    }
}

export function goBackToSessions() {
    setSessionMode();
    currentRound = null;
    currentRounds = [];
    clearAllPanels();
    els.chatMessages.innerHTML = `
        <div class="system-intro">
            <div class="intro-icon">🛸</div>
            <h1>Welcome to Agent Teams</h1>
            <p>Select a session from the sidebar to view details.</p>
        </div>`;
    if (els.workflowPanel) els.workflowPanel.style.display = 'none';
    if (els.workflowCollapsed) els.workflowCollapsed.style.display = 'none';
}

function _esc(text) {
    if (!text) return '';
    const d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
}
