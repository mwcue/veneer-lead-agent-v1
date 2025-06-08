import functions_framework
from flask import jsonify, request
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Import the main lead generation process
from agent_runner import run_lead_generation_process

# Define valid API key
VALID_API_KEY = os.environ.get("MY_SHARED_API_KEY", "sjmorse-secret-key")

@functions_framework.http
def sj_morse_lead_generator(request):
    # Handle CORS preflight (OPTIONS) request
    if request.method == "OPTIONS":
        return ('', 204, {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type, X-Api-Key'
        })

    # Check for required API key
    api_key = request.headers.get("X-Api-Key")
    if not api_key or api_key != VALID_API_KEY:
        return jsonify({"error": "API key required or invalid."}), 401, {
            'Access-Control-Allow-Origin': '*'
        }

    # Only allow POST method for actual processing
    if request.method != "POST":
        return jsonify({"error": "Method not allowed. Use POST."}), 405, {
            'Access-Control-Allow-Origin': '*'
        }

    request_json = request.get_json(silent=True)

    if not request_json or "segments_to_run" not in request_json:
        return jsonify({"error": "Missing 'segments_to_run' in request."}), 400, {
            'Access-Control-Allow-Origin': '*'
        }

    user_selected_segments = request_json["segments_to_run"]

    # Debugging: log selected segments
    print("→ Segments selected:", user_selected_segments)
    print("→ Starting agent pipeline...")

    try:
        results = run_lead_generation_process(selected_segment_names=user_selected_segments)
        return jsonify(results), 200, {
            'Access-Control-Allow-Origin': '*'
        }
    except Exception as e:
        print("[ERROR] Exception in lead generation:", str(e))
        return jsonify({"error": "Internal server error."}), 500, {
            'Access-Control-Allow-Origin': '*'
        }
