import streamlit as st
import asyncio
import edge_tts
import pdfplumber
from docx import Document
from pathlib import Path
import time
import io
import re
from pydub import AudioSegment
from langdetect import detect, LangDetectException

# ===========================================================
# PAGE CONFIGURATION
# ===========================================================
st.set_page_config(
    page_title="WordWave Studio",
    page_icon="logo.png",
    layout="wide"
)

# ===========================================================
# HEADER
# ===========================================================
col1, col2 = st.columns([1, 8])
with col1:
    logo_path = Path("logo.png")
    if logo_path.exists():
        st.image(str(logo_path), width=120)
    else:
        st.write("🎙️")
with col2:
    st.title("WordWave Studio")
    st.caption("Professional Audiobook & Text-to-Speech Pipeline")

# ===========================================================
# CONFIGURATION
# ===========================================================
MAX_CHARS_PER_REQUEST = 1200
MAX_RETRIES = 3
RETRY_BASE_SECONDS = 2
REQUEST_PAUSE_SECONDS = 0.25

LANGUAGE_MAP = {
    "en-US": "English (United States)", "en-GB": "English (United Kingdom)",
    "en-AU": "English (Australia)", "en-CA": "English (Canada)", "en-IN": "English (India)",
    "ur-PK": "Urdu (Pakistan)", "ur-IN": "Urdu (India)",
    "hi-IN": "Hindi (India)", "ar-SA": "Arabic (Saudi Arabia)",
    "tr-TR": "Turkish (Turkey)", "fr-FR": "French (France)", "de-DE": "German (Germany)",
    "es-ES": "Spanish (Spain)", "it-IT": "Italian (Italy)", "pt-BR": "Portuguese (Brazil)",
    "ru-RU": "Russian (Russia)", "ja-JP": "Japanese (Japan)", "ko-KR": "Korean (South Korea)",
    "zh-CN": "Chinese (China)", "bn-BD": "Bengali (Bangladesh)", "fa-IR": "Persian (Iran)",
    "id-ID": "Indonesian (Indonesia)", "ms-MY": "Malay (Malaysia)", "nl-NL": "Dutch (Netherlands)",
    "pl-PL": "Polish (Poland)", "sv-SE": "Swedish (Sweden)", "ta-IN": "Tamil (India)",
    "te-IN": "Telugu (India)", "th-TH": "Thai (Thailand)", "uk-UA": "Ukrainian (Ukraine)",
    "vi-VN": "Vietnamese (Vietnam)"
}

# ===========================================================
# TEXT EXTRACTION
# ===========================================================
def extract_text(uploaded_file):
    extension = uploaded_file.name.rsplit(".", 1)[-1].lower()
    if extension == "txt":
        return uploaded_file.getvalue().decode("utf-8-sig", errors="replace")
    if extension == "pdf":
        pages = []
        with pdfplumber.open(uploaded_file) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text()
                if page_text:
                    pages.append(page_text)
        return "\n\n".join(pages)
    if extension == "docx":
        document = Document(uploaded_file)
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    return ""


def split_text_safely(text, max_chars=MAX_CHARS_PER_REQUEST):
    """Split text into manageable chunks, preferring paragraph/sentence/word boundaries."""
    text = (text or "").strip()
    if not text:
        return []

    # Keep paragraph boundaries where possible, but do not let one paragraph become huge.
    units = re.split(r"\n+|(?<=[.!?。！？؟])\s+", text)
    chunks = []
    current = ""

    for unit in units:
        unit = unit.strip()
        if not unit:
            continue

        # Split a single oversized sentence at word boundaries.
        while len(unit) > max_chars:
            cut = unit.rfind(" ", 0, max_chars + 1)
            if cut < 1:
                cut = max_chars
            piece = unit[:cut].strip()
            if piece:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.append(piece)
            unit = unit[cut:].strip()

        if not unit:
            continue

        candidate = f"{current} {unit}".strip() if current else unit
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = unit

    if current:
        chunks.append(current)
    return chunks


