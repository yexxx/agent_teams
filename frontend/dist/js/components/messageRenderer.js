/**
 * components/messageRenderer.js
 * Unified message renderer used by both SSE streaming and historical display.
 * All message rendering goes through this module to keep the two views consistent.
 */
import { parseMarkdown } from '../utils/markdown.js';

// ─── Block builder ────────────────────────────────────────────────────────────

/**
 * Create and append a message block to `container`.
 * @param {HTMLElement} container  - target scroll container
 * @param {'user'|'model'|string} role
 * @param {string} label           - display name (e.g. "Coordinator", "hello_agent")
 * @param {Array}  parts           - pydantic-ai message parts array (may be empty)
 * @returns {{ wrapper, contentEl, pendingToolBlocks }}  — refs for live streaming
 */
export function renderMessageBlock(container, role, label, parts = []) {
    const safeLabel = label || 'Agent';
    const wrapper = document.createElement('div');
    wrapper.className = 'message';
    wrapper.dataset.role = role;

    const roleClass = _roleClass(role, safeLabel);
    wrapper.innerHTML = `
        <div class="msg-header">
            <span class="msg-role ${roleClass}">${safeLabel.toUpperCase()}</span>
        </div>
        <div class="msg-content"></div>
    `;
    container.appendChild(wrapper);
    _scrollBottom(container);

    const contentEl = wrapper.querySelector('.msg-content');
    const pendingToolBlocks = {};

    if (parts.length > 0) {
        _renderParts(contentEl, parts, pendingToolBlocks);
    }

    return { wrapper, contentEl, pendingToolBlocks };
}

/**
 * Render historical messages (pydantic-ai message objects) into a container.
 */
export function renderHistoricalMessageList(container, messages) {
    const pendingToolBlocks = {};

    messages.forEach(msgItem => {
        const role = msgItem.role;          // 'user' | 'model'
        const msgObj = msgItem.message;
        if (!msgObj) return;

        const parts = msgObj.parts || [];

        // Pure tool-return messages: inject into previous tool block result div
        const isPureToolReturn = role === 'user' && parts.length > 0 &&
            parts.every(p => p.part_kind === 'tool-return' || (p.tool_name !== undefined && p.content !== undefined && p.args === undefined));

        if (isPureToolReturn) {
            parts.forEach(part => {
                const resultDiv = pendingToolBlocks[part.tool_name];
                if (resultDiv) {
                    const val = typeof part.content === 'object'
                        ? JSON.stringify(part.content, null, 2)
                        : String(part.content);
                    resultDiv.innerHTML = parseMarkdown(val);
                    // mark status success
                    const status = resultDiv.closest('.tool-block')?.querySelector('.tool-status');
                    if (status) status.innerHTML = `<svg class="status-icon status-success" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg>`;
                }
            });
            return;
        }

        const label = _labelFromRole(role, msgItem.role_id, msgItem.instance_id);
        const { wrapper, contentEl } = renderMessageBlock(container, role, label, []);
        _renderParts(contentEl, parts, pendingToolBlocks);
    });

    _scrollBottom(container);
}

// ─── Streaming helpers ────────────────────────────────────────────────────────

/** State for currently streaming message per panel/container */
const _streamState = new Map(); // key = containerId or instanceId

export function getOrCreateStreamBlock(container, instanceId, roleId, label) {
    let st = _streamState.get(instanceId);
    if (!st || st.container !== container) {
        const { wrapper, contentEl } = renderMessageBlock(container, 'model', label, []);
        st = {
            container,
            wrapper,
            contentEl,
            activeTextEl: null,
            raw: '',
            roleId,
            label
        };
        _streamState.set(instanceId, st);
    }
    return st;
}

export function appendStreamChunk(instanceId, text) {
    const st = _streamState.get(instanceId);
    if (!st) return;

    if (!st.activeTextEl) {
        st.activeTextEl = document.createElement('div');
        st.activeTextEl.className = 'msg-text';
        st.contentEl.appendChild(st.activeTextEl);
        st.raw = '';
    }

    st.raw += text;
    st.activeTextEl.innerHTML = parseMarkdown(st.raw);
    _scrollBottom(st.container);
}

export function finalizeStream(instanceId) {
    const st = _streamState.get(instanceId);
    if (st && st.activeTextEl) {
        st.activeTextEl.innerHTML = parseMarkdown(st.raw);
    }
    _streamState.delete(instanceId);
}

export function clearStreamState(instanceId) {
    _streamState.delete(instanceId);
}

export function clearAllStreamState() {
    _streamState.clear();
}

