/**
 * core/stream.js
 * Creates a run via HTTP, then subscribes to run events over SSE.
 */
import { state } from './state.js';
import { els } from '../utils/dom.js';
import { sysLog } from '../utils/logger.js';
import { routeEvent } from './eventRouter.js';

export async function startIntentStream(promptText, sessionId, executionMode, confirmationGate, onCompleted) {
    state.isGenerating = true;
    if (els.sendBtn) els.sendBtn.disabled = true;
    if (els.promptInput) els.promptInput.disabled = true;
    if (els.stopBtn) {
        els.stopBtn.style.display = 'inline-flex';
        els.stopBtn.disabled = false;
    }

    const panel = document.getElementById('workflow-panel');
    if (panel) panel.classList.add('generating');

    if (state.activeEventSource) {
        state.activeEventSource.close();
        state.activeEventSource = null;
    }

    let runId = null;
    try {
        const createRes = await fetch('/api/runs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                intent: promptText,
                session_id: sessionId,
                execution_mode: executionMode,
                confirmation_gate: confirmationGate,
            }),
        });
        if (!createRes.ok) {
            let detail = 'Failed to create run';
            try {
                const payload = await createRes.json();
                if (typeof payload?.detail === 'string' && payload.detail) {
                    detail = payload.detail;
                }
            } catch (_) {
                // ignore parse error and keep default message
            }
            throw new Error(detail);
        }
        const run = await createRes.json();
        runId = run.run_id;
        state.activeRunId = runId;
    } catch (err) {
        sysLog(err.message || 'Failed to create run', 'log-error');
        endStream();
        return;
    }

    resumeRunStream(runId, sessionId, onCompleted, {
        reason: `start mode=${executionMode} gate=${confirmationGate}`,
        makeUiBusy: false,
    });
}

export function endStream() {
    if (state.activeEventSource) {
        state.activeEventSource.close();
        state.activeEventSource = null;
    }
    state.isGenerating = false;

    const panel = document.getElementById('workflow-panel');
    if (panel) panel.classList.remove('generating');

    if (els.sendBtn) els.sendBtn.disabled = false;
    if (els.stopBtn) {
        els.stopBtn.disabled = true;
        els.stopBtn.style.display = 'none';
    }
    if (els.promptInput) {
        els.promptInput.disabled = false;
        els.promptInput.focus();
    }
}

export function resumeRunStream(runId, sessionId = state.currentSessionId, onCompleted = null, options = {}) {
    const safeRunId = typeof runId === 'string' ? runId.trim() : '';
    if (!safeRunId) return;

    const reason = typeof options.reason === 'string' && options.reason
        ? options.reason
        : 'resume';
    const makeUiBusy = options.makeUiBusy !== false;

    state.activeRunId = safeRunId;
    if (makeUiBusy) {
        state.isGenerating = true;
        if (els.sendBtn) els.sendBtn.disabled = true;
        if (els.promptInput) els.promptInput.disabled = true;
        if (els.stopBtn) {
            els.stopBtn.style.display = 'inline-flex';
            els.stopBtn.disabled = false;
        }
        const panel = document.getElementById('workflow-panel');
        if (panel) panel.classList.add('generating');
    }

    if (state.activeEventSource) {
        state.activeEventSource.close();
        state.activeEventSource = null;
    }

    const url = `/api/runs/${safeRunId}/events`;
    sysLog(`SSE ${reason} run=${safeRunId}`);
    const es = new EventSource(url);
    state.activeEventSource = es;

    let done = false;
    const finish = () => {
        if (done) return;
        done = true;
        endStream();
        if (typeof onCompleted === 'function') {
            onCompleted(sessionId);
            return;
        }
        if (sessionId) {
            void refreshRoundsAfterCompletion(sessionId);
        }
    };

    es.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.error) {
                sysLog(`Run stream error: ${data.error}`, 'log-error');
                finish();
                return;
            }

            const evType = data.event_type;
            const payload = JSON.parse(data.payload_json || '{}');
            routeEvent(evType, payload, data);

            if (evType === 'run_completed' || evType === 'run_failed' || evType === 'run_stopped') {
                finish();
            }
        } catch (e) {
            console.error('SSE parse error', e, event.data);
        }
    };

    es.onerror = () => {
        if (done) return;
        sysLog('SSE closed.', 'log-error');
        finish();
    };
}

async function refreshRoundsAfterCompletion(sessionId) {
    if (!sessionId || state.currentSessionId !== sessionId) return;
    try {
        const roundsModule = await import('../components/rounds.js');
        if (typeof roundsModule.loadSessionRounds === 'function' && state.currentSessionId === sessionId) {
            await roundsModule.loadSessionRounds(sessionId);
        }
    } catch (e) {
        console.error('Failed to refresh rounds after stream completion', e);
    }
}
