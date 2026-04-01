import type {
  AppSettings,
  JobRecord,
  ProjectRecord,
  SetupStatus,
  SynthesisControls,
  TranscriptSegment,
  VoiceProfile,
} from "@voice-studio/shared";

const baseUrl = "http://127.0.0.1:8765";
const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

const recoverJob = async (jobId?: string): Promise<JobRecord | null> => {
  if (!jobId) {
    return null;
  }
  for (let attempt = 0; attempt < 6; attempt += 1) {
    try {
      const response = await fetch(`${baseUrl}/api/jobs/${jobId}`);
      if (response.ok) {
        return (await response.json()) as JobRecord;
      }
    } catch {
      // Keep retrying while the backend settles.
    }
    await sleep(500 * (attempt + 1));
  }
  return null;
};

const call = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const method = init?.method ?? "GET";
  const retries = method === "GET" ? 2 : 0;

  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      const response = await fetch(`${baseUrl}${path}`, init);
      if (!response.ok) {
        throw new Error(await response.text());
      }
      return response.json() as Promise<T>;
    } catch (error) {
      if (attempt < retries) {
        await sleep(350 * (attempt + 1));
        continue;
      }
      const detail = error instanceof Error ? error.message : "Unknown network failure";
      throw new Error(`Backend unavailable at ${baseUrl}. Start the backend with npm run dev or npm run backend:dev. ${detail}`);
    }
  }
  throw new Error(`Backend unavailable at ${baseUrl}. Start the backend with npm run dev or npm run backend:dev.`);
};

export const api = {
  mediaUrl: (path?: string) => (path ? `${baseUrl}/api/media?path=${encodeURIComponent(path)}` : ""),
  getOverview: () =>
    call<{
      profiles: VoiceProfile[];
      projects: ProjectRecord[];
      jobs: JobRecord[];
      settings: AppSettings;
    }>("/api/overview"),
  createProfile: (payload: {
    name: string;
    description?: string;
    samplePaths: string[];
    authorizedUseConfirmed: boolean;
  }) =>
    call<VoiceProfile>("/api/voice-profiles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  uploadProfile: async (payload: {
    name: string;
    description?: string;
    authorizedUseConfirmed: boolean;
    files: File[];
    clientJobId?: string;
    onUploadProgress?: (progress: number) => void;
  }) => {
    const form = new FormData();
    form.append("name", payload.name);
    form.append("description", payload.description ?? "");
    form.append("authorizedUseConfirmed", String(payload.authorizedUseConfirmed));
    if (payload.clientJobId) {
      form.append("clientJobId", payload.clientJobId);
    }
    payload.files.forEach((file) => form.append("files", file));
    return new Promise<JobRecord>((resolve, reject) => {
      const request = new XMLHttpRequest();
      request.open("POST", `${baseUrl}/api/voice-profiles/upload`);
      request.upload.onprogress = (event) => {
        if (event.lengthComputable && payload.onUploadProgress) {
          payload.onUploadProgress(event.loaded / event.total);
        }
      };
      request.onload = () => {
        if (request.status >= 200 && request.status < 300) {
          resolve(JSON.parse(request.responseText) as JobRecord);
          return;
        }
        reject(new Error(request.responseText || "Upload failed"));
      };
      request.timeout = 15 * 60 * 1000;
      request.onerror = () => {
        void recoverJob(payload.clientJobId)
          .then((job) => {
            if (job) {
              resolve(job);
              return;
            }
            reject(new Error(`Backend unavailable at ${baseUrl}. Start the backend with npm run dev or npm run backend:dev.`));
          })
          .catch(() =>
            reject(new Error(`Backend unavailable at ${baseUrl}. Start the backend with npm run dev or npm run backend:dev.`)),
          );
      };
      request.ontimeout = () => {
        void recoverJob(payload.clientJobId)
          .then((job) => {
            if (job) {
              resolve(job);
              return;
            }
            reject(new Error("Profile upload timed out while waiting for the backend to respond."));
          })
          .catch(() => reject(new Error("Profile upload timed out while waiting for the backend to respond.")));
      };
      request.onabort = () => reject(new Error("Profile upload was aborted."));
      request.send(form);
    });
  },
  getJob: (id: string) => call<JobRecord>(`/api/jobs/${id}`),
  deleteProfile: (id: string) =>
    call<{ ok: boolean }>(`/api/voice-profiles/${id}`, { method: "DELETE" }),
  synthesize: (payload: {
    text: string;
    profileId: string;
    controls: SynthesisControls;
    projectName?: string;
    clientJobId?: string;
  }) =>
    call<JobRecord>("/api/tts/synthesize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  replaceAudio: (payload: { inputPath: string; profileId: string; controls: SynthesisControls; clientJobId?: string }) =>
    call<JobRecord>("/api/audio-replacement", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  replaceVideo: (payload: { inputPath: string; profileId: string; controls: SynthesisControls; clientJobId?: string }) =>
    call<JobRecord>("/api/video-replacement", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  inspectSegments: (kind: "audio" | "video", inputPath: string) =>
    call<TranscriptSegment[]>(`/api/segments/${kind}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ inputPath }),
    }),
  updateSettings: (payload: Partial<AppSettings>) =>
    call<AppSettings>("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  getSetupStatus: () => call<SetupStatus>("/api/setup-status"),
};
