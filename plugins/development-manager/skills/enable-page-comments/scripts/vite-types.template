// Types for `.page-comments/vite.mjs`, written by development-manager's
// enable-page-comments. Without them a vite.config.ts that type-checks
// (`tsc --noEmit`) stops on TS7016, "Could not find a declaration file".
// They name no Vite types, so they need nothing from node_modules.
// Remove them with the enable script's --undo.
export interface PageCommentsVitePlugin {
  name: string;
  apply?: "serve" | "build";
}

export default function pageComments(
  options?: Record<string, unknown>,
): PageCommentsVitePlugin | Promise<PageCommentsVitePlugin>;
