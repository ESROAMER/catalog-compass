"""Assemble real UI captures, editable captions, and locally generated narration.

Requires Pillow and imageio-ffmpeg. Captures are made with the browser tool;
this script never controls or captures the computer. No interface is simulated.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import wave

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
sys.path.insert(0, str(PROJECT / '.media-tools'))
import imageio_ffmpeg

BUILD = ROOT / 'build'
FRAMES = BUILD / 'frames'
FRAMES.mkdir(parents=True, exist_ok=True)
STORY = json.loads((ROOT / 'storyboard.json').read_text(encoding='utf-8'))
W, H = 1920, 1080
BG, INK, MUTED, ACCENT = '#102e2a', '#ffffff', '#bdd1ca', '#e2b569'
FONTS = Path('C:/Windows/Fonts')


def font(size, bold=False):
    return ImageFont.truetype(str(FONTS / ('segoeuib.ttf' if bold else 'segoeui.ttf')), size)


def wrap(draw, text, face, width):
    lines, current = [], ''
    for word in text.split():
        candidate = (current + ' ' + word).strip()
        if draw.textlength(candidate, font=face) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def render(scene, caption, index, total):
    frame = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(frame)
    draw.text((58, 22), 'CATALOG COMPASS', font=font(25, True), fill=ACCENT)
    draw.text((440, 18), scene['title'], font=font(32, True), fill=INK)
    draw.text((1790, 24), f"{index:02d} / {total:02d}", font=font(22), fill=MUTED)
    if scene['image']:
        original = Image.open(ROOT / 'captures' / scene['image']).convert('RGB')
        shot = ImageOps.contain(original, (1500, 844), Image.Resampling.LANCZOS)
        x, y = (W - shot.width) // 2, 86
        draw.rounded_rectangle((x-5, y-5, x+shot.width+5, y+shot.height+5), radius=8, fill='#476760')
        frame.paste(shot, (x, y))
        if scene.get('focus'):
            left, top, width, height = scene['focus']
            scale = shot.width / original.width
            box = (x + left*scale, y + top*scale, x + (left+width)*scale, y + (top+height)*scale)
            draw.rounded_rectangle(box, radius=6, outline='#e29827', width=4)
    else:
        draw.text((150, 178), 'Review one file.', font=font(78, True), fill=INK)
        draw.text((150, 280), 'Deliver clear exceptions.', font=font(78, True), fill=INK)
        for n, (label, detail) in enumerate([
            ('AI suggests', 'Qwen + llama.cpp'),
            ('You confirm', 'Resolve ambiguous matches'),
            ('Rules check', 'Export rows and evidence'),
        ]):
            left = 150 + n * 550
            draw.rounded_rectangle((left, 465, left+510, 665), radius=16, fill='#1c413a', outline='#507569', width=2)
            draw.text((left+32, 490), str(n+1).zfill(2), font=font(30, True), fill=ACCENT)
            draw.text((left+32, 540), label, font=font(38, True), fill=INK)
            draw.text((left+32, 606), detail, font=font(25), fill=MUTED)
        draw.text((150, 737), '44 tests pass  |  MIT application code', font=font(33, True), fill=INK)
        draw.text((150, 793), 'Next: a supervised trial with a freelancer', font=font(30), fill=MUTED)
    lines = wrap(draw, caption, font(32), 1780)
    if len(lines) > 2:
        raise ValueError(f'Caption is too long: {caption}')
    start_y = 953 if len(lines) == 2 else 972
    for i, line in enumerate(lines):
        tw = draw.textlength(line, font=font(32))
        draw.text(((W-tw)/2, start_y+i*40), line, font=font(32), fill=INK)
    draw.text((58, 1049), 'Real UI captures  /  Edited walkthrough  /  Synthetic English narration', font=font(18), fill=MUTED)
    draw.text((1550, 1049), 'Fictional supplier data', font=font(18), fill=MUTED)
    return frame


def stamp(seconds):
    ms = round(seconds*1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'


def main():
    timeline, subtitles, audio_chunks, concat = [], [], [], []
    sample_rate = None
    cursor = 0
    transcript = ['# Catalog Compass demo narration', '', STORY['disclosure'], '']
    for scene_index, scene in enumerate(STORY['scenes'], 1):
        transcript.extend(['## ' + scene['title'], '', *[c+'\n' for c in scene['captions']]])
        scene_start = cursor
        for cue, caption in enumerate(scene['captions']):
            audio_path = BUILD / 'audio' / f"{scene['id']}-{cue}.wav"
            with wave.open(str(audio_path), 'rb') as wav:
                params = (wav.getnchannels(), wav.getsampwidth(), wav.getframerate())
                if params[:2] != (1, 2):
                    raise ValueError('Expected mono PCM16 narration')
                if sample_rate is not None and sample_rate != params[2]:
                    raise ValueError('Mismatched audio rates')
                sample_rate = params[2]
                data = wav.readframes(wav.getnframes())
            pre = .30 if cue == 0 else .12
            post = .55 if cue == len(scene['captions'])-1 else .12
            duration = pre + len(data)/(sample_rate*2) + post
            audio_chunks.extend([b'\0'*round(pre*sample_rate)*2, data, b'\0'*round(post*sample_rate)*2])
            path = FRAMES / f"{scene['id']}-{cue}.png"
            render(scene, caption, scene_index, len(STORY['scenes'])).save(path)
            concat.extend([f"file '{path.as_posix()}'", f'duration {duration:.6f}'])
            subtitles.append(f"{len(subtitles)+1}\n{stamp(cursor+pre)} --> {stamp(cursor+duration-post)}\n{caption}\n")
            cursor += duration
        timeline.append({'scene': scene['id'], 'title': scene['title'], 'start': round(scene_start, 3), 'end': round(cursor, 3), 'capture': scene['image']})
    concat.append(f"file '{path.as_posix()}'")
    (BUILD / 'frames.txt').write_text('\n'.join(concat)+'\n', encoding='utf-8')
    with wave.open(str(BUILD / 'narration.wav'), 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(sample_rate)
        wav.writeframes(b''.join(audio_chunks))
    (ROOT / 'captions.en.srt').write_text('\n'.join(subtitles), encoding='utf-8')
    (ROOT / 'narration.en.md').write_text('\n'.join(transcript), encoding='utf-8')
    captures = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / 'captures').glob('*.jpg')}
    (ROOT / 'timeline.json').write_text(json.dumps({'duration_seconds': round(cursor,3), 'resolution': [W,H], 'fps': 24, 'voice':'Microsoft Zira Desktop', 'disclosure':STORY['disclosure'], 'timeline':timeline, 'capture_sha256':captures}, indent=2)+'\n', encoding='utf-8')
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    command = [ffmpeg, '-hide_banner', '-loglevel', 'warning', '-y', '-f', 'concat', '-safe', '0', '-i', str(BUILD/'frames.txt'), '-i', str(BUILD/'narration.wav'), '-map', '0:v:0', '-map', '1:a:0', '-vf', 'fps=24,format=yuv420p', '-c:v', 'libx264', '-preset', 'medium', '-tune', 'stillimage', '-crf', '19', '-c:a', 'aac', '-b:a', '128k', '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-t', f'{cursor:.6f}', '-movflags', '+faststart', str(ROOT/'catalog-compass-demo.mp4')]
    subprocess.run(command, check=True)
    poster = render(STORY['scenes'][-1], 'Local AI suggestions. Human decisions. Clear reports.', 12, 12)
    poster.save(ROOT/'poster.jpg', quality=94)
    thumbs = Image.new('RGB', (1200, 3*250), '#e9eceb')
    thumbs_draw = ImageDraw.Draw(thumbs)
    chosen = [STORY['scenes'][i] for i in (0,1,2,3,5,7,8,10,11)]
    for i, scene in enumerate(chosen):
        png = FRAMES/f"{scene['id']}-0.png"
        thumb = ImageOps.contain(Image.open(png), (390,220))
        thumbs.paste(thumb, (i%3*400, i//3*250+25))
        thumbs_draw.text((i%3*400+5, i//3*250+4), scene['id']+' '+scene['title'], font=font(13), fill='#163e32')
    thumbs.save(ROOT/'video-contact-sheet.jpg', quality=93)
    print(json.dumps({'video': str(ROOT/'catalog-compass-demo.mp4'), 'duration_seconds': round(cursor, 3), 'size_mb':round((ROOT/'catalog-compass-demo.mp4').stat().st_size/1e6,2)}))


if __name__ == '__main__':
    main()
