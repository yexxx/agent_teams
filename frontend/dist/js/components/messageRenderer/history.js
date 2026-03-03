/**
 * components/messageRenderer/history.js
 * Historical message rendering and approval state hydration.
 */
import { resolveToolApproval } from '../../core/api.js';
import {
    applyToolReturn,
    buildToolBlock,
    decoratePendingApprovalBlock,
    findToolBlockInContainer,
    labelFromRole,
    parseApprovalArgsPreview,
    renderMessageBlock,
    renderParts,
    resolvePendingToolBlock,
    scrollBottom,
} from './helpers.js';

export function renderHistoricalMessageList(container, messages, options = {}) {
    const pendingToolApprovals = Array.isArray(options.pendingToolApprovals)
        ? options.pendingToolApprovals
        : [];
    const runId = typeof options.runId === 'string' ? options.runId : '';
    const pendingStreamText = typeof options.pendingStreamText === 'string'
        ? options.pendingStreamText
        : '';
    const pendingStreamRoleId = typeof options.pendingStreamRoleId === 'string'
        ? options.pendingStreamRoleId
        : '';
    const pendingStreamInstanceId = typeof options.pendingStreamInstanceId === 'string'
        ? options.pendingStreamInstanceId
        : '';
    const pendingToolBlocks = {};
    const historyMessages = Array.isArray(messages) ? messages.slice() : [];
    const pendingStreamPatch = buildPendingStreamPatch(
        historyMessages,
        pendingStreamText,
        pendingStreamRoleId,
        pendingStreamInstanceId,
    );

    if (pendingStreamPatch) {
        historyMessages.push({
            role: 'assistant',
            role_id: pendingStreamRoleId,
            instance_id: pendingStreamInstanceId,
            message: {
                parts: [
                    {
                        part_kind: 'text',
                        content: pendingStreamPatch,
                    },
                ],
            },
        });
    }

    historyMessages.forEach(msgItem => {
        const role = msgItem.role;
        const msgObj = msgItem.message;
        if (!msgObj) return;

        const parts = msgObj.parts || [];

        const isPureToolReturn = role === 'user' && parts.length > 0 &&
            parts.every(p => {
                if (p.part_kind !== undefined) return p.part_kind === 'tool-return';
                return p.tool_name !== undefined && p.content !== undefined && p.args === undefined;
            });

        if (isPureToolReturn) {
            parts.forEach(part => {
                const toolBlock = resolvePendingToolBlock(
                    pendingToolBlocks,
                    part.tool_name,
                    part.tool_call_id,
                );
                if (toolBlock) applyToolReturn(toolBlock, part.content);
            });
            return;
        }

        const label = labelFromRole(role, msgItem.role_id, msgItem.instance_id);
        const { contentEl } = renderMessageBlock(container, role, label, []);
        renderParts(contentEl, parts, pendingToolBlocks);
    });

    applyPendingApprovalsToHistory(container, pendingToolApprovals, runId);
    scrollBottom(container);
}

function buildPendingStreamPatch(messages, pendingText, roleId, instanceId) {
    const rawPending = String(pendingText || '');
    if (!rawPending.trim()) return '';

    const historyText = collectHistoryText(messages, roleId, instanceId);
    const historyNorm = normalizeText(historyText);
    const pendingNorm = normalizeText(rawPending);
    if (!pendingNorm) return '';
    if (!historyNorm) return rawPending;
    if (historyNorm.includes(pendingNorm)) return '';

    const overlap = longestSuffixPrefixOverlap(historyText, rawPending);
    if (overlap <= 0) return rawPending;

    const delta = rawPending.slice(overlap);
    return delta.trim() ? delta : '';
}

function collectHistoryText(messages, roleId, instanceId) {
    const targetRole = String(roleId || '');
    const targetInstance = String(instanceId || '');
    const matchedChunks = [];
    const fallbackChunks = [];

    messages.forEach(msgItem => {
        if (!msgItem || typeof msgItem !== 'object') return;
        const msgRole = String(msgItem.role || '');
        const isAssistantLike = msgRole !== 'user';
        if (!isAssistantLike) return;

        const itemInstance = String(msgItem.instance_id || '');
        const itemRole = String(msgItem.role_id || '');
        const matchedByTarget = targetInstance
            ? itemInstance === targetInstance
            : (!!targetRole && itemRole === targetRole);
        const useMatchedBucket = !!targetInstance || !!targetRole;

        const msgObj = msgItem.message;
        const parts = Array.isArray(msgObj?.parts) ? msgObj.parts : [];
        parts.forEach(part => {
            const kind = String(part?.part_kind || '');
            const content = typeof part?.content === 'string' ? part.content : '';
            if (!content) return;
            if (kind !== 'text') return;
            fallbackChunks.push(content);
            if (useMatchedBucket && matchedByTarget) {
                matchedChunks.push(content);
            }
        });
    });

    if (matchedChunks.length > 0) return matchedChunks.join('\n');
    return fallbackChunks.join('\n');
}