# ===========================================================
# EDGE TTS ENGINE (CHUNKING AND RETRIES RUN SILENTLY IN BACKGROUND)
# ===========================================================
async def synthesize_one_chunk(text, voice, rate="+0%", pitch="+0Hz", word_timings=None):
    """One Edge TTS request; optionally retain Edge TTS word-boundary metadata."""
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    audio_buffer = bytearray()

    async for message in communicate.stream():
        if message.get("type") == "audio":
            audio_buffer.extend(message.get("data", b""))
        elif message.get("type") == "WordBoundary" and word_timings is not None:
            # Edge TTS timestamps are in 100-nanosecond ticks.
            word_timings.append({
                "text": message.get("text", ""),
                "offset_ms": int(message.get("offset", 0) / 10000),
                "duration_ms": int(message.get("duration", 0) / 10000),
            })

    if not audio_buffer:
        raise RuntimeError("No audio data was received from Edge TTS for this text chunk.")

    # MP3 decoding is performed once during audio merging to avoid duplicate work.
    return bytes(audio_buffer)


async def synthesize_with_retry(
    text, voice, rate="+0%", pitch="+0Hz", chunk_label="chunk", word_timings=None
):
    """Retry an individual text chunk and report the exact failed chunk."""
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        attempt_timings = [] if word_timings is not None else None
        try:
            audio_result = await synthesize_one_chunk(
                text, voice, rate, pitch, attempt_timings
            )
            if word_timings is not None and attempt_timings:
                word_timings.extend(attempt_timings)
            return audio_result
        except Exception as error:
            last_error = error
            if attempt < MAX_RETRIES:
                wait_seconds = RETRY_BASE_SECONDS ** attempt
                await asyncio.sleep(wait_seconds)

    raise RuntimeError(
        f"Audio generation failed in {chunk_label} after {MAX_RETRIES} attempts. "
        f"Original error: {type(last_error).__name__}: {last_error}"
    ) from last_error


async def generate_audio_chunks_async(
    text, voice, rate="+0%", pitch="+0Hz", progress_callback=None,
    max_chars=MAX_CHARS_PER_REQUEST, pause_seconds=REQUEST_PAUSE_SECONDS
):
    """External chunking, retries, MP3 decoding, and safe audio concatenation."""
    text_chunks = split_text_safely(text, max_chars=max_chars)
    if not text_chunks:
        raise ValueError("There is no readable text to synthesize.")

    combined = AudioSegment.empty()
    total = len(text_chunks)

    for index, text_chunk in enumerate(text_chunks, start=1):
        if progress_callback:
            progress_callback(index, total, text_chunk)

        chunk_bytes = await synthesize_with_retry(
            text_chunk,
            voice,
            rate,
            pitch,
            chunk_label=f"Text chunk {index}/{total}"
        )
        segment = AudioSegment.from_file(io.BytesIO(chunk_bytes), format="mp3")
        combined += segment

        if index < total and pause_seconds > 0:
            await asyncio.sleep(pause_seconds)

    if len(combined) == 0:
        raise RuntimeError("All requests completed but the combined audio is empty.")

    output = io.BytesIO()
    combined.export(output, format="mp3", bitrate="192k")
    result = output.getvalue()
    if not result:
        raise RuntimeError("MP3 export completed but produced an empty file.")
    return result, total


def show_generation_error(title, error):
    """Display the actual failure only when generation fails."""
    st.error(f"{title}\n\n{type(error).__name__}: {error}")


def voice_label(voice):
    name = voice.get("ShortName", "Unknown")
    locale = voice.get("Locale", "Unknown")
    gender = voice.get("Gender", "Unknown")
    display_name = name.split("-")[-1].replace("Neural", "")
    country = locale.split("-")[-1] if "-" in locale else locale
    return f"{display_name} ({gender}, {country})"


def render_text_stats(text):
    """Render live text statistics; Streamlit reruns after every text edit."""
    text = text or ""
    words = len(re.findall(r"\S+", text))
    sentences = len([
        part for part in re.split(r"[.!?؟。！？]+", text)
        if part.strip()
    ])
    if text.strip() and sentences == 0:
        sentences = 1
    read_minutes = words / 150 if words else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Characters", f"{len(text):,}")
    c2.metric("Words", f"{words:,}")
    c3.metric("Sentences", f"{sentences:,}")
    c4.metric("Est. Read Time", f"{read_minutes:.1f} min")


# ===========================================================
# LOAD VOICES
# ===========================================================
@st.cache_data(ttl=1800, show_spinner=False)
def load_voices():
    return asyncio.run(edge_tts.list_voices())

try:
    with st.spinner("Initializing Voice Engine..."):
        voices = load_voices()
    if not voices:
        st.error("The voice service returned an empty voice list. Check your connection and try refreshing.")
        st.stop()
except Exception as error:
    show_generation_error("Could not load Microsoft Edge TTS voices.", error)
    st.stop()