/** Attach a tool-call block to the currently streaming message for instanceId */
export function appendToolCallBlock(container, instanceId, toolName, args) {
    let st = _streamState.get(instanceId);
    if (!st) {
        const label = toolName ? `tool` : 'agent';
        const { wrapper, contentEl } = renderMessageBlock(container, 'model', label, []);
        st = { container, wrapper, contentEl, activeTextEl: null, raw: '', roleId: '', label };
        _streamState.set(instanceId, st);
    }

    // Finalize current text segment
    st.activeTextEl = null;
    st.raw = '';

    let argsStr = '';
    try {
        argsStr = typeof args === 'object' ? JSON.stringify(args, null, 2) : String(args || '');
    } catch (e) {
        argsStr = String(args);
    }

    const toolBlock = document.createElement('div');
    toolBlock.className = 'tool-block';
    toolBlock.dataset.toolName = toolName;
    toolBlock.style.display = 'block';
    toolBlock.style.visibility = 'visible';

    toolBlock.innerHTML = `
        <div class="tool-header" onclick="this.nextElementSibling.classList.toggle('open')">
            <div class="tool-title">
                <svg viewBox="0 0 24 24" fill="none" class="icon" style="width:14px;height:14px;"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" stroke="currentColor" stroke-width="2"/></svg>
                <span class="name">${toolName}</span>
            </div>
            <div class="tool-status"><div class="spinner"></div></div>
        </div>
        <div class="tool-body">
            <pre class="tool-args" style="white-space:pre-wrap;">${argsStr}</pre>
            <div class="tool-result">Processing...</div>
        </div>
    `;
    st.contentEl.appendChild(toolBlock);
    _scrollBottom(st.container || container);
    return toolBlock;
}

export function updateToolResult(instanceId, toolName, result, isError) {
    const st = _streamState.get(instanceId);
    if (!st) return;

    const toolBlock = _findLatestToolBlock(st.contentEl, toolName);
    if (!toolBlock) return;

    const statusEl = toolBlock.querySelector('.tool-status');
    const resultEl = toolBlock.querySelector('.tool-result');
    if (isError) {
        statusEl.innerHTML = `<svg class="status-icon status-error" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>`;
        resultEl.classList.add('error-text');
    } else {
        statusEl.innerHTML = `<svg class="status-icon status-success" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg>`;
        resultEl.classList.remove('error-text');
    }
    const val = typeof result === 'object' ? JSON.stringify(result, null, 2) : String(result ?? '');
    resultEl.innerHTML = parseMarkdown(val);

    const approvalEl = toolBlock.querySelector('.tool-approval-inline');
    if (approvalEl) {
        const stateEl = approvalEl.querySelector('.tool-approval-state');
        if (stateEl && !stateEl.textContent?.includes('DENY') && !stateEl.textContent?.includes('TIMEOUT')) {
            stateEl.textContent = isError ? 'Approval/Execution failed' : 'Approved';
        }
        approvalEl.querySelectorAll('button').forEach(btn => { btn.disabled = true; });
    }
    _scrollBottom(st.container);
}

export function attachToolApprovalControls(instanceId, toolName, payload, handlers) {
    const st = _streamState.get(instanceId);
    if (!st) return false;

    const toolBlock = _findLatestToolBlock(st.contentEl, toolName);
    if (!toolBlock) return false;
    if (payload?.tool_call_id) {
        toolBlock.dataset.toolCallId = payload.tool_call_id;
    }

    let approvalEl = toolBlock.querySelector('.tool-approval-inline');
    if (!approvalEl) {
        approvalEl = document.createElement('div');
        approvalEl.className = 'tool-approval-inline';
        approvalEl.innerHTML = `
            <div class="tool-approval-state">Approval required</div>
            <div class="gate-actions">
                <button class="gate-approve-btn">Approve</button>
                <button class="gate-revise-btn">Deny</button>
            </div>
        `;
        const body = toolBlock.querySelector('.tool-body');
        const resultEl = toolBlock.querySelector('.tool-result');
        if (body && resultEl) {
            body.insertBefore(approvalEl, resultEl);
        } else if (body) {
            body.appendChild(approvalEl);
        }
    }

    const approveBtn = approvalEl.querySelector('.gate-approve-btn');
    const denyBtn = approvalEl.querySelector('.gate-revise-btn');
    const stateEl = approvalEl.querySelector('.tool-approval-state');
    if (stateEl) stateEl.textContent = 'Approval required';

    if (approveBtn) {
        approveBtn.disabled = false;
        approveBtn.onclick = async () => {
            approveBtn.disabled = true;
            if (denyBtn) denyBtn.disabled = true;
            try {
                await handlers.onApprove();
            } catch (e) {
                approveBtn.disabled = false;
                if (denyBtn) denyBtn.disabled = false;
                if (handlers.onError) handlers.onError(e);
            }
        };
    }
    if (denyBtn) {
        denyBtn.disabled = false;
        denyBtn.onclick = async () => {
            denyBtn.disabled = true;
            if (approveBtn) approveBtn.disabled = true;
            try {
                await handlers.onDeny();
            } catch (e) {
                denyBtn.disabled = false;
                if (approveBtn) approveBtn.disabled = false;
                if (handlers.onError) handlers.onError(e);
            }
        };
    }

    _scrollBottom(st.container);
    return true;
}

