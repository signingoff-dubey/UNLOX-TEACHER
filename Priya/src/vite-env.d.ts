/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend origin, e.g. http://192.168.1.20:8000. Empty = same origin (or the Vite dev proxy). */
  readonly VITE_API_BASE?: string;
}
