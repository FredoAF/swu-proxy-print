#!/bin/python
import os
import io
import shutil
import zipfile
import requests
import tempfile
from pathlib import Path
from PIL import Image
from flask import Flask, make_response, render_template_string, request, send_file

app = Flask(__name__)

# --- Configuration & Constants ---
SWU_API_BASE = "https://swudb.com/api/deck/"
IMAGE_BASE_URL = "https://swudb.com/cdn-cgi/image/quality=100/images"
CANVAS_SIZE = (1800, 1200) # 6x4 at 300 DPI
CARD_SIZE = (744, 1039)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Download Deck Proxies | SWU</title>
    <style>
        /* ... Your existing styles ... */
        body { background-color: #0b0b0b; color: #ffffff; font-family: sans-serif; display: flex; flex-direction: column; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .container { background: #151515; padding: 2rem; border-top: 5px solid #fff200; border-radius: 4px; width: 100%; max-width: 500px; text-align: center; flex-direction: column}
        .info-box {
            background: #222;
            padding: 1rem;
            border-left: 3px solid #fff200;
            font-size: 0.9rem;
            line-height: 1.4;
            margin-bottom: 1.5rem;
            color: #ccc;
        }
        /* Loading Spinner Styles */
        .loader-container { display: none; margin-top: 2rem; }
        .spinner {
            border: 4px solid rgba(255, 242, 0, 0.1);
            width: 40px;
            height: 40px;
            border-radius: 50%;
            border-left-color: #fff200;
            animation: spin 1s linear infinite;
            margin: 0 auto 1rem;
        }
        /* Legal Section Styling */
        .legal-box {
            margin-top: 2rem;
            padding-top: 1.5rem;
            border-top: 1px solid #333;
            font-size: 0.75rem;
            color: #888;
            line-height: 1.6;
            text-align: justify;
        }
        .legal-box strong { color: #bbb; }
        .legal-box a { color: #fff200; text-decoration: none; }
        .legal-box a:hover { text-decoration: underline; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        
        .status-text { color: #fff200; font-weight: bold; text-transform: uppercase; font-size: 0.8rem; letter-spacing: 1px; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <h1>SWU Proxy Prints</h1>

        <div class="info-box">
            Other proxy download services are in letter or A4 size. Downloading proxies on 6x4 photo prints allows you to take advantage of relatively cheap photo printing services to get good quality prints on thicker photo paper, which work well once cut and sleeved.
        </div>
        
        <div id="form-section">
            <p style="color: #ccc; font-size: 0.9rem;">Enter your SWUDB Deck ID or URL below.</p>
            <div class="form-group">
                <input type="text" id="deckId" placeholder="e.g. WkVDKcdHMEFEb or https://swudb.com/deck/WkVDKcdHMEFEb" required 
                       style="width: 100%; padding: 12px; background: #000; border: 1px solid #444; color: #fff; margin-bottom: 1rem;">
                <button onclick="generateProxies()" id="submit-btn" style="width: 100%; padding: 12px; background: #fff200; color: #000; font-weight: bold; border: none; cursor: pointer;">
                    Generate Proxy ZIP
                </button>
            </div>
        </div>

        <div id="loader" class="loader-container">
            <div class="spinner"></div>
            <div class="status-text">Gathering cards from the outer rim...</div>
            <p style="font-size: 0.7rem; color: #666; margin-top: 10px;">This may take up to 60 seconds for large decks.</p>
        </div>
    </div>

    <div class="legal-box">
        <p><strong>Disclaimer:</strong> This website is a fan-made utility and is <strong>not</strong> affiliated with, endorsed, sponsored, or specifically approved by Fantasy Flight Games, Lucasfilm Ltd., or Disney. All card images, names, and text are property of their respective trademark and copyright holders.</p>
        
        <p><strong>Source Attribution:</strong> This tool does not host or own any image assets. All card data and images are retrieved in real-time via the <a href="https://swudb.com" target="_blank">swudb.com</a> API. We are grateful to the SWUDB community for providing this data resource.</p>
        
        <p><strong>Usage Policy:</strong> These generated files are intended for <strong>personal, non-commercial use only</strong> (e.g., playtesting or proxying). Please support the official release by purchasing genuine cards from your local game store.</p>
    </div>

    <script>
        async function generateProxies() {
            const deckIdInput = document.getElementById('deckId').value;
            const submitBtn = document.getElementById('submit-btn');
            const formSection = document.getElementById('form-section');
            const loader = document.getElementById('loader');

            if (!deckIdInput) return alert("Please enter a Deck ID");

            // UI Switch
            formSection.classList.add('hidden');
            loader.style.display = 'block';

            try {
                const response = await fetch('/download', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: `deckId=${encodeURIComponent(deckIdInput)}`
                });

                if (response.ok) {
                    // Trigger download
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `SWU_Proxies_${deckIdInput}.zip`;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    
                    // Reset UI
                    // alert("Download complete!");
                } else {
                    const err = await response.text();
                    alert("Error: " + err);
                }
            } catch (e) {
                alert("Request failed. Check your connection.");
            } finally {
                loader.style.display = 'none';
                formSection.classList.remove('hidden');
            }
        }
    </script>
</body>
</html>
"""

class ProxyGenerator:
    def __init__(self, deck_id):
        self.deck_id = deck_id
        self.temp_dir = tempfile.mkdtemp()
        self.print_array = []
        self.print_count = 1

    def download_image(self, path):
        """Downloads image content from SWUDB."""
        clean_path = path.replace('~', '')
        url = f"{IMAGE_BASE_URL}{clean_path}"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            print(f"Error downloading {url}: {e}")
            return None

    def create_photo_layout(self, card1_data, card2_data, filename, rotate_cards=False):
        """Tiles two cards onto a 6x4 canvas."""
        canvas = Image.new('RGB', CANVAS_SIZE, 'white')
        
        c1 = Image.open(io.BytesIO(card1_data))
        c2 = Image.open(io.BytesIO(card2_data))

        if rotate_cards:
            c1 = c1.rotate(90, expand=True)
            # c2 = c2.rotate(90, expand=True)

        c1 = c1.resize(CARD_SIZE, resample=Image.Resampling.LANCZOS)
        c2 = c2.resize(CARD_SIZE, resample=Image.Resampling.LANCZOS)

        # Positioning logic
        canvas.paste(c1, (100, 100)) 
        canvas.paste(c2, (900, 100)) 

        save_path = os.path.join(self.temp_dir, f"{filename}.jpg")
        canvas.save(save_path, dpi=(300, 300), quality=95)

    def process_deck(self):
        """Main logic to fetch deck and generate images."""
        resp = requests.get(f"{SWU_API_BASE}{self.deck_id}", timeout=10)
        if resp.status_code != 200:
            return None
        
        deck_json = resp.json()

        # 1. Process Leaders (Side-by-side Portrait)
        for leader_key in ['leader', 'secondLeader']:
            if deck_json.get(leader_key):
                img_path = deck_json[leader_key]['defaultImagePath']
                front = self.download_image(img_path)
                
                # Attempt to find back side
                back_path = img_path.replace(".png", "-back.png") # Simplified logic
                portrait_path = img_path.replace(".png", "-portrait.png")
                back = self.download_image(back_path) or self.download_image(portrait_path) # Fallback to front if no back
                
                self.create_photo_layout(front, back, leader_key, rotate_cards=True)

        # 2. Process Base
        base_img = self.download_image(deck_json['base']['defaultImagePath'])
        if base_img:
            self.create_photo_layout(base_img, base_img, "base", rotate_cards=True)

        # 3. Process Main Deck
        for item in deck_json.get('shuffledDeck', []):
            card_img_data = self.download_image(item['card']['defaultImagePath'])
            if not card_img_data: continue

            for _ in range(int(item['count'])):
                self.print_array.append(card_img_data)
                
                if len(self.print_array) == 2:
                    self.create_photo_layout(self.print_array[0], self.print_array[1], f"deck_{self.print_count}")
                    self.print_array = []
                    self.print_count += 1
        
        # Handle trailing card if deck is odd
        if self.print_array:
            self.create_photo_layout(self.print_array[0], self.print_array[0], f"deck_{self.print_count}")

        # Create ZIP
        zip_path = os.path.join(tempfile.gettempdir(), f"{self.deck_id}.zip")
        shutil.make_archive(zip_path.replace('.zip', ''), 'zip', self.temp_dir)
        
        # Cleanup individual images
        shutil.rmtree(self.temp_dir)
        return zip_path

def verify_deck_id(input_str):
    """Clean and validate the deck ID."""
    deck_id = input_str.rstrip('/').split('/')[-1]
    # Simple alphanumeric check (SWUDB IDs are usually alphanumeric)
    if len(deck_id) >= 15:
        return None
    if not deck_id.isalpha():
        return None
    return deck_id

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/download', methods=['POST'])
def download():
    raw_id = request.form.get('deckId')
    deck_id = verify_deck_id(raw_id)
    
    if not deck_id:
        return "Invalid Deck ID", 400

    generator = ProxyGenerator(deck_id)
    zip_file_path = generator.process_deck()

    if zip_file_path and os.path.exists(zip_file_path):
        return send_file(zip_file_path, as_attachment=True)
    
    return "Failed to generate proxy deck.", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=False)