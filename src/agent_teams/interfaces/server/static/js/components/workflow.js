/**
 * components/workflow.js
 * Renders the Execution Graph DAG.
 */
import { sysLog } from '../utils/logger.js';
import { state } from '../core/state.js';
import { fetchSessionWorkflows } from '../core/api.js';
import { openAgentPanel } from './agentPanel.js';

export let currentWorkflows = [];

export async function loadSessionWorkflows(sessionId) {
    try {
        const workflows = await fetchSessionWorkflows(sessionId);
        currentWorkflows = workflows || [];
        renderNativeDAG(currentWorkflows.length > 0 ? currentWorkflows[currentWorkflows.length - 1] : null);
    } catch (e) {
        console.error('Failed loading workflows', e);
    }
}

export function updateDagActiveNode() {
    document.querySelectorAll('.dag-node').forEach(node => {
        if (node.dataset.role === state.activeAgentRoleId) {
            node.classList.add('running');
        } else {
            node.classList.remove('running');
        }
    });
}

export function renderNativeDAG(workflow) {
    const canvas = document.getElementById('workflow-canvas');
    if (!canvas) return;
    canvas.innerHTML = '';

    if (!workflow?.tasks || Object.keys(workflow.tasks).length === 0) {
        canvas.innerHTML = '<div class="panel-empty">No workflow graph.</div>';
        return;
    }

    const container = document.createElement('div');
    container.className = 'dag-container';

    const tasks = workflow.tasks;
    const taskIds = Object.keys(tasks);
    const nodeLevels = _computeNodeLevels(tasks, taskIds);
    const maxLevel = Math.max(...Object.values(nodeLevels));

    const layers = [];
    for (let level = 0; level <= maxLevel; level += 1) {
        const layerNodes = [];
        for (const t of taskIds) {
            if (nodeLevels[t] !== level) continue;
            layerNodes.push({
                id: t,
                title: t,
                role: tasks[t].role_id || t,
                icon: 'A',
                deps: tasks[t].depends_on || [],
            });
        }
        if (layerNodes.length > 0) layers.push(layerNodes);
    }

    const nodeElements = [];
    layers.forEach(layer => {
        const col = document.createElement('div');
        col.className = 'dag-layer';

        layer.forEach(node => {
            const el = document.createElement('div');
            el.className = 'dag-node';
            el.id = `node-${node.id}`;
            el.dataset.role = node.role;

            const instanceId = _instanceForRole(node.role);
            if (instanceId) el.dataset.instanceId = instanceId;

            if (state.activeAgentRoleId === node.role) el.classList.add('running');

            el.innerHTML = `
                <div class="node-icon">${node.icon}</div>
                <div class="node-title">${node.title}</div>
                <div class="node-role">${node.role}</div>
            `;

            el.onclick = () => {
                const iid = el.dataset.instanceId || instanceId;
                if (iid) {
                    openAgentPanel(iid, node.role);
                } else {
                    sysLog(`No instance mapped for role: ${node.role}`, 'log-info');
                }
            };

            nodeElements.push(el);
            col.appendChild(el);
        });
        container.appendChild(col);
    });

    canvas.appendChild(container);
    _compactDagForCanvas(canvas, container, nodeElements);

    const svg = _createEdgeSvg();
    container.appendChild(svg);

    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            _drawEdges(svg, container, layers);
        });
    });
}

function _computeNodeLevels(tasks, taskIds) {
    const nodeLevels = {};
    taskIds.forEach(t => {
        nodeLevels[t] = 0;
    });

    let changed = true;
    let guard = 0;
    while (changed && guard < taskIds.length * 4) {
        changed = false;
        guard += 1;
        for (const t of taskIds) {
            const deps = tasks[t].depends_on || [];
            if (deps.length === 0) {
                if (nodeLevels[t] !== 0) {
                    nodeLevels[t] = 0;
                    changed = true;
                }
                continue;
            }
            let maxDep = 0;
            deps.forEach(d => {
                if (nodeLevels[d] !== undefined) {
                    maxDep = Math.max(maxDep, nodeLevels[d]);
                }
            });
            const newLevel = maxDep + 1;
            if (nodeLevels[t] !== newLevel) {
                nodeLevels[t] = newLevel;
                changed = true;
            }
        }
    }

    return nodeLevels;
}

