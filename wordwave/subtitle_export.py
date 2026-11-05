def _stamp(milliseconds, webvtt=False):
    ms = max(0, int(milliseconds))
    hours, rem = divmod(ms, 3600000)
    minutes, rem = divmod(rem, 60000)
    seconds, millis = divmod(rem, 1000)
    sep = "." if webvtt else ","
    return f"{hours:02}:{minutes:02}:{seconds:02}{sep}{millis:03}"

def make_srt(timings):
    rows = []
    for item in timings or []:
        word = (item.get("text") or "").strip()
        if not word:
            continue
        start = max(0, int(item.get("start_ms", 0)))
        end = max(start + 1, int(item.get("end_ms", start + 1)))
        rows.append(f"{len(rows)+1}\n{_stamp(start)} --> {_stamp(end)}\n{word}")
    if not rows:
        raise ValueError("No actual Edge TTS word-boundary timings are available.")
    return "\n\n".join(rows) + "\n"

def make_vtt(timings):
    srt = make_srt(timings)
    return "WEBVTT\n\n" + srt.replace(",", ".")
