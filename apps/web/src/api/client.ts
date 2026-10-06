const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface Project {
  id: string;
  name: string;
  created_at: string;
}

export type JobStatus = "pending" | "processing" | "completed" | "failed";

export interface Media {
  id: string;
  project_id: string;
  filename: string;
  storage_path: string;
  created_at: string;
  ready_for_dubbing: boolean;
}

export interface Job {
  id: string;
  media_id: string;
  status: JobStatus;
  progress: number;
  error_message: string | null;
  retry_count: number;
  created_at: string;
  updated_at: string;
}

export type SegmentReviewStatus = "pending" | "approved" | "needs_changes";

export interface Segment {
  id: string;
  index: number;
  start_ms: number;
  end_ms: number;
  duration_ms: number;
  speaker_label: string;
  text: string;
  translated_text: string | null;
  review_status: SegmentReviewStatus;
}

export interface SegmentUpdate {
  text?: string;
  translated_text?: string;
  speaker_label?: string;
  start_ms?: number;
  end_ms?: number;
}

export interface MediaWithJob {
  media: Media;
  job: Job;
  segments: Segment[];
  approved_count: number;
  total_count: number;
}

export interface ProjectDetail extends Project {
  media: MediaWithJob[];
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

export function getProject(id: string): Promise<ProjectDetail> {
  return request<ProjectDetail>(`/projects/${id}`);
}

export function createProject(name: string): Promise<Project> {
  return request<Project>("/projects", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function uploadMedia(
  projectId: string,
  file: File,
): Promise<MediaWithJob> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_URL}/projects/${projectId}/media`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await parseErrorMessage(response));
  }

  return response.json() as Promise<MediaWithJob>;
}

export function getJob(jobId: string): Promise<Job> {
  return request<Job>(`/jobs/${jobId}`);
}

export function retryJob(jobId: string): Promise<Job> {
  return request<Job>(`/jobs/${jobId}/retry`, { method: "POST" });
}

export function updateSegment(
  segmentId: string,
  patch: SegmentUpdate,
): Promise<Segment> {
  return request<Segment>(`/segments/${segmentId}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export function approveSegment(segmentId: string): Promise<Segment> {
  return request<Segment>(`/segments/${segmentId}/approve`, { method: "POST" });
}

export function requestSegmentChanges(segmentId: string): Promise<Segment> {
  return request<Segment>(`/segments/${segmentId}/request-changes`, {
    method: "POST",
  });
}

export function markReadyForDubbing(mediaId: string): Promise<Media> {
  return request<Media>(`/media/${mediaId}/ready-for-dubbing`, {
    method: "POST",
  });
}
