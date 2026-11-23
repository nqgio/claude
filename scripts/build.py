#!/usr/bin/env python3
"""Build one episode: episode.json -> voices -> timeline -> frames -> final MP4.

Usage: python3 scripts/build.py channels/<channel>/episodes/day-001 [--preview]
  --preview  only render 3 still frames (fast check) instead of the full video
Output: <episode>/out/final.mp4 (+ timeline.json, audio.wav, stills)
The channel folder (two levels up) holds channel.json, bible.json (voices etc.) and story.json.
"""
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding="utf-8"); _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
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
        _kokoro = Kokoro(str(ROOT / "models/kokoro-v1.0.onnx"), str(ROOT / "models/voices-v1.0.bin"))
    return _kokoro


def voice_style(spec):
    """'am_michael' or a blend like 'am_michael:0.6,am_puck:0.4' (keeps the first voice's sound, borrows the others' flow)."""
    if ":" not in spec:
        return spec
    parts = [p.split(":") for p in spec.split(",")]
    total = sum(float(w) for _, w in parts)
    return sum(float(w) / total * kokoro().get_voice_style(v.strip()) for v, w in parts)


# Words spelled the same but pronounced differently; flagged at build time so the phonemes can be checked.
HETERONYMS = {"live", "lives", "read", "lead", "leads", "tear", "tears", "wind", "close", "bass", "wound", "record",
              "present", "object", "minute", "bow", "row", "dove", "desert", "use", "excuse", "content", "invalid",
              "produce", "refuse", "polish", "sow", "moped", "wound", "separate", "permit", "conduct", "subject"}


def apply_pronunciations(text, fixes):
    """fixes: {"word or phrase": "respelling"} applied to the spoken text only (captions keep the original)."""
    for src, dst in (fixes or {}).items():
        text = re.sub(rf"\b{re.escape(src)}\b", dst, text, flags=re.I)
    return text


def check_heteronyms(text):
    hits = [w for w in re.findall(r"[A-Za-z']+", text) if w.lower() in HETERONYMS]
    if hits:
        print(f"  pronunciation check {hits}: {kokoro().tokenizer.phonemize(text, 'en-us')}")


def tts(text, voice, speed):
    audio, sr = kokoro().create(text, voice=voice_style(voice), speed=speed, lang="en-us")
    assert sr == SR
    # trim leading/trailing silence
    idx = np.where(np.abs(audio) > 0.01)[0]
    if len(idx):
        audio = audio[max(0, idx[0] - 600): idx[-1] + 1200]
    return audio.astype(np.float32)


POLISH_CHAIN = ("highpass=f=70,equalizer=f=180:t=q:w=1:g=2.5,"
                "acompressor=threshold=-22dB:ratio=2.5:attack=8:release=150:makeup=1.5")
# NOTE: never add short echoes/reverb (aecho) to voices: it makes them sound metallic/robotic.


def polish(audio):
    """Optional gentle polish (voices with "polish": true): high-pass, warmth EQ, light compression. No echo."""
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        i, o = os.path.join(d, "i.wav"), os.path.join(d, "o.wav")
        sf.write(i, audio, SR)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", i, "-af", POLISH_CHAIN, o], check=True)
        return sf.read(o, dtype="float32")[0]


def tighten_pauses(audio, max_pause=0.07, floor_db=-38):
    """Shorten silences between words/phrases so narration flows continuously (no audio effects applied)."""
    hop = int(0.005 * SR)
    n = len(audio) // hop
    if n == 0:
        return audio
    frames = audio[: n * hop].reshape(n, hop)
    db = 20 * np.log10(np.sqrt(np.mean(frames ** 2, axis=1)) + 1e-7)
    quiet = db < (db.max() + floor_db)
    keep = int(max_pause / 0.005)
    out, i = [], 0
    while i < n:
        j = i
        while j < n and quiet[j] == quiet[i]:
            j += 1
        seg = frames[i:j].reshape(-1)
        if quiet[i] and (j - i) > keep:
            half = keep * hop // 2
            seg = np.concatenate([seg[:half], seg[-half:]])
        out.append(seg)
        i = j
    return np.concatenate(out + [audio[n * hop:]]).astype(np.float32)


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


