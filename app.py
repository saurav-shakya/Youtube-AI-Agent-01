import streamlit as st
import google.generativeai as genai
from googleapiclient.discovery import build
from dotenv import load_dotenv
import os
import re
from datetime import datetime
import isodate
from pytube import YouTube
import tempfile
import cv2
import numpy as np
from PIL import Image
import io
import base64
import yt_dlp
from phi.agent import Agent
from phi.model.google import Gemini
from phi.tools.duckduckgo import DuckDuckGo
from google.generativeai import upload_file, get_file
import time
from streamlit.runtime.scriptrunner import get_script_run_ctx
from streamlit.runtime.state import SessionState
import threading

# Add thread-local storage
thread_local = threading.local()

def get_session():
    """Get the current Streamlit session context"""
    ctx = get_script_run_ctx()
    if ctx is None:
        # Return a dummy session when running outside Streamlit
        return type('DummySession', (), {'session_state': {}})()
    return ctx.session_state

def safe_streamlit_call(func):
    """Decorator to ensure Streamlit calls are made in the correct context"""
    def wrapper(*args, **kwargs):
        if get_script_run_ctx() is not None:
            return func(*args, **kwargs)
        return None
    return wrapper

@safe_streamlit_call
def update_progress(progress_bar, status_text, progress, message):
    """Thread-safe progress updates"""
    if progress_bar is not None:
        progress_bar.progress(progress)
    if status_text is not None:
        status_text.write(message)

load_dotenv()

# Configure APIs
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# Initialize YouTube API
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

# Initialize session state
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'video_data' not in st.session_state:
    st.session_state.video_data = None
if 'transcript' not in st.session_state:
    st.session_state.transcript = None
if 'comments_data' not in st.session_state:
    st.session_state.comments_data = None
if 'video_path' not in st.session_state:
    st.session_state.video_path = None
if 'frames' not in st.session_state:
    st.session_state.frames = []
if 'current_url' not in st.session_state:
    st.session_state.current_url = None
if 'uploaded_file_resource' not in st.session_state:
    st.session_state.uploaded_file_resource = None

