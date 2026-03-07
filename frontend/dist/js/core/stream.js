/**
 * core/stream.js
 * Creates a run via HTTP, then subscribes to run events over SSE.
 */
import { sendUserPrompt, stopRun } from './api.js';
import { state } from './state.js';
import { els } from '../utils/dom.js';
import { sysLog } from '../utils/logger.js';
import { routeEvent } from './eventRouter.js';
import { clearRunStreamState } from '../components/messageRenderer.js';

let pendingStopRequest = false;
let creatingRun = false;

export async function startIntentStream(promptText, sessionId, executionMode, onCompleted, options = {}) {
    creatingRun = true;
    state.activeRunId = null;
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
        const run = await sendUserPrompt(sessionId, promptText, { executionMode });
        runId = run.run_id;
        state.activeRunId = runId;
        if (typeof options.onRunCreated === 'function') {
            options.onRunCreated(run);
        }
    } catch (err) {
        creatingRun = false;
        pendingStopRequest = false;
        sysLog(err.message || 'Failed to create run', 'log-error');
        endStream();
        return;
    }
    creatingRun = false;

    const shouldStopImmediately = pendingStopRequest;
    pendingStopRequest = false;
    if (shouldStopImmediately) {
        try {
            await stopRun(runId, { scope: 'main' });
            sysLog('Stop requested before stream attachment; stopped immediately after run creation.');
            await finalizeStopAndSyncRecovery(runId, sessionId);
            return;
        } catch (err) {
            sysLog(err.message || 'Failed to stop run', 'log-error');
        }
    }
    resumeRunStream(runId, sessionId, onCompleted, {
        reason: `start mode=${executionMode}`,
        makeUiBusy: false,
    });
}

export function endStream() {
    creatingRun = false;
    pendingStopRequest = false;
    const finishedRunId = state.activeRunId;
    if (state.activeEventSource) {
        state.activeEventSource.close();
        state.activeEventSource = null;
    }
    if (finishedRunId) {
        clearRunStreamState(finishedRunId);
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
    clearRunStreamState(safeRunId);

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
        const recoveryModule = await import('../app/recovery.js');
        if (typeof recoveryModule.hydrateSessionView === 'function' && state.currentSessionId === sessionId) {
            await recoveryModule.hydrateSessionView(sessionId, { includeRounds: true, quiet: true });
        }
    } catch (e) {
        console.error('Failed to refresh rounds after stream completion', e);
    }
}

export async function requestStopCurrentRun() {
    const activeRunId = String(state.activeRunId || '').trim();
    if (activeRunId) {
        await stopRun(activeRunId, { scope: 'main' });
        await finalizeStopAndSyncRecovery(activeRunId, state.currentSessionId);
        return true;
    }
    if (
        creatingRun
        || state.isGenerating
        || !!state.activeEventSource
        || !!els.promptInput?.disabled
        || !!els.sendBtn?.disabled
    ) {
        pendingStopRequest = true;
        sysLog('Stop requested. Waiting for run creation before sending stop.');
        return true;
    }
    return false;
}

async function syncRecoveryAfterStopRequest(runId, sessionId) {
    const safeRunId = String(runId || '').trim();
    const safeSessionId = String(sessionId || state.currentSessionId || '').trim();
    if (!safeRunId || !safeSessionId || state.currentSessionId !== safeSessionId) return;
    try {
        const recoveryModule = await import('../app/recovery.js');
        if (typeof recoveryModule.hydrateSessionView !== 'function') return;
        const snapshot = await recoveryModule.hydrateSessionView(safeSessionId, {
            includeRounds: true,
            quiet: true,
        });
        const activeRun = snapshot?.activeRun || null;
        if (!activeRun || activeRun.run_id !== safeRunId) return;

        const status = String(activeRun.status || '');
        const phase = String(activeRun.phase || '');
        const isRecoverable = activeRun.is_recoverable !== false;
        if (
            status === 'stopped'
            || phase === 'stopped'
            || status === 'completed'
            || status === 'failed'
            || !isRecoverable
        ) {
            endStream();
        }
    } catch (e) {
        console.error('Failed to sync recovery after stop request', e);
    }
}

async function finalizeStopAndSyncRecovery(runId, sessionId) {
    const safeRunId = String(runId || '').trim();
    const safeSessionId = String(sessionId || state.currentSessionId || '').trim();
    if (!safeRunId) return;

    endStream();
    await applyLocalStoppedSnapshot(safeRunId, safeSessionId);
    await syncRecoveryAfterStopRequest(safeRunId, safeSessionId);
}

async function applyLocalStoppedSnapshot(runId, sessionId) {
    const safeRunId = String(runId || '').trim();
    const safeSessionId = String(sessionId || state.currentSessionId || '').trim();
    if (!safeRunId) return;
    try {
        const recoveryModule = await import('../app/recovery.js');
        if (typeof recoveryModule.applyRecoverySnapshot === 'function') {
            recoveryModule.applyRecoverySnapshot({
                active_run: {
                    run_id: safeRunId,
                    status: 'stopped',
                    phase: 'stopped',
                    is_recoverable: true,
                    checkpoint_event_id: 0,
                    last_event_id: 0,
                    pending_tool_approval_count: 0,
                    stream_connected: false,
                    should_show_recover: true,
                },
                pending_tool_approvals: [],
                paused_subagent: null,
                round_snapshot: null,
            });
        }
        if (safeSessionId && typeof recoveryModule.scheduleRecoveryContinuityRefresh === 'function') {
            recoveryModule.scheduleRecoveryContinuityRefresh({
                sessionId: safeSessionId,
                delayMs: 0,
                includeRounds: true,
                quiet: true,
                reason: 'stop-sync',
            });
        }
    } catch (e) {
        console.error('Failed to apply local stopped snapshot', e);
    }
}
