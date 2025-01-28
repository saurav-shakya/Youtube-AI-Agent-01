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

# Custom UI Theme
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap');
    
    :root {
        --primary: #3B82F6;
        --secondary: #8B5CF6;
        --background: #0F172A;
    }
    
    body {
        background: linear-gradient(135deg, var(--background), #1E1B4B);
        color: white;
        font-family: 'Inter', sans-serif;
    }
    
    .header {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 20px;
        padding: 2rem;
        margin-bottom: 2rem;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .chat-message {
        padding: 1.5rem;
        border-radius: 15px;
        margin-bottom: 1rem;
        max-width: 85%;
        line-height: 1.6;
    }

    .user-message {
        background: rgba(59, 130, 246, 0.1);
        border: 1px solid rgba(59, 130, 246, 0.3);
        margin-left: auto;
    }

    .assistant-message {
        background: rgba(139, 92, 246, 0.1);
        border: 1px solid rgba(139, 92, 246, 0.3);
        margin-right: auto;
    }

    .video-info {
        background: rgba(30, 41, 59, 0.7);
        border-radius: 15px;
        padding: 1.5rem;
        margin: 1rem 0;
        border: 1px solid rgba(59, 130, 246, 0.3);
    }

    .metadata-section {
        background: rgba(30, 41, 59, 0.4);
        border-radius: 10px;
        padding: 1rem;
        margin-top: 1rem;
    }
    </style>
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

            def progress_hook(d):
                if d['status'] == 'downloading':
                    try:
                        total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
                        downloaded = d.get('downloaded_bytes', 0)
                        if total:
                            # Check if file will exceed 2GB
                            if total > 2000 * 1024 * 1024:  # 2GB in bytes
                                raise Exception("Video file size exceeds 2GB limit")
                            percentage = (downloaded / total) * 100
                            progress_bar.progress(int(percentage))
                            status_text.write(f"⬇️ Downloaded: {downloaded//(1024*1024)}MB / {total//(1024*1024)}MB")
                    except Exception as e:
                        if "exceeds 2GB limit" in str(e):
                            raise e
                        pass
                elif d['status'] == 'finished':
                    status_text.write("✅ Download complete! Processing video...")

            # Download video
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    ydl.download([url])
                except Exception as e:
                    raise Exception(f"Download failed: {str(e)}")

            # Verify download and check size
            if os.path.exists(video_path):
                file_size = os.path.getsize(video_path)
                if file_size > 2000 * 1024 * 1024:  # 2GB in bytes
                    os.remove(video_path)
                    raise Exception("Video file size exceeds 2GB limit")
                file_size_mb = file_size / (1024 * 1024)
                st.success(f"✅ Video uploaded successfully! ({file_size_mb:.1f} MB)")
                return video_path
            else:
                raise Exception("Video file not found after download")

    except Exception as e:
        st.error(f"❌ Download Error: {str(e)}")
        st.info("""💡 Tips:
        1. Video size must be less than 2GB
        2. Try selecting a lower quality version
        3. Check your internet connection
        4. Try a different video URL
        5. Try again after some time""")
        return None

def analyze_video_content(video_path, user_query):
    """Analyze video content using Gemini 2.0 Flash for direct video understanding"""
    try:
        # First check video length
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        duration_minutes = (total_frames / fps) / 60
        cap.release()

        # Validate video length
        if duration_minutes > 50:  # 50 minutes max for Gemini 2.0 Flash
            raise Exception("Video is too long. Maximum duration is 50 minutes.")

        with st.spinner("🎥 Analyzing video..."):
            # Read video file in binary mode
            with open(video_path, 'rb') as f:
                video_data = f.read()
            
            # Create content with video and prompt
            content = {
                "contents": [{
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": "video/mp4",
                                "data": base64.b64encode(video_data).decode('utf-8')
                            }
                        },
                        {
                            "text": f"""
                            Please provide a detailed analysis of the video.
                            
                            User's question: {user_query}
                            
                            Focus on these points:
                            1. Main topic/subject of the video
                            2. What's happening (actions, events, conversations)
                            3. People/characters in the video
                            4. Setting and environment
                            5. Important visual and audio elements
                            6. Video style and quality
                            7. Key moments and highlights
                            
                            Guidelines:
                            - Provide accurate and detailed analysis
                            - Explain in a natural conversational style
                            - Focus on information relevant to user's question
                            - Mention if anything is unclear
                            """
                        }
                    ]
                }]
            }
            
            # Initialize Gemini 2.0 Flash model
            model = genai.GenerativeModel('gemini-2.0-flash-exp', generation_config={
                'temperature': 0.4,
                'top_p': 0.8,
                'top_k': 40,
                'max_output_tokens': 2048
            })
            
            # Generate analysis with retries
            with st.spinner("🤖 Generating analysis..."):
                max_retries = 3
                retry_count = 0
                
                while retry_count < max_retries:
                    try:
                        response = model.generate_content(**content)
                        if response and response.text:
                            return response.text
                        break
                    except Exception as e:
                        if "RATE_LIMIT_EXCEEDED" in str(e) and retry_count < max_retries - 1:
                            retry_count += 1
                            time.sleep(5)  # Wait 5 seconds before retrying
                            continue
                        raise e
                
                return "❌ Failed to generate video analysis. Please try again."

    except Exception as e:
        st.error(f"❌ Analysis Error: {str(e)}")
        st.info("""💡 Tips:
        1. Video size should be less than 2000MB (2GB)
        2. Video length should be less than 50 minutes (with audio)
        3. Video format should be MP4, MOV, WebM or 3GPP
        4. Check your internet connection
        5. Try again after some time""")
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
                    st.markdown(f"""
                        <div class='chat-message assistant-message'>
                            {analysis}
                        </div>
                    """, unsafe_allow_html=True)
        
        # New video button
        if st.button("📺 Analyze Another Video"):
            # Cleanup
            if st.session_state.video_path and os.path.exists(st.session_state.video_path):
                os.remove(st.session_state.video_path)
            st.session_state.video_path = None
            st.session_state.current_url = None
            st.rerun()
    else:
        st.error("❌ Video file not found! Please try downloading again.")
