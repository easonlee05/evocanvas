/**
 * @file quoteSelection.js
 * @description 文本引用与选择的辅助函数库。支持规范化被选文本、生成引用草稿、追加草稿引用项、以及构造向后端发送的带有引用片段的 Payload 载荷。
 */

/**
 * 规范化文本，将其中的多余空白字符替换成单个空格并去除首尾空白
 * @param {string} text - 原始文本
 * @returns {string} 规范化后的文本
 */
function normalizeText(text) {
  return String(text || '').replace(/\s+/g, ' ').trim();
}

/**
 * 截断引用文本，在超过指定最大长度时追加省略号
 * @param {string} text - 待截断文本
 * @param {number} [maxLength=150] - 最大长度
 * @returns {string} 截断后的文本
 */
function truncateQuoteText(text, maxLength = 150) {
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength)}…`;
}

/**
 * 根据引用的条目总数，动态计算 Tooltip 中每个文本片段的允许字数预算
 * @param {number} itemCount - 条目总数
 * @returns {number} 允许的字数预算
 */
function getTooltipTextBudget(itemCount) {
  if (itemCount <= 1) return 150;
  const dynamicBudget = Math.floor(220 / itemCount);
  return Math.max(48, Math.min(150, dynamicBudget));
}

/**
 * 根据引用的条目总数，动态返回 CSS 中 `-webkit-line-clamp` 属性的行数限制数值
 * @param {number} itemCount - 引用条目数
 * @returns {number} 行数限制
 */
export function getQuoteTooltipLineClamp(itemCount) {
  if (itemCount <= 1) return 5;
  if (itemCount === 2) return 3;
  return 2;
}

/**
 * 构造单个引用的草稿对象
 * @param {Object} params
 * @param {'message'|'editor'} [params.sourceType='message'] - 引用源类型
 * @param {string} [params.sourceId='unknown'] - 引用源 ID
 * @param {string} [params.sourceLabel='未知来源'] - 引用源标签名称
 * @param {string} params.text - 被引用的原始文本片段
 * @returns {Object} 格式化的引用草稿对象
 */
export function buildQuoteDraft({ sourceType, sourceId, sourceLabel, text }) {
  return {
    sourceType: sourceType || 'message',
    sourceId: sourceId || 'unknown',
    sourceLabel: sourceLabel || '未知来源',
    text: normalizeText(text),
  };
}

/**
 * 将新的引用条目追加至现有的引用草稿中（去重合并逻辑）
 * @param {Object|null} currentDraft - 当前的引用草稿对象，含 items 列表
 * @param {Object} nextItem - 待追加的新引用条目
 * @returns {Object|null} 追加合并后的新引用草稿对象，若为空则返回 null
 */
export function appendQuoteDraft(currentDraft, nextItem) {
  if (!nextItem || !nextItem.text) {
    return currentDraft || null;
  }

  const items = currentDraft?.items ? [...currentDraft.items] : [];
  const exists = items.some(
    (item) =>
      item.sourceType === nextItem.sourceType &&
      item.sourceId === nextItem.sourceId &&
      item.text === nextItem.text
  );

  if (!exists) {
    items.push(nextItem);
  }

  if (!items.length) {
    return null;
  }

  return {
    items,
    summary: summarizeQuoteDraft({ items }),
  };
}

/**
 * 生成引用草稿的简短摘要文字
 * @param {Object} draft - 引用草稿对象
 * @returns {string} 摘要文本（如："2 个已选文本片段"）
 */
export function summarizeQuoteDraft(draft) {
  const count = draft?.items?.length || 0;
  return `${count} 个已选文本片段`;
}

/**
 * 清空引用草稿，直接返回 null
 * @returns {null}
 */
export function clearQuoteDraft() {
  return null;
}

/**
 * 构造发送给后端的裁决与决策 Payload 对象，将驼峰式属性映射为后端的下划线式字段
 * @param {string} decision - 用户填写的决策/指令说明
 * @param {Object|null} quoteDraft - 包含被引用内容的一组草稿数据
 * @returns {Object} 后端期待的数据格式负载
 */
export function buildDecisionPayload(decision, quoteDraft) {
  const payload = { decision };
  if (quoteDraft?.items?.length) {
    payload.quoted_selections = quoteDraft.items.map((item) => ({
      source_type: item.sourceType,
      source_id: item.sourceId,
      source_label: item.sourceLabel,
      text: item.text,
    }));
  }
  return payload;
}

/**
 * 构造用于展示在悬浮 Tooltip 上的文本行数组，交替存放标题与截断后的引用内容
 * @param {Object} quoteDraft - 引用草稿对象
 * @returns {Array<string>} 供渲染消费的一维字符串数组
 */
export function buildQuoteTooltipLines(quoteDraft) {
  const items = quoteDraft?.items || [];
  const textBudget = getTooltipTextBudget(items.length);
  return items.flatMap((item) => [item.sourceLabel, truncateQuoteText(item.text, textBudget)]);
}

