
import streamlit as st
import asyncio
import edge_tts
import aiohttp
import pdfplumber
import pandas as pd
from docx import Document
from pathlib import Path

# ---------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------
st.set_page_config(
    page_title="Keep Laughing Voice Generator",
    page_icon="🎙️",
    layout="wide"
)

# ---------------------------------------------------
# HEADER
# ---------------------------------------------------
col1, col2 = st.columns([1, 8])

with col1:
    logo_path = Path("logo.png")
    if logo_path.exists():
        st.image(str(logo_path), width=120)
    else:
        st.write("🎙️")

with col2:
    st.title("Keep Laughing with Hussaa1nn")
    st.caption("Text-to-speech and audiobook generator")

# ---------------------------------------------------
# LOAD VOICES
# ---------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def load_voices():
    async def get_voices():
        return await edge_tts.list_voices()

    return asyncio.run(get_voices())


try:
    with st.spinner("Loading voices..."):
        voices = load_voices()
except Exception as e:
    st.error(f"Could not load voices: {type(e).__name__}")
    st.info("Check the Streamlit Cloud logs and try again.")
    print("Voice loading error:", repr(e))
    st.stop()

if not voices:
    st.error("No voices are currently available.")
    st.stop()

# ---------------------------------------------------
# LANGUAGE MAP
# ---------------------------------------------------
LANGUAGE_MAP = {
    "en-US": "English (United States)",
    "en-GB": "English (United Kingdom)",
    "en-AU": "English (Australia)",
    "en-CA": "English (Canada)",
    "en-IN": "English (India)",
    "ur-PK": "Urdu (Pakistan)",
    "hi-IN": "Hindi (India)",
    "ar-SA": "Arabic (Saudi Arabia)",
    "tr-TR": "Turkish (Turkey)",
    "fr-FR": "French (France)",
    "de-DE": "German (Germany)",
    "es-ES": "Spanish (Spain)",
    "it-IT": "Italian (Italy)",
    "pt-BR": "Portuguese (Brazil)",
    "ru-RU": "Russian (Russia)",
    "ja-JP": "Japanese (Japan)",
    "ko-KR": "Korean (South Korea)",
    "zh-CN": "Chinese (China)",
    "bn-BD": "Bengali (Bangladesh)",
    "fa-IR": "Persian (Iran)",
    "id-ID": "Indonesian (Indonesia)",
    "ms-MY": "Malay (Malaysia)",
    "nl-NL": "Dutch (Netherlands)",
    "pl-PL": "Polish (Poland)",
    "sv-SE": "Swedish (Sweden)",
    "ta-IN": "Tamil (India)",
    "te-IN": "Telugu (India)",
    "th-TH": "Thai (Thailand)",
    "uk-UA": "Ukrainian (Ukraine)",
    "vi-VN": "Vietnamese (Vietnam)"
}

# ---------------------------------------------------
# LANGUAGE SELECTION
# ---------------------------------------------------
locale_display = {}

for voice in voices:
    locale = voice["Locale"]
    locale_display[locale] = LANGUAGE_MAP.get(
        locale,
        locale
    )

sorted_languages = sorted(
    locale_display.items(),
    key=lambda item: item[1]
)

language_choice = st.selectbox(
    "🌍 Select Language",
    [label for code, label in sorted_languages]
)

selected_locale = next(
    code for code, label in sorted_languages
    if label == language_choice
)

filtered_voices = [
    voice for voice in voices
    if voice["Locale"] == selected_locale
]

# ---------------------------------------------------
# VOICE GENDER FILTER
# ---------------------------------------------------
if "gender_filter" not in st.session_state:
    st.session_state.gender_filter = "All"

g1, g2, g3 = st.columns(3)

with g1:
    if st.button("All Voices", use_container_width=True):
        st.session_state.gender_filter = "All"

with g2:
    if st.button("Male Voices", use_container_width=True):
        st.session_state.gender_filter = "Male"