def sfx_ding():
    L = int(0.35 * SR); tt = np.arange(L) / SR
    tone = np.sin(2 * np.pi * 1318 * tt) * (tt < 0.09) + np.sin(2 * np.pi * 1760 * tt) * (tt >= 0.09)
    return (0.35 * tone * np.exp(-tt * 9)).astype(np.float32)


def sfx_pop():
    L = int(0.12 * SR); tt = np.arange(L) / SR
    f = 900 * np.exp(-tt * 25) + 200
    return (0.5 * np.sin(2 * np.pi * np.cumsum(f) / SR) * env_adsr(L, 0.001, 0.04)).astype(np.float32)


def mix_into(buf, clip, at_sec, gain=1.0):
    s = int(at_sec * SR)
    e = min(len(buf), s + len(clip))
    if e > s:
        buf[s:e] += clip[: e - s] * gain


def music_dark(seconds):
    """Low drone + slow heartbeat-like pulse + sparse high notes (horror)."""
    n = int(seconds * SR); tt = np.arange(n) / SR
    out = 0.10 * np.sin(2 * np.pi * 55 * tt) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.11 * tt))
    out += 0.06 * np.sin(2 * np.pi * 58.3 * tt)  # beating dissonance
    out += 0.03 * np.sin(2 * np.pi * 110 * tt + np.sin(2 * np.pi * 0.3 * tt))
    rng = np.random.default_rng(7)
    for t0 in np.arange(1.0, seconds, 4.3):
        L = int(2.5 * SR); s = int(t0 * SR); f = rng.choice([622, 740, 659, 880])
        seg = 0.05 * np.sin(2 * np.pi * f * np.arange(L) / SR) * env_adsr(L, 0.3, 0.9)
        out[s:s + L] += seg[: n - s]
    return out.astype(np.float32)


def music_tense(seconds, bpm=118):
    """Pulsing bass ostinato + ticking hats (crime / thriller)."""
    n = int(seconds * SR) + SR; out = np.zeros(n, np.float32)
    beat = 60 / bpm; hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    pattern = [40, 40, 43, 40, 40, 38, 40, 35]
    t, i = 0.0, 0
    while t < seconds + 1:
        s = int(t * SR); L = int(beat / 2 * 0.9 * SR); tt = np.arange(L) / SR
        f = hz(pattern[i % 8])
        seg = 0.16 * (np.sign(np.sin(2 * np.pi * f * tt)) * 0.5 + np.sin(2 * np.pi * f * tt)) * env_adsr(L, 0.005, 0.12)
        out[s:s + L] += seg[: n - s]
        Lh = int(0.03 * SR)
        out[s:s + Lh] += (0.04 * np.random.default_rng(i).standard_normal(Lh) * env_adsr(Lh, 0.001, 0.01))[: n - s]
        if i % 8 == 0:
            Lk = int(0.25 * SR); tk = np.arange(Lk) / SR
            out[s:s + Lk] += (0.35 * np.sin(2 * np.pi * (50 + 80 * np.exp(-tk * 30)) * tk) * np.exp(-tk * 12))[: n - s]
        t += beat / 2; i += 1
    return out[: int(seconds * SR)]


