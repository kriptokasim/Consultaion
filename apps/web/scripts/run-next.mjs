import { mkdirSync } from "node:fs";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const tempDir = fileURLToPath(new URL("../.tmp", import.meta.url));
mkdirSync(tempDir, { recursive: true });

const mode = process.argv[2] || "build";
const nextArgs = mode === "dev" ? ["dev", "-p", "3000"] : ["build"];
const nextBin = fileURLToPath(
  new URL("../node_modules/next/dist/bin/next", import.meta.url),
);
const child = spawn(process.execPath, [nextBin, ...nextArgs], {
  cwd: root,
  env: {
    ...process.env,
    TMPDIR: tempDir,
    ...(process.platform === "win32" ? { NEXT_STANDALONE: "false" } : {}),
    ...(mode === "analyze" ? { ANALYZE: "true" } : {}),
  },
  stdio: "inherit",
});

child.on("error", (error) => {
  console.error(error);
  process.exitCode = 1;
});
child.on("exit", (code, signal) => {
  process.exitCode = code ?? (signal ? 1 : 0);
});
