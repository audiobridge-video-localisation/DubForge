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

export type ArtifactStatus =
  "pending" | "processing" | "completed" | "failed" | "outdated";

export type SegmentAudioStatus =
  "no_audio" | "pending" | "failed" | "outdated" | "mismatch" | "ready";

export interface Artifact {
  id: string;
  status: ArtifactStatus;
  audio_path: string | null;
  duration_ms: number | null;
  voice_profile: string | null;
  error_message: string | null;
  retry_count: number;
  created_at: string;
  updated_at: string;
}

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
  artifact: Artifact | null;
  audio_status: SegmentAudioStatus;
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
  usable_audio_count: number;
}

export interface ProjectDetail extends Project {
  media: MediaWithJob[];
}

export type ExportKind = "mp3" | "mp4";

export interface ExportJob {
  id: string;
  media_id: string;
  kind: ExportKind;
  status: JobStatus;
  progress: number;
  output_path: string | null;
  error_message: string | null;
  retry_count: number;
  created_at: string;
  updated_at: string;
}

const NETWORK_ERROR =
  "Couldn't reach the DubForge API. Check that it is running, then try again.";

function detailFrom(status: number, body: string): string {
  try {
    const parsed = JSON.parse(body);
    if (typeof parsed.detail === "string") return parsed.detail;
  } catch {
    // response had no JSON body
  }
  return `Request failed with status ${status}`;
}

async function parseErrorMessage(response: Response): Promise<string> {
  return detailFrom(response.status, await response.text());
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new Error(NETWORK_ERROR);
  }

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

export interface UploadOptions {
  /** called with 0-100 as the file is sent */
  onProgress?: (percent: number) => void;
  signal?: AbortSignal;
}

// XMLHttpRequest rather than fetch: fetch cannot report upload progress.
export function uploadMedia(
  projectId: string,
  file: File,
  { onProgress, signal }: UploadOptions = {},
): Promise<MediaWithJob> {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/projects/${projectId}/media`);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress?.(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as MediaWithJob);
        } catch {
          reject(
            new Error("The server sent a response that could not be read."),
          );
        }
      } else {
        reject(new Error(detailFrom(xhr.status, xhr.responseText)));
      }
    };
    xhr.onerror = () => reject(new Error(NETWORK_ERROR));
    xhr.onabort = () =>
      reject(new DOMException("Upload cancelled", "AbortError"));

    signal?.addEventListener("abort", () => xhr.abort(), { once: true });
    if (signal?.aborted) {
      xhr.abort();
      return;
    }
    xhr.send(formData);
  });
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

export function regenerateSegment(segmentId: string): Promise<Artifact> {
  return request<Artifact>(`/segments/${segmentId}/regenerate`, {
    method: "POST",
  });
}

export function exportMp3(mediaId: string): Promise<ExportJob> {
  return request<ExportJob>(`/media/${mediaId}/export/mp3`, { method: "POST" });
}

export function exportMp4(mediaId: string): Promise<ExportJob> {
  return request<ExportJob>(`/media/${mediaId}/export/mp4`, { method: "POST" });
}

export function getExportJob(exportJobId: string): Promise<ExportJob> {
  return request<ExportJob>(`/export-jobs/${exportJobId}`);
}

export function srtDownloadUrl(mediaId: string): string {
  return `${API_URL}/media/${mediaId}/export/srt`;
}

export function vttDownloadUrl(mediaId: string): string {
  return `${API_URL}/media/${mediaId}/export/vtt`;
}

export function exportDownloadUrl(exportJobId: string): string {
  return `${API_URL}/export-jobs/${exportJobId}/download`;
}
