import streamlit as st
import asyncio
import edge_tts
import aiohttp
import pdfplumber
import pandas as pd
from docx import Document

---------------------------------------------------

PAGE CONFIGURATION

---------------------------------------------------

st.set_page_config(
page_title="Keep Laughing Voice Generator",
page_icon="logo.png",
layout="wide"
)

---------------------------------------------------

HEADER

---------------------------------------------------

col1, col2 = st.columns([1, 8])

with col1:
try:
st.image("logo.png", width=150)
except Exception:
st.write("🎙️")

with col2:
st.title("Keep Laughing with Hussaa1nn")
st.caption("Text-to-speech and audiobook generator")

---------------------------------------------------

LOAD EDGE TTS VOICES

---------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def load_voices():
async def get_voices():
return await edge_tts.list_voices()

return asyncio.run(get_voices())

try:
with st.spinner("Loading available voices..."):
voices = load_voices()

except Exception as e:
st.error(
"Could not load the available voices from the speech service."
)
st.write(f"Error type: {type(e).name}")
st.info(
"Check your internet connection and Streamlit Cloud logs. "
"If the service is temporarily unavailable, try again later."
)
print("Voice loading error:", repr(e))
st.stop()

if not voices:
st.error("No voices were returned by the speech service.")
st.stop()

---------------------------------------------------

FILE TEXT EXTRACTION

---------------------------------------------------

def extract_text(file):
extension = file.name.rsplit(".", 1)[-1].lower()

if extension == "txt":
    return file.getvalue().decode("utf-8-sig")

elif extension == "pdf":
    extracted_pages = []

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                extracted_pages.append(page_text)

    return "\n\n".join(extracted_pages)

elif extension == "docx":
    doc = Document(file)
    return "\n".join(
        paragraph.text for paragraph in doc.paragraphs
    )

elif extension in ["xls", "xlsx"]:
    dataframe = pd.read_excel(file)
    return dataframe.to_string(index=False)

return ""

---------------------------------------------------

LANGUAGE MAP

---------------------------------------------------

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

---------------------------------------------------

LANGUAGE SELECTION

---------------------------------------------------

locale_display = {}

for voice in voices:
locale = voice["Locale"]

if locale in LANGUAGE_MAP:
    locale_display[locale] = LANGUAGE_MAP[locale]
else:
    parts = locale.split("-")

    if len(parts) == 2:
        locale_display[locale] = (
            f"{parts[0].upper()} ({parts[1].upper()})"
        )
    else:
        locale_display[locale] = locale

sorted_languages = sorted(
locale_display.items(),
key=lambda item: item[1]
)

language_labels = [
label for code, label in sorted_languages
]

language_choice = st.selectbox(
"🌍 Select Language",
language_labels,
key="language_choice"
)

selected_locale = next(
code
for code, label in sorted_languages
if label == language_choice
)

filtered_voices = [
voice for voice in voices
if voice["Locale"] == selected_locale
]

---------------------------------------------------

GENDER FILTER

---------------------------------------------------

if "gender_filter" not in st.session_state:
st.session_state.gender_filter = "All"

st.markdown("### 🎭 Voice Gender")

col1, col2, col3 = st.columns(3)

with col1:
if st.button("All Voices", use_container_width=True):
st.session_state.gender_filter = "All"

with col2:
if st.button("Male Voices", use_container_width=True):
st.session_state.gender_filter = "Male"

with col3:
if st.button("Female Voices", use_container_width=True):
st.session_state.gender_filter = "Female"

if st.session_state.gender_filter in ["Male", "Female"]:
filtered_voices = [
voice for voice in filtered_voices
if voice["Gender"] == st.session_state.gender_filter
]

---------------------------------------------------

VOICE SELECTION

---------------------------------------------------

voice_map = {}

for voice in filtered_voices:
short_name = voice["ShortName"]

clean_name = (
    short_name.split("-")[-1].replace("Neural", "")
)

