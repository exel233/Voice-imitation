import type {
  AppSettings,
  JobRecord,
  ProjectRecord,
  SynthesisControls,
  TranscriptSegment,
  VoiceProfile,
} from "@voice-studio/shared";

const call = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(`http://127.0.0.1:8765${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
};

export const api = {
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
      body: JSON.stringify(payload),
    }),
  deleteProfile: (id: string) =>
    call<{ ok: boolean }>(`/api/voice-profiles/${id}`, { method: "DELETE" }),
  synthesize: (payload: {
    text: string;
    profileId: string;
    controls: SynthesisControls;
    projectName?: string;
  }) =>
    call<JobRecord>("/api/tts/synthesize", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  replaceAudio: (payload: { inputPath: string; profileId: string; controls: SynthesisControls }) =>
    call<JobRecord>("/api/audio-replacement", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  replaceVideo: (payload: { inputPath: string; profileId: string; controls: SynthesisControls }) =>
    call<JobRecord>("/api/video-replacement", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  inspectSegments: (kind: "audio" | "video", inputPath: string) =>
    call<TranscriptSegment[]>(`/api/segments/${kind}`, {
      method: "POST",
      body: JSON.stringify({ inputPath }),
    }),
  updateSettings: (payload: Partial<AppSettings>) =>
    call<AppSettings>("/api/settings", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
};
