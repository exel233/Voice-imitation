import { z } from "zod";

export const appSectionSchema = z.enum([
  "dashboard",
  "voiceProfiles",
  "textToSpeech",
  "audioReplacement",
  "videoReplacement",
  "projects",
  "settings",
]);

export const emotionPresetSchema = z.enum([
  "neutral",
  "warm",
  "excited",
  "serious",
  "sad",
  "calm",
  "energetic",
]);

export const synthesisControlsSchema = z.object({
  emotion: emotionPresetSchema.default("neutral"),
  style: z.string().default("natural"),
  speakingRate: z.number().min(0.5).max(2).default(1),
  pitch: z.number().min(-12).max(12).default(0),
  intensity: z.number().min(0).max(1).default(0.5),
  expressiveness: z.number().min(0).max(1).default(0.5),
  pauseScale: z.number().min(0.5).max(2).default(1),
  emphasis: z.array(z.string()).default([]),
});

export const voiceProfileSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().default(""),
  tags: z.array(z.string()).default([]),
  createdAt: z.string(),
  updatedAt: z.string(),
  sampleIds: z.array(z.string()).default([]),
  previewAudioPath: z.string().optional(),
  authorizedUseConfirmed: z.boolean().default(false),
  metadata: z.record(z.string(), z.any()).default({}),
});

export const projectSchema = z.object({
  id: z.string(),
  name: z.string(),
  kind: z.enum(["tts", "audioReplacement", "videoReplacement"]),
  createdAt: z.string(),
  updatedAt: z.string(),
  profileId: z.string().optional(),
  sourceMediaPath: z.string().optional(),
  outputPath: z.string().optional(),
  settings: z.record(z.string(), z.any()).default({}),
});

export const jobSchema = z.object({
  id: z.string(),
  type: z.string(),
  status: z.enum(["queued", "running", "completed", "failed", "cancelled"]),
  progress: z.number().min(0).max(1).default(0),
  step: z.string().default("Queued"),
  message: z.string().default(""),
  logs: z.array(z.string()).default([]),
  createdAt: z.string(),
  updatedAt: z.string(),
  projectId: z.string().optional(),
  outputPath: z.string().optional(),
});

export const settingsSchema = z.object({
  backendUrl: z.string().default("http://127.0.0.1:8765"),
  device: z.enum(["cpu", "cuda", "auto"]).default("auto"),
  precision: z.enum(["fp32", "fp16", "int8"]).default("fp32"),
  storageRoot: z.string().default("storage"),
  enableDenoise: z.boolean().default(true),
  enableSourceSeparation: z.boolean().default(true),
  preferredTtsProvider: z.string().default("fallback"),
  preferredAsrProvider: z.string().default("fallback"),
  preferredVcProvider: z.string().default("fallback"),
});

export const transcriptSegmentSchema = z.object({
  id: z.string(),
  startSec: z.number(),
  endSec: z.number(),
  text: z.string(),
  speaker: z.string().optional(),
});

export type AppSection = z.infer<typeof appSectionSchema>;
export type SynthesisControls = z.infer<typeof synthesisControlsSchema>;
export type VoiceProfile = z.infer<typeof voiceProfileSchema>;
export type ProjectRecord = z.infer<typeof projectSchema>;
export type JobRecord = z.infer<typeof jobSchema>;
export type AppSettings = z.infer<typeof settingsSchema>;
export type TranscriptSegment = z.infer<typeof transcriptSegmentSchema>;

export const defaultSynthesisControls = synthesisControlsSchema.parse({});
