import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { loadSkills, NodeExecutionEnv, type Skill } from "@earendil-works/pi-agent-core/node";
import { BACKGROUND_CONTEXT } from "@earendil-works/chord/context";

/** 产品方法是仓库内建的 Pi Skill，不是运行时代码中的 Prompt 正文。 */
export interface ProductMethod {
  skill: Skill;
  version: string;
  content_hash: string;
  ref: string;
  raw: Uint8Array;
}

const SKILL_DIR = join(dirname(fileURLToPath(import.meta.url)), "../../skills");
const METHOD_NAMES = ["scenario-shaping", "decision-challenge"] as const;
export type ProductMethodName = typeof METHOD_NAMES[number];

export function productMethodPath(name: ProductMethodName): string {
  return join(SKILL_DIR, name, "SKILL.md");
}

/** 每轮重新由 Pi 原生 Loader 装载，轮内使用同一份快照。 */
export async function loadProductMethods(): Promise<Map<ProductMethodName, ProductMethod>> {
  const env = new NodeExecutionEnv({ cwd: SKILL_DIR });
  const loaded = await loadSkills(env, SKILL_DIR, BACKGROUND_CONTEXT);
  for (const diagnostic of loaded.diagnostics) console.warn("Pi Skill Loader:", diagnostic);
  const methods = new Map<ProductMethodName, ProductMethod>();
  for (const skill of loaded.skills) {
    if (!METHOD_NAMES.includes(skill.name as ProductMethodName) || skill.filePath !== productMethodPath(skill.name as ProductMethodName)) continue;
    const version = /^版本：(\d+\.\d+\.\d+)$/m.exec(skill.content)?.[1];
    if (!version) { console.warn(`Pi Skill Loader: ${skill.filePath} 缺少版本声明`); continue; }
    let raw: Buffer;
    try { raw = await readFile(skill.filePath); }
    catch (error) { console.warn(`Pi Skill Loader: ${skill.filePath} 快照读取失败`, error); continue; }
    // Loader 的正文与快照必须是同一版；发布中途替换文件时拒绝冒充已加载版本。
    const normalized = raw.toString("utf8").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    const frontmatterEnd = normalized.startsWith("---") ? normalized.indexOf("\n---", 3) : -1;
    if (frontmatterEnd < 0 || normalized.slice(frontmatterEnd + 4).trim() !== skill.content) {
      console.warn(`Pi Skill Loader: ${skill.filePath} 在装载期间发生变化`);
      continue;
    }
    // 模型读取的是完整 SKILL.md；哈希覆盖 frontmatter 与正文，而不只覆盖 Loader 返回的正文。
    const content_hash = `sha256:${createHash("sha256").update(raw).digest("hex")}`;
    methods.set(skill.name as ProductMethodName, {
      skill, version, content_hash, raw,
      ref: `${skill.name}@${version}#${content_hash}`,
    });
  }
  return methods;
}

/** 只识别当前 User Entry 的明确挑战请求；后续逐轮回复沿用 Session 中已读取的方法。 */
export function explicitlyRequestsDecisionChallenge(text: string): boolean {
  const clauses = text.trim().split(/[。！？\n，,；;]|但是|不过|但/).map(clause => clause.trim()).filter(Boolean);
  const asks = /(?:挑战一下|逐轮挑战|一轮一轮(?:挑战|找问题)|一个问题一个问题(?:来|问)|全面挑战|红队一下|红队分析|找找问题|找出(?:这个|当前|方案的)?问题|red[ -]?team|challenge this)/i;
  for (const clause of clauses.reverse()) {
    if (!asks.test(clause)) continue;
    return !/(?:不要|别|不需要|暂不|先不|无需)[^。！？\n]{0,12}(?:挑战|红队|找问题)/i.test(clause);
  }
  return false;
}
