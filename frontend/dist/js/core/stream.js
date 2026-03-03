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
        if (!createRes.ok) throw new Error('Failed to create run');
        const run = await createRes.json();
        runId = run.run_id;
    } catch (err) {
        console.error(err);
        endStream();
        return;
    }

    const url = `/api/runs/${runId}/events`;
    sysLog(`SSE start run=${runId} (mode=${executionMode} gate=${confirmationGate})`);
    const es = new EventSource(url);
    state.activeEventSource = es;

    let done = false;
    function finish() {
        if (done) return;
        done = true;
        endStream();
        if (onCompleted) onCompleted(sessionId);
    }

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

            if (evType === 'run_completed' || evType === 'run_failed') {
                finish();
            }
        } catch (e) {
            console.error('SSE parse error', e, event.data);
        }
    };

    es.onerror = () => {
        sysLog('SSE closed.', 'log-error');
        finish();
    };
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
    if (els.promptInput) {
        els.promptInput.disabled = false;
        els.promptInput.focus();
    }
}
