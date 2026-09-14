<script lang="tsx">
import type { PropType } from "vue";
import { defineComponent, renderSlot } from "vue";

export default defineComponent({
  name: "Flex",
  props: {
    flexAlign: {
      type: String as PropType<"center" | "vertical" | "horizontal">,
      required: false,
    },
    direction: {
      type: String as PropType<"vertical" | "horizontal">,
      default: "vertical",
    },
    wrap: {
      type: Boolean,
      default: false,
    },
  },
  setup(props, { slots }) {
    const isVertical = props.direction === "vertical";

    // 构建 flex 类名
    const getFlexClasses = () => {
      const classes: string[] = [];

      // 方向
      if (isVertical) {
        classes.push("flex-col");
      } else {
        classes.push("flex-row");
      }

      // 对齐
      if (props.flexAlign === "center") {
        classes.push("items-center", "justify-center");
      } else if (props.flexAlign === "horizontal") {
        classes.push("justify-center");
      } else if (props.flexAlign === "vertical") {
        classes.push("items-center");
      }

      // 换行
      if (props.wrap) {
        classes.push("flex-wrap");
      }

      return classes.join(" ");
    };

    return () => (
      <div class={`flex ${getFlexClasses()}`} style={{ gap: "revert-layer" }}>
        {renderSlot(slots, "default")}
      </div>
    );
  },
});
</script>
