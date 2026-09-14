<!-- eslint-disable vue/custom-event-name-casing -->
<script lang="tsx">
import type { UploadFile, UploadInstance, UploadProps } from "element-plus";

import type { PropType } from "vue";
import {
  ElButton,
  ElCard,
  ElInput,
  ElMessage,
  ElUpload,
} from "element-plus";
import { HiIcon } from "hoci";
import { computed, defineComponent, ref } from "vue";
import fileIcon from "@/assets/icon/file.svg";
import sendIcon from "@/assets/icon/send.svg";
import stopIcon from "@/assets/icon/stop.svg";
import Flex from "../flex.vue";

const DOCX_MIME_TYPES = new Set([
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/octet-stream",
  "",
]);
const MAX_DOC_SIZE_BYTES = 15 * 1024 * 1024;

export default defineComponent({
  name: "ChatInput",
  components: {
    ElButton,
    ElCard,
    ElInput,
    HiIcon,
    ElUpload,
  },
  props: {
    modelValue: {
      type: String as PropType<string>,
      default: "",
    },
    stopState: {
      type: Boolean as PropType<boolean>,
      default: true,
    },
    docUploading: {
      type: Boolean as PropType<boolean>,
      default: false,
    },
  },
  emits: {
    "update:modelValue": (_value: string) => true,
    "send": (_value: string) => true,
    "stop": () => true,
    "doc-change": (_file: File | null) => true,
  },
  setup(props, { emit }) {
    const inputValue = computed({
      get: () => props.modelValue || "",
      set: (value: string) => emit("update:modelValue", value),
    });
    const selectedFileName = ref("");
    const uploadRef = ref<UploadInstance>();

    const clearSelectedDoc = (notifyParent = true) => {
      selectedFileName.value = "";
      uploadRef.value?.clearFiles();
      if (notifyParent) {
        emit("doc-change", null);
      }
    };

    const isSupportedDocFile = (file: File) => {
      const fileName = file.name.toLowerCase();
      return fileName.endsWith(".docx") && DOCX_MIME_TYPES.has(file.type);
    };

    const handleDocChange: UploadProps["onChange"] = (uploadFile: UploadFile) => {
      const rawFile = uploadFile.raw;
      if (!rawFile) {
        return;
      }

      uploadRef.value?.clearFiles();

      if (!isSupportedDocFile(rawFile)) {
        ElMessage.error("当前仅支持上传 .docx 文件");
        clearSelectedDoc(false);
        return;
      }

      if (rawFile.size > MAX_DOC_SIZE_BYTES) {
        ElMessage.error("文件大小不能超过 15MB");
        clearSelectedDoc(false);
        return;
      }

      selectedFileName.value = rawFile.name;
      emit("doc-change", rawFile);
    };

    const handleClick = () => {
      if (!props.stopState) {
        return emit("stop");
      }

      if (props.docUploading) {
        ElMessage.info("文件上传中，请稍候...");
        return;
      }

      if (!inputValue.value.trim()) {
        ElMessage.info("请输入内容");
        return;
      }

      const msg = inputValue.value;
      inputValue.value = "";
      emit("send", msg);
      // 这里只清理输入框里的文档展示，不回传父组件，避免误删当前会话的 document_id。
      clearSelectedDoc(false);
    };

    const handleKeydown = (e: KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleClick();
      }
    };

    return () => (
      <Flex class="gap-8px! flex-col">
        {selectedFileName.value && (
          <div class="selected-file flex gap-8px flex-wrap mb-2">
            <div
              class={
                props.docUploading
                  ? "file-item flex items-center gap-8px px-3 py-1 rounded-full file-uploading"
                  : "file-item flex items-center gap-8px px-3 py-1 rounded-full"
              }
              style={{
                background: "#eef",
                border: "1px solid #ccf",
              }}
            >
              {props.docUploading
                ? (
                    <span class="upload-spinner w-4 h-4 inline-block" />
                  )
                : (
                    <HiIcon
                      src={fileIcon}
                      class="w-4 h-4"
                      style={{ color: "#55f" }}
                    />
                  )}
              <span
                class="text-sm"
                style={{
                  color: "#55f",
                  maxWidth: "120px",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
                title={selectedFileName.value}
              >
                {selectedFileName.value}
                {props.docUploading && " 上传中..."}
              </span>
              <span
                class="cursor-pointer text-xs hover:opacity-70"
                style={{ color: "#999" }}
                onClick={() => clearSelectedDoc()}
              >
                ×
              </span>
            </div>
          </div>
        )}
        {/* 输入框 */}
        <ElCard
          class="shadow-outer rounded-3xl"
          bodyStyle={{ width: "100%", padding: "12px" }}
        >
          <div class="flex flex-col w-full">
            <ElInput
              v-model={inputValue.value}
              class="bg-transparent"
              placeholder="在此输入您想了解的内容，Enter发送，Shift+Enter换行"
              type="textarea"
              autosize={{ minRows: 2, maxRows: 8 }}
              style={{ flex: 1 }}
              onKeydown={(e: Event | KeyboardEvent) => handleKeydown(e as KeyboardEvent)}
            />
            <div class="flex justify-between items-center mt-2">
              <div title="上传文件">
                <ElUpload
                  ref={uploadRef}
                  auto-upload={false}
                  show-file-list={false}
                  multiple={false}
                  accept=".docx"
                  onChange={handleDocChange}
                >
                  <ElButton
                    class="upload-btn"
                    style={{
                      border: "none",
                      padding: "8px",
                      background: "transparent",
                    }}
                  >
                    <HiIcon src={fileIcon} class="w-5 h-5" style={{ color: "#999" }} />
                  </ElButton>
                </ElUpload>
              </div>
              <ElButton
                type="primary"
                circle
                onClick={handleClick}
              >
                <HiIcon
                  src={props.stopState ? sendIcon : stopIcon}
                  class="w-4 h-4 "
                />
              </ElButton>
            </div>
          </div>
        </ElCard>
      </Flex>
    );
  },
});
</script>

<style scoped lang="less">
:deep(.el-textarea__inner) {
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
  padding: 0 !important;
  resize: none !important;
}

:deep(.el-textarea) {
  display: block !important;
}

:deep(.el-input__wrapper) {
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
  padding: 0 !important;
}

:deep(.el-card__body) {
  padding: 12px;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.upload-spinner {
  border: 2px solid #ccf;
  border-top-color: #55f;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}

.file-uploading {
  animation: pulse 1.5s ease-in-out infinite;
}
</style>