export function markToolApprovalResolved(instanceId, payload) {
    const st = _streamState.get(instanceId);
    if (!st) return false;
    const toolCallId = payload?.tool_call_id;
    if (!toolCallId) return false;

    let toolBlock = st.contentEl.querySelector(`.tool-block[data-tool-call-id="${toolCallId}"]`);
    if (!toolBlock && payload?.tool_name) {
        toolBlock = _findLatestToolBlock(st.contentEl, payload.tool_name);
        if (toolBlock) toolBlock.dataset.toolCallId = toolCallId;
    }
    if (!toolBlock) return false;

    const approvalEl = toolBlock.querySelector('.tool-approval-inline');
    if (!approvalEl) return false;
    const action = String(payload.action || 'resolved').toUpperCase();
    const stateEl = approvalEl.querySelector('.tool-approval-state');
    if (stateEl) stateEl.textContent = `Approval ${action}`;
    approvalEl.querySelectorAll('button').forEach(btn => { btn.disabled = true; });
    return true;
}

// ─── Private helpers ──────────────────────────────────────────────────────────

function _renderParts(contentEl, parts, pendingToolBlocks) {
    let combinedText = '';

    const flushText = () => {
        if (combinedText.trim()) {
            const textEl = document.createElement('div');
            textEl.className = 'msg-text';
            textEl.innerHTML = parseMarkdown(combinedText.trim());
            contentEl.appendChild(textEl);
            combinedText = '';
        }
    };

    parts.forEach(part => {
        const kind = part.part_kind;

        if (kind === 'text' || kind === 'user-prompt') {
            combinedText += (part.content || '') + '\n\n';
        } else if (kind === 'tool-call' || (part.tool_name && part.args !== undefined)) {
            flushText();
            const tb = _buildToolBlock(part.tool_name, part.args);
            contentEl.appendChild(tb);
            pendingToolBlocks[part.tool_name] = tb.querySelector('.tool-result');
        } else if (kind === 'tool-return') {
            const rd = pendingToolBlocks[part.tool_name];
            if (rd) {
                const val = typeof part.content === 'object'
                    ? JSON.stringify(part.content, null, 2)
                    : String(part.content);
                rd.innerHTML = parseMarkdown(val);
                const status = rd.closest('.tool-block')?.querySelector('.tool-status');
                if (status) status.innerHTML = `<svg class="status-icon status-success" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg>`;
            }
        }
    });

    flushText();
}

function _buildToolBlock(toolName, args) {
    const tb = document.createElement('div');
    tb.className = 'tool-block';
    tb.dataset.toolName = toolName;
    tb.innerHTML = `
        <div class="tool-header" onclick="this.nextElementSibling.classList.toggle('open')">
            <div class="tool-title">
                <svg viewBox="0 0 24 24" fill="none" class="icon" style="width:14px;height:14px;"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" stroke="currentColor" stroke-width="2"/></svg>
                <span class="name">${toolName}</span>
            </div>
            <div class="tool-status"><svg class="status-icon status-success" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg></div>
        </div>
        <div class="tool-body">
            <div class="tool-args">${JSON.stringify(args || {}, null, 2)}</div>
            <div class="tool-result"></div>
        </div>
    `;
    return tb;
}

function _roleClass(role, label) {
    if (label?.toLowerCase().includes('coordinator')) return 'role-coordinator_agent';
    if (role === 'user') return 'role-user';
    return 'role-agent';
}

function _labelFromRole(role, roleId, instanceId) {
    if (role === 'user') return 'System';
    if (roleId === 'coordinator_agent') return 'Coordinator';
    if (roleId) return roleId;
    return instanceId ? instanceId.slice(0, 8) : 'Agent';
}

function _scrollBottom(container) {
    if (container) container.scrollTop = container.scrollHeight;
}

function _findLatestToolBlock(contentEl, toolName) {
    const blocks = contentEl.querySelectorAll(`.tool-block[data-tool-name="${toolName}"]`);
    return blocks.length > 0 ? blocks[blocks.length - 1] : null;
}
