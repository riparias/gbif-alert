import type { MenuItem } from "primevue/menuitem";

/**
 * A navbar entry: PrimeVue's MenuItem plus our red "there is something unseen"
 * dot. PrimeVue's MenuItem has an open index signature, so extra fields are
 * allowed.
 *
 * This lives outside NavBar.vue because MobileNavDrawer renders the same items
 * in a different shape, and both need the type.
 */
export interface NavItem extends MenuItem {
    showDot?: boolean;
}
