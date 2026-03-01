/**
 * components/navbar.js
 * Wires UI toggle controls for the header navigation and sidebar overlays.
 */
import { els } from '../utils/dom.js';

export function setupNavbarBindings() {
    _initSidebarResize();
    _initRightRailResize();

    if (els.sidebarToggleBtn) {
        els.sidebarToggleBtn.onclick = () => {
            const collapsed = els.sidebar.classList.toggle('collapsed');
            if (collapsed) {
                localStorage.setItem('agent_teams_sidebar_collapsed', '1');
            } else {
                localStorage.setItem('agent_teams_sidebar_collapsed', '0');
            }
        };
    }

    const railInspector = document.getElementById('rail-inspector');
    const toggleInspectorBtn = document.getElementById('toggle-inspector');
    if (toggleInspectorBtn && railInspector) {
        const header = railInspector.querySelector('.inspector-header');
        const iconPath = toggleInspectorBtn.querySelector('path');
        
        const toggle = () => {
            const isExpanded = railInspector.classList.toggle('expanded');
            if (iconPath) {
                if (isExpanded) {
                    iconPath.setAttribute('d', 'M19 9l-7 7-7-7');
                } else {
                    iconPath.setAttribute('d', 'M7 13l5 5 5-5M7 6l5 5 5-5');
                }
            }
        };
        
        if (header) header.onclick = toggle;
        toggleInspectorBtn.onclick = (e) => {
            e.stopPropagation();
            toggle();
        };
    }

    if (els.themeToggleBtn) {
        els.themeToggleBtn.onclick = () => {
            document.body.classList.toggle('light-theme');
            const isLight = document.body.classList.contains('light-theme');
            localStorage.setItem('agent_teams_theme', isLight ? 'light' : 'dark');
        };

        // Load theme from localStorage on start
        const savedTheme = localStorage.getItem('agent_teams_theme');
        if (savedTheme === 'light') {
            document.body.classList.add('light-theme');
        }
    }
}

function _initSidebarResize() {
    if (!els.sidebar) return;

    const savedWidth = localStorage.getItem('agent_teams_sidebar_width');
    let initialWidth = 280;
    if (savedWidth && /^\d+$/.test(savedWidth)) {
        const px = Number(savedWidth);
        if (px >= 180) {
            els.sidebar.style.width = `${px}px`;
            els.sidebar.style.setProperty('--sidebar-width', `${px}px`);
            initialWidth = px;
        }
    }
    document.documentElement.style.setProperty('--sidebar-width', `${initialWidth}px`);

    const collapsed = localStorage.getItem('agent_teams_sidebar_collapsed');
    if (collapsed === '1') {
        els.sidebar.classList.add('collapsed');
    }

    if (!els.sidebarResizer) return;
    let dragging = false;

    const onMove = (e) => {
        if (!dragging || !els.sidebar || els.sidebar.classList.contains('collapsed')) return;
        const rightRail = document.getElementById('right-rail');
        const rightRailWidth = rightRail ? rightRail.offsetWidth : 280;
        const maxWidth = window.innerWidth - rightRailWidth - 100;
        const next = Math.max(180, Math.min(maxWidth, e.clientX));
        els.sidebar.style.width = `${next}px`;
        els.sidebar.style.setProperty('--sidebar-width', `${next}px`);
        document.documentElement.style.setProperty('--sidebar-width', `${next}px`);
        localStorage.setItem('agent_teams_sidebar_width', String(next));
    };

    const onUp = () => {
        if (!dragging) return;
        dragging = false;
        els.sidebarResizer.classList.remove('dragging');
        document.body.style.userSelect = '';
        window.removeEventListener('mousemove', onMove);
        window.removeEventListener('mouseup', onUp);
    };

    els.sidebarResizer.addEventListener('mousedown', (e) => {
        if (els.sidebar.classList.contains('collapsed')) return;
        dragging = true;
        els.sidebarResizer.classList.add('dragging');
        document.body.style.userSelect = 'none';
        window.addEventListener('mousemove', onMove);
        window.addEventListener('mouseup', onUp);
        e.preventDefault();
    });
}

function _initRightRailResize() {
    const rightRail = document.getElementById('right-rail');
    const rightRailResizer = document.getElementById('right-rail-resizer');
    if (!rightRail || !rightRailResizer) return;

    const savedWidth = localStorage.getItem('agent_teams_right_rail_width');
    let initialWidth = 280;
    if (savedWidth && /^\d+$/.test(savedWidth)) {
        const px = Number(savedWidth);
        if (px >= 180) {
            initialWidth = px;
        }
    }
    rightRail.style.width = `${initialWidth}px`;
    rightRail.style.setProperty('--right-rail-width', `${initialWidth}px`);
    document.documentElement.style.setProperty('--right-rail-width', `${initialWidth}px`);

    let dragging = false;

    const onMove = (e) => {
        if (!dragging) return;
        const sidebar = document.querySelector('.sidebar');
        const sidebarWidth = parseInt(sidebar?.style?.width) || 280;
        const windowWidth = window.innerWidth;
        const minWidth = 180;
        const maxWidth = windowWidth - sidebarWidth - 100;
        const next = Math.max(minWidth, Math.min(maxWidth, windowWidth - e.clientX));
        rightRail.style.width = `${next}px`;
        rightRail.style.setProperty('--right-rail-width', `${next}px`);
        document.documentElement.style.setProperty('--right-rail-width', `${next}px`);
        localStorage.setItem('agent_teams_right_rail_width', String(next));
    };

    const onUp = () => {
        if (!dragging) return;
        dragging = false;
        rightRailResizer.classList.remove('dragging');
        document.body.style.userSelect = '';
        window.removeEventListener('mousemove', onMove);
        window.removeEventListener('mouseup', onUp);
    };

    rightRailResizer.addEventListener('mousedown', (e) => {
        dragging = true;
        rightRailResizer.classList.add('dragging');
        document.body.style.userSelect = 'none';
        window.addEventListener('mousemove', onMove);
        window.addEventListener('mouseup', onUp);
        e.preventDefault();
    });
}
