import { authFetch } from "@/utils/auth-fetch";

export interface MCPServerConfig {
  name: string;
  description: string;
  connection: Record<string, any>;
}

export interface MCPTool {
  name: string;
  title?: string | null;
  description?: string | null;
  inputSchema: Record<string, any>;
  outputSchema?: Record<string, any> | null;
}

export interface MCPServerInfo {
  name: string;
  description: string;
  type: string;
  endpoint: string;
  tools: MCPTool[];
}

const MCP_API_PREFIX = "/agent/v1/mcp/servers";

export async function listMCPServers(): Promise<MCPServerConfig[]> {
  return requestJson<MCPServerConfig[]>(MCP_API_PREFIX);
}

export async function createMCPServer(payload: MCPServerConfig): Promise<MCPServerConfig> {
  return requestJson<MCPServerConfig>(MCP_API_PREFIX, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getMCPServerInfo(name: string): Promise<MCPServerInfo> {
  return requestJson<MCPServerInfo>(`${MCP_API_PREFIX}/${encodeURIComponent(name)}`);
}

export async function deleteMCPServer(name: string): Promise<void> {
  await requestJson<void>(`${MCP_API_PREFIX}/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
}

async function requestJson<T>(url: string, init: RequestInit = {}): Promise<T> {
  const response = await authFetch(url, init);

  if (!response.ok) {
    let message = "MCP 请求失败";
    try {
      const payload = await response.json();
      message = payload.detail || message;
    } catch {
      // keep fallback message
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}
