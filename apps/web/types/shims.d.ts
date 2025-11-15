declare namespace NodeJS {
  interface ProcessEnv {
    [key: string]: string | undefined;
  }
  interface Process {
    env: ProcessEnv;
  }
}

declare var process: NodeJS.Process;
declare const __dirname: string;

declare module 'fs';
declare module 'path';
declare module 'os';

interface Window {
  Sentry?: {
    init: (config: Record<string, any>) => void;
    captureException: (error: unknown) => void;
  };
}
