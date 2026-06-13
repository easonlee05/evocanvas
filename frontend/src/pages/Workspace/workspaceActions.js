/**
 * @file workspaceActions.js
 * @description 工作台页面相关的动作逻辑辅助函数，主要用于判断任务状态及界面按钮的文案渲染。
 */

/**
 * 判断是否应当在界面通知栏中显示“继续执行”或运行提示按钮。
 * @param {string} rawStatus - 后端任务的原始运行状态（例如 created, cancelled, waiting_for_user 等）
 * @returns {boolean} 是否应当显示运行按钮
 */
export function shouldShowRunPrompt(rawStatus) {
  return ['created', 'cancelled', 'waiting_for_user'].includes(rawStatus);
}

/**
 * 获取文档控制动作在 Tooltip 或按钮上的提示文案。
 * @param {Object} params
 * @param {boolean} params.done - 任务是否已经完成
 * @returns {string} 按钮文案字面量
 */
export function getDocumentActionLabel({ done }) {
  return done ? '查看文档' : '打开文档';
}

