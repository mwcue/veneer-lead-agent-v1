# config.py
import os
from dotenv import load_dotenv
from utils.logging_utils import setup_logging

# Load environment variables
load_dotenv()

class Config:
    """Central configuration for the HR & Regional B2B Lead Generation system."""

    # --- API Keys ---
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    SERPER_API_KEY = os.getenv("SERPER_API_KEY")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

    # --- LLM Settings ---
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower() # Default to openai, ensure lowercase

    # Specific model names per provider
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-3.5-turbo")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL","anthropic/claude-3-5-haiku-20241022")     #  "claude-3-sonnet-20240229")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini/gemini-1.5-flash") # Use flash as a reasonable default
    MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral/mistral-large-lates")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "ollama/llama3.2")


    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))

    # --- Agent Settings ---
    RESEARCH_AGENT_MAX_ITER = int(os.getenv("RESEARCH_AGENT_MAX_ITER", "10"))
    ANALYSIS_AGENT_MAX_ITER = int(os.getenv("ANALYSIS_AGENT_MAX_ITER", "10")) # Reviewer uses this too

    # --- URLs Processing ---
    MAX_URLS_TO_PROCESS = int(os.getenv("MAX_URLS_TO_PROCESS", "2")) # choose up to 1o

    # --- Output Settings ---
    OUTPUT_PATH = os.getenv("OUTPUT_PATH", os.path.join(os.path.dirname(__file__), "output.csv"))

    # --- Logging ---
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper() # Ensure uppercase for logging levels

    # --- API Rate Limits (Optional - not directly used by factory but good practice) ---
    OPENAI_RATE_LIMIT_RETRY = int(os.getenv("OPENAI_RATE_LIMIT_RETRY", "3"))
    SERPER_RATE_LIMIT_RETRY = int(os.getenv("SERPER_RATE_LIMIT_RETRY", "3"))

    # --- Request Retry Settings (Optional - relevant for scraper/requests) ---
    API_RETRY_DELAY = int(os.getenv("API_RETRY_DELAY", "2"))
    API_RETRY_BACKOFF = int(os.getenv("API_RETRY_BACKOFF", "2"))

    # --- Scraper Settings ---
    SCRAPER_REQUEST_TIMEOUT = int(os.getenv("SCRAPER_REQUEST_TIMEOUT", "20"))

    # --- Company Filtering ---
    GENERIC_COMPANY_NAMES = [
        'company', 'organization', 'the firm', 'client',
        'example', 'test', 'none', 'n/a', 'website', 'url'
    ]

    @classmethod
    def validate(cls):
        """Validate critical configuration settings based on chosen provider."""
        missing_keys = []

        supported_providers_requiring_keys = ["openai", "anthropic", "google", "mistralai"]
        all_supported_providers = supported_providers_requiring_keys + ["ollama"]

        # Always check Serper
        if not cls.SERPER_API_KEY:
            missing_keys.append("SERPER_API_KEY")

        # Check provider-specific key if required
        provider = cls.LLM_PROVIDER # Read the provider set in config (from .env)

        # Check provider-specific key
        if provider == "openai" and not cls.OPENAI_API_KEY:
            missing_keys.append("OPENAI_API_KEY (for selected provider 'openai')")
        elif provider == "anthropic" and not cls.ANTHROPIC_API_KEY:
            missing_keys.append("ANTHROPIC_API_KEY (for selected provider 'anthropic')")
        elif provider == "google" and not cls.GOOGLE_API_KEY:
            missing_keys.append("GOOGLE_API_KEY (for selected provider 'google')")
        elif provider == "mistralai" and not cls.MISTRAL_API_KEY:
            missing_keys.append("MISTRAL_API_KEY (for provider '{provider}')")
        elif provider == "ollama":
            pass # no api key needed for ollama
        elif cls.LLM_PROVIDER not in all_supported_providers:
             missing_keys.append(f"LLM_PROVIDER '{provider}' is not recognized/supported by config validation. Supported: {all_supported_providers}")

        return missing_keys

    @classmethod
    def configure_logging(cls):
        """Configure logging based on settings."""
        # Moved setup_logging import here to avoid potential circular dependency if utils imports config
        from utils.logging_utils import setup_logging
        setup_logging(cls.LOG_LEVEL)


# config.py
# ... (all existing Config class and other code) ...

# --- Client-Specific Campaign Brief ---
# TODO: In the future, this could be loaded from a YAML/JSON file per client.
# config.py
# ... (existing Config class and other code) ...

# config.py
# ...

