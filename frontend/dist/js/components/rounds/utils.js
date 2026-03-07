/**
 * components/rounds/utils.js
 * Shared utility helpers for rounds timeline rendering.
 */

export function roundSectionId(runId) {
    return `round-${String(runId).replace(/[^a-zA-Z0-9_-]/g, '_')}`;
}

export function esc(text) {
    if (!text) return '';
    const d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
}

export function roundStateTone(round) {
    const phase = String(round?.run_phase || '');
    const status = String(round?.run_status || '');
    if (phase === 'awaiting_tool_approval' || phase === 'awaiting_subagent_followup') {
        return 'warning';
    }
    switch (status) {
        case 'running':
            return 'running';
        case 'completed':
            return 'success';
        case 'failed':
            return 'danger';
        case 'stopped':
            return 'stopped';
        default:
            return 'idle';
    }
}

export function roundStateLabel(round) {
    const phase = String(round?.run_phase || '');
    const status = String(round?.run_status || '');
    if (phase === 'awaiting_tool_approval') return 'Awaiting Approval';
    if (phase === 'awaiting_subagent_followup') return 'Awaiting Follow-up';
    switch (status) {
        case 'queued':
            return 'Queued';
        case 'running':
            return 'Running';
        case 'paused':
            return 'Paused';
        case 'stopped':
            return 'Stopped';
        case 'completed':
            return 'Completed';
        case 'failed':
            return 'Failed';
        default:
            return '';
    }
}
