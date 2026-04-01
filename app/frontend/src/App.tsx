import {
  defaultSynthesisControls,
  type AppSection,
  type AppSettings,
  type JobRecord,
  type ProjectRecord,
  type SetupStatus,
  type SynthesisControls,
  type TranscriptSegment,
  type VoiceProfile,
} from "@voice-studio/shared";
import {
  AlertTriangle,
  AudioLines,
  Clapperboard,
  FolderKanban,
  House,
  Mic2,
  PlayCircle,
  Settings2,
  Sparkles,
  Upload,
  Waves,
} from "lucide-react";
import { type ReactNode, useEffect, useMemo, useState } from "react";
import { api } from "./lib/api";

type Overview = {
  profiles: VoiceProfile[];
  projects: ProjectRecord[];
  jobs: JobRecord[];
  settings: AppSettings | null;
};

const nav: { id: AppSection; label: string; icon: typeof House }[] = [
  { id: "dashboard", label: "Home", icon: House },
  { id: "voiceProfiles", label: "Voice Profiles", icon: Mic2 },
  { id: "textToSpeech", label: "Text to Speech", icon: Sparkles },
  { id: "audioReplacement", label: "Audio Replacement", icon: AudioLines },
  { id: "videoReplacement", label: "Video Replacement", icon: Clapperboard },
  { id: "projects", label: "Projects", icon: FolderKanban },
  { id: "settings", label: "Settings", icon: Settings2 },
];

const card = "rounded-[28px] border border-black/5 bg-white/80 p-6 shadow-panel backdrop-blur";