function _compactDagForCanvas(canvas, container, nodeEls) {
    const isFloating = !!canvas.closest('.workflow-panel-floating');
    if (!isFloating) {
        _resetDagCompaction(canvas, container, nodeEls);
        return;
    }

    const maxPass = 3;
    for (let pass = 0; pass < maxPass; pass += 1) {
        const avail = Math.max(120, canvas.clientWidth - 8);
        const natural = Math.max(1, container.scrollWidth);
        if (natural <= avail) break;

        const ratio = avail / natural;
        const density = Math.max(0.56, Math.min(1, ratio * (pass === 0 ? 1.0 : 0.95)));
        const gap = Math.max(8, Math.round(64 * density));
        const padX = Math.max(8, Math.round(28 * density));
        const padY = Math.max(8, Math.round(20 * density));
        const nodeMin = Math.max(68, Math.round(130 * density));
        const nodePadY = Math.max(5, Math.round(10 * density));
        const nodePadX = Math.max(7, Math.round(14 * density));
        const titleSize = Math.max(10, Math.round(13 * density));
        const roleSize = Math.max(9, Math.round(11 * density));
        const iconSize = Math.max(12, Math.round(18 * density));

        container.style.gap = `${gap}px`;
        container.style.padding = `${padY}px ${padX}px`;

        nodeEls.forEach(el => {
            el.style.minWidth = `${nodeMin}px`;
            el.style.padding = `${nodePadY}px ${nodePadX}px`;
            const title = el.querySelector('.node-title');
            if (title) title.style.fontSize = `${titleSize}px`;
            const role = el.querySelector('.node-role');
            if (role) role.style.fontSize = `${roleSize}px`;
            const icon = el.querySelector('.node-icon');
            if (icon) icon.style.fontSize = `${iconSize}px`;
        });
    }

    const hasOverflow = container.scrollWidth > canvas.clientWidth + 2;
    canvas.style.overflowX = hasOverflow ? 'auto' : 'hidden';
}

function _resetDagCompaction(canvas, container, nodeEls) {
    canvas.style.overflowX = 'auto';
    container.style.gap = '';
    container.style.padding = '';
    nodeEls.forEach(el => {
        el.style.minWidth = '';
        el.style.padding = '';
        const title = el.querySelector('.node-title');
        if (title) title.style.fontSize = '';
        const role = el.querySelector('.node-role');
        if (role) role.style.fontSize = '';
        const icon = el.querySelector('.node-icon');
        if (icon) icon.style.fontSize = '';
    });
}

function _createEdgeSvg() {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'dag-edges');
    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
    marker.setAttribute('id', 'arrow');
    marker.setAttribute('viewBox', '0 0 10 10');
    marker.setAttribute('refX', '8');
    marker.setAttribute('refY', '5');
    marker.setAttribute('markerWidth', '6');
    marker.setAttribute('markerHeight', '6');
    marker.setAttribute('orient', 'auto-start-reverse');
    const pathArrow = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    pathArrow.setAttribute('d', 'M 0 0 L 10 5 L 0 10 z');
    pathArrow.setAttribute('fill', 'var(--border-color)');
    marker.appendChild(pathArrow);
    defs.appendChild(marker);
    svg.appendChild(defs);
    return svg;
}

function _drawEdges(svg, container, layers) {
    while (svg.childNodes.length > 1) {
        svg.removeChild(svg.lastChild);
    }

    const contRect = container.getBoundingClientRect();
    layers.forEach(layer => {
        layer.forEach(node => {
            const sources = node.deps || [];
            if (!sources.length) return;
            sources.forEach(srcId => {
                const srcEl = document.getElementById(`node-${srcId}`);
                const dstEl = document.getElementById(`node-${node.id}`);
                if (!srcEl || !dstEl) return;

                const srcRect = srcEl.getBoundingClientRect();
                const dstRect = dstEl.getBoundingClientRect();
                const startX = srcRect.right - contRect.left;
                const startY = srcRect.top + srcRect.height / 2 - contRect.top;
                const endX = dstRect.left - contRect.left;
                const endY = dstRect.top + dstRect.height / 2 - contRect.top;
                const curve = Math.abs(endX - startX) * 0.5;
                const d = `M ${startX} ${startY} C ${startX + curve} ${startY}, ${endX - curve} ${endY}, ${endX} ${endY}`;
                const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                path.setAttribute('d', d);
                path.setAttribute('class', 'dag-edge-path');
                path.setAttribute('marker-end', 'url(#arrow)');
                svg.appendChild(path);
            });
        });
    });
}

function _instanceForRole(roleId) {
    if (!state.instanceRoleMap) return null;
    for (const [iid, rid] of Object.entries(state.instanceRoleMap)) {
        if (rid === roleId) return iid;
    }
    return null;
}
