<route lang="yaml">
meta:
  title: 工具
  fullPage: true
</route>

<script setup lang="ts">
import type { MCPServerConfig, MCPServerInfo, MCPTool } from "@/service";
import {
  Delete,
  Document,
  Expand,
  Fold,
  Plus,
  Refresh,
} from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { computed, onMounted, reactive, ref } from "vue";
import {
  createMCPServer,
  deleteMCPServer,
  getMCPServerInfo,
  listMCPServers,
} from "@/service";

type TransportType = "http" | "stdio";

// 服务列表与当前详情状态。
const servers = ref<MCPServerConfig[]>([]);
const selectedServer = ref<MCPServerInfo | null>(null);
const selectedName = ref("");
const loadingServers = ref(false);
const loadingInfo = ref(false);
const saving = ref(false);
const deleting = ref("");
const addDialogVisible = ref(false);
const serviceDrawerOpen = ref(true);

// 新增 MCP 服务配置表单。
const form = reactive({
  name: "",
  description: "",
  transport: "http" as TransportType,
  url: "",
  command: "",
  args: "",
  headers: "{}",
  env: "{}",
});

const selectedTools = computed(() => selectedServer.value?.tools ?? []);

onMounted(() => {
  void refreshServers();
});

// 刷新已保存的 MCP 服务列表。
async function refreshServers() {
  loadingServers.value = true;
  try {
    servers.value = await listMCPServers();
    if (selectedName.value && !servers.value.some((server) => server.name === selectedName.value)) {
      selectedName.value = "";
      selectedServer.value = null;
    }
  } catch (error) {
    ElMessage.error(errorMessage(error, "服务列表加载失败"));
  } finally {
    loadingServers.value = false;
  }
}

// 新增服务时直接保存 langchain-mcp-adapters 的连接配置。
async function addServer() {
  const name = form.name.trim();
  if (!name) {
    ElMessage.warning("请输入服务名");
    return;
  }

  let connection: Record<string, any>;
  try {
    connection = buildConnection();
  } catch (error) {
    ElMessage.error(errorMessage(error, "连接配置无效"));
    return;
  }

  saving.value = true;
  try {
    const server = await createMCPServer({
      name,
      description: form.description.trim(),
      connection,
    });
    resetForm();
    addDialogVisible.value = false;
    await refreshServers();
    await selectServer(server.name);
    ElMessage.success("MCP 服务已接入");
  } catch (error) {
    ElMessage.error(errorMessage(error, "MCP 服务接入失败"));
  } finally {
    saving.value = false;
  }
}

// 点击服务后再读取该服务的工具详情。
async function selectServer(name: string) {
  selectedName.value = name;
  loadingInfo.value = true;
  try {
    selectedServer.value = await getMCPServerInfo(name);
  } catch (error) {
    selectedServer.value = null;
    ElMessage.error(errorMessage(error, "工具信息读取失败"));
  } finally {
    loadingInfo.value = false;
  }
}

// 删除当前接入的 MCP 服务配置。
async function removeServer(name: string) {
  try {
    await ElMessageBox.confirm(`删除 ${name}？`, "删除 MCP 服务", {
      confirmButtonText: "删除",
      cancelButtonText: "取消",
      type: "warning",
    });
  } catch {
    return;
  }

  deleting.value = name;
  try {
    await deleteMCPServer(name);
    if (selectedName.value === name) {
      selectedName.value = "";
      selectedServer.value = null;
    }
    await refreshServers();
    ElMessage.success("MCP 服务已删除");
  } catch (error) {
    ElMessage.error(errorMessage(error, "删除失败"));
  } finally {
    deleting.value = "";
  }
}

// 根据传输方式组装连接配置。
function buildConnection() {
  if (form.transport === "http") {
    const url = form.url.trim();
    if (!url) {
      throw new Error("请输入 HTTP 地址");
    }
    return {
      transport: "http",
      url,
      headers: parseJsonObject(form.headers, "Headers"),
    };
  }

  const command = form.command.trim();
  if (!command) {
    throw new Error("请输入启动命令");
  }
  return {
    transport: "stdio",
    command,
    args: splitArgs(form.args),
    env: parseJsonObject(form.env, "Env"),
  };
}

