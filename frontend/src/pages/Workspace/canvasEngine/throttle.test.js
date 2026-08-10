import { describe, it, mock, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { createThrottleRAF } from '../canvasEngine/throttle.js';

function installFakeRAF() {
  let callback = null;
  const originalRAF = globalThis.requestAnimationFrame;
  const originalCAF = globalThis.cancelAnimationFrame;

  globalThis.requestAnimationFrame = (fn) => {
    callback = fn;
    return 1;
  };
  globalThis.cancelAnimationFrame = () => {};

  return {
    flush() {
      const fn = callback;
      callback = null;
      if (fn) fn();
    },
    hasPending() {
      return callback !== null;
    },
    restore() {
      globalThis.requestAnimationFrame = originalRAF;
      globalThis.cancelAnimationFrame = originalCAF;
    },
  };
}

describe('createThrottleRAF', () => {
  afterEach(() => {
    mock.restoreAll();
  });

  it('coalesces multiple calls within one frame into a single execution', () => {
    const raf = installFakeRAF();
    const updates = [];
    const throttle = createThrottleRAF();

    throttle(() => updates.push(1));
    throttle(() => updates.push(2));
    throttle(() => updates.push(3));

    assert.equal(raf.hasPending(), true);
    assert.equal(updates.length, 0, 'no execution happens before the frame');

    raf.flush();
    assert.deepEqual(updates, [3], 'only the latest update runs in the frame');

    raf.restore();
  });

  it('keeps last args across frames and executes once per frame', () => {
    const raf = installFakeRAF();
    const updates = [];
    const throttle = createThrottleRAF();

    throttle(() => updates.push('a'));
    raf.flush();
    throttle(() => updates.push('b'));
    throttle(() => updates.push('c'));
    raf.flush();

    assert.deepEqual(updates, ['a', 'c']);
    raf.restore();
  });

  it('does not schedule a new frame when idle', () => {
    const raf = installFakeRAF();
    const throttle = createThrottleRAF();
    assert.equal(raf.hasPending(), false);
    raf.restore();
  });

  it('cancel drops the pending update', () => {
    const raf = installFakeRAF();
    const updates = [];
    const throttle = createThrottleRAF();

    throttle(() => updates.push('x'));
    throttle.cancel();
    raf.flush();

    assert.deepEqual(updates, []);
    raf.restore();
  });
});