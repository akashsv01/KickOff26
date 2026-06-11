import { existsSync, rmSync } from "node:fs";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const nextDir = join(root, ".next");
const tsBuildInfo = join(root, "tsconfig.tsbuildinfo");

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function removeWithRetry(path, attempts = 5) {
  for (let i = 0; i < attempts; i++) {
    try {
      if (existsSync(path)) {
        rmSync(path, { recursive: true, force: true, maxRetries: 3, retryDelay: 200 });
      }
      return;
    } catch {
      await sleep(400 * (i + 1));
    }
  }
}

await removeWithRetry(nextDir);
await removeWithRetry(tsBuildInfo);

const child = spawn("npx", ["next", "dev"], {
  cwd: root,
  stdio: "inherit",
  shell: true,
});

child.on("exit", (code) => process.exit(code ?? 0));
