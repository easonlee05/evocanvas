/**
 * @file throttle.js
 * @description EvoCanvas 画布 rAF 合帧工具。参考 Excalidraw 的 throttleRAF：
 * 同一帧内多次调用只保留最后一次参数，并只调度一个 requestAnimationFrame 回调，
 * 用于把高频 wheel / pointermove 事件合并为每帧一次重渲染。
 *
 * 当前使用状态：Canvas.jsx 的滚轮和平移用内联 rAF（因需累积 delta / ref 存位置），
 * 本工具暂未被业务代码直接调用，保留供未来需要"闭包式合帧"的交互复用。
 */

/**
 * 创建一个 rAF 合帧的节流函数。
 * 返回的 throttle 函数可多次调用，同帧内多次调用只保留最后一次参数，
 * 每帧最多触发一次 executor。executor 通过参数接管最新入参。
 *
 * throttle(fn) 的入参约定：外部传入的是一个"携带最新参数"的闭包，
 * 例如 () => setTransform(computeLatest())。
 */
export function createThrottleRAF() {
  let ticking = false;
  let latestUpdate = null;

  const throttle = (update) => {
    latestUpdate = update;
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      ticking = false;
      const pending = latestUpdate;
      latestUpdate = null;
      if (pending) pending();
    });
  };

  throttle.cancel = () => {
    latestUpdate = null;
  };

  return throttle;
}