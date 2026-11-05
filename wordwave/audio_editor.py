import io
from pydub import AudioSegment

def edit_audio_bytes(audio_file, start_seconds=0, end_seconds=None, fade_in=0, fade_out=0, volume_db=0):
    audio_file.seek(0)
    audio = AudioSegment.from_file(audio_file)
    start_ms = max(0, int(start_seconds * 1000))
    end_ms = len(audio) if end_seconds is None else min(len(audio), int(end_seconds * 1000))
    if end_ms <= start_ms:
        raise ValueError("End time must be greater than start time.")
    audio = audio[start_ms:end_ms]
    if fade_in:
        audio = audio.fade_in(min(len(audio), int(fade_in * 1000)))
    if fade_out:
        audio = audio.fade_out(min(len(audio), int(fade_out * 1000)))
    if volume_db:
        audio += int(volume_db)
    output = io.BytesIO()
    audio.export(output, format="mp3", bitrate="192k")
    return output.getvalue(), len(audio), audio.channels, audio.frame_rate
