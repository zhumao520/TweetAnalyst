from typing import List, Optional
from pydantic import BaseModel, Field

class LLMAnalysisResponse(BaseModel):
    """
    Pydantic model for the expected structured output from the LLM.
    """
    should_push: bool = Field(..., description="Whether the content is relevant enough to warrant a push notification (True/False).")
    confidence: Optional[int] = Field(None, ge=0, le=100, description="Confidence score (0-100) in the 'should_push' decision.")
    reason: Optional[str] = Field(None, description="A brief explanation for the 'should_push' decision.")
    summary: str = Field(..., description="A concise summary of the content. If AI fails to provide a summary, this might be a snippet of the original content.")
    
    # Optional detailed analysis fields - can replace 'analytical_briefing'
    detailed_analysis: Optional[str] = Field(None, description="In-depth analysis or points of interest in the content. Can be used for more detailed insights if needed.")
    
    # Specific content categorization (optional)
    impact_areas: Optional[List[str]] = Field(None, description="List of areas potentially impacted by the content (e.g., specific industries, regions).")
    tech_areas: Optional[List[str]] = Field(None, description="List of technology areas mentioned or relevant to the content.")
    news_categories: Optional[List[str]] = Field(None, description="Suggested news categories for the content (e.g., Politics, Sports, Technology).")

    # To handle potential old 'analytical_briefing' if the LLM still produces it.
    # This field can be populated if 'analytical_briefing' is found in the raw LLM output,
    # and then its content can be merged into 'summary' or 'detailed_analysis' by the processing logic.
    analytical_briefing: Optional[str] = Field(None, description="Legacy field for detailed analysis, content should ideally be in 'summary' or 'detailed_analysis'.")

    # Metadata from the LLM call (not part of the LLM's direct JSON output, but added during processing)
    # These are not part of the format instructions to the LLM.
    ai_provider_id: Optional[str] = Field(None, description="Identifier of the AI provider used.")
    ai_model: Optional[str] = Field(None, description="Specific AI model used.")
    
    class Config:
        # Example for how the model might be used or generated
        # This is not strictly necessary for the model definition itself
        # but can be useful for documentation or testing.
        json_schema_extra = {
            "example": {
                "should_push": True,
                "confidence": 85,
                "reason": "High impact news relevant to subscribed keywords.",
                "summary": "Company X announced a new product Y that will revolutionize the Z market.",
                "detailed_analysis": "The new product Y features innovative technology A and B, which addresses common issues in the Z market. This is expected to increase Company X's market share by Q1 next year.",
                "impact_areas": ["Z Market", "Technology Stocks"],
                "tech_areas": ["Innovation A", "Technology B"],
                "news_categories": ["Technology", "Business"]
            }
        }