with g3:
    if st.button("Female Voices", use_container_width=True):
        st.session_state.gender_filter = "Female"

if st.session_state.gender_filter != "All":
    filtered_voices = [
        voice for voice in filtered_voices
        if voice["Gender"] == st.session_state.gender_filter
    ]

# ---------------------------------------------------
# VOICE SELECTION
# ---------------------------------------------------
voice_map = {}

for voice in filtered_voices:
    short_name = voice["ShortName"]
    clean_name = short_name.split("-")[-1].replace(
        "Neural", ""
    ).strip()

    label = f"{clean_name} ({voice['Gender']})"
    voice_map[label] = short_name

voice_labels = sorted(voice_map.keys())

if not voice_labels:
    st.warning("No voices found for this selection.")
    st.stop()

voice_choice = st.selectbox(
    "🎤 Select Voice",
    voice_labels
)

selected_voice = voice_map[voice_choice]

# ---------------------------------------------------
# SPEED AND PITCH
# ---------------------------------------------------
st.markdown("### 🎚️ Voice Settings")

c1, c2 = st.columns(2)

with c1:
    speed = st.slider(
        "⚡ Speed",
        min_value=-50,
        max_value=50,
        value=0
    )

with c2:
    pitch = st.slider(
        "🎵 Pitch",
        min_value=-50,
        max_value=50,
        value=0
    )


def format_rate(value):
    return f"{value:+d}%"


def format_pitch(value):
    return f"{value:+d}Hz"

# ---------------------------------------------------
# SAMPLE VOICE PREVIEW
# ---------------------------------------------------
async def create_sample():
    communicate = edge_tts.Communicate(
        text="Hello, this is a sample voice preview.",
        voice=selected_voice
    )
    await communicate.save("sample.mp3")


if st.button("▶ Play Sample Voice"):
    try:
        with st.spinner("Generating sample..."):
            asyncio.run(create_sample())

        with open("sample.mp3", "rb") as sample_file:
            st.audio(sample_file.read(), format="audio/mpeg")

    except Exception as e:
        st.error(f"Sample failed: {type(e).__name__}")

        if isinstance(
            e,
            aiohttp.client_exceptions.WSServerHandshakeError
        ):
            st.error(f"Speech service HTTP status: {e.status}")

        print("Sample error:", repr(e))

# ---------------------------------------------------
# FILE TEXT EXTRACTION
# ---------------------------------------------------
def extract_text(uploaded_file):
    extension = uploaded_file.name.rsplit(".", 1)[-1].lower()

    if extension == "txt":
        return uploaded_file.getvalue().decode("utf-8-sig")

    if extension == "pdf":
        pages = []

        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    pages.append(page_text)

        return "\n\n".join(pages)

    if extension == "docx":
        document = Document(uploaded_file)
        return "\n".join(
            paragraph.text for paragraph in document.paragraphs
        )

    if extension in ("xls", "xlsx"):
        dataframe = pd.read_excel(uploaded_file)
        return dataframe.to_string(index=False)

    return ""

# ---------------------------------------------------
# TEXT INPUT OR FILE UPLOAD
# ---------------------------------------------------
st.markdown("### 📄 Text Input")

uploaded_file = st.file_uploader(
    "Upload PDF, DOCX, TXT, XLS, or XLSX",
    type=["pdf", "docx", "txt", "xls", "xlsx"]
)

if "original_text" not in st.session_state:
    st.session_state.original_text = ""

if "edited_text" not in st.session_state:
    st.session_state.edited_text = ""

if "last_file_signature" not in st.session_state:
    st.session_state.last_file_signature = None

