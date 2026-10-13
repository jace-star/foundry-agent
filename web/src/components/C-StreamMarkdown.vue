<script lang="ts" setup>
import MarkdownRender from "markstream-vue";
import { computed } from "vue";
import "markstream-vue/index.css";

const props = withDefaults(
  defineProps<{
    text: string;
    /** 仍在加载/流式输出中；未传 final 时用 !loading 推断 */
    loading?: boolean;
    /** 流是否结束；传给 markstream-vue 的 final，避免未闭合语法卡住 */
    final?: boolean;
    contentClass?: string;
  }>(),
  {
    loading: false,
    final: undefined,
    contentClass: "",
  },
);

const isFinal = computed(() =>
  props.final !== undefined ? props.final : !props.loading,
);
</script>

<template>
  <div
    v-loading="loading && !text"
    class="markdown-container"
    :class="[contentClass, loading && !text ? 'inline-block' : '']"
  >
    <MarkdownRender
      mode="chat"
      :content="text"
      :final="isFinal"
      :render-batch-size="16"
      :render-batch-delay="8"
      :max-live-nodes="0"
    />
  </div>
</template>

<style scoped>
.markdown-container {
  word-wrap: break-word;
}

/* 重置元素 margin */
.markdown-container :deep(body),
.markdown-container :deep(blockquote),
.markdown-container :deep(dl),
.markdown-container :deep(dd),
.markdown-container :deep(h1),
.markdown-container :deep(h2),
.markdown-container :deep(h3),
.markdown-container :deep(h4),
.markdown-container :deep(h5),
.markdown-container :deep(h6),
.markdown-container :deep(hr),
.markdown-container :deep(figure),
.markdown-container :deep(p),
.markdown-container :deep(pre) {
  margin: 0;
}

/* 基础图片样式 */
.markdown-container :deep(img) {
  max-width: 100%;
  height: auto;
}

/* 缩小表格与正文之间的间距 */
.markdown-container :deep(table) {
  margin-top: 0.5em;
  margin-bottom: 0.5em;
}
</style>
