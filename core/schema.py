from pydantic import BaseModel, Field

class ViralClipSpec(BaseModel):
    clip_number: int = Field(description="Sequential clip number starting from 1")
    start_seconds: float = Field(description="Precise start timestamp in seconds (e.g. 142.5)")
    end_seconds: float = Field(description="Precise end timestamp in seconds (duration 35 to 55 seconds)")
    on_screen_hook: str = Field(description="4-6 words punchy top banner text in ALL CAPS, no emojis")
    viral_score: int = Field(description="Predicted retention and virality score from 1 to 100")
    hook_rationale: str = Field(description="Brief 1-sentence breakdown of why this visual/verbal moment hooks viewers")
    yt_shorts_title: str = Field(description="High-CTR curiosity-gap title under 60 chars including #Shorts")
    ig_caption_hook: str = Field(description="First 2 lines of Instagram caption designed to stop scrolling and prompt saves")
    ig_seo_keyword_paragraph: str = Field(
        description="3-sentence semantic SEO paragraph loaded with high-search-volume keywords "
        "that Instagram/Meta AI and TikTok search algorithms index for Explore recommendations"
    )
    niche_hashtags: list[str] = Field(description="5 targeted niche-specific classification hashtags")
    algo_hijack_hashtags: list[str] = Field(
        description="12 high-velocity trending feeder hashtags (e.g. #explorepage #viralreels "
        "#trendingnow #foryou #growthmindset) that trigger broad algorithmic testing pools"
    )
    yt_studio_tags: list[str] = Field(
        description="15 high-volume YouTube search phrases (comma-separated ready) for Shorts shelf ranking"
    )

class VideoAnalysisResult(BaseModel):
    video_summary: str = Field(description="Concise 2-3 sentence overview of the video's core premise")
    dominant_theme: str = Field(description="Primary content genre (e.g. Business, Tech, Self-Improvement, Gaming, Story)")
    clips: list[ViralClipSpec] = Field(description="List of viral clip candidates matching the requested target count, ordered from highest to lowest viral_score")
