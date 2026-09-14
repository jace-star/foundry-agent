<script lang="tsx">
import type { PropType } from "vue";
import {
  defineComponent,
  ref,
  renderSlot,
  watch,
} from "vue";
import chevronDownIcon from "@/assets/icon/chevron-down.svg";

export default defineComponent({
  name: "Collapse",
  props: {
    title: {
      type: String as PropType<string>,
      default: "",
    },
    titleIcon: {
      type: String as PropType<string>,
      default: "",
    },
    titleLoading: {
      type: Boolean as PropType<boolean>,
      default: false,
    },
    modelValue: {
      type: Boolean as PropType<boolean>,
      default: false,
    },
  },
  emits: ["update:modelValue"],
  setup(props, { emit, slots }) {
    const isExpanded = ref(props.modelValue);

    watch(
      () => props.modelValue,
      (val) => {
        isExpanded.value = val;
      },
    );

    const handleToggle = () => {
      isExpanded.value = !isExpanded.value;
      emit("update:modelValue", isExpanded.value);
    };

    return () => (
      <div class="box-border">
        <button
          class="w-full flex justify-between items-center font-semibold text-base text-left bg-transparent border-none cursor-pointer p-2"
          onClick={handleToggle}
        >
          <span class="text-slate-700 flex items-center gap-1">
            {props.titleLoading
              ? <span class="collapse-title-spinner" aria-hidden="true"></span>
              : props.titleIcon && (
                <img src={props.titleIcon} alt="" aria-hidden="true" class="w-4 h-4 shrink-0"></img>
              )}
            {props.title}
          </span>
          <span
            class={`inline-flex items-center transition-transform duration-300 text-[#909399] ${isExpanded.value ? "rotate-0" : "-rotate-90"}`}
          >
            <img src={chevronDownIcon} alt="" class="w-5 h-5"></img>
          </span>
        </button>
        <div
          class={`grid transition-all duration-300 ease-in-out ${isExpanded.value ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}
        >
          <div class="overflow-hidden">
            <div class="mt-3">
              {renderSlot(slots, "default")}
            </div>
          </div>
        </div>
      </div>
    );
  },
});
</script>

<style scoped>
.collapse-title-spinner {
  width: 14px;
  height: 14px;
  flex: 0 0 14px;
  border: 2px solid rgba(17, 124, 104, 0.18);
  border-top-color: #117c68;
  border-radius: 999px;
  box-sizing: border-box;
  animation: collapse-title-spin 0.72s linear infinite;
}

@keyframes collapse-title-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
