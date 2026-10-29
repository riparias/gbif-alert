const TAG_PALETTE = [
    "#0b7285",
    "#7048e8",
    "#c92a2a",
    "#e67700",
    "#2b8a3e",
    "#1864ab",
    "#a61e4d",
    "#087f5b",
    "#862e9c",
    "#d9480f",
];

// Deterministic color from tag name so the same tag always gets the same color.
export function tagColor(name: string): string {
    let h = 0;
    for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) & 0xffff;
    return TAG_PALETTE[h % TAG_PALETTE.length];
}
