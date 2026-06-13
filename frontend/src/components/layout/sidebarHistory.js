/**
 * @file sidebarHistory.js
 * @description 辅助工具函数，用于将后端按时间分组的对话历史数据（今天、昨天、更早）扁平化，生成易于在 React 中单层循环渲染的列表数据结构。
 */

/**
 * 将分组的对话/任务历史扁平化为一个一维数组。
 * @param {Object} groups - 按时间段分类的任务列表对象
 * @param {Array<Object>} [groups.today=[]] - 今天的任务列表
 * @param {Array<Object>} [groups.yesterday=[]] - 昨天的任务列表
 * @param {Array<Object>} [groups.older=[]] - 更早的任务列表
 * @returns {Array<Object>} 扁平化后的数组。数组元素有两种类型：
 *   - 组标题节点：`{ type: 'group', label: string }`
 *   - 具体数据节点：`{ type: 'item', id: string, label: string, time: string, ... }`
 */
export function flattenConversationGroups({ today = [], yesterday = [], older = [] }) {
  const sections = [
    { label: '今天', items: today },
    { label: '昨天', items: yesterday },
    { label: '更早', items: older },
  ];

  return sections.flatMap(({ label, items }) => {
    // 如果该时间段内没有任何对话历史，则不生成对应的组标题和列表项
    if (!items.length) return [];
    // 将组标题作为数组第一项插入，并将其余具体数据项标记为 type: 'item'
    return [{ type: 'group', label }, ...items.map((item) => ({ type: 'item', ...item }))];
  });
}

