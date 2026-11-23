#!/usr/bin/env python3
"""Build one episode: episode.json -> voices -> timeline -> frames -> final MP4.

Usage: python3 scripts/build.py episodes/day-001 [--preview]
  --preview  only render 3 still frames (fast check) instead of the full video
Output: <episode>/out/final.mp4 (+ timeline.json, audio.wav, stills)
"""
import json, math, re, subprocess, sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
FPS, W, H, SR = 30, 1080, 1920, 24000
_kokoro = None


def kokoro():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        _kokoro = Kokoro(str(ROOT / "models/kokoro-v1.0.int8.onnx"), str(ROOT / "models/voices-v1.0.bin"))
    return _kokoro


def tts(text, voice, speed):
    audio, sr = kokoro().create(text, voice=voice, speed=speed, lang="en-us")
    assert sr == SR
    # trim leading/trailing silence
    idx = np.where(np.abs(audio) > 0.01)[0]
    if len(idx):
        audio = audio[max(0, idx[0] - 600): idx[-1] + 1200]
    return audio.astype(np.float32)


def mouth_envelope(audio, n_frames):
    hop = SR / FPS
    env = []
    for i in range(n_frames):
        seg = audio[int(i * hop): int((i + 1) * hop)]
        env.append(float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0)
    env = np.array(env)
    ref = np.percentile(env, 90) if env.max() > 0 else 1
    env = np.clip(env / (ref + 1e-6), 0, 1)
    env = np.where(env < 0.18, 0, env)
    # alternate open/close so it reads as talking, not a held-open mouth
    wobble = 0.65 + 0.35 * np.abs(np.sin(np.arange(n_frames) * 1.9))
    return [round(float(v), 3) for v in env * wobble]


def chunk_captions(text, start_frame, n_frames, max_chars=18):
    words = text.split()
    chunks, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            chunks.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
        if re.search(r"[.!?,]$", w) and len(cur) > 8:
            chunks.append(cur); cur = ""
    if cur:
        chunks.append(cur)
    total = sum(len(c) + 3 for c in chunks)
    out, f = [], start_frame
    for c in chunks:
        d = max(8, round(n_frames * (len(c) + 3) / total))
        out.append({"start_frame": f, "end_frame": min(start_frame + n_frames, f + d), "text": c.rstrip(",")})
        f += d
    return out


# ---------- synthesized audio (no stock assets) ----------
def env_adsr(n, a=0.005, r=0.25):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t / r)


