"""Render a course's animated lesson videos (H.264 MP4), English captions (WebVTT) and poster images.

Development tool only; the LMS does not need it at runtime. Storyboards and narration come from the course data
file, so the videos always match the lesson text. Requirements: Pillow and imageio-ffmpeg (which bundles ffmpeg),
Windows fonts (Segoe UI, Consolas) and, for narration, the Windows offline speech engine (System.Speech).

    python backend/tools/generate_course_videos.py                       # all lessons, narrated
    python backend/tools/generate_course_videos.py --only lesson-03       # one lesson
    python backend/tools/generate_course_videos.py --silent               # captions only, no narration
"""
import argparse
import json
import math
import re
import subprocess
import tempfile
import wave
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
W, H, FPS = 1280, 720, 24
LEFT, RIGHT = 56, 1224
BG, PANEL, PANEL_EDGE = (21, 58, 49), (14, 44, 37), (44, 92, 78)
WHITE, BODY, MUTED, LINE = (255, 255, 255), (199, 217, 208), (122, 156, 142), (44, 86, 74)
MINT, MINT_DARK, CORAL = (143, 221, 186), (61, 128, 104), (240, 146, 128)
FONTS = Path('C:/Windows/Fonts')


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


F = {'eyebrow': font('segoeuib.ttf', 16), 'title': font('segoeuib.ttf', 40), 'hero': font('segoeuib.ttf', 52), 'body': font('segoeui.ttf', 24),
     'item': font('segoeui.ttf', 27), 'label': font('segoeuib.ttf', 25), 'small': font('segoeui.ttf', 19), 'mono': font('consola.ttf', 23),
     'chip': font('consola.ttf', 26), 'header': font('segoeui.ttf', 15), 'big': font('segoeuib.ttf', 44)}


def ease(p):
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


def appear(t, start, length=0.55):
    return ease((t - start) / length)


def mix(color, background, alpha):
    return tuple(int(background[i] + (color[i] - background[i]) * alpha) for i in range(3))


def wrap(text, typeface, width):
    lines, line = [], ''
    for word in text.split():
        candidate = f'{line} {word}'.strip()
        if typeface.getlength(candidate) <= width:
            line = candidate
        else:
            lines.append(line)
            line = word
    return lines + ([line] if line else [])


def text(draw, xy, value, typeface, color, alpha, background=BG, spacing=1.35, width=None):
    x, y = xy
    lines = wrap(value, typeface, width) if width else value.split('\n')
    step = int(typeface.size * spacing)
    for line in lines:
        draw.text((x, y), line, font=typeface, fill=mix(color, background, alpha))
        y += step
    return y


def spaced(value):
    return '  '.join(value) if len(value) < 3 else ' '.join(value)