label = f"{clean_name} ({voice['Gender']})"
voice_map[label] = short_name

voice_labels = sorted(voice_map.keys())

if not voice_labels:
st.warning(
"No voices match this language and gender filter. "
"Select another language or choose All Voices."
)
st.stop()

voice_choice = st.selectbox(
"🎤 Select Voice",
voice_labels,
key="voice_choice"
)

selected_voice = voice_map[voice_choice]

---------------------------------------------------

SPEED AND PITCH

---------------------------------------------------

st.markdown("### 🎚️ Voice Settings")

col1, col2 = st.columns(2)

with col1:
speed = st.slider(
"⚡ Speed",
min_value=-50,
max_value=50,
value=0,
step=1
)

with col2:
pitch = st.slider(
"🎵 Pitch",
min_value=-50,
max_value=50,
value=0,
step=1
)

def format_rate(value):
return f"{value:+d}%"

def format_pitch(value):
return f"{value:+d}Hz"

---------------------------------------------------

SAMPLE VOICE PREVIEW

---------------------------------------------------

async def create_sample():
communicate = edge_tts.Communicate(
text="Hello, this is a sample voice preview.",
voice=selected_voice
)
await communicate.save("sample.mp3")

if st.button("▶ Play Sample Voice"):
try:
with st.spinner("Creating voice sample..."):
asyncio.run(create_sample())

    st.audio("sample.mp3", format="audio/mpeg")

except Exception as e:
    st.error(
        f"Sample generation failed: {type(e).__name__}"
    )
    if isinstance(
        e, aiohttp.client_exceptions.WSServerHandshakeError
    ):
        st.error(f"Speech service HTTP status: {e.status}")

    print("Sample generation error:", repr(e))

---------------------------------------------------

INPUT TEXT OR UPLOAD A FILE

---------------------------------------------------

st.markdown("### 📄 Text Input")

uploaded_file = st.file_uploader(
"Upload a PDF, DOCX, TXT, XLS, or XLSX file",
type=["pdf", "docx", "txt", "xls", "xlsx"]
)

if "original_text" not in st.session_state:
st.session_state.original_text = ""

if "edited_text" not in st.session_state:
st.session_state.edited_text = ""

if "last_file_signature" not in st.session_state:
st.session_state.last_file_signature = None

final_text = ""

if uploaded_file is not None:
file_signature = (
uploaded_file.name,
uploaded_file.size
)

if (
    st.session_state.last_file_signature
    != file_signature
):
    try:
        extracted = extract_text(uploaded_file)

        st.session_state.original_text = extracted
        st.session_state.edited_text = extracted
        st.session_state.last_file_signature = file_signature

        # Reset the editor when a different file is uploaded.
        st.session_state.text_editor = extracted

    except Exception as e:
        st.error(
            f"Could not read the uploaded file: {type(e).__name__}"
        )
        print("File extraction error:", repr(e))
        st.stop()

st.info(f"📂 File loaded: {uploaded_file.name}")

st.markdown("#### ✏️ Edit Extracted Text")
st.caption(
    "Edit the extracted text below. The edited version "
    "will be used to generate the audio."
)

if "text_editor" not in st.session_state:
    st.session_state.text_editor = (
        st.session_state.edited_text
    )

edited = st.text_area(
    "Text Editor",
    height=400,
    key="text_editor",
    label_visibility="collapsed"
)

st.session_state.edited_text = edited
final_text = edited

col1, col2 = st.columns(2)

with col1:
    if st.button(
        "🔄 Reset to Original",
        use_container_width=True
    ):
        st.session_state.text_editor = (
            st.session_state.original_text
        )
        st.session_state.edited_text = (
            st.session_state.original_text
        )
        st.rerun()

with col2:
    if st.button(
        "🗑 Clear All",
        use_container_width=True
    ):
        st.session_state.text_editor = ""
        st.session_state.edited_text = ""
        st.rerun()

