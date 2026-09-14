<script lang="ts" setup>
import { MarkdownRender } from "markstream-vue";
import remend from "remend";
import { ref, watch } from "vue";
import "markstream-vue/index.css";

const props = withDefaults(
  defineProps<{
    text: string;
    loading?: boolean;
    breaks?: boolean;
    contentClass?: string;
    mode?: "streaming" | "static";
  }>(),
  {
    loading: false,
    breaks: false,
    contentClass: "",
    mode: "streaming",
  },
);

const processedText = ref("");
const lastProcessedText = ref("");

// 使用 remend 预处理不完整的 Markdown 语法
watch(
  () => props.text,
  (newText) => {
    // 避免重复处理相同的文本
    if (newText === lastProcessedText.value) {
      return;
    }

    lastProcessedText.value = newText;
    // 使用 remend 处理不完整的 Markdown 语法
    processedText.value = newText ? remend(newText) : "";
  },
  { immediate: true },
);
</script>

<template>
  <div
    v-loading="loading && !text"
    class="markdown-container"
    :class="[contentClass, loading && !text ? 'inline-block' : '']"
  >
    <MarkdownRender
      :content="processedText"
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