export function App() {
  const [section, setSection] = useState<AppSection>("dashboard");
  const [overview, setOverview] = useState<Overview>({ profiles: [], projects: [], jobs: [], settings: null });
  const [setupStatus, setSetupStatus] = useState<SetupStatus | null>(null);
  const [controls, setControls] = useState<SynthesisControls>(defaultSynthesisControls);
  const [selectedProfileId, setSelectedProfileId] = useState("");
  const [ttsText, setTtsText] = useState("This speaker-conditioned preview should sound shaped by the uploaded profile.");
  const [mediaPath, setMediaPath] = useState("");
  const [segments, setSegments] = useState<TranscriptSegment[]>([]);
  const [status, setStatus] = useState("Ready");
  const [generatedAudioPath, setGeneratedAudioPath] = useState("");
  const [profileDraft, setProfileDraft] = useState({
    name: "",
    description: "",
    authorizedUseConfirmed: true,
  });
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [profileBuildState, setProfileBuildState] = useState<{
    jobId: string;
    uploadProgress: number;
    processingProgress: number;
    step: string;
    message: string;
    active: boolean;
    error?: string;
  } | null>(null);
  const [operationState, setOperationState] = useState<{
    jobId: string;
    label: string;
    progress: number;
    step: string;
    message: string;
    active: boolean;
    error?: string;
  } | null>(null);
  const [inspectState, setInspectState] = useState<{
    kind: "audio" | "video";
    active: boolean;
    progress: number;
    message: string;
    error?: string;
  } | null>(null);

  const selectedProfile = useMemo(
    () => overview.profiles.find((profile) => profile.id === selectedProfileId) ?? null,
    [overview.profiles, selectedProfileId],
  );

  const refresh = async () => {
    try {
      const data = await api.getOverview();
      const setup = await api.getSetupStatus();
      setOverview(data);
      setSetupStatus(setup);
      if (!selectedProfileId && data.profiles[0]) {
        setSelectedProfileId(data.profiles[0].id);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Backend refresh failed";
      setStatus(message);
    }
  };

  useEffect(() => {
    void refresh();
    const interval = window.setInterval(() => void refresh(), 4000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!profileBuildState?.active) {
      return;
    }

    const interval = window.setInterval(() => {
      void api
        .getJob(profileBuildState.jobId)
        .then((job) => {
          setProfileBuildState((current) => {
            if (!current || current.jobId !== job.id) {
              return current;
            }
            const next = {
              ...current,
              processingProgress: job.progress,
              step: job.step,
              message: job.message || job.step,
              active: job.status === "queued" || job.status === "running",
              error: job.status === "failed" ? job.message || "Profile build failed" : undefined,
            };
            return next;
          });
          if (job.status === "completed" || job.status === "failed") {
            void refresh();
          }
        })
        .catch(() => {
          // Ignore transient polling errors during startup/teardown.
        });
    }, 900);

    return () => window.clearInterval(interval);
  }, [profileBuildState?.active, profileBuildState?.jobId]);

  useEffect(() => {
    if (!profileBuildState?.active) {
      return;
    }

    const interval = window.setInterval(() => {
      setProfileBuildState((current) => {
        if (!current || !current.active || current.processingProgress >= 0.9) {
          return current;
        }
        return {
          ...current,
          processingProgress: Math.min(0.9, current.processingProgress + 0.03),
          message:
            current.uploadProgress >= 1 && current.message.startsWith("Uploading")
              ? "Building speaker profile artifacts"
              : current.message,
        };
      });
    }, 800);

    return () => window.clearInterval(interval);
  }, [profileBuildState?.active]);

  useEffect(() => {
    if (!operationState?.active) {
      return;
    }

    const interval = window.setInterval(() => {
      void api
        .getJob(operationState.jobId)
        .then((job) => {
          setOperationState((current) => {
            if (!current || current.jobId !== job.id) {
              return current;
            }
            return {
              ...current,
              progress: job.progress,
              step: job.step,
              message: job.message || job.step,
              active: job.status === "queued" || job.status === "running",
              error: job.status === "failed" ? job.message || `${current.label} failed` : undefined,
            };
          });
          if (job.status === "completed" || job.status === "failed") {
            void refresh();
          }
        })
        .catch(() => {
          // Ignore transient polling errors.
        });
    }, 900);

    return () => window.clearInterval(interval);
  }, [operationState?.active, operationState?.jobId]);

  useEffect(() => {
    if (!operationState?.active) {
      return;
    }

    const interval = window.setInterval(() => {
      setOperationState((current) => {
        if (!current || !current.active || current.progress >= 0.9) {
          return current;
        }
        return {
          ...current,
          progress: Math.min(0.9, current.progress + 0.02),
        };
      });
    }, 800);

    return () => window.clearInterval(interval);
  }, [operationState?.active]);

  useEffect(() => {
    if (!inspectState?.active) {
      return;
    }

    const interval = window.setInterval(() => {
      setInspectState((current) => {
        if (!current || !current.active || current.progress >= 0.9) {
          return current;
        }
        return { ...current, progress: Math.min(0.9, current.progress + 0.08) };
      });
    }, 350);

    return () => window.clearInterval(interval);
  }, [inspectState?.active]);

  const createProfile = async () => {
    if (!pendingFiles.length) {
      setStatus("Add at least one audio file first.");
      return;
    }
    const jobId = `job_profile_${Date.now().toString(36)}`;
    setProfileBuildState({
      jobId,
      uploadProgress: 0,
      processingProgress: 0,
      step: "Uploading samples",
      message: "Uploading samples",
      active: true,
    });
    setStatus("Uploading voice samples");
    try {
      const created = await api.uploadProfile({
        ...profileDraft,
        files: pendingFiles,
        clientJobId: jobId,
        onUploadProgress: (progress) =>
          setProfileBuildState((current) =>
            current && current.jobId === jobId
              ? {
                  ...current,
                  uploadProgress: progress,
                  step: progress < 1 ? "Uploading samples" : current.step,
                  message: progress < 1 ? `Uploading ${Math.round(progress * 100)}%` : current.message,
                }
              : current,
          ),
      });
      setStatus(`Built profile ${created.name} with ${created.samples.length} samples`);
      setSelectedProfileId(created.id);
      setPendingFiles([]);
      setProfileDraft({ name: "", description: "", authorizedUseConfirmed: true });
      setProfileBuildState((current) =>
        current && current.jobId === jobId
          ? {
              ...current,
              uploadProgress: 1,
              processingProgress: 1,
              step: "Completed",
              message: `Profile ready: ${created.name}`,
              active: false,
            }
          : current,
      );
      await refresh();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Profile upload failed";
      setStatus(message);
      setProfileBuildState((current) =>
        current && current.jobId === jobId
          ? {
              ...current,
              active: false,
              error: message,
              message,
              step: "Failed",
            }
          : current,
      );
    }
  };

  const synthesize = async () => {
    if (!selectedProfileId) return;
    const jobId = `job_tts_${Date.now().toString(36)}`;
    setOperationState({
      jobId,
      label: "Text to Speech",
      progress: 0.08,
      step: "Queueing synthesis",
      message: "Preparing synthesis request",
      active: true,
    });
    try {
      const job = await api.synthesize({ text: ttsText, profileId: selectedProfileId, controls, clientJobId: jobId });
      setGeneratedAudioPath(job.outputPath ?? "");
      setStatus(job.message);
      setSection("textToSpeech");
      setOperationState((current) =>
        current && current.jobId === jobId
          ? {
              ...current,
              progress: 1,
              step: "Completed",
              message: job.message,
              active: false,
            }
          : current,
      );
      await refresh();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Synthesis failed";
      setStatus(message);
      setOperationState((current) =>
        current && current.jobId === jobId
          ? { ...current, active: false, error: message, message, step: "Failed" }
          : current,
      );
    }
  };

  const inspect = async (kind: "audio" | "video") => {
    setInspectState({
      kind,
      active: true,
      progress: 0.12,
      message: `Inspecting ${kind} segments`,
    });
    try {
      const found = await api.inspectSegments(kind, mediaPath);
      setSegments(found);
      setStatus(`Loaded ${found.length} segments`);
      setInspectState({
        kind,
        active: false,
        progress: 1,
        message: `Loaded ${found.length} segments`,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : `Failed to inspect ${kind}`;
      setStatus(message);
      setInspectState({
        kind,
        active: false,
        progress: 1,
        message,
        error: message,
      });
    }
  };

  const replaceMedia = async (kind: "audio" | "video") => {
    if (!selectedProfileId) return;
    const jobId = `job_${kind}_${Date.now().toString(36)}`;
    setOperationState({
      jobId,
      label: kind === "audio" ? "Audio Replacement" : "Video Replacement",
      progress: 0.08,
      step: "Queueing replacement",
      message: `Preparing ${kind} replacement`,
      active: true,
    });
    try {
      const job =
        kind === "audio"
          ? await api.replaceAudio({ inputPath: mediaPath, profileId: selectedProfileId, controls, clientJobId: jobId })
          : await api.replaceVideo({ inputPath: mediaPath, profileId: selectedProfileId, controls, clientJobId: jobId });
      setGeneratedAudioPath(job.outputPath ?? "");
      setStatus(job.message);
      setSection("projects");
      setOperationState((current) =>
        current && current.jobId === jobId
          ? {
              ...current,
              progress: 1,
              step: "Completed",
              message: job.message,
              active: false,
            }
          : current,
      );
      await refresh();
    } catch (error) {
      const message = error instanceof Error ? error.message : `${kind} replacement failed`;
      setStatus(message);
      setOperationState((current) =>
        current && current.jobId === jobId
          ? { ...current, active: false, error: message, message, step: "Failed" }
          : current,
      );
    }
  };

  const updateSetting = async (key: Extract<keyof AppSettings, string>, value: string) => {
    const settings = await api.updateSettings({ [key]: value } as Partial<AppSettings>);
    setOverview((current) => ({ ...current, settings }));
    setStatus(`Updated ${key}`);
  };

  return (
    <div className="min-h-screen text-studio-ink">
      <div className="mx-auto flex min-h-screen max-w-[1600px] gap-6 p-6">
        <aside className="w-[280px] rounded-[34px] bg-studio-ink p-5 text-studio-fog shadow-panel">
          <div className="mb-10">
            <div className="font-display text-3xl">Voice Studio</div>
            <p className="mt-2 text-sm text-studio-fog/70">
              Build reusable speaker profiles from uploaded audio, then preview synthesis before export.
            </p>
          </div>
          <nav className="space-y-2">
            {nav.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setSection(id)}
                className={`flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left transition ${
                  section === id ? "bg-studio-fog text-studio-ink" : "bg-white/5 text-studio-fog/85 hover:bg-white/10"
                }`}
              >
                <Icon size={18} />
                <span>{label}</span>
              </button>
            ))}
          </nav>
          <div className="mt-8 rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-studio-fog/70">
            Voice samples must be owned by you or used with explicit authorization.
          </div>
        </aside>

        <main className="flex-1 space-y-6">
          <header className={`${card} flex items-center justify-between`}>
            <div>
              <div className="font-display text-4xl">Speaker-conditioned desktop dubbing</div>
              <p className="mt-2 max-w-3xl text-sm text-studio-ink/65">
                Uploaded samples are preprocessed into reusable profile artifacts, and profile-conditioned synthesis is labeled honestly when it falls back.
              </p>
              {setupStatus && (
                <div className="mt-3 flex flex-wrap gap-2 text-xs">
                  <Badge>{`requested: ${setupStatus.requestedTtsProvider}`}</Badge>
                  <Badge>{`active: ${setupStatus.activeTtsProvider}`}</Badge>
                  <Badge>{setupStatus.xtts.available ? "XTTS active" : "XTTS inactive"}</Badge>
                </div>
              )}
            </div>
            <div className="rounded-2xl bg-studio-ink px-4 py-3 text-sm text-studio-fog">{status}</div>
          </header>

          {section === "dashboard" && (
            <section className="grid gap-6 lg:grid-cols-3">
              <div className={`${card} lg:col-span-2`}>
                <div className="mb-5 flex items-center gap-3">
                  <Waves className="text-studio-ember" />
                  <h2 className="m-0 text-xl">Recent Jobs</h2>
                </div>
                <div className="space-y-3">
                  {overview.jobs.slice(0, 6).map((job) => (
                    <div key={job.id} className="rounded-2xl bg-studio-fog/80 p-4">
                      <div className="flex justify-between font-medium">
                        <span>{job.type}</span>
                        <span>{Math.round(job.progress * 100)}%</span>
                      </div>
                      <div className="mt-2 text-sm text-studio-ink/65">{job.message || job.step}</div>
                    </div>
                  ))}
                </div>
              </div>
              <div className={`${card} space-y-4`}>
                <Metric label="Voice Profiles" value={String(overview.profiles.length)} />
                <Metric label="Ready Profiles" value={String(overview.profiles.filter((p) => p.status === "ready").length)} />
                <Metric label="Jobs" value={String(overview.jobs.length)} />
              </div>
            </section>
          )}

          {section === "voiceProfiles" && (
            <section className="grid gap-6 xl:grid-cols-[1.05fr,0.95fr]">
              <div className={card}>
                <div className="flex items-center gap-3">
                  <Upload className="text-studio-ember" />
                  <h2 className="m-0 text-xl">Create Profile from Uploaded Audio</h2>
                </div>
                <div className="mt-5 space-y-4">
                  {profileBuildState && (
                    <div className="rounded-3xl bg-studio-fog/90 p-5">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="font-medium">Profile Build Progress</div>
                          <div className="mt-1 text-sm text-studio-ink/65">
                            {profileBuildState.error || profileBuildState.message}
                          </div>
                        </div>
                        <div className="text-sm font-medium">
                          {Math.round(
                            ((profileBuildState.uploadProgress * 0.35 + profileBuildState.processingProgress * 0.65) /
                              (profileBuildState.active || profileBuildState.processingProgress > 0 ? 1 : 1)) *
                              100,
                          )}
                          %
                        </div>
                      </div>
                      <div className="mt-4 space-y-3">
                        <ProgressBar label={`Upload: ${Math.round(profileBuildState.uploadProgress * 100)}%`} value={profileBuildState.uploadProgress} tone="lake" />
                        <ProgressBar
                          label={`${profileBuildState.step}: ${Math.round(profileBuildState.processingProgress * 100)}%`}
                          value={profileBuildState.processingProgress}
                          tone={profileBuildState.error ? "ember" : "ink"}
                        />
                      </div>
                    </div>
                  )}
                  <input className="w-full rounded-2xl border-0 bg-studio-fog px-4 py-3" placeholder="Profile name" value={profileDraft.name} onChange={(e) => setProfileDraft((c) => ({ ...c, name: e.target.value }))} />
                  <textarea className="min-h-24 w-full rounded-2xl border-0 bg-studio-fog px-4 py-3" placeholder="Description" value={profileDraft.description} onChange={(e) => setProfileDraft((c) => ({ ...c, description: e.target.value }))} />
                  <label className="block rounded-3xl border border-dashed border-studio-ink/20 bg-studio-fog/70 p-6 text-center">
                    <input
                      type="file"
                      multiple
                      accept=".wav,.mp3,.m4a,.flac,.ogg,audio/*"
                      className="hidden"
                      onChange={(e) => setPendingFiles(Array.from(e.target.files ?? []))}
                    />
                    <div className="font-medium">Drag files here or click to choose</div>
                    <div className="mt-2 text-sm text-studio-ink/60">Supported: WAV, MP3, M4A, FLAC, OGG</div>
                  </label>
                  <div className="space-y-3">
                    {pendingFiles.map((file) => (
                      <div key={file.name + file.size} className="rounded-2xl bg-studio-fog/80 p-4">
                        <div className="font-medium">{file.name}</div>
                        <div className="mt-1 text-xs text-studio-ink/55">{(file.size / 1024 / 1024).toFixed(2)} MB</div>
                        <audio controls className="mt-3 w-full" src={URL.createObjectURL(file)} />
                      </div>
                    ))}
                  </div>
                  <label className="flex items-center gap-3 text-sm">
                    <input type="checkbox" checked={profileDraft.authorizedUseConfirmed} onChange={(e) => setProfileDraft((c) => ({ ...c, authorizedUseConfirmed: e.target.checked }))} />
                    I confirm these samples are user-owned or authorized.
                  </label>
                  <button onClick={() => void createProfile()} className="rounded-2xl bg-studio-ink px-5 py-3 text-studio-fog">
                    Build Speaker Profile
                  </button>
                </div>
              </div>

              <div className={card}>
                <h2 className="m-0 text-xl">Saved Profiles</h2>
                <div className="mt-5 space-y-4">
                  {overview.profiles.map((profile) => (
                    <div key={profile.id} className="rounded-3xl bg-studio-fog/80 p-5">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <button className="font-medium underline-offset-2 hover:underline" onClick={() => setSelectedProfileId(profile.id)}>
                            {profile.name}
                          </button>
                          <div className="mt-1 text-sm text-studio-ink/65">{profile.description}</div>
                          <div className="mt-2 flex flex-wrap gap-2 text-xs">
                            <Badge>{profile.status}</Badge>
                            <Badge>{profile.synthesisProvider}</Badge>
                            <Badge>{profile.samples.length} samples</Badge>
                            <Badge>{profile.diagnostics.totalDurationSec.toFixed(1)}s</Badge>
                          </div>
                        </div>
                        <button className="text-sm text-red-700" onClick={() => void api.deleteProfile(profile.id).then(refresh)}>
                          Delete
                        </button>
                      </div>
                      <div className="mt-4 space-y-2">
                        {profile.diagnostics.warnings.slice(0, 2).map((warning) => (
                          <div key={warning} className="flex items-start gap-2 text-sm text-amber-800">
                            <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                            <span>{warning}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {selectedProfile && (
                <div className={`${card} xl:col-span-2`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="m-0 text-xl">{selectedProfile.name}</h2>
                      <div className="mt-2 text-sm text-studio-ink/65">
                        {selectedProfile.cloningCapable
                          ? "Profile-conditioned synthesis is active."
                          : selectedProfile.fallbackReason || "Generic fallback is active."}
                      </div>
                    </div>
                    <div className="flex gap-2 text-xs">
                      <Badge>{selectedProfile.status}</Badge>
                      <Badge>{Math.round(selectedProfile.diagnostics.qualityScore * 100)}% quality</Badge>
                    </div>
                  </div>
                  <div className="mt-5 grid gap-6 lg:grid-cols-2">
                    <div>
                      <div className="mb-3 text-sm font-medium">Source Samples</div>
                      <div className="space-y-3">
                        {selectedProfile.samples.map((sample) => (
                          <div key={sample.id} className="rounded-2xl bg-studio-fog/80 p-4">
                            <div className="font-medium">{sample.originalName}</div>
                            <div className="mt-1 text-xs text-studio-ink/55">
                              {sample.durationSec.toFixed(1)}s, {sample.sampleRate} Hz
                            </div>
                            <audio controls className="mt-3 w-full" src={api.mediaUrl(sample.processedPath)} />
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="space-y-4">
                      <div>
                        <div className="mb-3 text-sm font-medium">Quick Profile Preview</div>
                        {selectedProfile.quickPreviewAudioPath && (
                          <audio controls className="w-full" src={api.mediaUrl(selectedProfile.quickPreviewAudioPath)} />
                        )}
                      </div>
                      <div>
                        <div className="mb-3 text-sm font-medium">Profile Quality Notes</div>
                        <div className="space-y-2 text-sm text-studio-ink/70">
                          {selectedProfile.diagnostics.notes.map((note) => (
                            <div key={note}>{note}</div>
                          ))}
                          {selectedProfile.diagnostics.warnings.map((warning) => (
                            <div key={warning} className="text-amber-800">
                              {warning}
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </section>
          )}

          {(section === "textToSpeech" || section === "audioReplacement" || section === "videoReplacement") && (
            <section className="grid gap-6 xl:grid-cols-[1.2fr,0.8fr]">
              <div className={card}>
                <div className="flex items-center justify-between">
                  <h2 className="m-0 text-xl">
                    {section === "textToSpeech" ? "Text to Speech" : section === "audioReplacement" ? "Audio Replacement" : "Video Replacement"}
                  </h2>
                  <select className="rounded-2xl border-0 bg-studio-fog px-4 py-3" value={selectedProfileId} onChange={(e) => setSelectedProfileId(e.target.value)}>
                    <option value="">Select profile</option>
                    {overview.profiles.map((profile) => (
                      <option key={profile.id} value={profile.id}>
                        {profile.name}
                      </option>
                    ))}
                  </select>
                </div>

                {selectedProfile && (
                  <div className="mt-4 rounded-2xl bg-studio-fog/80 p-4 text-sm">
                    <div className="font-medium">{selectedProfile.name}</div>
                    <div className="mt-1 text-studio-ink/65">
                      Status: {selectedProfile.status}. Samples: {selectedProfile.samples.length}. Duration: {selectedProfile.diagnostics.totalDurationSec.toFixed(1)}s.
                    </div>
                    <div className="mt-1 text-studio-ink/65">
                      Requested: {selectedProfile.requestedProvider}. Active: {selectedProfile.synthesisProvider} {selectedProfile.cloningCapable ? "(speaker-conditioned)" : "(generic fallback)"}
                    </div>
                    {setupStatus?.xtts.available && selectedProfile.synthesisProvider === "xtts" && (
                      <div className="mt-2 text-emerald-700">XTTS neural cloning is active for this profile.</div>
                    )}
                    {selectedProfile.diagnostics.warnings[0] && (
                      <div className="mt-2 text-amber-800">{selectedProfile.diagnostics.warnings[0]}</div>
                    )}
                  </div>
                )}

                {section === "textToSpeech" ? (
                  <div className="mt-5 space-y-4">
                    {operationState && operationState.label === "Text to Speech" && (
                      <OperationCard state={operationState} />
                    )}
                    <textarea className="min-h-64 w-full rounded-3xl border-0 bg-studio-fog px-5 py-4" value={ttsText} onChange={(e) => setTtsText(e.target.value)} />
                    <button onClick={() => void synthesize()} className="rounded-2xl bg-studio-ink px-5 py-3 text-studio-fog">
                      Generate Profile-Based Speech
                    </button>
                    {setupStatus && (
                      <div className="rounded-2xl bg-studio-fog/80 p-4 text-sm text-studio-ink/70">
                        Neural backend: {setupStatus.activeTtsProvider === "xtts" ? "XTTS active" : `using ${setupStatus.activeTtsProvider}`}
                      </div>
                    )}
                    {generatedAudioPath && (
                      <div className="rounded-2xl bg-studio-fog/80 p-4">
                        <div className="mb-2 flex items-center gap-2 text-sm font-medium">
                          <PlayCircle size={18} />
                          Generated Preview
                        </div>
                        <audio controls className="w-full" src={api.mediaUrl(generatedAudioPath)} />
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="mt-5 space-y-4">
                    {inspectState && inspectState.kind === (section === "audioReplacement" ? "audio" : "video") && (
                      <div className="rounded-2xl bg-studio-fog/90 p-4">
                        <div className="mb-3 flex items-center justify-between">
                          <div className="font-medium">Segment Inspection</div>
                          <div className="text-sm font-medium">{Math.round(inspectState.progress * 100)}%</div>
                        </div>
                        <div className="mb-2 text-sm text-studio-ink/65">{inspectState.error || inspectState.message}</div>
                        <ProgressBar
                          label={inspectState.error ? "Inspection failed" : "Inspecting media"}
                          value={inspectState.progress}
                          tone={inspectState.error ? "ember" : "lake"}
                        />
                      </div>
                    )}
                    {operationState && operationState.label === (section === "audioReplacement" ? "Audio Replacement" : "Video Replacement") && (
                      <OperationCard state={operationState} />
                    )}
                    <input className="w-full rounded-2xl border-0 bg-studio-fog px-4 py-3 font-mono text-sm" placeholder={section === "audioReplacement" ? "Input audio path" : "Input video path"} value={mediaPath} onChange={(e) => setMediaPath(e.target.value)} />
                    <div className="flex gap-3">
                      <button onClick={() => void inspect(section === "audioReplacement" ? "audio" : "video")} className="rounded-2xl bg-studio-lake px-5 py-3 text-white">
                        Inspect Segments
                      </button>
                      <button onClick={() => void replaceMedia(section === "audioReplacement" ? "audio" : "video")} className="rounded-2xl bg-studio-ink px-5 py-3 text-studio-fog">
                        Run Replacement
                      </button>
                    </div>
                    {!!generatedAudioPath && section !== "videoReplacement" && (
                      <audio controls className="w-full" src={api.mediaUrl(generatedAudioPath)} />
                    )}
                    <div className="space-y-2">
                      {segments.map((segment) => (
                        <div key={segment.id} className="rounded-2xl bg-studio-fog/80 p-4 text-sm">
                          <div className="font-medium">{segment.startSec.toFixed(2)}s - {segment.endSec.toFixed(2)}s</div>
                          <div className="mt-1 text-studio-ink/65">{segment.text}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className={`${card} space-y-4`}>
                <Slider label="Speaking Rate" min={0.5} max={2} step={0.05} value={controls.speakingRate} onChange={(value) => setControls({ ...controls, speakingRate: value })} />
                <Slider label="Pitch" min={-12} max={12} step={1} value={controls.pitch} onChange={(value) => setControls({ ...controls, pitch: value })} />
                <Slider label="Intensity" min={0} max={1} step={0.05} value={controls.intensity} onChange={(value) => setControls({ ...controls, intensity: value })} />
                <Slider label="Expressiveness" min={0} max={1} step={0.05} value={controls.expressiveness} onChange={(value) => setControls({ ...controls, expressiveness: value })} />
                <Slider label="Pause Scale" min={0.5} max={2} step={0.05} value={controls.pauseScale} onChange={(value) => setControls({ ...controls, pauseScale: value })} />
                <label className="block">
                  <div className="mb-2 text-sm font-medium">Emotion Preset</div>
                  <select className="w-full rounded-2xl border-0 bg-studio-fog px-4 py-3" value={controls.emotion} onChange={(e) => setControls({ ...controls, emotion: e.target.value as SynthesisControls["emotion"] })}>
                    {["neutral", "warm", "excited", "serious", "sad", "calm", "energetic"].map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <div className="mb-2 text-sm font-medium">Speaking Style</div>
                  <input className="w-full rounded-2xl border-0 bg-studio-fog px-4 py-3" value={controls.style} onChange={(e) => setControls({ ...controls, style: e.target.value })} />
                </label>
              </div>
            </section>
          )}

          {section === "projects" && (
            <section className="grid gap-6 lg:grid-cols-2">
              <div className={card}>
                <h2 className="m-0 text-xl">Projects</h2>
                <div className="mt-5 space-y-3">
                  {overview.projects.map((project) => (
                    <div key={project.id} className="rounded-2xl bg-studio-fog/80 p-4">
                      <div className="font-medium">{project.name}</div>
                      <div className="mt-1 text-sm text-studio-ink/65">{project.kind}</div>
                      <div className="mt-1 text-xs text-studio-ink/50">{project.outputPath || "Output pending"}</div>
                      {project.outputPath?.endsWith(".wav") && <audio controls className="mt-3 w-full" src={api.mediaUrl(project.outputPath)} />}
                    </div>
                  ))}
                </div>
              </div>
              <div className={card}>
                <h2 className="m-0 text-xl">Jobs</h2>
                <div className="mt-5 space-y-3">
                  {overview.jobs.map((job) => (
                    <div key={job.id} className="rounded-2xl bg-studio-fog/80 p-4">
                      <div className="flex justify-between">
                        <div className="font-medium">{job.type}</div>
                        <div className="text-sm capitalize">{job.status}</div>
                      </div>
                      <div className="mt-1 text-sm text-studio-ink/65">{job.message || job.step}</div>
                      {job.logs.length > 0 && <div className="mt-2 text-xs text-studio-ink/50">{job.logs[0]}</div>}
                    </div>
                  ))}
                </div>
              </div>
            </section>
          )}

          {section === "settings" && overview.settings && (
            <section className="grid gap-6">
              <div className={`${card} grid gap-4 lg:grid-cols-2`}>
                <SelectSetting label="Device" value={overview.settings.device} options={["auto", "cpu", "cuda"]} onChange={(value) => void updateSetting("device", value)} />
                <SelectSetting label="Precision" value={overview.settings.precision} options={["fp32", "fp16", "int8"]} onChange={(value) => void updateSetting("precision", value)} />
                <SelectSetting label="TTS Provider" value={overview.settings.preferredTtsProvider} options={["xtts", "openvoice", "adaptive_clone", "fallback_generic"]} onChange={(value) => void updateSetting("preferredTtsProvider", value)} />
                <SelectSetting label="ASR Provider" value={overview.settings.preferredAsrProvider} options={["fallback", "faster-whisper"]} onChange={(value) => void updateSetting("preferredAsrProvider", value)} />
              </div>
              {setupStatus && (
                <div className={card}>
                  <h2 className="m-0 text-xl">Setup Status</h2>
                  <div className="mt-4 grid gap-4 lg:grid-cols-3">
                    <SetupCard title="Requested TTS" value={setupStatus.requestedTtsProvider} />
                    <SetupCard title="Active TTS" value={setupStatus.activeTtsProvider} />
                    <SetupCard title="FFmpeg" value={setupStatus.mediaTools.ffmpeg ? "available" : "missing"} />
                  </div>
                  {setupStatus.providerResolutionNote && (
                    <div className="mt-4 rounded-2xl bg-amber-50 p-4 text-sm text-amber-900">
                      {setupStatus.providerResolutionNote}
                    </div>
                  )}
                  <div className="mt-4 space-y-2 text-sm text-studio-ink/70">
                    <div>XTTS import: {setupStatus.xtts.importable ? "ready" : "not installed"}</div>
                    <div>XTTS active: {setupStatus.xtts.available ? "yes" : "no"}</div>
                    <div>XTTS license acceptance needed: {setupStatus.xtts.needsTosAcceptance ? "yes" : "no"}</div>
                    <div>OpenVoice import: {setupStatus.openvoice.importable ? "ready" : "not installed"}</div>
                    <div>ffprobe: {setupStatus.mediaTools.ffprobe ? "available" : "missing"}</div>
                  </div>
                  <div className="mt-4 rounded-2xl bg-studio-fog/80 p-4 text-sm text-studio-ink/70">
                    To keep XTTS active across normal backend runs, set <code>COQUI_TOS_AGREED=1</code> in your local backend environment after accepting Coqui&apos;s terms.
                  </div>
                </div>
              )}
            </section>
          )}
        </main>
      </div>
    </div>
  );
}

function Metric(props: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-studio-fog/80 p-4">
      <div className="text-sm text-studio-ink/60">{props.label}</div>
      <div className="mt-1 font-display text-4xl">{props.value}</div>
    </div>
  );
}

function Slider(props: { label: string; min: number; max: number; step: number; value: number; onChange: (value: number) => void }) {
  return (
    <label className="block">
      <div className="mb-2 flex justify-between text-sm font-medium">
        <span>{props.label}</span>
        <span>{props.value}</span>
      </div>
      <input className="w-full" type="range" min={props.min} max={props.max} step={props.step} value={props.value} onChange={(e) => props.onChange(Number(e.target.value))} />
    </label>
  );
}

function SelectSetting(props: { label: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <div className="mb-2 text-sm font-medium">{props.label}</div>
      <select className="w-full rounded-2xl border-0 bg-studio-fog px-4 py-3" value={props.value} onChange={(e) => props.onChange(e.target.value)}>
        {props.options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function Badge(props: { children: ReactNode }) {
  return <span className="rounded-full bg-studio-ink px-3 py-1 text-studio-fog">{props.children}</span>;
}

function SetupCard(props: { title: string; value: string }) {
  return (
    <div className="rounded-2xl bg-studio-fog/80 p-4">
      <div className="text-sm text-studio-ink/60">{props.title}</div>
      <div className="mt-1 font-medium">{props.value}</div>
    </div>
  );
}

function OperationCard(props: {
  state: {
    label: string;
    progress: number;
    step: string;
    message: string;
    error?: string;
  };
}) {
  return (
    <div className="rounded-2xl bg-studio-fog/90 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="font-medium">{props.state.label} Progress</div>
        <div className="text-sm font-medium">{Math.round(props.state.progress * 100)}%</div>
      </div>
      <div className="mb-2 text-sm text-studio-ink/65">{props.state.error || props.state.message}</div>
      <ProgressBar
        label={props.state.step}
        value={props.state.progress}
        tone={props.state.error ? "ember" : "ink"}
      />
    </div>
  );
}

function ProgressBar(props: { label: string; value: number; tone: "lake" | "ink" | "ember" }) {
  const toneClass =
    props.tone === "lake" ? "bg-studio-lake" : props.tone === "ember" ? "bg-studio-ember" : "bg-studio-ink";

  return (
    <div>
      <div className="mb-2 flex justify-between text-sm font-medium">
        <span>{props.label}</span>
        <span>{Math.round(props.value * 100)}%</span>
      </div>
      <div className="h-3 overflow-hidden rounded-full bg-white/70">
        <div className={`h-full rounded-full transition-all duration-300 ${toneClass}`} style={{ width: `${Math.max(4, props.value * 100)}%` }} />
      </div>
    </div>
  );
}
