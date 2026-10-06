// HTML for PrimeVue tooltips that carry an image (v-tooltip with escape: false).
// Every interpolated value goes through escapeHtml.

export function escapeHtml(s: string): string {
    return s
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

// The image, a caption saying what it shows, and its credit ("" for none).
// onerror hides all three for a dead link instead of showing a broken-image
// icon.
export function imageTooltipHtml(img: {
    url: string;
    alt: string;
    caption: string;
    credit: string;
}): string {
    const credit = img.credit
        ? `<div class="species-tooltip-credit">${escapeHtml(img.credit)}</div>`
        : "";
    return (
        `<div><img src="${escapeHtml(img.url)}" alt="${escapeHtml(img.alt)}" ` +
        `class="species-tooltip-img" onerror="this.parentElement.style.display='none'" />` +
        `<div class="species-tooltip-caption">${escapeHtml(img.caption)}</div>${credit}</div>`
    );
}
