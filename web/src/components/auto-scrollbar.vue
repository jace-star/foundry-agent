<script lang="tsx">
import type { PropType } from "vue";
import { useResizeObserver } from "@vueuse/core";
import {
  computed,
  defineComponent,
  nextTick,
  onMounted,
  ref,
  renderSlot,
} from "vue";

export default defineComponent({
  name: "AutoScrollbar",
  props: {
    contentClass: {
      type: [String, Array] as PropType<string | string[]>,
      default: "",
    },
    backBtn: {
      type: Boolean as PropType<boolean>,
      default: true,
    },
  },
  emits: ["update:auto", "reachTop"],
  setup(props, { emit, slots, expose }) {
    const isAutoScroll = ref(true);
    const containerRef = ref<HTMLElement>();
    const contentRef = ref<HTMLElement>();
    const isShowScrollbar = ref(false);
    const topThreshold = 32;
    const hasReachedTop = ref(false);
    let isProgrammaticScroll = false;

    const backThreshold = computed(() => {
      const rootFontSize = Number.parseFloat(
        window.getComputedStyle(document.documentElement).fontSize,
      );
      return rootFontSize * 2 + 10;
    });

    onMounted(() => {
      if (!containerRef.value) {
        return;
      }

      useResizeObserver(contentRef.value, () => {
        if (isAutoScroll.value) {
          scrollToBottom(true);
        }
      });
    });

    function updateScrollState(target: HTMLElement, shouldEmit = true) {
      const { scrollTop, clientHeight, scrollHeight } = target;
      const maxScrollTop = Math.max(0, scrollHeight - clientHeight);
      const newAutoScroll = scrollTop >= maxScrollTop - backThreshold.value;
      const nearTop = scrollTop <= topThreshold;

      isShowScrollbar.value = scrollHeight > clientHeight;
      isAutoScroll.value = newAutoScroll;

      if (shouldEmit) {
        emit("update:auto", newAutoScroll);
        if (nearTop) {
          if (!hasReachedTop.value) {
            hasReachedTop.value = true;
            emit("reachTop");
          }
        } else {
          hasReachedTop.value = false;
        }
      }
    }

    function scrollToBottom(silent = false) {
      if (silent) {
        isProgrammaticScroll = true;
      }
      nextTick(() => {
        const container = containerRef.value;
        if (container) {
          container.scrollTop = Math.max(0, container.scrollHeight - container.clientHeight);

          requestAnimationFrame(() => {
            updateScrollState(container, !silent);
            if (silent) {
              isProgrammaticScroll = false;
            }
          });
        } else if (silent) {
          isProgrammaticScroll = false;
        }
      });
    }

    function handleScroll(e: Event) {
      const target = e.currentTarget as HTMLElement;

      if (isProgrammaticScroll) {
        updateScrollState(target, false);
        return;
      }

      updateScrollState(target);
    }

    function handleBackToBottom() {
      isAutoScroll.value = true;
      emit("update:auto", true);
      scrollToBottom(true);
    }

    expose({
      scrollbarBottom: scrollToBottom,
    });

    return () => (
      <div
        ref={containerRef}
        class="el-scrollbar"
        onScroll={handleScroll}
        style="overflow-y: auto; position: relative;"
      >
        <div
          ref={contentRef}
          class={`space-y-20px ${props.contentClass || ""}`}
          style="position: relative;"
        >
          {renderSlot(slots, "default")}
        </div>
        {props.backBtn && !isAutoScroll.value && isShowScrollbar.value && (
          <div
            class="back-bottom-control"
          >
            <button
              type="button"
              class="back-bottom-button"
              title="回到底部"
              onClick={handleBackToBottom}
            >
              <svg
                viewBox="0 0 24 24"
                width="16"
                height="16"
                fill="none"
                stroke="currentColor"
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
              >
                <path d="M12 5v14" />
                <path d="m6 13 6 6 6-6" />
              </svg>
            </button>
          </div>
        )}
      </div>
    );
  },
});
</script>

<style scoped>
.el-scrollbar {
  scrollbar-width: thin;
}

.el-scrollbar::-webkit-scrollbar {
  width: 6px;
}

.el-scrollbar::-webkit-scrollbar-thumb {
  background-color: rgba(144, 147, 153, 0.3);
  border-radius: 3px;
}

.el-scrollbar::-webkit-scrollbar-track {
  background-color: transparent;
}

.back-bottom-control {
  position: sticky;
  bottom: 34px;
  z-index: 3;
  display: flex;
  justify-content: flex-end;
  height: 0;
  padding-right: 0;
  pointer-events: none;
}

.back-bottom-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid rgba(17, 124, 104, 0.26);
  border-radius: 999px;
  color: #117c68;
  background: rgba(255, 253, 250, 0.94);
  box-shadow: 0 10px 24px rgba(22, 32, 27, 0.16);
  cursor: pointer;
  pointer-events: auto;
  transition:
    transform 0.16s ease,
    border-color 0.16s ease,
    background-color 0.16s ease,
    box-shadow 0.16s ease;
}

.back-bottom-button:hover {
  border-color: rgba(17, 124, 104, 0.42);
  background: #fffdfa;
  box-shadow: 0 12px 28px rgba(22, 32, 27, 0.2);
  transform: translateY(-1px);
}

.back-bottom-button:active {
  transform: translateY(0);
}
</style>
