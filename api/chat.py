from http.server import BaseHTTPRequestHandler
import json
import re
from datetime import datetime
import os
import base64
import google.generativeai as genai

# Configure Gemini
genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-2.0-flash')

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            
            user_message = data.get('message', '').strip()
            # History passed from client side to maintain context statelessly
            client_history = data.get('history', [])
            image_data = data.get('image', None)
            
            # Validate message topic (only strictly required on first message without an image)
            has_image = bool(image_data)
            if not has_image and not self.is_home_repair_related(user_message) and len(client_history) == 0:
                response = {
                    "explanation": (
                        "I specialize in DIY home repair advice. Please ask about:\n"
                        "- Plumbing (leaks, clogs, toilets)\n"
                        "- Electrical (outlets, wiring)\n"
                        "- Carpentry (furniture, shelves)\n"
                        "- Painting (walls, prep work)\n"
                        "- General home maintenance"
                    ),
                    "tools_needed": [],
                    "safety_level": "Green"
                }
                self.send_json_response(response)
                return
            
            # Format history for Gemini
            gemini_history = []
            for msg in client_history:
                gemini_history.append({
                    "role": "user" if msg['role'] == "user" else "model",
                    "parts": [msg['content']]
                })
            
            # Get response from Gemini statelessly using the history array
            try:
                parts = []
                if image_data:
                    if ',' in image_data:
                        image_data = image_data.split(',')[1]
                    parts.append({
                        "inline_data": {
                            "mime_type": "image/jpeg", 
                            "data": base64.b64decode(image_data)
                        }
                    })
                
                parts.append(
                    f"Respond as a DIY home repair expert.\n"
                    f"Return ONLY a valid JSON object with EXACTLY these keys:\n"
                    f"1. 'explanation': Markdown formatted step-by-step instructions.\n"
                    f"2. 'tools_needed': A JSON array of strings for all required tools and materials.\n"
                    f"3. 'safety_level': Strictly 'Green', 'Yellow', or 'Red'.\n"
                    f"User Request: {user_message}"
                )
                
                # Append the new message to history
                gemini_history.append({
                    "role": "user",
                    "parts": parts
                })
                
                gemini_response = model.generate_content(gemini_history)
                raw_text = gemini_response.text.strip()
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                if raw_text.startswith("```"):
                    raw_text = raw_text[3:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                
                response = json.loads(raw_text.strip())
            except Exception as e:
                print(f"Gemini API Error: {e}")
                response = self.get_fallback_response(user_message)
                response["explanation"] = f"**DEBUG - Gemini API Error**: {str(e)}\n\n" + response["explanation"]
            
            self.send_json_response(response)
            
        except Exception as e:
            self.send_error(500, f"Server error: {str(e)}")

    def send_json_response(self, response):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({
            'response': response
        }).encode())

    def is_home_repair_related(self, message):
        """Basic topic validation"""
        message = message.lower()
        diy_keywords = [
            'repair', 'fix', 'home', 'house', 'diy', 'leak', 'pipe', 
            'electr', 'wire', 'paint', 'drywall', 'wood', 'hammer',
            'nail', 'screw', 'drill', 'tool', 'faucet', 'toilet', 'sink',
            'install', 'mount', 'build', 'replace', 'broken', 'maintenance',
            'door', 'window', 'floor', 'tile', 'roof', 'hvac', 'plumb', 'caulk'
        ]
        return any(keyword in message for keyword in diy_keywords)

    def get_fallback_response(self, user_message):
        """Fallback when Gemini fails or API key is missing"""
        simple_responses = {
            r'\bleak|faucet|drip\b': "For leaky faucets: 1) Turn off water supply 2) Cover the drain 3) Remove handle and replace the damaged washer or O-ring 4) Reassemble.",
            r'\bdrywall|patch|hole\b': "Patching drywall: 1) Cut a clean square around the hole 2) Add a wood backing if large 3) Secure new drywall piece 4) Apply joint compound and tape 5) Sand smooth.",
            r'\bclog|drain|block\b': "Unclogging drains: 1) Try a plunger first 2) Pour baking soda followed by vinegar 3) Use a plumbing snake for stubborn clogs. NEVER mix chemical cleaners.",
            r'\bpaint|brush|roller\b': "Painting tips: 1) Clean and prep walls, fill holes 2) Use painter's tape on edges 3) Cut in edges with a brush first 4) Use a roller in a 'W' pattern for main walls."
        }
        
        for pattern, response_text in simple_responses.items():
            if re.search(pattern, user_message.lower()):
                return {
                    "explanation": response_text,
                    "tools_needed": ["Basic tools"],
                    "safety_level": "Yellow"
                }
                
        return {
            "explanation": "I can help with plumbing, electrical, painting, and other home repairs. Could you provide more details about your project?",
            "tools_needed": [],
            "safety_level": "Green"
        }