def music_bed(seconds, bpm=104):
    """Light, bouncy loop: bass + plucked arpeggio over I-V-vi-IV in C."""
    n = int(seconds * SR) + SR
    out = np.zeros(n, np.float32)
    beat = 60 / bpm
    chords = [[60, 64, 67], [55, 59, 62], [57, 60, 64], [53, 57, 60]]
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    t_beat, i = 0.0, 0
    while t_beat < seconds + 1:
        ch = chords[(i // 4) % 4]
        s = int(t_beat * SR)
        if i % 2 == 0:  # bass on every other beat
            L = int(beat * 1.8 * SR)
            tt = np.arange(L) / SR
            out[s:s + L] += (0.22 * np.sign(np.sin(2 * np.pi * hz(ch[0] - 24) * tt)) * env_adsr(L, 0.01, 0.25))[: n - s]
        for k in range(2):  # two eighth-note plucks per beat
            ss = int((t_beat + k * beat / 2) * SR)
            L = int(0.35 * SR)
            tt = np.arange(L) / SR
            note = ch[(i * 2 + k) % 3] + 12
            tone = np.sin(2 * np.pi * hz(note) * tt) + 0.3 * np.sin(4 * np.pi * hz(note) * tt)
            seg = (0.12 * tone * env_adsr(L, 0.003, 0.09)).astype(np.float32)
            out[ss:ss + L] += seg[: max(0, n - ss)]
        if i % 2 == 1:  # soft hat
            L = int(0.05 * SR)
            out[s:s + L] += (0.05 * np.random.default_rng(i).standard_normal(L) * env_adsr(L, 0.001, 0.015))[: n - s]
        t_beat += beat; i += 1
    return out[: int(seconds * SR)]


def sfx_poof():
    L = int(0.7 * SR); rng = np.random.default_rng(1)
    noise = rng.standard_normal(L)
    k = np.ones(40) / 40
    lp = np.convolve(noise, k, mode="same")
    return (0.9 * lp * env_adsr(L, 0.01, 0.18)).astype(np.float32)


def sfx_sparkle():
    L = int(1.0 * SR); out = np.zeros(L, np.float32)
    for j, f in enumerate([1568, 2093, 2637, 3136, 4186]):
        s = int(j * 0.07 * SR); l = L - s; tt = np.arange(l) / SR
        out[s:] += (0.18 * np.sin(2 * np.pi * f * tt) * env_adsr(l, 0.002, 0.18)).astype(np.float32)
    return out


def sfx_pop():
    L = int(0.12 * SR); tt = np.arange(L) / SR
    f = 900 * np.exp(-tt * 25) + 200
    return (0.5 * np.sin(2 * np.pi * np.cumsum(f) / SR) * env_adsr(L, 0.001, 0.04)).astype(np.float32)


def mix_into(buf, clip, at_sec, gain=1.0):
    s = int(at_sec * SR)
    e = min(len(buf), s + len(clip))
    if e > s:
        buf[s:e] += clip[: e - s] * gain


# ---------- main ----------
def build(ep_dir: Path, preview=False):
    bible = json.loads((ROOT / "series/bible.json").read_text())
    story = json.loads((ROOT / "series/story.json").read_text())
    ep = json.loads((ep_dir / "episode.json").read_text())
    out = ep_dir / "out"; out.mkdir(exist_ok=True)
    voices = bible["voices"]

    # cast: theo (current state) + recurring characters + cameo guests
    cast = {"theo": dict(story["theo_state"])}
    for who in ("deb", "brett", "nina"):
        cast[who] = bible["cast"][who]["state"]
    guests = {}
    for key, g in (ep.get("cast") or {}).items():
        guests[key] = g  # {"username": "@x", "role": "doctor", "voice": "guest_f"}

    intro = 0.35
    t = intro
    scenes, voice_clips = [], []
    for sc in ep["scenes"]:
        speaker = sc.get("speaker", "narrator")
        if speaker in guests:
            vkey = guests[speaker].get("voice", "guest_m")
        else:
            vkey = speaker if speaker in voices else "narrator"
        v = voices[vkey]
        audio = tts(sc["say"], v["voice"], v["speed"])
        dur = len(audio) / SR
        tail = 0.28
        tr = None
        if sc.get("transform"):
            tail = 1.6
            tr = dict(sc["transform"])
        start_f = round(t * FPS)
        speak_frames = math.ceil(dur * FPS)
        end_f = round((t + dur + tail) * FPS)
        scene = {
            "start_frame": start_f, "end_frame": end_f, "bg": sc.get("bg", "studio"), "speaker": speaker,
            "theo": sc.get("theo", {}), "others": sc.get("others", []), "prop": sc.get("prop"),
            "captions": chunk_captions(sc["say"], start_f, speak_frames),
            "mouth": mouth_envelope(audio, end_f - start_f),
        }
        if tr:
            tr["frame"] = start_f + speak_frames + 4
            scene["transform"] = tr
        scenes.append(scene)
        voice_clips.append((t, audio))
        t += dur + tail

    cta_len = 2.6
    total = t + cta_len
    scenes[-1]["end_frame"] = round(total * FPS)
    scenes[-1]["mouth"] += [0] * (scenes[-1]["end_frame"] - scenes[-1]["start_frame"] - len(scenes[-1]["mouth"]))

    # resolve cameo guests into cast
    import subprocess as sp
    for key, g in guests.items():
        js = (f"const c=require('{ROOT}/render/character.js');"
              f"console.log(JSON.stringify(c.guestState({json.dumps(g['username'])},{json.dumps(g.get('role',''))},{json.dumps(bible['role_outfits'])})))")
        st = json.loads(sp.check_output(["node", "-e", js]))
        tag = g["username"] if len(g["username"]) <= 18 else g["username"][:17] + "…"
        st["tag"] = tag
        cast[key] = st

    tl = {
        "fps": FPS, "width": W, "height": H, "total_frames": round(total * FPS),
        "day": ep["day"], "title": ep["title"], "accent": ep.get("accent", "#7cfc5a"),
        "days_left": 101 - ep["day"],
        "credit": f"TOP COMMENT: {ep['chosen_comment']['author']}" if ep.get("chosen_comment") else None,
        "cta": {"start_frame": round((total - cta_len) * FPS), "lines": ep.get("cta", ["TOP COMMENT DECIDES", f"DAY {ep['day'] + 1}"])},
        "cast": cast, "scenes": scenes,
    }
    (out / "timeline.json").write_text(json.dumps(tl))

    if preview:
        for name, f in [("hook", 12), ("mid", scenes[len(scenes) // 2]["start_frame"] + 20), ("cta", tl["total_frames"] - 10)]:
            subprocess.run(["node", str(ROOT / "render/render.mjs"), str(out / "timeline.json"), "-", "--still", str(f), str(out / f"still-{name}.png")], check=True)
        print("stills ->", out)
        return

    # audio mix
    n = int(total * SR) + SR
    mixbuf = np.zeros(n, np.float32)
    mixbuf[: int(total * SR)] += music_bed(total) * 0.28
    for at, a in voice_clips:
        mix_into(mixbuf, a, at, 1.0)
    mix_into(mixbuf, sfx_pop(), 0.05, 0.8)
    for sc in scenes:
        if sc.get("transform"):
            at = sc["transform"]["frame"] / FPS
            mix_into(mixbuf, sfx_poof(), at - 0.15, 0.7)
            mix_into(mixbuf, sfx_sparkle(), at + 0.1, 0.8)
    mix_into(mixbuf, sfx_pop(), (total - cta_len), 0.8)
    mixbuf = mixbuf[: int(total * SR)]
    mixbuf /= max(1.0, float(np.max(np.abs(mixbuf))) / 0.95)
    sf.write(out / "audio.wav", mixbuf, SR)

    silent = out / "video_silent.mp4"
    subprocess.run(["node", str(ROOT / "render/render.mjs"), str(out / "timeline.json"), str(silent)], check=True)
    final = out / "final.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(out / "audio.wav"),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-shortest", "-movflags", "+faststart", str(final)], check=True)
    silent.unlink()
    print(f"FINAL -> {final}  ({total:.1f}s)")


if __name__ == "__main__":
    build(Path(sys.argv[1]).resolve(), preview="--preview" in sys.argv)