// Headers / Env 保持 JSON 对象，便于后端原样保存。
function parseJsonObject(value: string, label: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return {};
  }
  const parsed = JSON.parse(trimmed);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`${label} 必须是 JSON 对象`);
  }
  return parsed;
}

// stdio 参数每行一个，避免复杂命令被空格误拆。
function splitArgs(value: string) {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function openAddDialog() {
  resetForm();
  addDialogVisible.value = true;
}

function resetForm() {
  form.name = "";
  form.description = "";
  form.transport = "http";
  form.url = "";
  form.command = "";
  form.args = "";
  form.headers = "{}";
  form.env = "{}";
}

// Schema 展示辅助函数。
function schemaFields(schema: Record<string, any> | null | undefined) {
  const properties = schema?.properties;
  if (!properties || typeof properties !== "object") {
    return [];
  }
  return Object.entries(properties).map(([name, value]) => ({
    name,
    schema: value as Record<string, any>,
  }));
}

function schemaType(schema: Record<string, any>) {
  const type = schema.type;
  return Array.isArray(type) ? type.join(" | ") : String(type || "-");
}

function toolTitle(tool: MCPTool) {
  return tool.title || tool.name;
}

function serverEndpoint(server: MCPServerConfig) {
  const connection = server.connection ?? {};
  if (connection.transport === "stdio") {
    const args = Array.isArray(connection.args) ? connection.args.join(" ") : "";
    return [connection.command, args].filter(Boolean).join(" ");
  }
  return connection.url || "-";
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}
</script>

<template>
  <div class="mcp-page">
    <!-- 页面顶部操作区。 -->
    <header class="mcp-header">
      <div class="left-actions">
        <el-button :icon="serviceDrawerOpen ? Fold : Expand" @click="serviceDrawerOpen = !serviceDrawerOpen">
          服务列表
        </el-button>
        <el-button type="primary" :icon="Plus" @click="openAddDialog">
          新增工具
        </el-button>
      </div>
      <div class="header-actions">
        <el-button :icon="Refresh" :loading="loadingServers" @click="refreshServers">
          刷新
        </el-button>
      </div>
    </header>

    <main class="mcp-layout">
      <!-- MCP 服务列表，页面的主要工作区。 -->
      <section
        class="panel list-panel"
        :class="{ collapsed: !serviceDrawerOpen }"
      >
        <div class="panel-title">
          <span>服务列表</span>
          <small>{{ servers.length }} 个服务</small>
        </div>

        <el-scrollbar v-loading="loadingServers" class="server-list">
          <article
            v-for="server in servers"
            :key="server.name"
            class="server-card"
            :class="{ active: server.name === selectedName }"
            tabindex="0"
            @click="selectServer(server.name)"
            @keydown.enter="selectServer(server.name)"
          >
            <span class="server-card-top">
              <strong>{{ server.name }}</strong>
              <span class="server-actions">
                <em>{{ server.connection.transport || "-" }}</em>
                <el-button
                  text
                  type="danger"
                  :icon="Delete"
                  :loading="deleting === server.name"
                  @click.stop="removeServer(server.name)"
                />
              </span>
            </span>
            <span class="server-desc">{{ server.description || "无描述" }}</span>
            <span class="server-endpoint">{{ serverEndpoint(server) }}</span>
          </article>
          <el-empty v-if="!servers.length && !loadingServers" description="暂无服务">
            <el-button type="primary" :icon="Plus" @click="openAddDialog">
              新增工具
            </el-button>
          </el-empty>
        </el-scrollbar>
      </section>

      <!-- 选中某个服务后展示连接信息和工具 Schema。 -->
      <section class="panel detail-panel">
        <div class="panel-title">
          <span>服务详情</span>
        </div>

        <div v-loading="loadingInfo" class="detail-body">
          <el-empty v-if="!selectedServer" description="请选择左侧服务查看工具" />
          <template v-else>
            <div class="tool-stack">
              <article v-for="tool in selectedTools" :key="tool.name" class="tool-item">
                <div class="tool-head">
                  <Document class="tool-icon" />
                  <div>
                    <h3>{{ toolTitle(tool) }}</h3>
                    <p>{{ tool.description || tool.name }}</p>
                  </div>
                </div>

                <div class="schema-grid">
                  <div class="schema-block">
                    <h4>输入字段</h4>
                    <div v-if="schemaFields(tool.inputSchema).length" class="field-list">
                      <div v-for="field in schemaFields(tool.inputSchema)" :key="field.name" class="field-row">
                        <span>{{ field.name }}</span>
                        <b>{{ schemaType(field.schema) }}</b>
                        <em>{{ field.schema.description || "-" }}</em>
                      </div>
                    </div>
                    <el-empty v-else :image-size="64" description="无字段" />
                  </div>

                  <div class="schema-block">
                    <h4>返回字段</h4>
                    <div v-if="schemaFields(tool.outputSchema).length" class="field-list">
                      <div v-for="field in schemaFields(tool.outputSchema)" :key="field.name" class="field-row">
                        <span>{{ field.name }}</span>
                        <b>{{ schemaType(field.schema) }}</b>
                        <em>{{ field.schema.description || "-" }}</em>
                      </div>
                    </div>
                    <el-empty v-else :image-size="64" description="无字段" />
                  </div>
                </div>
              </article>
              <el-empty v-if="!selectedTools.length" :image-size="96" description="该服务暂无工具" />
            </div>
          </template>
        </div>
      </section>
    </main>

    <!-- 新增工具弹窗，仅在点击新增后展示配置表单。 -->
    <el-dialog
      v-model="addDialogVisible"
      width="560px"
      class="mcp-dialog"
      title="新增工具"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item label="服务名">
          <el-input v-model="form.name" placeholder="weather" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" placeholder="天气查询、文件系统、知识库" />
        </el-form-item>
        <el-form-item label="连接方式">
          <el-segmented v-model="form.transport" :options="['http', 'stdio']" />
        </el-form-item>

        <template v-if="form.transport === 'http'">
          <el-form-item label="URL">
            <el-input v-model="form.url" placeholder="http://localhost:8000/mcp" />
          </el-form-item>
          <el-form-item label="Headers">
            <el-input v-model="form.headers" type="textarea" :rows="5" />
          </el-form-item>
        </template>

        <template v-else>
          <el-form-item label="Command">
            <el-input v-model="form.command" placeholder="npx" />
          </el-form-item>
          <el-form-item label="Args">
            <el-input
              v-model="form.args"
              type="textarea"
              :rows="5"
              placeholder="-y&#10;@modelcontextprotocol/server-filesystem&#10;/tmp"
            />
          </el-form-item>
          <el-form-item label="Env">
            <el-input v-model="form.env" type="textarea" :rows="5" />
          </el-form-item>
        </template>
      </el-form>

      <template #footer>
        <el-button @click="addDialogVisible = false">
          取消
        </el-button>
        <el-button type="primary" :icon="Plus" :loading="saving" @click="addServer">
          接入
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="less">
.mcp-page {
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 0;
  border-radius: 0;
  padding: 28px;
  color: #16201b;
  background:
    linear-gradient(135deg, rgba(17, 124, 104, 0.08), transparent 34%),
    linear-gradient(315deg, rgba(214, 95, 71, 0.1), transparent 28%),
    #f6f4ef;
}

.mcp-header {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.left-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.mcp-layout {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  gap: 16px;
  align-items: stretch;
}

.panel {
  min-height: 120px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(22, 32, 27, 0.12);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.84);
  box-shadow: 0 16px 36px rgba(54, 48, 39, 0.08);
  backdrop-filter: blur(10px);
}

.list-panel {
  width: 280px;
  flex: 0 0 280px;
  transition:
    width 0.24s cubic-bezier(0.2, 0.8, 0.2, 1),
    flex-basis 0.24s cubic-bezier(0.2, 0.8, 0.2, 1);
}

.list-panel.collapsed {
  width: 132px;
  flex-basis: 132px;
  padding: 18px 10px;

  .panel-title {
    justify-content: center;

    small {
      display: none;
    }
  }

  .server-list {
    padding-right: 0;
  }

  .server-card {
    min-height: 46px;
    padding: 10px;
    align-content: center;
  }

  .server-card-top {
    justify-content: center;

    strong {
      max-width: 100%;
      overflow: hidden;
      text-align: center;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .server-actions,
  .server-desc,
  .server-endpoint {
    display: none;
  }
}

.list-panel,
.detail-panel {
  padding: 18px;
}

.detail-panel {
  flex: 1 1 auto;
}

.panel-title {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 32px;
  margin-bottom: 16px;
  color: #24342c;
  font-weight: 750;

  small {
    color: #6f7b72;
    font-size: 12px;
  }
}

.server-list {
  flex: 1 1 auto;
  min-height: 0;

  :deep(.el-scrollbar__view) {
    padding: 6px 4px 12px 0;
  }
}

.server-card {
  display: grid;
  width: 100%;
  min-height: 108px;
  margin-bottom: 10px;
  padding: 14px;
  cursor: pointer;
  border: 1px solid rgba(22, 32, 27, 0.12);
  border-radius: 8px;
  background: #fffdfa;
  color: inherit;
  text-align: left;
  transition: border-color 0.16s ease, transform 0.16s ease, background 0.16s ease, box-shadow 0.16s ease;

  &:focus-visible {
    outline: 2px solid rgba(17, 124, 104, 0.42);
    outline-offset: 2px;
  }

  &:hover,
  &.active {
    border-color: rgba(17, 124, 104, 0.42);
    background: #effaf6;
    box-shadow: 0 10px 24px rgba(17, 124, 104, 0.08);
  }
}

.server-actions {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;

  :deep(.el-button) {
    width: 26px;
    height: 26px;
    padding: 0;
  }
}

.server-card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;

  strong {
    overflow-wrap: anywhere;
    font-size: 16px;
    line-height: 1.3;
  }

  em {
    flex: 0 0 auto;
    padding: 2px 8px;
    border-radius: 999px;
    background: #16201b;
    color: #fff;
    font-size: 12px;
    font-style: normal;
  }
}

.server-desc,
.server-endpoint {
  overflow: hidden;
  color: #6f7b72;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.server-desc {
  margin-top: 10px;
}

.server-endpoint {
  margin-top: 8px;
  color: #9a6a45;
}

.detail-panel {
  min-height: 0;
}

.detail-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 3px 4px 12px 0;
}

.tool-stack {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.tool-item {
  padding: 14px;
  border: 1px solid rgba(22, 32, 27, 0.12);
  border-radius: 8px;
  background: #fffdfa;
}

.tool-head {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;

  h3 {
    margin: 0;
    overflow-wrap: anywhere;
    font-size: 16px;
  }

  p {
    margin: 4px 0 0;
    color: #6f7b72;
    font-size: 13px;
    line-height: 1.5;
  }
}

.tool-icon {
  width: 22px;
  height: 22px;
  flex: 0 0 auto;
  color: #d65f47;
}

.schema-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.schema-block {
  display: flex;
  max-height: 380px;
  flex-direction: column;
  min-height: 120px;
  padding: 12px;
  overflow: hidden;
  border-radius: 8px;
  background: #f6f4ef;

  h4 {
    flex: 0 0 auto;
    margin: 0 0 10px;
    font-size: 13px;
  }
}

.field-list {
  flex: 1 1 auto;
  min-height: 0;
  display: grid;
  gap: 8px;
  overflow-y: auto;
  padding-right: 4px;
}

.field-row {
  display: grid;
  grid-template-columns: minmax(70px, 0.9fr) minmax(52px, 0.5fr) minmax(0, 1.4fr);
  gap: 8px;
  align-items: start;
  min-height: 34px;
  color: #24342c;
  font-size: 12px;

  span,
  em {
    overflow-wrap: anywhere;
  }

  b {
    color: #117c68;
    font-weight: 700;
  }

  em {
    color: #6f7b72;
    font-style: normal;
  }
}

:deep(.mcp-dialog) {
  width: min(560px, calc(100vw - 32px)) !important;
  border-radius: 8px;
}

@media (max-width: 1180px) {
  .list-panel {
    width: 240px;
    flex-basis: 240px;
  }

  .list-panel.collapsed {
    width: 120px;
    flex-basis: 120px;
  }
}

@media (max-width: 720px) {
  .mcp-page {
    padding: 16px;
  }

  .mcp-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .left-actions,
  .header-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .mcp-layout {
    gap: 12px;
  }

  .list-panel {
    width: 200px;
    flex-basis: 200px;
  }

  .list-panel.collapsed {
    width: 104px;
    flex-basis: 104px;
  }

  .schema-grid {
    grid-template-columns: 1fr;
  }

  .server-list,
  .detail-body {
    min-height: 0;
  }

  .field-row {
    grid-template-columns: 1fr;
  }
}
</style>