if uploaded_file is not None:
    signature = (
        uploaded_file.name,
        uploaded_file.size
    )

    if signature != st.session_state.last_file_signature:
        try:
            extracted_text = extract_text(uploaded_file)
            st.session_state.original_text = extracted_text
            st.session_state.edited_text = extracted_text
            st.session_state.last_file_signature = signature
            st.session_state.text_editor = extracted_text

        except Exception as e:
            st.error(f"File reading failed: {type(e).__name__}")
            print("File extraction error:", repr(e))
            st.stop()

    st.info(f"File loaded: {uploaded_file.name}")

    st.caption("Edit the extracted text before generating audio.")

    if "text_editor" not in st.session_state:
        st.session_state.text_editor = st.session_state.edited_text

    final_text = st.text_area(
        "Edit extracted text",
        height=350,
        key="text_editor"
    )

    st.session_state.edited_text = final_text

    b1, b2 = st.columns(2)

    with b1:
        if st.button("🔄 Reset to Original", use_container_width=True):
            st.session_state.text_editor = st.session_state.original_text
            st.session_state.edited_text = st.session_state.original_text
            st.rerun()

    with b2:
        if st.button("🗑 Clear All", use_container_width=True):
            st.session_state.text_editor = ""
            st.session_state.edited_text = ""
            st.rerun()

else:
    final_text = st.text_area(
        "Paste your text",
        height=250,
        key="pasted_text",
        placeholder="Enter the text you want to convert to speech..."
    )

# ---------------------------------------------------
# TEXT STATISTICS
# ---------------------------------------------------
st.markdown("### 📊 Text Statistics")

characters = len(final_text)
words = len(final_text.split())

sentences = len([
    item for item in (
        final_text.replace("!", ".")
        .replace("?", ".")
        .split(".")
    )
    if item.strip()
])

paragraphs = len([
    item for item in final_text.split("\n\n")
    if item.strip()
])

lines = len([
    item for item in final_text.splitlines()
    if item.strip()
])

s1, s2, s3, s4, s5 = st.columns(5)

s1.metric("Characters", characters)
s2.metric("Words", words)
s3.metric("Sentences", sentences)
s4.metric("Paragraphs", paragraphs)
s5.metric("Lines", lines)

# ---------------------------------------------------
# AUDIO GENERATION
# ---------------------------------------------------
OUTPUT_FILE = "output.mp3"


async def generate_audio():
    communicate = edge_tts.Communicate(
        text=final_text,
        voice=selected_voice,
        rate=format_rate(speed),
        pitch=format_pitch(pitch)
    )

    await communicate.save(OUTPUT_FILE)

# ---------------------------------------------------
# GENERATE AUDIO BUTTON
# ---------------------------------------------------
if st.button(
    "🚀 Generate Audiobook",
    type="primary",
    use_container_width=True
):
    if not final_text.strip():
        st.warning("Please enter text or upload a file first.")

    else:
        try:
            with st.spinner("Generating audio... Please wait."):
                asyncio.run(generate_audio())

            with open(OUTPUT_FILE, "rb") as audio_file:
                audio_bytes = audio_file.read()

            st.success("Audio generated successfully! 🎧")
            st.audio(audio_bytes, format="audio/mpeg")

            st.download_button(
                label="⬇️ Download MP3",
                data=audio_bytes,
                file_name="audiobook.mp3",
                mime="audio/mpeg",
                use_container_width=True
            )

        except aiohttp.client_exceptions.WSServerHandshakeError as e:
            st.error("The speech service rejected the connection.")
            st.error(f"HTTP status: {e.status}")
            st.info(
                "This is a speech-service connection issue. "
                "Check the Streamlit Cloud logs for details."
            )
            print("TTS handshake error:", repr(e))

        except aiohttp.ClientError as e:
            st.error("Could not connect to the speech service.")
            st.write(f"Error type: {type(e).__name__}")
            print("TTS network error:", repr(e))

        except Exception as e:
            st.error(f"Audio generation failed: {type(e).__name__}")
            st.info("Open the Streamlit Cloud logs for the full error.")
            print("TTS generation error:", repr(e))