function normalizeText(text) {
    return String(text || '')
        .replace(/\s+/g, ' ')
        .trim();
}

function longestSuffixPrefixOverlap(baseText, appendText) {
    const base = String(baseText || '');
    const append = String(appendText || '');
    const max = Math.min(base.length, append.length);
    for (let len = max; len > 0; len -= 1) {
        if (base.slice(base.length - len) === append.slice(0, len)) return len;
    }
    return 0;
}

function applyPendingApprovalsToHistory(container, approvals, runId) {
    if (!approvals || approvals.length === 0) return;

    const missing = [];
    approvals.forEach(approval => {
        const toolBlock = findToolBlockInContainer(
            container,
            approval?.tool_name,
            approval?.tool_call_id || null,
            true,
        );
        if (toolBlock) {
            decoratePendingApprovalBlock(toolBlock, approval);
            attachPendingApprovalActions(toolBlock, approval, runId);
        } else {
            missing.push(approval);
        }
    });

    if (missing.length === 0) return;
    const { contentEl } = renderMessageBlock(container, 'model', 'Coordinator', []);
    missing.forEach(approval => {
        const toolBlock = buildToolBlock(
            approval?.tool_name || 'unknown_tool',
            parseApprovalArgsPreview(approval?.args_preview),
            approval?.tool_call_id || null,
        );
        contentEl.appendChild(toolBlock);
        decoratePendingApprovalBlock(toolBlock, approval);
        attachPendingApprovalActions(toolBlock, approval, runId);
    });
}

function attachPendingApprovalActions(toolBlock, approval, runId) {
    const status = String(approval?.status || 'requested').toLowerCase();
    const toolCallId = String(approval?.tool_call_id || '');
    if (status !== 'requested' || !toolCallId || !runId) return;

    let approvalEl = toolBlock.querySelector('.tool-approval-inline');
    if (!approvalEl) {
        approvalEl = document.createElement('div');
        approvalEl.className = 'tool-approval-inline';
        const body = toolBlock.querySelector('.tool-body');
        const resultEl = toolBlock.querySelector('.tool-result');
        if (body && resultEl) {
            body.insertBefore(approvalEl, resultEl);
        } else if (body) {
            body.appendChild(approvalEl);
        }
    }
    approvalEl.innerHTML = `
        <div class="tool-approval-state">Approval required</div>
        <div class="gate-actions">
            <button class="gate-approve-btn">Approve</button>
            <button class="gate-revise-btn">Deny</button>
        </div>
    `;

    const stateEl = approvalEl.querySelector('.tool-approval-state');
    const approveBtn = approvalEl.querySelector('.gate-approve-btn');
    const denyBtn = approvalEl.querySelector('.gate-revise-btn');
    const resultEl = toolBlock.querySelector('.tool-result');
    const bodyEl = toolBlock.querySelector('.tool-body');
    if (bodyEl) bodyEl.classList.add('open');

    const setBusy = (busy) => {
        if (approveBtn) approveBtn.disabled = busy;
        if (denyBtn) denyBtn.disabled = busy;
    };
    const markResolved = (action) => {
        if (stateEl) stateEl.textContent = `Approval ${String(action).toUpperCase()}`;
        setBusy(true);
        if (!resultEl) return;
        if (String(action).toLowerCase() === 'deny') {
            resultEl.classList.remove('warning-text');
            resultEl.classList.remove('error-text');
            resultEl.innerHTML = 'Approval denied. Tool will not execute.';
        } else {
            resultEl.classList.remove('error-text');
            resultEl.classList.add('warning-text');
            resultEl.innerHTML = 'Approval submitted. Waiting for tool result...';
        }
    };

    if (approveBtn) {
        approveBtn.onclick = async () => {
            setBusy(true);
            try {
                await resolveToolApproval(runId, toolCallId, 'approve', '');
                markResolved('approve');
                emitApprovalResolved(runId);
            } catch (e) {
                setBusy(false);
                if (stateEl) stateEl.textContent = `Approval failed: ${e.message}`;
            }
        };
    }

    if (denyBtn) {
        denyBtn.onclick = async () => {
            setBusy(true);
            try {
                await resolveToolApproval(runId, toolCallId, 'deny', '');
                markResolved('deny');
                emitApprovalResolved(runId);
            } catch (e) {
                setBusy(false);
                if (stateEl) stateEl.textContent = `Approval failed: ${e.message}`;
            }
        };
    }
}

function emitApprovalResolved(runId) {
    const safeRunId = String(runId || '');
    if (!safeRunId) return;
    document.dispatchEvent(
        new CustomEvent('run-approval-resolved', {
            detail: { runId: safeRunId },
        }),
    );
}
