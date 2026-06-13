/**
 * @file workspaceSession.js
 * @description 管理工作台会话状态的辅助工具函数，控制打开页面时的自动化交互行为。
 */

/**
 * 决定是否应当在特定事件触发时自动展开/打开右侧文档区。
 * @param {Object} params
 * @param {string} params.reason - 触发判断的原因（例如 'writer-event' 代表 Writer Agent 开始写入文档）
 * @param {boolean} params.hasUserOpenedDoc - 用户在此之前是否曾主动打开过文档。用于遵循用户原有的界面布局意愿。
 * @returns {boolean} 是否自动打开
 */
export function shouldAutoOpenDocument({ reason, hasUserOpenedDoc }) {
  if (reason === 'writer-event') {
    // 仅在用户之前主动打开过文档的前提下，由于 Writer 写入事件自动打开，以防止打扰用户
    return Boolean(hasUserOpenedDoc);
  }
  return false;
}

/**
 * 决定打开工作台页面时，是否自动为未启动的任务包发起运行请求。
 * 当前设计返回 false，需要由用户点击“继续执行”等按钮进行手动审核触发。
 * @returns {boolean} 是否自动运行
 */
export function shouldAutoRunTaskOnOpen() {
  return false;
}

