/**
 * app/index.js
 * Root app orchestration.
 */
import { initApp } from './bootstrap.js';
import { handleSend } from './prompt.js';
import { bindGlobalSelectSession, selectSession } from './session.js';

export { selectSession } from './session.js';

export async function startApp() {
    bindGlobalSelectSession();
    await initApp(selectSession, handleSend);
}