SJ_MORSE_PROFILE = {
    # ... (CLIENT_NAME, WEBSITE, CORE_PRODUCTS_USPS, EXISTING_CLIENT_INFO remain the same) ...
    "TARGET_SEGMENTS": [
        # === SEGMENT 1: Architects & Interior Designers (Corporate & Luxury Focus) ===
        {
            "SEGMENT_NAME": "Architects & Interior Designers (Corporate & Luxury Focus)",
            "SEARCH_KEYWORDS_EXAMPLES": [
                "top US architectural firms corporate interior design", # Added US
                "US interior design firms luxury hospitality projects", # Added US
                "A&E firms specifying architectural wood veneer USA", # Added USA
                "US designers for private jet interiors", "US yacht interior design firms",
                "AWI member architectural firms in USA"
            ],
            "GEOGRAPHIC_FOCUS_TEXT": "Firms primarily based and operating within the USA, specializing in high-end corporate, hospitality, civic, cultural, or luxury residential/transportation projects.", # Emphasized USA
            "GEOGRAPHIC_AREAS_FOR_SEARCH": ["New York NY", "Los Angeles CA", "Chicago IL", "Dallas TX", "San Francisco CA", "Miami FL", "major US cities architecture firms"], # All US locations
            # ... (PROJECT_CRITERIA_EXAMPLES, DECISION_MAKER_TITLES_TO_SUGGEST, SEGMENT_SPECIFIC_PAIN_POINTS_SJ_MORSE_CAN_SOLVE, PRODUCT_FOCUS_FOR_SEGMENT remain focused on the service, not location here) ...
        },

        # === SEGMENT 2: Specialty Millwork & Architectural Woodworking Shops ===
        {
            "SEGMENT_NAME": "Specialty Millwork & Architectural Woodworking Shops",
            "SEARCH_KEYWORDS_EXAMPLES": [
                "custom architectural millwork USA [state]", "AWI certified woodworking shops USA",
                "US veneer panel fabricators corporate interiors", "US commercial casework manufacturers",
                "millwork shops for luxury residential USA", "Decorative Hardwoods Association members USA"
            ],
            "GEOGRAPHIC_FOCUS_TEXT": "Primarily US-based shops, with a focus on those within SJ Morse's key service regions (WV, VA, MD, DC, PA, NJ, DE, southern NY) for delivery advantages, but also considering nationally recognized high-quality US shops.", # Clarified US based
            "GEOGRAPHIC_AREAS_FOR_SEARCH": ["Pennsylvania", "New Jersey", "New York", "Virginia", "Maryland", "Delaware", "West Virginia", "North Carolina", "Ohio", "major US industrial areas millwork"], # US states/regions
            # ... (Rest of the fields for this segment) ...
        },

        # === SEGMENT 3: Institutional & End-User Owners (Corporate, Govt, Healthcare, Education) ===
        {
            "SEGMENT_NAME": "Institutional & End-User Owners (Corporate, Govt, Healthcare, Education)",
            "SEARCH_KEYWORDS_EXAMPLES": [
                "US corporate headquarters construction", "US university campus expansion projects",
                "US hospital interior renovation preferred vendor lists", "GSA building interior finish standards USA",
                "US facilities management specifying wood veneer"
            ],
            "GEOGRAPHIC_FOCUS_TEXT": "US-based institutions and large corporations, particularly those with facilities in SJ Morse's primary service region or with national US interior standards programs.", # Emphasized US-based
            "GEOGRAPHIC_AREAS_FOR_SEARCH": ["Washington DC (federal/corporate HQs)", "New York NY (corporate HQs)", "Chicago IL (corporate HQs)", "Texas (corporate HQs)", "California (corporate/education HQs)"], # US focus areas
            # ... (Rest of the fields for this segment) ...
        },

        # === SEGMENT 4: Luxury Residential, Yacht & Private Aviation Outfitters ===
        {
            "SEGMENT_NAME": "Luxury Residential, Yacht & Private Aviation Outfitters",
            "SEARCH_KEYWORDS_EXAMPLES": [
                "US luxury home builders wood veneer", "US custom yacht interior builders",
                "US private jet interior completion centers",
                "high-end residential architects USA wood veneer",
                "US bespoke furniture makers wood veneer"
            ],
            "GEOGRAPHIC_FOCUS_TEXT": "Primarily US-based firms specializing in ultra-luxury markets. Key areas include South Florida (yachts), major US aviation hubs, and US high-net-worth residential areas.", # Emphasized US-based
            "GEOGRAPHIC_AREAS_FOR_SEARCH": ["South Florida (yachts)", "Texas (aviation/luxury resi)", "California (luxury resi/aviation)", "New York (luxury resi)", "major US luxury markets"], # US focus
            # ... (Rest of the fields for this segment) ...
        }
    ]
}
