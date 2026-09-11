const CSRF_COOKIE_NAME = "csrftoken";

/**
 * Value of Django's CSRF cookie, or "" when absent.
 *
 * Parses cookie by cookie and compares the name exactly: a substring match
 * (the old `/csrftoken=(...)/` regex) also hit a cookie merely *ending* in
 * "csrftoken" - another app on the same host, or a parent-domain cookie - and
 * when the browser listed that one first, every write failed with 403.
 */
export function getCsrf(): string {
    for (const part of document.cookie.split("; ")) {
        const eq = part.indexOf("=");
        if (eq !== -1 && part.slice(0, eq) === CSRF_COOKIE_NAME) {
            return decodeURIComponent(part.slice(eq + 1));
        }
    }
    return "";
}
