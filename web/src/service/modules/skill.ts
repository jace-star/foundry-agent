import { authFetch } from "@/utils/auth-fetch";

export interface SkillConfig {
  name: string;
  description: string;
  allowed_tools: string;
  system_prompt: string;
}

export interface SkillCreateRequest {
  name: string;
  description?: string;
  allowed_tools?: string;
  system_prompt?: string;
}

export interface SkillUpdateRequest {
  description?: string;
  allowed_tools?: string;
  system_prompt?: string;
}

export interface SkillSummary {
  name: string;
  description: string;
  allowed_tools: string;
}

function skillApiPrefix(agentKey: string): string {
  return `/agent/v1/agents/${encodeURIComponent(agentKey)}/skills`;
}

export async function listSkills(agentKey: string): Promise<SkillSummary[]> {
  return requestJson<SkillSummary[]>(skillApiPrefix(agentKey));
}

export async function getSkill(agentKey: string, skillName: string): Promise<SkillConfig> {
  return requestJson<SkillConfig>(`${skillApiPrefix(agentKey)}/${encodeURIComponent(skillName)}`);
}

export async function createSkill(agentKey: string, payload: SkillCreateRequest): Promise<SkillConfig> {
  return requestJson<SkillConfig>(skillApiPrefix(agentKey), {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateSkill(agentKey: string, skillName: string, payload: SkillUpdateRequest): Promise<SkillConfig> {
  return requestJson<SkillConfig>(`${skillApiPrefix(agentKey)}/${encodeURIComponent(skillName)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function deleteSkill(agentKey: string, skillName: string): Promise<void> {
  await requestJson<void>(`${skillApiPrefix(agentKey)}/${encodeURIComponent(skillName)}`, {
    method: "DELETE",
  });
}

async function requestJson<T>(url: string, init: RequestInit = {}): Promise<T> {
  const response = await authFetch(url, init);

  if (!response.ok) {
    let message = "技能请求失败";
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
