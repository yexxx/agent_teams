/**
 * core/api/request.js
 * Shared HTTP request helper for JSON endpoints.
 */

export async function requestJson(url, options, errorMessage) {
    const res = await fetch(url, options);
    if (!res.ok) {
        let detail = errorMessage;
        try {
            const payload = await res.json();
            if (typeof payload?.detail === 'string' && payload.detail) {
                detail = payload.detail;
            }
        } catch (_) {
            // keep fallback message
        }
        throw new Error(detail);
    }
    return res.json();
}
