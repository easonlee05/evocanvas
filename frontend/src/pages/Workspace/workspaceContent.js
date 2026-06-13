/**
 * @file workspaceContent.js
 * @description 工作台文本内容清洗辅助逻辑，统一过滤内部思考标签与流式光标字符。
 */

/**
 * 清洗工作台要展示的 markdown / 文本内容。
 * @param {string} text - 原始文本内容
 * @returns {string} 清洗后的可展示文本
 */
export function sanitizeWorkspaceContent(text) {
  if (!text) return '';
  return String(text)
    .replace(/<think>[\s\S]*?(?:<\/think>|$)/gi, '')
    .replace(/▋/g, '')
    .trim();
}