base_lang_map = {}
for voice_item in voices:
    locale = voice_item.get("Locale")
    if not locale:
        continue
    display_name = LANGUAGE_MAP.get(locale, locale)
    base_name = display_name.split(" (")[0] if " (" in display_name else display_name
    base_lang_map.setdefault(base_name, []).append(locale)

base_languages = sorted(base_lang_map)
if not base_languages:
    st.error("No supported voice languages were returned by the TTS service.")
    st.stop()

# ===========================================================
# MAIN APP TABS
# ===========================================================
tab1, tab2, tab3 = st.tabs(["🎙️ Quick Voice", "🎭 Multi-Voice Dialogue", "📚 Audiobook Studio"])

# ===========================================================
# TAB 1: QUICK VOICE
# ===========================================================
with tab1:
    st.markdown("### 📄 Text Input")
    uploaded_file = st.file_uploader(
        "Upload PDF, DOCX, or TXT", type=["pdf", "docx", "txt"], key="tab1_upload"
    )
    # Populate the editor once when a new file is uploaded.
    if uploaded_file:
        try:
            upload_signature = (uploaded_file.name, uploaded_file.size)
            if st.session_state.get("tab1_upload_signature") != upload_signature:
                st.session_state["tab1_text"] = extract_text(uploaded_file)
                st.session_state["tab1_upload_signature"] = upload_signature
        except Exception as error:
            st.error(f"Could not read the uploaded file: {type(error).__name__}: {error}")

    text_to_speak = st.text_area(
        "Edit or type your text here:",
        height=250,
        key="tab1_text"
    )
    render_text_stats(text_to_speak)

    st.divider()
    if "selected_base_lang_t1" not in st.session_state or st.session_state.selected_base_lang_t1 not in base_languages:
        st.session_state.selected_base_lang_t1 = "English" if "English" in base_languages else base_languages[0]
    if "detect_msg_t1" not in st.session_state:
        st.session_state.detect_msg_t1 = None

    def detect_lang_t1():
        source_text = st.session_state.get("tab1_text", "")
        if not source_text.strip():
            st.session_state.detect_msg_t1 = "warning|Please enter text first."
            return
        try:
            detected_code = detect(source_text[:1500])
            match = next(
                (base for base, locales in base_lang_map.items()
                 if any(locale.split("-")[0] == detected_code for locale in locales)),
                None
            )
            if match:
                st.session_state.selected_base_lang_t1 = match
                st.session_state.detect_msg_t1 = f"success|Detected language: {match}"
            else:
                st.session_state.detect_msg_t1 = f"warning|Detected '{detected_code}', but no matching voice is available."
        except LangDetectException:
            st.session_state.detect_msg_t1 = "error|Language detection failed. Enter a longer text sample."
        except Exception as error:
            st.session_state.detect_msg_t1 = f"error|{type(error).__name__}: {error}"

    col_lang, col_btn = st.columns([3, 1])
    with col_lang:
        selected_base_lang = st.selectbox(
            "🌍 Main Language", base_languages, key="selected_base_lang_t1"
        )
    with col_btn:
        st.write("")
        st.write("")
        st.button("🔍 Auto-Detect", use_container_width=True, on_click=detect_lang_t1)

    if st.session_state.detect_msg_t1:
        msg_type, msg_text = st.session_state.detect_msg_t1.split("|", 1)
        if msg_type == "success":
            st.success(msg_text)
        elif msg_type == "warning":
            st.warning(msg_text)
        else:
            st.error(msg_text)

    valid_locales = base_lang_map[selected_base_lang]
    filtered_voices = [v for v in voices if v.get("Locale") in valid_locales]
    if not filtered_voices:
        st.warning("No voices are available for this language right now.")
    else:
        if "gender_filter_t1" not in st.session_state:
            st.session_state.gender_filter_t1 = "All"

        g1, g2, g3 = st.columns(3)
        if g1.button("All Voices", use_container_width=True, key="btn_g1"):
            st.session_state.gender_filter_t1 = "All"
        if g2.button("Male Voices", use_container_width=True, key="btn_g2"):
            st.session_state.gender_filter_t1 = "Male"
        if g3.button("Female Voices", use_container_width=True, key="btn_g3"):
            st.session_state.gender_filter_t1 = "Female"

        visible_voices = filtered_voices
        if st.session_state.gender_filter_t1 != "All":
            visible_voices = [v for v in filtered_voices if v.get("Gender") == st.session_state.gender_filter_t1]
        if not visible_voices:
            st.warning("No voices match this gender filter. Select All Voices.")
        else:
            voice_names = [voice_label(v) for v in visible_voices]
            voice_choice = st.selectbox("🎤 Select Voice", voice_names, key="quick_voice_choice")
            selected_voice_t1 = visible_voices[voice_names.index(voice_choice)]["ShortName"]

            with st.expander("⚙️ Voice Settings"):
                c_speed, c_pitch = st.columns(2)
                speed_t1 = c_speed.slider("⚡ Speed", -50, 50, 0, key="quick_speed")
                pitch_t1 = c_pitch.slider("🎵 Pitch", -50, 50, 0, key="quick_pitch")

            if st.button("🎙️ Generate Full Audio File", use_container_width=True, type="primary"):
                if not text_to_speak.strip():
                    st.warning("Please provide text before generating.")
                else:
                    status = st.empty()
                    progress = st.progress(0)
                    start_time = time.time()
                    try:
                        def update_quick_progress(index, total, chunk):
                            percent = max(1, min(99, int(index / total * 100)))
                            progress.progress(percent, text=f"{percent}%")

                        audio_bytes, chunk_count = asyncio.run(
                            generate_audio_chunks_async(
                                text_to_speak,
                                selected_voice_t1,
                                f"{speed_t1:+d}%",
                                f"{pitch_t1:+d}Hz",
                                progress_callback=update_quick_progress
                            )
                        )
                        progress.progress(100, text="100%")
                        status.success("Audio created successfully.")
                        st.caption(f"⏱️ Generated in {time.time() - start_time:.1f} seconds")
                        st.audio(audio_bytes, format="audio/mp3")
                        st.download_button(
                            "⬇️ Download MP3", audio_bytes,
                            "WordWave_Quick.mp3", "audio/mpeg", use_container_width=True
                        )
                    except Exception as error:
                        progress.empty()
                        status.empty()
                        show_generation_error("Quick Voice generation failed.", error)

