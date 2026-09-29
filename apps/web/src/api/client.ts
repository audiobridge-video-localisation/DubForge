const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface Project {
  id: string;
  name: string;
  created_at: string;
}

async function parseErrorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // response had no JSON body
  }
  return `Request failed with status ${response.status}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!response.ok) {
    throw new Error(await parseErrorMessage(response));
  }

  return response.json() as Promise<T>;
}

export function listProjects(): Promise<Project[]> {
  return request<Project[]>("/projects");
}

export function getProject(id: string): Promise<Project> {
  return request<Project>(`/projects/${id}`);
}

export function createProject(name: string): Promise<Project> {
  return request<Project>("/projects", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}
