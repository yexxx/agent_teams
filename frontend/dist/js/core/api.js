/**
 * core/api.js
 * Backward-compatible facade. New implementation lives under ./api/.
 */
export {
    fetchSessions,
    startNewSession,
    fetchSessionHistory,
    fetchSessionWorkflows,
    fetchSessionRounds,
    fetchSessionAgents,
    fetchAgentMessages,
    sendUserPrompt,
    resolveGate,
    resolveToolApproval,
    dispatchHumanTask,
    injectMessage,
    deleteSession,
    fetchConfigStatus,
    fetchModelConfig,
    fetchModelProfiles,
    saveModelProfile,
    deleteModelProfile,
    saveModelConfig,
    reloadModelConfig,
    reloadMcpConfig,
    reloadSkillsConfig,
} from './api/index.js';
