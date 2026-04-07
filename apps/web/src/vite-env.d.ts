/// <reference types="vite/client" />

declare module "*.css" {
  const content: string;
  export default content;
}

declare module "@ui5/webcomponents-base/dist/config/Theme.js" {
  export function setTheme(theme: string): Promise<void>;
  export function getTheme(): string;
}
