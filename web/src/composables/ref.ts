import type { MaybeRefOrGetter, Ref } from "vue";
import { extendRef, toRef } from "@vueuse/core";
import { ref } from "vue";

/**
 * 可重置的引用类型
 * 提供重置功能，将引用值恢复到初始状态。
 */
export interface ResetRef<T> extends Ref<T> {
  /**
   * 重置
   * @returns
   */
  $reset: () => Promise<void>;
  /**
   * 获取原始值
   */
  raw: T;
}

export function resetRef<T>(initValue: MaybeRefOrGetter<T>): ResetRef<T> {
  const initRef = toRef(initValue);

  const fn = () => {
    const value = initRef.value;
    return (typeof value === "object" ? { ...value } : value) as T;
  };

  const state = ref<T>(fn()) as Ref<T>;

  return extendRef(state, {
    async $reset() {
      state.value = fn();
    },
    get raw() {
      return fn();
    }
  });
}