# Custom UI Theme
st.set_page_config(
    page_title="Youtube Video AI Agent",
    page_icon="🎥",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    .main {
        background: linear-gradient(135deg, #0f1729, #1e1b4b, #0f1729);
        min-height: 100vh;
        font-family: 'Inter', sans-serif;
    }
    
    .header-container {
        display: flex;
        align-items: center;
        gap: 2rem;
        padding: 1.5rem;
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 24px;
        margin-bottom: 2rem;
    }
    
    .neo-container {
        background: rgba(255, 255, 255, 0.02);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 24px;
        padding: 2rem;
        margin-bottom: 2rem;
        transition: transform 0.3s ease;
    }
    
    .chat-message {
        background: rgba(59, 130, 246, 0.1);
        border-left: 4px solid #3b82f6;
        padding: 1.5rem;
        border-radius: 12px;
        margin: 1rem 0;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <div class="header-container">
        <h1 style="color: white; margin: 0;">🎥 Youtube Video AI Agent</h1>
        <span style="background: rgba(59,130,246,0.1); color: #3b82f6; padding: 0.2rem 0.8rem; border-radius: 12px; font-size: 0.9rem;">
            Powered by Gemini 2.0 Flash
        </span>
    </div>
""", unsafe_allow_html=True)

def format_duration(duration_str):
    """Convert ISO 8601 duration to readable format"""
    duration = isodate.parse_duration(duration_str)
    hours = duration.total_seconds() // 3600
    minutes = (duration.total_seconds() % 3600) // 60
    seconds = duration.total_seconds() % 60

    if hours > 0:
        return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
    else:
        return f"{int(minutes)}m {int(seconds)}s"

def format_number(num):
    """Format large numbers with K, M, B suffixes"""
    if not num or num == 'N/A':
        return 'N/A'
    num = int(num)
    if num >= 1000000000:
        return f"{num/1000000000:.1f}B"
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    if num >= 1000:
        return f"{num/1000:.1f}K"
    return str(num)

def get_video_details(video_id):
    """Fetch comprehensive video details using YouTube API"""
    try:
        # Get basic video info
        response = youtube.videos().list(
            part='snippet,contentDetails,statistics',
            id=video_id
        ).execute()

        if not response['items']:
            return None

        item = response['items'][0]

        # Get channel details
        channel_response = youtube.channels().list(
            part='snippet,statistics',
            id=item['snippet']['channelId']
        ).execute()

        channel_info = channel_response['items'][0] if channel_response['items'] else None

        # Format the data
        published_at = datetime.strptime(item['snippet']['publishedAt'], '%Y-%m-%dT%H:%M:%SZ')

        return {
            'title': item['snippet']['title'],
            'description': item['snippet']['description'],
            'channel': item['snippet']['channelTitle'],
            'channel_subs': format_number(channel_info['statistics']['subscriberCount']) if channel_info else 'N/A',
            'channel_total_views': format_number(channel_info['statistics']['viewCount']) if channel_info else 'N/A',
            'published': published_at.strftime('%B %d, %Y'),
            'duration': format_duration(item['contentDetails']['duration']),
            'views': format_number(item['statistics'].get('viewCount', 'N/A')),
            'likes': format_number(item['statistics'].get('likeCount', 'N/A')),
            'comments': format_number(item['statistics'].get('commentCount', 'N/A')),
            'thumbnail': item['snippet']['thumbnails']['high']['url']
        }
    except Exception as e:
        st.error(f"Error fetching video details: {str(e)}")
    return None

def get_video_comments(video_id, max_comments=50):
    """Fetch top comments from the video"""
    try:
        comments = []
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=max_comments,
            order="relevance"
        )
        response = request.execute()

        for item in response['items']:
            comment = item['snippet']['topLevelComment']['snippet']
            comments.append({
                'author': comment['authorDisplayName'],
                'text': comment['textDisplay'],
                'likes': format_number(comment['likeCount']),
                'published': datetime.strptime(comment['publishedAt'], '%Y-%m-%dT%H:%M:%SZ').strftime('%B %d, %Y')
            })

        return comments
    except Exception as e:
        return None

def get_video_transcript(video_id):
    """Fetch available captions using YouTube API"""
    try:
        transcripts = youtube.captions().list(
            part='snippet',
            videoId=video_id
        ).execute()

        if not transcripts.get('items'):
            return None

        caption_id = transcripts['items'][0]['id']
        transcript = youtube.captions().download(
            id=caption_id,
            tfmt='srt'
        ).execute()

        return transcript
    except Exception as e:
        return None

# Initialize Gemini Agent
@st.cache_resource
def initialize_agent():
    return Agent(
        name="Video AI Agent",
        model=Gemini(id="gemini-2.0-flash-exp"),
        tools=[DuckDuckGo()],
        markdown=True,
    )

# Initialize the agent
multimodal_agent = initialize_agent()

def process_with_retry(processed_video, max_attempts=3):
    """Retry processing video with rate limit handling"""
    for _ in range(max_attempts):
        try:
            result = get_file(processed_video.name)
            if result:
                return result
        except Exception as e:
            if "RATE_LIMIT_EXCEEDED" in str(e):
                time.sleep(5)
                continue
            raise e
    raise Exception("Max retry attempts reached")

def download_youtube_video(url):
    """Download YouTube video using yt-dlp"""
    try:
        with st.spinner("⬇️ Uploading video..."):
            # Create temp directory for download
            temp_dir = tempfile.mkdtemp()
            video_path = os.path.join(temp_dir, 'video.mp4')

            # Configure yt-dlp options with file size limit (2GB = 2000MB)
            ydl_opts = {
                'format': 'best[filesize<2000M]',  # Limit to files under 2GB
                'outtmpl': video_path,
                'quiet': True,
                'no_warnings': True,
                'progress': True,
                'progress_hooks': [lambda d: progress_hook(d)],
            }

            # Progress callback for Streamlit
            progress_bar = st.progress(0)
            status_text = st.empty()

            @safe_streamlit_call
            def progress_hook(d):
                try:
                    if d['status'] == 'downloading':
                        total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
                        downloaded = d.get('downloaded_bytes', 0)
                        if total:
                            # Check if file will exceed 2GB
                            if total > 2000 * 1024 * 1024:  # 2GB in bytes
                                raise Exception("Video file size exceeds 2GB limit")
                            percentage = (downloaded / total) * 100
                            update_progress(
                                progress_bar,
                                status_text,
                                int(percentage),
                                f"⬇️ Downloaded: {downloaded//(1024*1024)}MB / {total//(1024*1024)}MB"
                            )
                    elif d['status'] == 'finished':
                        update_progress(progress_bar, status_text, 100, "✅ Download complete! Processing video...")
                except Exception as e:
                    if "exceeds 2GB limit" in str(e):
                        raise e
                    if get_script_run_ctx() is not None:
                        st.error(f"Download error: {str(e)}")

            # Download video
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(url, download=False)
                    # Check file size before downloading
                    filesize = info.get('filesize', 0) or info.get('filesize_approx', 0)
                    if filesize > 2000 * 1024 * 1024:  # 2GB in bytes
                        raise Exception("Video file size exceeds 2GB limit. Please try a lower quality version.")
                    
                    # Proceed with download if size is acceptable
                    ydl.download([url])
                except Exception as e:
                    raise Exception(f"Download failed: {str(e)}")

            # Verify download and check size
            if os.path.exists(video_path):
                file_size = os.path.getsize(video_path)
                if file_size > 2000 * 1024 * 1024:  # 2GB in bytes
                    os.remove(video_path)
                    raise Exception("Video file size exceeds 2GB limit")
                file_size_gb = file_size / (1024 * 1024 * 1024)
                st.success(f"✅ Video uploaded successfully! ({file_size_gb:.2f} GB)")
                return video_path
            else:
                raise Exception("Video file not found after download")

    except Exception as e:
        st.error(f"❌ Download Error: {str(e)}")
        st.info("""💡 Tips:
        1. Video must be less than 2GB
        2. Try selecting a lower quality version
        3. For long videos, try shorter clips
        4. Check your internet connection
        5. Try a different video URL""")
        return None

def wait_for_file_activation(uploaded_file_resource):
    """Polls the Gemini API until the file is in an ACTIVE state."""
    max_retries = 10
    retry_delay = 1  # seconds
    for i in range(max_retries):
        try:
            file_status = get_file(uploaded_file_resource.name) # use st.session_state here
            if file_status and file_status.state == 'ACTIVE':
                return
            else:
               st.warning(f"File not active, waiting... (attempt {i+1}/{max_retries})")
               time.sleep(retry_delay)
        except Exception as e:
            error_message = str(e)
            st.error(f"❌ Error checking file status: {error_message}")
            raise e  # Re-raise the exception to be handled by the caller

    raise Exception(f"File did not become ACTIVE after {max_retries} attempts.")

def analyze_video_content(video_path, user_query):
    """Analyzes video content using Gemini 2.0 Flash"""
    try:
        # Basic validation
        if not os.path.exists(video_path):
            raise Exception("Video file not found")
        
        # Check video length silently
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        duration_minutes = (total_frames / fps) / 60
        cap.release()

        if duration_minutes > 50:
            raise Exception("Video is too long. Maximum duration is 50 minutes.")

        with st.spinner("🎥 Analyzing video content..."):
            # Upload file
            video_file = upload_file(video_path)
            
            # Wait for file activation silently
            for _ in range(15):  # Increased retries
                try:
                    file_status = get_file(video_file.name)
                    if file_status and file_status.state == "ACTIVE":
                        break
                    time.sleep(2)
                except:
                    time.sleep(2)
                    continue

            # Initialize model with higher tokens
            model = genai.GenerativeModel('gemini-2.0-flash-exp', 
                generation_config={
                    'temperature': 0.4,
                    'top_p': 0.8,
                    'top_k': 40,
                    'max_output_tokens': 4096,
                    'candidate_count': 1
                }
            )

            # Create content
            content = {
                "contents": [{
                    "parts": [
                        {"text": f"""Please analyze this video and answer: {user_query}

                        Provide a detailed analysis covering:
                        1. Main answer to the question
                        2. Important visual elements and scenes
                        3. Key audio/speech content
                        4. Relevant details and context
                        """},
                        video_file
                    ]
                }]
            }

            # Generate with retries
            for attempt in range(3):
                try:
                    response = model.generate_content(**content)
                    if response and response.text:
                        return response.text
                    time.sleep(2)
                except Exception as e:
                    if "RATE_LIMIT_EXCEEDED" in str(e):
                        time.sleep(5)
                    elif attempt == 2:  # Last attempt
                        raise e
                    continue

            return None

    except Exception as e:
        st.error(f"❌ Analysis failed: {str(e)}")
        st.info("""
        💡 Try:
        1. Refresh and try again
        2. Check internet connection
        3. Try a different video
        """)
        return None

def extract_video_id(url):
    """Extract YouTube Video ID from URL"""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})',
        r'(?:embed\/)([0-9A-Za-z_-]{11})'
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

# Streamlit UI
st.markdown("<div class='header'><h1>🎥 Youtube Video AI Agent </h1><p>Powered by Gemini 2.0 Flash</p></div>", unsafe_allow_html=True)

# Input Section
yt_url = st.text_input("Enter YouTube URL:", placeholder="https://youtube.com/watch?v=... or https://youtu.be/...")

if yt_url:
    # Only download if URL changed
    if yt_url != st.session_state.current_url:
        # Cleanup old video if exists
        if st.session_state.video_path and os.path.exists(st.session_state.video_path):
            os.remove(st.session_state.video_path)

        # Download new video
        video_path = download_youtube_video(yt_url)
        if video_path:
            st.session_state.video_path = video_path
            st.session_state.current_url = yt_url
            st.session_state.uploaded_file_resource = None


    # Use stored video path
    if st.session_state.video_path and os.path.exists(st.session_state.video_path):
        # Show video player
        st.video(st.session_state.video_path)

        # Chat interface
        st.markdown("### 💬 Ask AI About This Video")

        # Suggested prompts
        st.markdown("""
            **Suggested Questions:**
            - What is this video about? Give me a detailed summary.
            - What are the main topics or points discussed?
            - How many people are in the video and what are they doing?
            - What is the setting/location of the video?
            - What are the key visual elements or scenes?
        """)

        # Chat input
        user_query = st.text_area("Your question about the video:", height=100)

        if st.button("🚀 Analyze", use_container_width=True):
            if user_query:
                # Analyze video
                analysis = analyze_video_content(st.session_state.video_path, user_query)
                if analysis:
                    st.markdown("""
                        <div class="neo-container">
                            <h3 style="color: #3b82f6; margin-bottom: 1rem;">💡 Analysis Results</h3>
                            <div class="chat-message">
                                {}
                            </div>
                        </div>
                    """.format(analysis), unsafe_allow_html=True)

        # New video button
        if st.button("📺 Analyze Another Video"):
             # Cleanup
            if st.session_state.video_path and os.path.exists(st.session_state.video_path):
                os.remove(st.session_state.video_path)
            st.session_state.video_path = None
            st.session_state.current_url = None
            st.session_state.uploaded_file_resource = None
            st.rerun()
    else:
        st.error("❌ Video file not found! Please try downloading again.")