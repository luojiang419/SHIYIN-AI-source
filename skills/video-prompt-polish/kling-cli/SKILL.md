---
name: kling-cli-prompt-writing
description: Rewrite prompts for Kling VIDEO 3.0 and VIDEO 3.0 Omni using the latest official Kling prompt syntax and reference-tag guidance.
source_status: official-guide-derived-adapter
---

# Kling VIDEO 3.0 / 3.0 Omni Prompt Writing

This is the project's local adapter for the latest publicly available Kling official prompt guides. It is not a claim that Kling publishes a standalone downloadable `SKILL.md` package.

## Mode selection

- **Text-to-Video**: write a concise scene direction with subject, environment, visible action, camera, lighting, mood, and optional audio.
- **Image-to-Video / start frame**: treat the supplied image as the visual fact and describe only how the scene evolves from it.
- **Start-and-end frames**: describe the continuous transition between the two supplied frames.
- **Multi-Shot / Custom Multi-Shot**: organize the prompt as `Shot 1`, `Shot 2`, etc.; each shot gets duration when known, framing, perspective, subject action, and one main camera move.
- **Omni reference workflow**: preserve the role of every element, image, video, and voice reference across all shots.

## Prompt order

Use this order unless the user's wording requires otherwise:

`[scene/environment] + [subject and visible appearance] + [action timeline] + [camera/framing] + [lighting/mood] + [audio/dialogue] + [technical constraints]`

Describe what the audience can see and hear. Use concrete motion verbs and real light sources. Keep one primary camera move per shot; avoid contradictory or overloaded movement instructions. A short prompt is preferred when the user supplied only a camera instruction.

## Latest official Omni reference syntax

Use the exact triple-angle tags when the selected Kling workflow supports Omni references:

- `<<<element_1>>>` — character, product, prop, or recurring subject identity.
- `<<<image_1>>>` — reference image, style, composition, or starting frame.
- `<<<video_1>>>` — motion or video-element reference.
- `<<<voice_1>>>` — voice binding for a referenced character.

Keep tag numbering and meaning stable. Do not invent a tag that is not backed by an input asset. Preserve the user's existing asset references when they are already present.

## Camera and physical motion

Prefer official plain-language directions such as `push in`, `pull back`, `pan left/right`, `tilt up/down`, `track`, `orbit`, or `static camera`, tied to a subject or reveal purpose. State speed and stability only when useful. For physics, describe visible cause and effect (gravity, collision, fluid, fabric, smoke) rather than abstract claims.

## Native audio and dialogue

Kling VIDEO 3.0 / 3.0 Omni can combine visuals, dialogue, ambience, and sound effects. Keep speaker label, line, language, and delivery together; preserve exact user dialogue. Do not add dialogue or music that the user did not request.

## User-intent guardrails

Do not change the user's subject, action, camera direction, timing, emotion, dialogue, negative constraints, or reference role. Infer only the minimum visual context needed to execute an underspecified instruction. Output only the final Kling-ready prompt, with no analysis, title, or Markdown fence.