def music_calm(seconds, bpm=84):
    """Music-box arpeggio over soft pad (explainer)."""
    n = int(seconds * SR) + SR; out = np.zeros(n, np.float32)
    beat = 60 / bpm; hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    chords = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]  # Am F C G
    t, i = 0.0, 0
    while t < seconds + 1:
        ch = chords[(i // 8) % 4]
        if i % 8 == 0:
            L = int(beat * 4 * SR); tt = np.arange(L) / SR; s = int(t * SR)
            pad = sum(np.sin(2 * np.pi * hz(m - 12) * tt) for m in ch) * 0.025 * np.minimum(1, tt / 0.8) * np.minimum(1, (L / SR - tt) / 0.8)
            out[s:s + L] += pad[: n - s]
        s = int(t * SR); L = int(0.9 * SR); tt = np.arange(L) / SR
        note = ch[i % 3] + 24 if i % 4 != 3 else ch[0] + 31
        bell = (np.sin(2 * np.pi * hz(note) * tt) + 0.4 * np.sin(2 * np.pi * hz(note) * 2.76 * tt)) * np.exp(-tt * 5) * 0.07
        out[s:s + L] += bell[: n - s]
        t += beat / 2; i += 1
    return out[: int(seconds * SR)]


MUSIC = {"bouncy": music_bed, "dark": music_dark, "tense": music_tense, "calm": music_calm, "none": lambda s: np.zeros(int(s * SR), np.float32)}


def _noise(L, seed=0):
    return np.random.default_rng(seed).standard_normal(L)


def sfx_whoosh():
    L = int(0.5 * SR); tt = np.arange(L) / SR; nz = _noise(L, 3)
    k = int(SR * 0.002); sm = np.convolve(nz, np.ones(k) / k, mode="same")
    return (0.5 * sm * np.sin(np.pi * tt / tt[-1]) ** 2).astype(np.float32)


def sfx_boom():
    L = int(1.2 * SR); tt = np.arange(L) / SR
    return (0.8 * np.sin(2 * np.pi * (40 + 60 * np.exp(-tt * 8)) * tt) * np.exp(-tt * 3.5)).astype(np.float32)


def sfx_knock():
    out = np.zeros(int(1.0 * SR), np.float32)
    for j, t0 in enumerate([0, 0.22, 0.44]):
        L = int(0.09 * SR); tt = np.arange(L) / SR; s = int(t0 * SR)
        hit = (np.sin(2 * np.pi * 180 * tt) + 0.6 * _noise(L, j) * np.exp(-tt * 120)) * np.exp(-tt * 45)
        out[s:s + L] += (0.6 * hit).astype(np.float32)
    return out


def sfx_heartbeat():
    out = np.zeros(int(1.6 * SR), np.float32)
    for t0, g in [(0, 1), (0.25, 0.7), (0.8, 1), (1.05, 0.7)]:
        L = int(0.18 * SR); tt = np.arange(L) / SR; s = int(t0 * SR)
        out[s:s + L] += (0.7 * g * np.sin(2 * np.pi * 55 * tt) * np.exp(-tt * 25)).astype(np.float32)
    return out


def sfx_stamp():
    L = int(0.4 * SR); tt = np.arange(L) / SR
    return (0.7 * (np.sin(2 * np.pi * 90 * tt) * np.exp(-tt * 18) + 0.3 * _noise(L, 9) * np.exp(-tt * 60))).astype(np.float32)


def sfx_tick():
    L = int(0.03 * SR); tt = np.arange(L) / SR
    return (0.4 * np.sin(2 * np.pi * 2400 * tt) * np.exp(-tt * 200)).astype(np.float32)


def sfx_doorbell():
    L = int(1.4 * SR); tt = np.arange(L) / SR
    a = np.sin(2 * np.pi * 659 * tt) * np.exp(-tt * 3) * (tt < 0.7)
    b = np.sin(2 * np.pi * 523 * (tt - 0.5)) * np.exp(-np.clip(tt - 0.5, 0, None) * 3) * (tt >= 0.5)
    return (0.35 * (a + b)).astype(np.float32)


def sfx_glitch():
    L = int(0.35 * SR); nz = _noise(L, 11)
    gate = (np.floor(np.arange(L) / (SR * 0.02)) % 2)
    return (0.3 * nz * gate * np.exp(-np.arange(L) / SR * 6)).astype(np.float32)


def sfx_riser():
    L = int(1.5 * SR); tt = np.arange(L) / SR
    f = 200 * 2 ** (tt * 2.5)
    return (0.2 * np.sin(2 * np.pi * np.cumsum(f) / SR) * (tt / tt[-1]) ** 2).astype(np.float32)


def sfx_click():
    L = int(0.02 * SR)
    return (0.5 * _noise(L, 5) * np.exp(-np.arange(L) / SR * 300)).astype(np.float32)


SFX = {"pop": sfx_pop, "ding": sfx_ding, "poof": sfx_poof, "sparkle": sfx_sparkle, "whoosh": sfx_whoosh, "boom": sfx_boom,
       "knock": sfx_knock, "heartbeat": sfx_heartbeat, "stamp": sfx_stamp, "tick": sfx_tick, "doorbell": sfx_doorbell,
       "glitch": sfx_glitch, "riser": sfx_riser, "click": sfx_click}


def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


def word_timings(sentence, t0, dur):
    """Approximate per-word timing inside one TTS'd sentence (weighted by length). *word* = highlighted."""
    raw = sentence.split()
    weights = [len(re.sub(r"[^\w']", "", w)) + 2 for w in raw]
    tot = sum(weights); out, t = [], t0
    for w, wt in zip(raw, weights):
        d = dur * wt / tot
        hl = "*" in w
        out.append({"t0": round(t, 3), "t1": round(t + d, 3), "text": w.replace("*", ""), "hl": hl})
        t += d
    return out


def guest_states(guests, bible):
    cast = {}
    for key, g in guests.items():
        js = (f"const c=require({json.dumps((ROOT / 'render' / 'character.js').as_posix())});"
              f"console.log(JSON.stringify(c.guestState({json.dumps(g['username'])},{json.dumps(g.get('role',''))},{json.dumps(bible.get('role_outfits', {}))})))")
        st = json.loads(subprocess.check_output(["node", "-e", js]))
        st["tag"] = g["username"] if len(g["username"]) <= 18 else g["username"][:17] + "…"
        cast[key] = st
    return cast


# ---------- main ----------
def build(ep_dir: Path, preview=False):
    ch_dir = ep_dir.parent.parent
    channel = json.loads((ch_dir / "channel.json").read_text(encoding="utf-8"))
    bible = json.loads((ch_dir / "bible.json").read_text(encoding="utf-8"))
    story = json.loads((ch_dir / "story.json").read_text(encoding="utf-8"))
    ep = json.loads((ep_dir / "episode.json").read_text(encoding="utf-8"))
    out = ep_dir / "out"; out.mkdir(exist_ok=True)
    voices = bible["voices"]
    style = channel["style"]
    guests = dict(ep.get("cast") or {})

    t = channel.get("intro", 0.35)
    gap = channel.get("scene_gap", 0.1)
    scenes, voice_clips, sfx_events = [], [], []
    for sc in ep["scenes"]:
        speaker = sc.get("speaker", "narrator")
        vkey = guests[speaker].get("voice", "guest_m") if speaker in guests else (speaker if speaker in voices else "narrator")
        v = voices[vkey]
        fixes = {**bible.get("pronunciations", {}), **ep.get("pronunciations", {}), **sc.get("pronounce", {})}
        clean_say = sc["say"].replace("*", "")
        # one TTS call per sentence -> sentence-accurate word timing for pop captions
        pieces, words, cursor = [], [], 0.0
        for sent in split_sentences(sc["say"]):
            spoken = apply_pronunciations(sent.replace("*", ""), fixes)
            check_heteronyms(spoken)
            a = tts(spoken, v["voice"], v["speed"])
            if v.get("tighten", True):
                a = tighten_pauses(a)
            if v.get("polish"):
                a = polish(a)
            words += word_timings(sent, t + cursor, len(a) / SR)
            pieces += [a, np.zeros(int(0.06 * SR), np.float32)]
            cursor += len(a) / SR + 0.06
        audio = np.concatenate(pieces)
        dur = len(audio) / SR
        tail = sc.get("hold", gap)
        if sc.get("transform"):
            tail = max(tail, 1.6)
        start_f = round(t * FPS)
        speak_frames = math.ceil(dur * FPS)
        end_f = round((t + dur + tail) * FPS)
        scene = {k: v_ for k, v_ in sc.items() if k not in ("say", "pronounce")}
        scene.update({
            "start_frame": start_f, "end_frame": end_f, "speaker": speaker, "say": clean_say,
            "captions": chunk_captions(clean_say, start_f, speak_frames),
            "words": [dict(w, f0=round(w["t0"] * FPS), f1=round(w["t1"] * FPS)) for w in words],
            "mouth": mouth_envelope(audio, end_f - start_f),
        })
        if sc.get("transform"):
            scene["transform"] = dict(sc["transform"], frame=start_f + speak_frames + 4)
            sfx_events += [("poof", scene["transform"]["frame"] / FPS - 0.15, 0.7), ("sparkle", scene["transform"]["frame"] / FPS + 0.1, 0.8)]
        if sc.get("texts"):
            n_t = len(sc["texts"])
            scene["texts"] = [dict(m, appear_frame=start_f + 10 + round(i * (speak_frames - 10) / n_t)) for i, m in enumerate(sc["texts"])]
            for m in scene["texts"]:
                sfx_events.append(("ding" if m.get("from") != "theo" else "pop", m["appear_frame"] / FPS, 0.8))
        for e in sc.get("sfx", []):  # "boom" or {"name": "knock", "at": 1.2, "gain": 0.8}
            e = {"name": e} if isinstance(e, str) else e
            sfx_events.append((e["name"], t + e.get("at", 0), e.get("gain", 0.8)))
        scenes.append(scene)
        voice_clips.append((t, audio))
        t += dur + tail

    cta_len = ep.get("cta_len", channel.get("cta_len", 2.6))
    total = t + cta_len
    scenes[-1]["end_frame"] = round(total * FPS)
    scenes[-1]["mouth"] += [0] * (scenes[-1]["end_frame"] - scenes[-1]["start_frame"] - len(scenes[-1]["mouth"]))

    tl = {"fps": FPS, "width": W, "height": H, "total_frames": round(total * FPS), "style": style,
          "cta_start_frame": round((total - cta_len) * FPS), "scenes": scenes,
          "ep": {k: v_ for k, v_ in ep.items() if k != "scenes"}, "story": story}
    if style == "theo":
        cast = {"theo": dict(story["theo_state"])}
        for who in ("deb", "brett", "nina"):
            cast[who] = bible["cast"][who]["state"]
        cast.update(guest_states(guests, bible))
        tl.update({"day": ep["day"], "title": ep["title"], "accent": ep.get("accent", "#7cfc5a"), "days_left": 101 - ep["day"],
                   "credit": f"TOP COMMENT: {ep['chosen_comment']['author']}" if ep.get("chosen_comment") else None,
                   "cta": {"start_frame": tl["cta_start_frame"], "lines": ep.get("cta", ["TOP COMMENT DECIDES", f"DAY {ep['day'] + 1}"])},
                   "cast": cast})
    else:
        tl["cast"] = guest_states(guests, bible)
    (out / "timeline.json").write_text(json.dumps(tl))

    if preview:
        picks = [("hook", 12)] + [(f"s{i+1}", sc["start_frame"] + int((sc["end_frame"] - sc["start_frame"]) * 0.6)) for i, sc in enumerate(scenes)] + [("cta", tl["total_frames"] - 8)]
        for name, f in picks:
            subprocess.run(["node", str(ROOT / "render/render.mjs"), str(out / "timeline.json"), "-", "--still", str(f), str(out / f"still-{name}.png")], check=True)
        print("stills ->", out)
        return

    n = int(total * SR) + SR
    mixbuf = np.zeros(n, np.float32)
    mixbuf[: int(total * SR)] += MUSIC[channel.get("music", "bouncy")](total) * channel.get("music_gain", 0.28)
    for at, a in voice_clips:
        mix_into(mixbuf, a, at, 1.0)
    sfx_events += [(channel.get("open_sfx", "pop"), 0.05, 0.8), (channel.get("cta_sfx", "pop"), total - cta_len, 0.8)]
    for name, at, g in sfx_events:
        if name in SFX:
            mix_into(mixbuf, SFX[name](), max(0, at), g)
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