class Lesson:
    def __init__(self, course, lesson, number, durations):
        self.course, self.lesson, self.number = course, lesson, number
        self.scenes = lesson['scenes']
        self.durations = durations
        self.starts = [sum(durations[:i]) for i in range(len(durations))]
        self.total = sum(durations)
        self.base = self.background()

    def background(self):
        image = Image.new('RGB', (W, H), BG)
        glow = Image.new('L', (W, H), 0)
        ImageDraw.Draw(glow).ellipse((700, -420, 1700, 520), fill=40)
        image.paste(Image.new('RGB', (W, H), (30, 74, 62)), mask=glow.resize((W // 8, H // 8)).resize((W, H), Image.BILINEAR))
        logo = Image.open(ROOT / 'frontend/public/assets/images/ShimentoX-Light-Logo.webp').convert('RGBA')
        logo.thumbnail((210, 40))
        image.paste(logo, (LEFT, 40), logo)
        draw = ImageDraw.Draw(image)
        label = f'{self.course.get("videoLabel", "GENERATIVE AI")}   /   LESSON {self.number:02d}'
        draw.text((RIGHT - draw.textlength(label, font=F['header']), 50), label, font=F['header'], fill=BODY)
        draw.line((LEFT, 100, RIGHT, 100), fill=LINE, width=1)
        footer = 'SHIMENTOX LEARNING   /   ' + self.course['title'].upper()
        draw.text((LEFT, 672), footer, font=F['header'], fill=MUTED)
        draw.rounded_rectangle((LEFT, 702, RIGHT, 706), radius=2, fill=LINE)
        return image

    def frame(self, t):
        index = max(i for i, start in enumerate(self.starts) if start <= t + 1e-9)
        local, length = t - self.starts[index], self.durations[index]
        fade = min(1.0, local / 0.35) if index or local < 0.35 else 1.0
        if index < len(self.scenes) - 1:
            fade = min(fade, max(0.0, (length - local) / 0.3))
        image = self.base.copy()
        draw = ImageDraw.Draw(image)
        scene = self.scenes[index]
        getattr(self, 'scene_' + scene['type'])(draw, scene, local, length, fade)
        counter = f'{index + 1} / {len(self.scenes)}'
        draw.text((RIGHT - draw.textlength(counter, font=F['header']), 672), counter, font=F['header'], fill=MUTED)
        draw.rounded_rectangle((LEFT, 702, LEFT + max(4, int((RIGHT - LEFT) * min(1.0, t / self.total))), 706), radius=2, fill=MINT)
        return image

    def heading(self, draw, scene, t, fade, body_key='body'):
        a = appear(t, 0.1) * fade
        draw.text((LEFT, 128), spaced(scene['eyebrow']), font=F['eyebrow'], fill=mix(MINT, BG, a))
        offset = int(14 * (1 - appear(t, 0.2)))
        y = text(draw, (LEFT, 152 + offset), scene['title'], F['title'], WHITE, appear(t, 0.2) * fade, width=RIGHT - LEFT)
        if scene.get(body_key):
            text(draw, (LEFT, y + 10), scene[body_key], F['body'], BODY, appear(t, 0.45) * fade, width=RIGHT - LEFT)

    def scene_title(self, draw, scene, t, length, fade):
        for i, radius in enumerate((150, 220, 290)):
            pulse = radius + 6 * math.sin(t * 1.4 + i)
            a = 0.35 * appear(t, 0.3 + i * 0.25) * fade
            draw.ellipse((1060 - pulse, 400 - pulse, 1060 + pulse, 400 + pulse), outline=mix(MINT_DARK, BG, a), width=2)
        a = appear(t, 0.1) * fade
        draw.text((LEFT, 236), spaced(scene['eyebrow']), font=F['eyebrow'], fill=mix(MINT, BG, a))
        y = text(draw, (LEFT, 264 + int(16 * (1 - appear(t, 0.25)))), scene['title'], F['hero'], WHITE, appear(t, 0.25) * fade, width=820)
        draw.rounded_rectangle((LEFT, y + 14, LEFT + int(170 * appear(t, 0.8, 0.9)), y + 19), radius=2, fill=mix(MINT, BG, fade))
        text(draw, (LEFT, y + 44), scene['body'], F['body'], BODY, appear(t, 0.9) * fade, width=760)

    def scene_bullets(self, draw, scene, t, length, fade):
        self.heading(draw, scene, t, fade)
        items = scene['items']
        gap = min(2.4, (length * 0.62) / len(items))
        for i, item in enumerate(items):
            a = appear(t, 1.0 + i * gap) * fade
            x, y = LEFT + 6 + int(30 * (1 - appear(t, 1.0 + i * gap))), 300 + i * 78
            draw.ellipse((x, y + 12, x + 14, y + 26), fill=mix(MINT, BG, a))
            text(draw, (x + 34, y), item, F['item'], WHITE, a, width=1060)

    def panel(self, draw, box, alpha, edge=PANEL_EDGE):
        draw.rounded_rectangle(box, radius=16, fill=mix(PANEL, BG, alpha), outline=mix(edge, BG, alpha), width=2)

    def scene_compare(self, draw, scene, t, length, fade):
        self.heading(draw, scene, t, fade)
        second = max(2.6, length * 0.45)
        for side, (column, start, color) in enumerate(((scene['left'], 0.9, BODY), (scene['right'], second, MINT))):
            x0 = LEFT if side == 0 else 676
            a = appear(t, start) * fade
            self.panel(draw, (x0, 290, x0 + 548, 640), a, edge=MINT_DARK if side else PANEL_EDGE)
            draw.text((x0 + 30, 314), column['heading'], font=F['label'], fill=mix(color, PANEL, a))
            for i, item in enumerate(column['items']):
                b = appear(t, start + 0.4 + i * 0.5) * fade
                draw.text((x0 + 30, 372 + i * 62), ('→  ' if side else '•  ') + item, font=F['item'], fill=mix(WHITE if side else BODY, PANEL, b))
        a = appear(t, second - 0.3) * fade
        draw.ellipse((618, 437, 662, 481), fill=mix(MINT, BG, a))
        draw.text((626, 446), 'vs', font=F['label'], fill=mix(PANEL, mix(MINT, BG, a), a))

    def scene_flow(self, draw, scene, t, length, fade):
        self.heading(draw, scene, t, fade, body_key=None)
        steps = scene['steps']
        gap, height, y0 = 64, 120, 330
        width = (RIGHT - LEFT - gap * (len(steps) - 1)) / len(steps)
        step_time = min(1.6, (length * 0.55) / len(steps))
        centers = []
        for i, label in enumerate(steps):
            start = 0.9 + i * step_time
            a = appear(t, start) * fade
            x = LEFT + i * (width + gap)
            centers.append((x, x + width))
            self.panel(draw, (x, y0, x + width, y0 + height), a, edge=MINT_DARK)
            draw.text((x + 22, y0 + 18), f'{i + 1:02d}', font=F['eyebrow'], fill=mix(MINT, PANEL, a))
            for j, line in enumerate(wrap(label, F['label'], width - 40)[:2]):
                draw.text((x + 22, y0 + 44 + j * 30), line, font=F['label'], fill=mix(WHITE, PANEL, a))
            if i:
                grow = appear(t, start - 0.25, 0.4)
                ax0, ax1, ay = centers[i - 1][1] + 8, centers[i - 1][1] + 8 + (gap - 16) * grow, y0 + height / 2
                if grow > 0:
                    draw.line((ax0, ay, ax1, ay), fill=mix(MINT, BG, fade), width=3)
                    if grow > 0.95:
                        draw.polygon([(ax1, ay), (ax1 - 10, ay - 7), (ax1 - 10, ay + 7)], fill=mix(MINT, BG, fade))
        done = 0.9 + len(steps) * step_time
        if t > done:
            phase = ((t - done) % 3.0) / 3.0
            px = LEFT + phase * (RIGHT - LEFT)
            draw.ellipse((px - 6, y0 + height + 22, px + 6, y0 + height + 34), fill=mix(MINT, BG, fade * min(1, (t - done) / 0.5)))
        text(draw, (LEFT, 540), scene['caption'], F['body'], BODY, appear(t, done - 0.4) * fade, width=RIGHT - LEFT)

    def scene_code(self, draw, scene, t, length, fade):
        self.heading(draw, scene, t, fade)
        top = 300 if len(scene['body']) < 70 else 330
        self.panel(draw, (LEFT, top, RIGHT, 650), appear(t, 0.6) * fade)
        code = scene['code']
        row_step = min(30, (650 - top - 40) // max(1, len(code.splitlines())))
        typeface = font('consola.ttf', min(23, row_step - 3))
        typing = min(length * 0.55, len(code) * 0.032)
        shown = code[:int(len(code) * min(1.0, max(0.0, (t - 0.9) / typing)))]
        y = top + 24
        rows = shown.split('\n')
        for row in rows:
            color = MUTED if row.lstrip().startswith('#') else (MINT if re.match(r'^(Ticket|Category|Prompt):', row) else (232, 242, 236))
            draw.text((LEFT + 30, y), row, font=typeface, fill=mix(color, PANEL, fade))
            y += row_step
        if int(t * 2) % 2 == 0:
            x = LEFT + 30 + draw.textlength(rows[-1], font=typeface)
            draw.rectangle((x + 2, y - row_step + 4, x + 10, y - 2), fill=mix(MINT, PANEL, fade))

    def scene_tokens(self, draw, scene, t, length, fade):
        self.heading(draw, scene, t, fade, body_key=None)
        tokens = scene['tokens']
        x, y = LEFT, 320
        step = min(0.9, (length * 0.5) / len(tokens))
        shades = [(46, 110, 92), (33, 88, 74), (63, 128, 106)]
        for i, token in enumerate(tokens):
            label = ('·' + token[1:]) if token.startswith(' ') else token
            width = draw.textlength(label, font=F['chip']) + 36
            if x + width > RIGHT:
                x, y = LEFT, y + 84
            a = appear(t, 0.9 + i * step) * fade
            lift = int(10 * (1 - appear(t, 0.9 + i * step)))
            draw.rounded_rectangle((x, y + lift, x + width, y + 60 + lift), radius=12, fill=mix(shades[i % 3], BG, a))
            draw.text((x + 18, y + 14 + lift), label, font=F['chip'], fill=mix(WHITE, BG, a))
            x += width + 14
        done = 0.9 + len(tokens) * step
        a = appear(t, done) * fade
        draw.text((LEFT, y + 100), f'{len(tokens)} tokens', font=F['big'], fill=mix(MINT, BG, a))
        draw.text((LEFT + 250, y + 118), '·  marks a leading space', font=F['small'], fill=mix(MUTED, BG, a))
        text(draw, (LEFT, 560), scene['caption'], F['body'], BODY, appear(t, done + 0.4) * fade, width=RIGHT - LEFT)

    def scene_cards(self, draw, scene, t, length, fade):
        self.heading(draw, scene, t, fade, body_key=None)
        cards = scene['cards']
        columns = len(cards) if len(cards) <= 5 else 3
        rows = math.ceil(len(cards) / columns)
        gap = 22
        width = (RIGHT - LEFT - gap * (columns - 1)) / columns
        height = 150 if rows == 1 else 132
        top = 300 if rows == 1 else 280
        step = min(1.8, (length * 0.62) / len(cards))
        for i, card in enumerate(cards):
            row, column = divmod(i, columns)
            start = 0.9 + i * step
            a = appear(t, start) * fade
            x, y = LEFT + column * (width + gap), top + row * (height + gap) + int(16 * (1 - appear(t, start)))
            self.panel(draw, (x, y, x + width, y + height), a)
            draw.rounded_rectangle((x + 20, y + 20, x + 64, y + 25), radius=2, fill=mix(MINT, PANEL, a))
            draw.text((x + 20, y + 40), card['label'], font=F['label'], fill=mix(WHITE, PANEL, a))
            text(draw, (x + 20, y + 80), card['detail'], F['small'], BODY, a, background=PANEL, width=width - 40)

    def mark(self, draw, x, y, good, alpha, background):
        color = mix(MINT if good else CORAL, background, alpha)
        if good:
            draw.line([(x, y + 10), (x + 7, y + 17), (x + 20, y + 2)], fill=color, width=4)
        else:
            draw.line([(x + 2, y + 2), (x + 18, y + 18)], fill=color, width=4)
            draw.line([(x + 18, y + 2), (x + 2, y + 18)], fill=color, width=4)

    def scene_checklist(self, draw, scene, t, length, fade):
        self.heading(draw, scene, t, fade, body_key=None)
        columns = ((scene['do'], 'Do', True, LEFT), (scene['dont'], 'Avoid', False, 676))
        count = max(len(scene['do']), len(scene['dont']))
        step = min(1.6, (length * 0.6) / (count * 2))
        for items, heading, good, x0 in columns:
            a = appear(t, 0.8 + (0 if good else 0.3)) * fade
            self.panel(draw, (x0, 280, x0 + 548, 620), a, edge=MINT_DARK if good else (110, 80, 72))
            draw.text((x0 + 30, 304), heading, font=F['label'], fill=mix(MINT if good else CORAL, PANEL, a))
            for i, item in enumerate(items):
                start = 1.4 + (i * 2 + (0 if good else 1)) * step
                b = appear(t, start) * fade
                self.mark(draw, x0 + 30, 372 + i * 76, good, b, PANEL)
                text(draw, (x0 + 66, 364 + i * 76), item, F['item'], WHITE, b, background=PANEL, width=450)


def synthesize(texts, folder, voice):
    """Narrate each scene with the offline Windows speech engine; returns WAV paths."""
    jobs = [{'text': value, 'path': str(folder / f'scene-{i:02d}.wav')} for i, value in enumerate(texts)]
    (folder / 'jobs.json').write_text(json.dumps(jobs), encoding='utf-8')
    script = folder / 'speak.ps1'
    script.write_text('''Add-Type -AssemblyName System.Speech
$jobs = Get-Content -Raw -Encoding UTF8 $args[0] | ConvertFrom-Json
$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice.SelectVoice($args[1])
$voice.Rate = -1
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(22050, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
foreach ($job in $jobs) { $voice.SetOutputToWaveFile($job.path, $format); $voice.Speak($job.text); $voice.SetOutputToNull() }
$voice.Dispose()
''', encoding='utf-8')
    subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script), str(folder / 'jobs.json'), voice], check=True)
    return [Path(job['path']) for job in jobs]


def wav_seconds(path):
    with wave.open(str(path)) as audio:
        return audio.getnframes() / audio.getframerate()


def build_track(clips, durations, lead, out):
    with wave.open(str(clips[0])) as first:
        params = first.getparams()
    rate, width = params.framerate, params.sampwidth
    with wave.open(str(out), 'wb') as track:
        track.setparams(params)
        for clip, duration in zip(clips, durations):
            with wave.open(str(clip)) as audio:
                frames = audio.readframes(audio.getnframes())
            pad = int(rate * duration) * width - len(frames) - int(rate * lead) * width
            track.writeframes(b'\0' * (int(rate * lead) * width) + frames + b'\0' * max(0, pad))


def stamp(seconds):
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f'{int(hours):02d}:{int(minutes):02d}:{secs:06.3f}'


def captions(scenes, starts, speech, lead):
    cues = ['WEBVTT', '']
    for scene, start, length in zip(scenes, starts, speech):
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', scene['narration']) if s.strip()]
        total = sum(len(s) for s in sentences)
        cursor = start + lead
        for sentence in sentences:
            span = length * len(sentence) / total
            cues += [f'{stamp(cursor)} --> {stamp(cursor + span)}', sentence, '']
            cursor += span
    return '\n'.join(cues)


def render(course, lesson, number, out_dir, silent, voice):
    lead, tail = 0.7, 0.9
    with tempfile.TemporaryDirectory(prefix='shimentox-video-') as temp:
        folder = Path(temp)
        if silent:
            speech = [len(scene['narration'].split()) / 2.5 for scene in lesson['scenes']]
        else:
            clips = synthesize([scene['narration'] for scene in lesson['scenes']], folder, voice)
            speech = [wav_seconds(clip) for clip in clips]
        durations = [max(5.0, lead + seconds + tail) for seconds in speech]
        builder = Lesson(course, lesson, number, durations)
        video = out_dir / f"{lesson['slug']}.mp4"
        command = [imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-']
        if not silent:
            track = folder / 'narration.wav'
            build_track(clips, durations, lead, track)
            command += ['-i', str(track), '-c:a', 'aac', '-b:a', '96k']
        command += ['-c:v', 'libx264', '-preset', 'medium', '-tune', 'animation', '-crf', '24', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-shortest', str(video)]
        encoder = subprocess.Popen(command, stdin=subprocess.PIPE)
        frames = int(builder.total * FPS)
        for i in range(frames):
            encoder.stdin.write(builder.frame(i / FPS).tobytes())
        encoder.stdin.close()
        if encoder.wait():
            raise SystemExit(f'ffmpeg failed for {video.name}')
        poster_scene = builder.starts[0] + min(builder.durations[0] - 0.4, 2.6)
        builder.frame(poster_scene).save(out_dir / f"{lesson['slug']}.jpg", quality=86)
        (out_dir / f"{lesson['slug']}.vtt").write_text(captions(lesson['scenes'], builder.starts, speech, lead), encoding='utf-8')
        return round(frames / FPS, 1)


def main():
    global FPS
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--course', default=str(ROOT / 'backend/data/generative-ai-course.json'))
    parser.add_argument('--only', help='Render a single lesson slug, for example lesson-03')
    parser.add_argument('--silent', action='store_true', help='Skip narration (captions are still written)')
    parser.add_argument('--voice', default='Microsoft Zira Desktop')
    parser.add_argument('--fps', type=int, default=24, choices=range(2, 31), help='Animation frames per second (2–30)')
    args = parser.parse_args()
    FPS = args.fps
    course = json.loads(Path(args.course).read_text(encoding='utf-8'))
    out_dir = ROOT / 'backend/videos' / course['id']
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    for number, lesson in enumerate(course['lessons'], 1):
        if args.only and lesson['slug'] != args.only:
            continue
        seconds = render(course, lesson, number, out_dir, args.silent, args.voice)
        manifest[lesson['slug']] = {'seconds': seconds, 'narrated': not args.silent}
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        print(f"{lesson['slug']}: {seconds}s -> {out_dir / (lesson['slug'] + '.mp4')}", flush=True)


if __name__ == '__main__':
    main()
