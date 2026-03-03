/**
 * components/rounds/navigator.js
 * Floating round navigator rendering and active-state sync.
 */
import { els } from '../../utils/dom.js';
import { esc } from './utils.js';

let navRounds = [];
let navActiveRunId = null;
let navOnSelectRound = null;

export function renderRoundNavigator(rounds, onSelectRound) {
    navRounds = Array.isArray(rounds) ? rounds : [];
    navOnSelectRound = onSelectRound;

    let nav = document.getElementById('round-nav-float');
    if (!nav) {
        nav = document.createElement('div');
        nav.id = 'round-nav-float';
        nav.className = 'round-nav-float';
        const chatContainer = document.querySelector('.chat-container');
        if (chatContainer) chatContainer.appendChild(nav);
    }

    if (navRounds.length === 0) {
        nav.style.display = 'none';
        nav.innerHTML = '';
        if (els.workflowPanel) els.workflowPanel.style.display = 'none';
        if (els.workflowCollapsed) els.workflowCollapsed.style.display = 'none';
        return;
    }

    renderNavigatorDom(nav);
}

export function setActiveRoundNav(runId) {
    navActiveRunId = runId || null;
    const nav = document.getElementById('round-nav-float');
    if (!nav || navRounds.length === 0) return;

    nav.querySelectorAll('.round-nav-item').forEach(el => {
        el.classList.toggle('active', el.dataset.runId === runId);
    });
    const active = nav.querySelector('.round-nav-item.active');
    if (active) {
        active.scrollIntoView({ block: 'nearest' });
    }
}

function renderNavigatorDom(nav) {
    nav.style.display = 'flex';
    nav.innerHTML = `
        <div class="round-nav-title">Rounds</div>
        <div class="round-nav-list"></div>
    `;

    const list = nav.querySelector('.round-nav-list');
    navRounds.forEach((round, idx) => {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'round-nav-item';
        item.dataset.runId = round.run_id;
        if (navActiveRunId && navActiveRunId === round.run_id) {
            item.classList.add('active');
        }
        item.innerHTML = `
            <span class="idx">${idx + 1}</span>
            <span class="txt">${esc(round.intent || 'No intent')}</span>
        `;
        item.onclick = () => {
            navActiveRunId = round.run_id;
            setActiveRoundNav(round.run_id);
            if (navOnSelectRound) navOnSelectRound(round);
        };
        list.appendChild(item);
    });
}
