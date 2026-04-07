export function getCsrf(): string {
    return (document.cookie.match(/csrftoken=([^;]+)/) ?? [])[1] ?? "";
}