# ===========================================================
# TAB 2: MULTI-VOICE DIALOGUE
# ===========================================================
with tab2:
    st.markdown("### 🎭 Multi-Voice Dialogue Generator")
    st.info("Format your script with names in brackets: `[Alex]: Hello there!` and `[Sarah]: Hi Alex!`")
    dialogue_text = st.text_area(
        "Script:", height=200,
        placeholder="[Alex]: Hello there!\n[Sarah]: Hi Alex, how are you?",
        key="tab2_script"
    )

    render_text_stats(dialogue_text)

    st.divider()
    st.markdown("#### 👥 Character Setup")
    if "num_chars" not in st.session_state:
        st.session_state.num_chars = 2

    col_add, col_rem, _ = st.columns([1, 1, 4])
    if col_add.button("➕ Add Character"):
        st.session_state.num_chars += 1
    if col_rem.button("➖ Remove Character") and st.session_state.num_chars > 1:
        st.session_state.num_chars -= 1

    char_configs = {}
    for i in range(st.session_state.num_chars):
        st.markdown(f"**Character {i + 1}**")
        c_name, c_lang, c_voice = st.columns([2, 2, 4])
        default_name = "Alex" if i == 0 else ("Sarah" if i == 1 else f"Character {i + 1}")
        char_name = c_name.text_input("Name", value=default_name, key=f"c_name_{i}").strip()
        char_language = c_lang.selectbox("Main Language", base_languages, key=f"c_lang_{i}")
        locales = base_lang_map[char_language]
        available = [v for v in voices if v.get("Locale") in locales]
        labels = [voice_label(v) for v in available]
        if available:
            selected_label = c_voice.selectbox("Voice", labels, key=f"c_voice_{i}")
            if char_name:
                char_configs[char_name.lower()] = available[labels.index(selected_label)]["ShortName"]
        else:
            c_voice.warning("No voices available for this language.")

    if st.button("🎬 Generate Dialogue Audio", use_container_width=True, type="primary"):
        if not dialogue_text.strip():
            st.warning("Please enter a script.")
        elif not char_configs:
            st.warning("Configure at least one character and voice.")
        else:
            lines = [line.strip() for line in dialogue_text.splitlines() if line.strip()]
            default_voice = next(iter(char_configs.values()))
            dialogue_segments = []
            status = st.empty()
            progress = st.progress(0)
            start_time = time.time()
            try:
                async def build_dialogue():
                    final_audio = AudioSegment.empty()
                    total_lines = len(lines)
                    for line_index, line in enumerate(lines, start=1):
                        match = re.match(r"^\[(.*?)\]:\s*(.*)$", line)
                        if match:
                            speaker = match.group(1).strip().lower()
                            spoken_text = match.group(2).strip()
                            voice = char_configs.get(speaker, default_voice)
                        else:
                            spoken_text = line
                            voice = default_voice

                        if not spoken_text:
                            continue

                        line_audio_bytes, _ = await generate_audio_chunks_async(
                            spoken_text, voice, pause_seconds=0
                        )
                        line_segment = AudioSegment.from_file(
                            io.BytesIO(line_audio_bytes), format="mp3"
                        )
                        final_audio += line_segment
                        # A short pause makes speaker turns easier to distinguish.
                        if line_index < total_lines:
                            final_audio += AudioSegment.silent(duration=250)
                        percent = max(1, min(100, int(line_index / total_lines * 100)))
                        progress.progress(percent, text=f"{percent}%")
                    if len(final_audio) == 0:
                        raise RuntimeError("No spoken dialogue was generated. Check speaker labels and text.")
                    output = io.BytesIO()
                    final_audio.export(output, format="mp3", bitrate="192k")
                    return output.getvalue()

                combined_audio = asyncio.run(build_dialogue())
                progress.progress(100, text="100%")
                status.success("Dialogue audio created successfully.")
                st.caption(f"⏱️ Generated in {time.time() - start_time:.1f} seconds")
                st.audio(combined_audio, format="audio/mp3")
                st.download_button(
                    "⬇️ Download Dialogue MP3", combined_audio,
                    "WordWave_Dialogue.mp3", "audio/mpeg", use_container_width=True
                )
            except Exception as error:
                progress.empty()
                status.empty()
                show_generation_error("Dialogue generation failed.", error)

