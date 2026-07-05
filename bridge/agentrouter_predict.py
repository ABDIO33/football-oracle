"""
agentrouter_predict.py — Football Oracle prediction via AgentRouter API
Uses Claude Opus 4.6 (free credits via AgentRouter)
"""
import requests
import json
import re

API_URL = "https://agentrouter.org/v1/chat/completions"
API_KEY = "sk-j22yAVjq7BcKpL4bgwRpqTGMcCWB74gE8ZEiGA8zyDN3AIVw"
MODEL = "claude-opus-4-6"


def get_match_prediction(match_data_json):
    """
    Analyze football match data via OpenRouter API and return a prediction.

    Args:
        match_data_json (str): JSON string containing match statistics

    Returns:
        dict: Parsed prediction JSON or None on failure
    """
    system_prompt = (
        "You are the 'Football Oracle' AI, an expert in football data analytics. "
        "You must analyze the provided match statistics and return your prediction "
        "EXCLUSIVELY as a valid JSON object. Do not include any conversational text, "
        "greetings, or markdown formatting (like ```json) outside the JSON structure."
    )

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": f"{system_prompt}\n\nAnalyze this match data and predict the outcome:\n\n{match_data_json}"}
        ],
        "thinking": {"type": "adaptive"},
        "temperature": 0.2,
        "max_tokens": 1024
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/RooVetGit/Roo-Cline",
        "X-Title": "Roo Code",
        "User-Agent": "RooCode/3.54.0"
    }

    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=90)
    except requests.exceptions.Timeout:
        print("ERROR: Request timed out.")
        return None
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to OpenRouter. Check network.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Request failed - {e}")
        return None

    if response.status_code != 200:
        print(f"ERROR: API returned status {response.status_code}")
        try:
            print(f"Body: {response.text[:500]}")
        except Exception:
            pass
        return None

    try:
        result = response.json()
        content = result["choices"][0]["message"]["content"]

        # Try direct JSON parse first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown code block
        json_match = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', content)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try finding {...} or [...] in the text
        brace_match = re.search(r'(\{[\s\S]+\}|\[[\s\S]+\])', content)
        if brace_match:
            try:
                return json.loads(brace_match.group(1))
            except json.JSONDecodeError:
                pass

        print(f"ERROR: Could not parse JSON from model output")
        print(f"Output preview: {content[:300]}")
        return None

    except (KeyError, IndexError) as e:
        print(f"ERROR: Unexpected API response - {e}")
        print(f"Raw: {response.text[:500]}")
        return None


if __name__ == "__main__":
    test_match = {
        "match": {
            "home_team": "Manchester City",
            "away_team": "Real Madrid",
            "competition": "UEFA Champions League",
            "date": "2026-06-25"
        },
        "home_stats": {
            "elo": 1985,
            "xg_for_avg": 2.34,
            "xg_against_avg": 0.87,
            "form_last_5": [1, 1, 0, 1, 1],
            "shots_for_avg": 15.2,
            "possession_avg": 63.0,
            "days_rest": 5,
            "home_advantage": True
        },
        "away_stats": {
            "elo": 1940,
            "xg_for_avg": 2.12,
            "xg_against_avg": 1.05,
            "form_last_5": [1, 0, 1, 1, 0],
            "shots_for_avg": 13.8,
            "possession_avg": 57.0,
            "days_rest": 4,
            "home_advantage": False
        },
        "context": {
            "travel_distance_km": 1520,
            "weather_temp_c": 18,
            "competition_stage": "Semi-final",
            "referee_experience_games": 187
        }
    }

    print("=" * 60)
    print("  Football Oracle - AgentRouter API Test")
    print("  Model: Claude Opus 4.6")
    print("=" * 60)
    print(f"\n  {test_match['match']['home_team']} vs {test_match['match']['away_team']}")
    print(f"  {test_match['match']['competition']} - {test_match['match']['date']}")
    print("\n  Sending request...")
    print("=" * 60)

    prediction = get_match_prediction(json.dumps(test_match, indent=2))

    if prediction:
        print("\nPREDICTION:\n")
        print(json.dumps(prediction, indent=2, ensure_ascii=False))
    else:
        print("\nFAILED to get prediction.")

    print("\n" + "=" * 60)
