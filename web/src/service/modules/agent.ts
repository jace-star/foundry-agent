import { authFetch } from "@/utils/auth-fetch";

export interface AgentConfig {
  id: string;
  key: string;
  name: string;
  description: string;
  system_prompt: string;
  tool_servers: string[];
  is_home: boolean;
  created_at: string;
  updated_at: string;
}

export interface AgentCreateRequest {
  key: string;
  name: string;
  description?: string;
  system_prompt?: string;
  tool_servers?: string[];
}

export interface AgentUpdateRequest {
  name?: string;
  description?: string;
  system_prompt?: string;
  tool_servers?: string[];
}

export interface AgentSummary {
  id: string;
  key: string;
  name: string;
  description: string;
  tool_servers: string[];
  is_home: boolean;
  created_at: string;
  updated_at: string;
}

const AGENT_API_PREFIX = "/agent/v1/agents";

export async function listAgents(): Promise<AgentSummary[]> {
  return requestJson<AgentSummary[]>(AGENT_API_PREFIX);
}

export async function getAgent(agentKey: string): Promise<AgentConfig> {
  return requestJson<AgentConfig>(`${AGENT_API_PREFIX}/${encodeURIComponent(agentKey)}`);
}

export async function createAgent(payload: AgentCreateRequest): Promise<AgentConfig> {
  return requestJson<AgentConfig>(AGENT_API_PREFIX, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateAgent(agentKey: string, payload: AgentUpdateRequest): Promise<AgentConfig> {
  return requestJson<AgentConfig>(`${AGENT_API_PREFIX}/${encodeURIComponent(agentKey)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function deleteAgent(agentKey: string): Promise<void> {
  await requestJson<void>(`${AGENT_API_PREFIX}/${encodeURIComponent(agentKey)}`, {
    method: "DELETE",
  });
}

export async function setAgentHome(agentKey: string): Promise<void> {
  await requestJson<void>(`${AGENT_API_PREFIX}/${encodeURIComponent(agentKey)}/home`, {
    method: "PUT",
  });
}

export async function unsetAgentHome(agentKey: string): Promise<void> {
  await requestJson<void>(`${AGENT_API_PREFIX}/${encodeURIComponent(agentKey)}/home`, {
    method: "DELETE",
  });
}

async function requestJson<T>(url: string, init: RequestInit = {}): Promise<T> {
  const response = await authFetch(url, init);

  if (!response.ok) {
    let message = "Agent 请求失败";
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
