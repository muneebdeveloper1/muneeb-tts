import streamlit as st
import asyncio
import edge_tts
from collections import defaultdict
import pdfplumber
from docx import Document
import pandas as pd

st.set_page_config(page_title="Keep laughing voice generator", page_icon="logo.png", layout="wide")

col1, col2 = st.columns([1, 8])
with col1:
    st.image("logo.png", width=150)
with col2:
    st.title("Keep laughing with Muneeb")

# -----------------------------------
# LOAD ALL EDGE TTS VOICES
# -----------------------------------
@st.cache_data
def load_voices():
    async def get():
        return await edge_tts.list_voices()
    return asyncio.run(get())

voices = load_voices()

# -----------------------------------
# FILE READER (NEW UPGRADE)
# -----------------------------------
def extract_text(file):
    file_type = file.name.split(".")[-1].lower()

    if file_type == "txt":
        return file.read().decode("utf-8")

    elif file_type == "pdf":
        text = ""
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                if page.extract_text():
                    text += page.extract_text() + "\n"
        return text

    elif file_type == "docx":
        doc = Document(file)
        return "\n".join([p.text for p in doc.paragraphs])

    elif file_type in ["xls", "xlsx"]:
        df = pd.read_excel(file)
        return df.to_string(index=False)

    else:
        return ""

# -----------------------------------
# LANGUAGE NAME MAPPING
# -----------------------------------
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
    "vi-VN": "Vietnamese (Vietnam)",
}

# -----------------------------------
# AUTO LANGUAGE DISPLAY
# -----------------------------------
locale_display = {}

for v in voices:
    locale = v["Locale"]
    if locale in LANGUAGE_MAP:
        locale_display[locale] = LANGUAGE_MAP[locale]
    else:
        parts = locale.split("-")
        if len(parts) == 2:
            locale_display[locale] = f"{parts[0].upper()} ({parts[1].upper()})"
        else:
            locale_display[locale] = locale

sorted_languages = sorted(locale_display.items(), key=lambda x: x[1])
language_labels = [label for code, label in sorted_languages]

language_choice = st.selectbox("🌍 Select Language", language_labels)

selected_locale = None
for code, label in sorted_languages:
    if label == language_choice:
        selected_locale = code
        break

filtered = [v for v in voices if v["Locale"] == selected_locale]

# -----------------------------------
# GENDER FILTER
# -----------------------------------
col1, col2, col3 = st.columns(3)

with col1:
    show_all = st.button("All Voices")
with col2:
    show_male = st.button("Male Voices")
with col3:
    show_female = st.button("Female Voices")

if show_male:
    filtered = [v for v in filtered if v["Gender"] == "Male"]

if show_female:
    filtered = [v for v in filtered if v["Gender"] == "Female"]

# -----------------------------------
# VOICE SELECTION
# -----------------------------------
voice_map = {}
voice_labels = []

for v in filtered:
    short_voice = v["ShortName"]
    clean_name = short_voice.split("-")[-1]
    clean_name = clean_name.replace("Neural", "")
    label = f"{clean_name} ({v['Gender']})"
    voice_map[label] = short_voice
    voice_labels.append(label)

voice_choice = st.selectbox("🎤 Select Voice", voice_labels)
voice = voice_map[voice_choice]

# -----------------------------------
# SAMPLE VOICE
# -----------------------------------
async def play_sample():
    sample_text = "Hello, this is a sample voice preview."
    communicate = edge_tts.Communicate(sample_text, voice)
    await communicate.save("sample.mp3")

if st.button("▶ Play Sample Voice"):
    asyncio.run(play_sample())
    st.audio("sample.mp3")

# -----------------------------------
# INPUT (FILE + TEXT)
# -----------------------------------
uploaded_file = st.file_uploader(
    "📁 Upload File (PDF, DOCX, TXT, Excel)",
    type=["pdf", "docx", "txt", "xls", "xlsx"]
)

if uploaded_file is not None:
    text = extract_text(uploaded_file)
else:
    text = st.text_area("📄 Paste your text", height=250)

# -----------------------------------
# TEXT STATS
# -----------------------------------
characters = len(text)
words = len(text.split())
sentences = len([s for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()])
paragraphs = len([p for p in text.split("\n\n") if p.strip()])
lines = len([line for line in text.split("\n") if line.strip()])

st.markdown("### 📊 Text Statistics")

c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    st.metric("Characters", characters)
with c2:
    st.metric("Words", words)
with c3:
    st.metric("Sentences", sentences)
with c4:
    st.metric("Paragraphs", paragraphs)
with c5:
    st.metric("Lines", lines)

# -----------------------------------
# SPEED + PITCH
# -----------------------------------
speed = st.slider("⚡ Speed", -50, 50, 0)
pitch = st.slider("🎚 Pitch", -50, 50, 0)

def format_rate(v):
    return f"+{v}%" if v >= 0 else f"{v}%"

def format_pitch(v):
    return f"+{v}Hz" if v >= 0 else f"{v}Hz"

# -----------------------------------
# AUDIO GENERATION
# -----------------------------------
output_file = "output.mp3"

async def generate():
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=format_rate(speed),
        pitch=format_pitch(pitch)
    )
    await communicate.save(output_file)

# -----------------------------------
# GENERATE BUTTON
# -----------------------------------
if st.button("🚀 Generate Audiobook"):
    if not text.strip():
        st.warning("Please add text or upload file")
    else:
        with st.spinner("Generating audio..."):
            asyncio.run(generate())

        st.success("Done!")
        st.audio(output_file)

        st.download_button(
            "⬇ Download MP3",
            open(output_file, "rb"),
            file_name="audiobook.mp3"
        )