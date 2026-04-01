import {
  defaultSynthesisControls,
  type AppSection,
  type AppSettings,
  type JobRecord,
  type ProjectRecord,
  type SynthesisControls,
  type TranscriptSegment,
  type VoiceProfile,
} from "@voice-studio/shared";
import {
  AudioLines,
  Clapperboard,
  FolderKanban,
  House,
  Mic2,
  Settings2,
  Sparkles,
  Waves,
} from "lucide-react";
import { useEffect, useState } from "react";
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
  const [controls, setControls] = useState<SynthesisControls>(defaultSynthesisControls);
  const [selectedProfileId, setSelectedProfileId] = useState("");
  const [ttsText, setTtsText] = useState("This is the first expressive synthesis pass from Voice Studio.");
  const [mediaPath, setMediaPath] = useState("");
  const [segments, setSegments] = useState<TranscriptSegment[]>([]);
  const [status, setStatus] = useState("Ready");
  const [profileDraft, setProfileDraft] = useState({
    name: "",
    description: "",
    samplePaths: "",
    authorizedUseConfirmed: true,
  });

  const refresh = async () => {
    const data = await api.getOverview();
    setOverview(data);
    if (!selectedProfileId && data.profiles[0]) {
      setSelectedProfileId(data.profiles[0].id);
    }
  };

  useEffect(() => {
    void refresh();
    const interval = window.setInterval(() => void refresh(), 4000);
    return () => window.clearInterval(interval);
  }, []);

  const createProfile = async () => {
    const created = await api.createProfile({
      ...profileDraft,
      samplePaths: profileDraft.samplePaths.split("\n").map((x) => x.trim()).filter(Boolean),
    });
    setStatus(`Created profile ${created.name}`);
    setSelectedProfileId(created.id);
    setProfileDraft({ name: "", description: "", samplePaths: "", authorizedUseConfirmed: true });
    await refresh();
  };

  const synthesize = async () => {
    if (!selectedProfileId) return;
    const job = await api.synthesize({ text: ttsText, profileId: selectedProfileId, controls });
    setStatus(`Queued synthesis job ${job.id}`);
    setSection("projects");
  };

  const inspect = async (kind: "audio" | "video") => {
    const found = await api.inspectSegments(kind, mediaPath);
    setSegments(found);
    setStatus(`Loaded ${found.length} segments`);
  };

  const replaceMedia = async (kind: "audio" | "video") => {
    if (!selectedProfileId) return;
    const job =
      kind === "audio"
        ? await api.replaceAudio({ inputPath: mediaPath, profileId: selectedProfileId, controls })
        : await api.replaceVideo({ inputPath: mediaPath, profileId: selectedProfileId, controls });
    setStatus(`Queued ${kind} job ${job.id}`);
    setSection("projects");
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
              Creator-grade desktop workflow for authorized voice synthesis and dubbing.
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
            Uploaded voice samples must be owned by you or used with explicit authorization.
          </div>
        </aside>

        <main className="flex-1 space-y-6">
          <header className={`${card} flex items-center justify-between`}>
            <div>
              <div className="font-display text-4xl">High-quality local dubbing pipeline</div>
              <p className="mt-2 max-w-3xl text-sm text-studio-ink/65">
                Expressive controls, reusable voice profiles, job tracking, and modular providers ready for stronger open-source model stacks.
              </p>
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
                      <div className="mt-2 text-sm text-studio-ink/65">{job.step}</div>
                    </div>
                  ))}
                </div>
              </div>
              <div className={`${card} space-y-4`}>
                <Metric label="Voice Profiles" value={String(overview.profiles.length)} />
                <Metric label="Projects" value={String(overview.projects.length)} />
                <Metric label="Jobs" value={String(overview.jobs.length)} />
              </div>
            </section>
          )}

          {section === "voiceProfiles" && (
            <section className="grid gap-6 lg:grid-cols-2">
              <div className={card}>
                <h2 className="m-0 text-xl">Create Profile</h2>
                <div className="mt-5 space-y-4">
                  <input className="w-full rounded-2xl border-0 bg-studio-fog px-4 py-3" placeholder="Profile name" value={profileDraft.name} onChange={(e) => setProfileDraft((c) => ({ ...c, name: e.target.value }))} />
                  <textarea className="min-h-24 w-full rounded-2xl border-0 bg-studio-fog px-4 py-3" placeholder="Description" value={profileDraft.description} onChange={(e) => setProfileDraft((c) => ({ ...c, description: e.target.value }))} />
                  <textarea className="min-h-40 w-full rounded-2xl border-0 bg-studio-fog px-4 py-3 font-mono text-sm" placeholder={"One sample path per line\nD:\\media\\voice\\sample.wav"} value={profileDraft.samplePaths} onChange={(e) => setProfileDraft((c) => ({ ...c, samplePaths: e.target.value }))} />
                  <label className="flex items-center gap-3 text-sm">
                    <input type="checkbox" checked={profileDraft.authorizedUseConfirmed} onChange={(e) => setProfileDraft((c) => ({ ...c, authorizedUseConfirmed: e.target.checked }))} />
                    I confirm these samples are user-owned or authorized.
                  </label>
                  <button onClick={() => void createProfile()} className="rounded-2xl bg-studio-ink px-5 py-3 text-studio-fog">
                    Create Voice Profile
                  </button>
                </div>
              </div>
              <div className={card}>
                <h2 className="m-0 text-xl">Saved Profiles</h2>
                <div className="mt-5 space-y-3">
                  {overview.profiles.map((profile) => (
                    <div key={profile.id} className="rounded-2xl bg-studio-fog/80 p-4">
                      <div className="flex justify-between gap-3">
                        <div>
                          <div className="font-medium">{profile.name}</div>
                          <div className="mt-1 text-sm text-studio-ink/65">{profile.description}</div>
                        </div>
                        <button className="text-sm text-red-700" onClick={() => void api.deleteProfile(profile.id).then(refresh)}>
                          Delete
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
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

                {section === "textToSpeech" ? (
                  <div className="mt-5 space-y-4">
                    <textarea className="min-h-64 w-full rounded-3xl border-0 bg-studio-fog px-5 py-4" value={ttsText} onChange={(e) => setTtsText(e.target.value)} />
                    <button onClick={() => void synthesize()} className="rounded-2xl bg-studio-ink px-5 py-3 text-studio-fog">
                      Generate Speech
                    </button>
                  </div>
                ) : (
                  <div className="mt-5 space-y-4">
                    <input className="w-full rounded-2xl border-0 bg-studio-fog px-4 py-3 font-mono text-sm" placeholder={section === "audioReplacement" ? "Input audio path" : "Input video path"} value={mediaPath} onChange={(e) => setMediaPath(e.target.value)} />
                    <div className="flex gap-3">
                      <button onClick={() => void inspect(section === "audioReplacement" ? "audio" : "video")} className="rounded-2xl bg-studio-lake px-5 py-3 text-white">
                        Inspect Segments
                      </button>
                      <button onClick={() => void replaceMedia(section === "audioReplacement" ? "audio" : "video")} className="rounded-2xl bg-studio-ink px-5 py-3 text-studio-fog">
                        Run Replacement
                      </button>
                    </div>
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
                      <div className="mt-1 text-sm text-studio-ink/65">{job.step}</div>
                      <div className="mt-1 text-xs text-studio-ink/50">{job.outputPath || job.message}</div>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          )}

          {section === "settings" && overview.settings && (
            <section className={`${card} grid gap-4 lg:grid-cols-2`}>
              <SelectSetting label="Device" value={overview.settings.device} options={["auto", "cpu", "cuda"]} onChange={(value) => void updateSetting("device", value)} />
              <SelectSetting label="Precision" value={overview.settings.precision} options={["fp32", "fp16", "int8"]} onChange={(value) => void updateSetting("precision", value)} />
              <SelectSetting label="TTS Provider" value={overview.settings.preferredTtsProvider} options={["fallback", "xtts", "styletts2", "f5tts"]} onChange={(value) => void updateSetting("preferredTtsProvider", value)} />
              <SelectSetting label="ASR Provider" value={overview.settings.preferredAsrProvider} options={["fallback", "faster-whisper"]} onChange={(value) => void updateSetting("preferredAsrProvider", value)} />
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
