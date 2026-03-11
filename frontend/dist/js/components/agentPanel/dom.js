/**
 * components/agentPanel/dom.js
 * DOM helpers for the session-level subagent panel.
 */
export function getDrawer() {
    return document.getElementById('agent-drawer');
}

export function getSubagentCard() {
    return document.querySelector('.rail-subagent-card');
}

export function openDrawerUi() {
    const drawer = getDrawer();
    if (drawer) drawer.classList.add('open');
    const card = getSubagentCard();
    if (card) card.classList.add('open');
}

export function closeDrawerUi() {
    const drawer = getDrawer();
    if (drawer) drawer.classList.remove('open');
    const card = getSubagentCard();
    if (card) card.classList.remove('open');
}
