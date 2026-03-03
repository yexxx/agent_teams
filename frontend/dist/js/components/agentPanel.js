/**
 * components/agentPanel.js
 * Backward-compatible facade. New implementation lives under ./agentPanel/.
 */
export {
    openAgentPanel,
    closeAgentPanel,
    clearAllPanels,
    loadAgentHistory,
    getPanelScrollContainer,
    showGateCard,
    removeGateCard,
    setRoundPendingApprovals,
    getActiveInstanceId,
    getActiveRoundRunId,
} from './agentPanel/index.js';
