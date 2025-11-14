declare namespace NodeJS {
  interface ProcessEnv {
    [key: string]: string | undefined;
  }

  interface Process {
    env: ProcessEnv;
  }
}

declare var process: NodeJS.Process;

declare module "fs" {
  const fs: any;
  export default fs;
}

declare module "path" {
  const path: any;
  export default path;
}
