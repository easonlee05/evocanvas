import { existsSync } from "node:fs";
import { spawn } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// Node 默认不读取 macOS/Linux 系统证书库；本机 HTTPS 代理使用系统 CA 时，
// 不配置这一项会把真实 Provider 请求误报成“模型未返回完整回复”。
// 优先尊重调用方显式配置，再从常见系统 CA 路径中选择存在的文件。
const caCandidates = [
  process.env.NODE_EXTRA_CA_CERTS,
  "/etc/ssl/cert.pem",
  "/etc/ssl/certs/ca-certificates.crt",
  "/etc/pki/tls/certs/ca-bundle.crt",
].filter(Boolean);
const systemCa = caCandidates.find((candidate) => existsSync(candidate));
const env = { ...process.env };
if (!env.NODE_EXTRA_CA_CERTS && systemCa) env.NODE_EXTRA_CA_CERTS = systemCa;
const runtimeRoot = join(dirname(fileURLToPath(import.meta.url)), "..");

const child = spawn(process.execPath, ["dist/server.js", ...process.argv.slice(2)], {
  cwd: runtimeRoot,
  env,
  stdio: "inherit",
});

const forwardSignal = (signal) => child.kill(signal);
process.once("SIGINT", () => forwardSignal("SIGINT"));
process.once("SIGTERM", () => forwardSignal("SIGTERM"));
child.once("error", (error) => {
  console.error(`Pi Runtime 启动失败：${error.message}`);
  process.exitCode = 1;
});
child.once("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exitCode = code ?? 1;
});