else:
if "pasted_text" not in st.session_state:
st.session_state.pasted_text = ""

final_text = st.text_area(
    "Paste your text here",
    height=250,
    key="pasted_text",
    placeholder="Enter the text you want to convert into speech..."
)

---------------------------------------------------

TEXT STATISTICS

---------------------------------------------------

st.markdown("### 📊 Text Statistics")

characters = len(final_text)
words = len(final_text.split())

sentences = len([
sentence
for sentence in (
final_text.replace("!", ".")
.replace("?", ".")
.split(".")
)
if sentence.strip()
])

paragraphs = len([
paragraph
for paragraph in final_text.split("\n\n")
import streamlit as st
import asyncio
import edge_tts
import aiohttp
import pdfplumber
import pandas as pd
from docx import Document

---------------------------------------------------

PAGE CONFIGURATION

---------------------------------------------------

st.set_page_config(
page_title="Keep Laughing Voice Generator",
page_icon="logo.png",
layout="wide"
)

---------------------------------------------------

HEADER

---------------------------------------------------

col1, col2 = st.columns([1, 8])

with col1:
try:
st.image("logo.png", width=150)
except Exception:
st.write("🎙️")

with col2:
st.title("Keep Laughing with Hussaa1nn")
st.caption("Text-to-speech and audiobook generator")

---------------------------------------------------

LOAD EDGE TTS VOICES

---------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def load_voices():
async def get_voices():
return await edge_tts.list_voices()

return asyncio.run(get_voices())

try:
with st.spinner("Loading available voices..."):
voices = load_voices()

except Exception as e:
st.error(
"Could not load the available voices from the speech service."
)
st.write(f"Error type: {type(e).name}")
st.info(
"Check your internet connection and Streamlit Cloud logs. "
"If the service is temporarily unavailable, try again later."
)
print("Voice loading error:", repr(e))
st.stop()

if not voices:
st.error("No voices were returned by the speech service.")
st.stop()

---------------------------------------------------

FILE TEXT EXTRACTION

---------------------------------------------------

def extract_text(file):
extension = file.name.rsplit(".", 1)[-1].lower()

if extension == "txt":
    return file.getvalue().decode("utf-8-sig")

elif extension == "pdf":
    extracted_pages = []

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                extracted_pages.append(page_text)

    return "\n\n".join(extracted_pages)

elif extension == "docx":
    doc = Document(file)
    return "\n".join(
        paragraph.text for paragraph in doc.paragraphs
    )

elif extension in ["xls", "xlsx"]:
    dataframe = pd.read_excel(file)
    return dataframe.to_string(index=False)

return ""

---------------------------------------------------

LANGUAGE MAP

---------------------------------------------------

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

---------------------------------------------------

LANGUAGE SELECTION

---------------------------------------------------

locale_display = {}

for voice in voices:
locale = voice["Locale"]

if locale in LANGUAGE_MAP:
    locale_display[locale] = LANGUAGE_MAP[locale]
else:
    parts = locale.split("-")

    if len(parts) == 2:
        locale_display[locale] = (
            f"{parts[0].upper()} ({parts[1].upper()})"
        )
    else:
        locale_display[locale] = locale

sorted_languages = sorted(
locale_display.items(),
key=lambda item: item[1]
)

language_labels = [
label for code, label in sorted_languages
]

language_choice = st.selectbox(
"🌍 Select Language",
language_labels,
key="language_choice"
)

selected_locale = next(
code
for code, label in sorted_languages
if label == language_choice
)

filtered_voices = [
voice for voice in voices
if voice["Locale"] == selected_locale
]

---------------------------------------------------

GENDER FILTER

---------------------------------------------------

if "gender_filter" not in st.session_state:
st.session_state.gender_filter = "All"

st.markdown("### 🎭 Voice Gender")

col1, col2, col3 = st.columns(3)

with col1:
if st.button("All Voices", use_container_width=True):
st.session_state.gender_filter = "All"

with col2:
if st.button("Male Voices", use_container_width=True):
st.session_state.gender_filter = "Male"

with col3:
if st.button("Female Voices", use_container_width=True):
st.session_state.gender_filter = "Female"

if st.session_state.gender_filter in ["Male", "Female"]:
filtered_voices = [
voice for voice in filtered_voices
if voice["Gender"] == st.session_state.gender_filter
]

---------------------------------------------------

VOICE SELECTION

---------------------------------------------------

voice_map = {}

for voice in filtered_voices:
short_name = voice["ShortName"]

clean_name = (
    short_name.split("-")[-1].replace("Neural", "")
)

label = f"{clean_name} ({voice['Gender']})"
voice_map[label] = short_name

voice_labels = sorted(voice_map.keys())

if not voice_labels:
st.warning(
"No voices match this language and gender filter. "
"Select another language or choose All Voices."
)
st.stop()

voice_choice = st.selectbox(
"🎤 Select Voice",
voice_labels,
key="voice_choice"
)

selected_voice = voice_map[voice_choice]

---------------------------------------------------

SPEED AND PITCH

---------------------------------------------------

st.markdown("### 🎚️ Voice Settings")

col1, col2 = st.columns(2)

with col1:
speed = st.slider(
"⚡ Speed",
min_value=-50,
max_value=50,
value=0,
step=1
)

with col2:
pitch = st.slider(
"🎵 Pitch",
min_value=-50,
max_value=50,
value=0,
step=1
)

def format_rate(value):
return f"{value:+d}%"

def format_pitch(value):
return f"{value:+d}Hz"

---------------------------------------------------

SAMPLE VOICE PREVIEW

---------------------------------------------------

async def create_sample():
communicate = edge_tts.Communicate(
text="Hello, this is a sample voice preview.",
voice=selected_voice
)
await communicate.save("sample.mp3")

if st.button("▶ Play Sample Voice"):
try:
with st.spinner("Creating voice sample..."):
asyncio.run(create_sample())

    st.audio("sample.mp3", format="audio/mpeg")

except Exception as e:
    st.error(
        f"Sample generation failed: {type(e).__name__}"
    )
    if isinstance(
        e, aiohttp.client_exceptions.WSServerHandshakeError
    ):
        st.error(f"Speech service HTTP status: {e.status}")

    print("Sample generation error:", repr(e))

---------------------------------------------------

INPUT TEXT OR UPLOAD A FILE

---------------------------------------------------

st.markdown("### 📄 Text Input")

uploaded_file = st.file_uploader(
"Upload a PDF, DOCX, TXT, XLS, or XLSX file",
type=["pdf", "docx", "txt", "xls", "xlsx"]
)

if "original_text" not in st.session_state:
st.session_state.original_text = ""

if "edited_text" not in st.session_state:
st.session_state.edited_text = ""

if "last_file_signature" not in st.session_state:
st.session_state.last_file_signature = None

final_text = ""

if uploaded_file is not None:
file_signature = (
uploaded_file.name,
uploaded_file.size
)

if (
    st.session_state.last_file_signature
    != file_signature
):
    try:
        extracted = extract_text(uploaded_file)

        st.session_state.original_text = extracted
        st.session_state.edited_text = extracted
        st.session_state.last_file_signature = file_signature

        # Reset the editor when a different file is uploaded.
        st.session_state.text_editor = extracted

    except Exception as e:
        st.error(
            f"Could not read the uploaded file: {type(e).__name__}"
        )
        print("File extraction error:", repr(e))
        st.stop()

st.info(f"📂 File loaded: {uploaded_file.name}")

st.markdown("#### ✏️ Edit Extracted Text")
st.caption(
    "Edit the extracted text below. The edited version "
    "will be used to generate the audio."
)

if "text_editor" not in st.session_state:
    st.session_state.text_editor = (
        st.session_state.edited_text
    )

edited = st.text_area(
    "Text Editor",
    height=400,
    key="text_editor",
    label_visibility="collapsed"
)

st.session_state.edited_text = edited
final_text = edited

col1, col2 = st.columns(2)

with col1:
    if st.button(
        "🔄 Reset to Original",
        use_container_width=True
    ):
        st.session_state.text_editor = (
            st.session_state.original_text
        )
        st.session_state.edited_text = (
            st.session_state.original_text
        )
        st.rerun()

with col2:
    if st.button(
        "🗑 Clear All",
        use_container_width=True
    ):
        st.session_state.text_editor = ""
        st.session_state.edited_text = ""
        st.rerun()

else:
if "pasted_text" not in st.session_state:
st.session_state.pasted_text = ""

final_text = st.text_area(
    "Paste your text here",
    height=250,
    key="pasted_text",
    placeholder="Enter the text you want to convert into speech..."
)

---------------------------------------------------

TEXT STATISTICS

---------------------------------------------------

st.markdown("### 📊 Text Statistics")

characters = len(final_text)
words = len(final_text.split())

sentences = len([
sentence
for sentence in (
final_text.replace("!", ".")
.replace("?", ".")
.split(".")
)
if sentence.strip()
])

paragraphs = len([
paragraph
for paragraph in final_text.split("\n\n")
if paragraph.strip()
])

lines = len([
line
for line in final_text.splitlines()
if line.strip()
])

c1, c2, c3, c4, c5 = st.columns(5)

c1.metric("Characters", characters)
c2.metric("Words", words)
c3.metric("Sentences", sentences)
c4.metric("Paragraphs", paragraphs)
c5.metric("Lines", lines)

---------------------------------------------------

AUDIO GENERATION

---------------------------------------------------

OUTPUT_FILE = "output.mp3"

async def generate_audio():
communicate = edge_tts.Communicate(
text=final_text,
voice=selected_voice,
rate=format_rate(speed),
pitch=format_pitch(pitch)
)

await communicate.save(OUTPUT_FILE)

---------------------------------------------------

GENERATE AUDIO BUTTON WITH ERROR DIAGNOSTICS

---------------------------------------------------

if st.button(
"🚀 Generate Audiobook",
type="primary",
use_container_width=True
):
if not final_text.strip():
st.warning(
"Please enter text or upload a file and make sure "
"the text editor is not empty."
)

else:
    try:
        with st.spinner(
            "Generating audio... Please wait."
        ):
            asyncio.run(generate_audio())

        st.success("Audio generated successfully! 🎧")

        st.audio(
            OUTPUT_FILE,
            format="audio/mpeg"
        )

        with open(OUTPUT_FILE, "rb") as audio_file:
            audio_bytes = audio_file.read()

        st.download_button(
            label="⬇️ Download MP3",
            data=audio_bytes,
            file_name="audiobook.mp3",
            mime="audio/mpeg",
            use_container_width=True
        )

    except aiohttp.client_exceptions.WSServerHandshakeError as e:
        st.error(
            "The speech service rejected the WebSocket connection."
        )
        st.error(f"HTTP status: {e.status}")
        st.write(
            "This is a connection or service-response issue, "
            "not an error caused by the page heading."
        )
        st.info(
            "Check the Streamlit Cloud app logs for the detailed "
            "exception. The HTTP status will help identify the cause."
        )
        print("TTS handshake error:", repr(e))

    except aiohttp.ClientError as e:
        st.error(
            "Could not connect to the speech service."
        )
        st.write(f"Error type: {type(e).__name__}")
        st.info(
            "Check the app logs and try again. The service or "
            "network connection may be temporarily unavailable."
        )
        print("TTS network error:", repr(e))

    except Exception as e:
        st.error(
            f"Audio generation failed: {type(e).__name__}"
        )
        st.write(
            "Open the Streamlit Cloud logs to see the detailed error."
        )
        print("TTS generation error:", repr(e))
