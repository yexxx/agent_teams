/**
 * core/api/request.js
 * Shared HTTP request helper for JSON endpoints.
 */

export async function requestJson(url, options, errorMessage) {
    const res = await fetch(url, options);
    if (!res.ok) throw new Error(errorMessage);
    return res.json();
}