# ===========================================================
# TAB 3: AUDIOBOOK STUDIO
# ===========================================================
with tab3:
    st.markdown("### 📚 Audiobook & Subtitle Studio")
    studio_text = st.text_area("Paste long text here:", height=250, key="tab3_text")
    render_text_stats(studio_text)

    with st.expander("🛠️ Studio Settings", expanded=True):
        default_lang_index = base_languages.index("English") if "English" in base_languages else 0
        audiobook_lang = st.selectbox(
            "Main Language", base_languages, index=default_lang_index, key="ab_lang"
        )
        ab_locales = base_lang_map[audiobook_lang]
        audiobook_voices = [v for v in voices if v.get("Locale") in ab_locales]
        ab_voice_labels = [voice_label(v) for v in audiobook_voices]
        ab_voice_label = st.selectbox("Select Voice", ab_voice_labels, key="ab_voice") if ab_voice_labels else None
        audiobook_voice = audiobook_voices[ab_voice_labels.index(ab_voice_label)]["ShortName"] if ab_voice_label else None

        st.divider()
        music_file = st.file_uploader("Upload Background Music (Optional MP3)", type=["mp3"], key="ab_music")
        music_volume = st.slider("Music Volume Reduction (dB)", -30, -5, -15)
        clean_pdf = st.checkbox("Remove PDF line breaks (fixes weird pausing)", value=True)
        st.caption("Edge TTS word timings are retained temporarily in memory. No SRT is created unless you request it after audio generation.")

    if st.button("🏭 Start Audiobook Production", use_container_width=True, type="primary"):
        if not studio_text.strip():
            st.warning("Please enter text.")
        elif not audiobook_voice:
            st.warning("No voice is available for the selected language.")
        else:
            # A new production replaces any previous temporary subtitle timings.
            st.session_state["ab_audio_ready"] = False
            st.session_state["ab_word_timings"] = []
            source_text = studio_text
            if clean_pdf:
                source_text = re.sub(r"(?<!\n)\n(?!\n)", " ", source_text)
            status = st.empty()
            progress = st.progress(0)
            start_time = time.time()
            try:
                text_chunks = split_text_safely(source_text)
                if not text_chunks:
                    raise ValueError("No readable text remained after text cleanup.")

                async def build_audiobook():
                    combined = AudioSegment.empty()
                    total = len(text_chunks)
                    cumulative_audio_ms = 0
                    all_word_timings = []
                    for chunk_index, text_chunk in enumerate(text_chunks, start=1):
                        chunk_word_timings = []
                        chunk_bytes = await synthesize_with_retry(
                            text_chunk,
                            audiobook_voice,
                            chunk_label=f"Audiobook chunk {chunk_index}/{total}",
                            word_timings=chunk_word_timings
                        )
                        segment = AudioSegment.from_file(io.BytesIO(chunk_bytes), format="mp3")

                        # Edge TTS timestamps are relative to each request; shift them
                        # onto the continuous audiobook timeline before storing.
                        for timing in chunk_word_timings:
                            all_word_timings.append({
                                "text": timing["text"],
                                "start_ms": cumulative_audio_ms + timing["offset_ms"],
                                "end_ms": cumulative_audio_ms + timing["offset_ms"] + max(1, timing["duration_ms"]),
                            })

                        combined += segment
                        cumulative_audio_ms += len(segment)
                        percent = max(1, min(99, int(chunk_index / total * 99)))
                        progress.progress(percent, text=f"{percent}%")
                        if chunk_index < total:
                            await asyncio.sleep(REQUEST_PAUSE_SECONDS)

                    if len(combined) == 0:
                        raise RuntimeError("Audiobook synthesis returned an empty audio track.")

                    if music_file is not None:
                        music_file.seek(0)
                        music = AudioSegment.from_file(music_file, format="mp3")
                        if len(music) == 0:
                            raise ValueError("The uploaded background music file is empty or unreadable.")
                        music = music - abs(music_volume)
                        if len(music) < len(combined):
                            repeats = (len(combined) // len(music)) + 1
                            music = music * repeats
                        music = music[:len(combined)]
                        combined = combined.overlay(music)

                    output = io.BytesIO()
                    combined.export(output, format="mp3", bitrate="192k")
                    return output.getvalue(), total, len(combined), all_word_timings

                final_bytes, total_chunks, duration_ms, word_timings_for_session = asyncio.run(build_audiobook())
                progress.progress(100, text="100%")
                status.success("Audiobook created successfully.")
                st.caption(
                    f"⏱️ Generated in {time.time() - start_time:.1f} seconds | "
                    f"Audio duration: {duration_ms / 60000:.1f} minutes"
                )
                st.audio(final_bytes, format="audio/mp3")
                st.download_button(
                    "⬇️ Download Full Audiobook (MP3)", final_bytes,
                    "WordWave_Audiobook.mp3", "audio/mpeg", use_container_width=True
                )

                # Temporary session-memory cache only. No SRT formatting/file work
                # is performed during audio synthesis.
                st.session_state["ab_word_timings"] = word_timings_for_session
                st.session_state["ab_audio_duration_ms"] = duration_ms
                st.session_state["ab_audio_ready"] = True


            except Exception as error:
                progress.empty()
                status.empty()
                show_generation_error("Audiobook production failed.", error)



    # Create exact word-by-word SRT only after the user explicitly requests it.
    # Timing data is held in Streamlit session memory and is not written to disk.
    if st.session_state.get("ab_audio_ready"):
        st.divider()
        st.markdown("#### Optional word-by-word subtitles")
        st.caption("Uses Edge TTS word-boundary timestamps retained temporarily during synthesis. No SRT is created during audio generation.")
        if st.button("📝 Create word-by-word SRT", key="create_word_srt"):
            saved_timings = st.session_state.get("ab_word_timings", [])
            if not saved_timings:
                st.error(
                    "Edge TTS did not return word-boundary timing metadata for this audio. "
                    "A word-by-word SRT cannot be created accurately."
                )
            else:
                def srt_stamp(milliseconds):
                    milliseconds = max(0, int(milliseconds))
                    hours = milliseconds // 3600000
                    minutes = (milliseconds % 3600000) // 60000
                    seconds = (milliseconds % 60000) // 1000
                    millis = milliseconds % 1000
                    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"

                srt_entries = []
                for item in saved_timings:
                    word = item.get("text", "").strip()
                    if not word:
                        continue
                    begin = item["start_ms"]
                    finish = max(begin + 1, item["end_ms"])
                    srt_entries.append(
                        f"{len(srt_entries) + 1}\n"
                        f"{srt_stamp(begin)} --> {srt_stamp(finish)}\n"
                        f"{word}\n"
                    )

                if srt_entries:
                    st.download_button(
                        "⬇️ Download Word-by-Word SRT",
                        "\n".join(srt_entries).encode("utf-8"),
                        "WordWave_Word_Timing.srt",
                        "application/x-subrip",
                        use_container_width=True,
                        key="download_word_srt"
                    )
                else:
                    st.error("No usable word-boundary timing entries were returned by Edge TTS.")

