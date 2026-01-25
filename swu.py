#!/bin/python
import io
import zipfile
from flask import Flask, make_response, render_template_string, request, send_file
import requests, json, os, sys
from pathlib import Path
from PIL import Image
from io import BytesIO
import shutil

app = Flask(__name__)

# The HTML Template (Styled for SWU)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Download Deck Proxies | SWU</title>
    <style>
        body {
            background-color: #0b0b0b;
            color: #ffffff;
            font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background-image: radial-gradient(circle, #1a1a1a 1px, transparent 1px);
            background-size: 30px 30px;
        }
        .container {
            background: #151515;
            padding: 2rem;
            border-top: 5px solid #fff200; /* SWU Yellow */
            border-radius: 4px;
            width: 100%;
            max-width: 700px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }
        h1 {
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 0.5rem;
            color: #fff200;
        }
        .info-box {
            background: #222;
            padding: 1rem;
            border-left: 3px solid #fff200;
            font-size: 0.9rem;
            line-height: 1.4;
            margin-bottom: 1.5rem;
            color: #ccc;
        }
        .form-group {
            margin-bottom: 1.5rem;
        }
        label {
            display: block;
            margin-bottom: 0.5rem;
            font-weight: bold;
            text-transform: uppercase;
            font-size: 0.8rem;
        }
        input[type="text"] {
            width: 100%;
            padding: 12px;
            box-sizing: border-box;
            background: #000;
            border: 1px solid #444;
            color: #fff;
            font-size: 1rem;
            border-radius: 4px;
        }
        input[type="text"]:focus {
            outline: none;
            border-color: #fff200;
        }
        button {
            width: 100%;
            padding: 12px;
            background: #fff200;
            color: #000;
            border: none;
            font-weight: bold;
            text-transform: uppercase;
            cursor: pointer;
            border-radius: 4px;
            transition: background 0.2s;
        }
        button:hover {
            background: #d4c900;
        }
        footer {
            margin-top: 2rem;
            font-size: 0.7rem;
            color: #666;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Download SWU Deck Proxies</h1>
        <div class="info-box">
            Other proxy download services are in full letter or A4 size. Downloading proxies on 6x4 photo prints allows you to take advantage of relatively cheap photo printing services to get good quality prints on thick photo paper, which work well once cut and sleeved.
        </div>
        
        <form action="/download" method="POST">
            <div class="form-group">
                <label for="deckId">Submit a swudb.com deck ID to download</label>
                <input type="text" id="deckId" name="deckId" placeholder="e.g. 1234567" required>
            </div>
            <button type="submit">Generate Proxy ZIP</button>
        </form>

        <footer>
            Not affiliated with Fantasy Flight Games or Lucasfilm Ltd.
        </footer>
    </div>
</body>
</html>
"""

printArray = []
printCount = 1
deckId = ""

def printPhoto(card1, card2, flip, filename):

    # 1. Define dimensions for 6x4 at 300 DPI
    width = 1800
    height = 1200

    # 2. Create a blank white canvas
    canvas = Image.new('RGB', (width, height), 'white')

    # 3. Open the image you want to place
    card1_to_paste = Image.open(BytesIO(card1))
    card2_to_paste = Image.open(BytesIO(card2))

    if flip:
        card1_to_paste = card1_to_paste.rotate(90, expand=True)
    # 4. (Optional) Resize your photo to fit a specific area
    # Let's say we want the photo to be 3x2 inches (900x600 px)
    resized_card1 = card1_to_paste.resize((744, 1039))
    resized_card2 = card2_to_paste.resize((744, 1039))
    

    # 5. Paste the photo onto the canvas 
    # The coordinates (x, y) start from the top-left corner
    canvas.paste(resized_card1, (100, 100)) 
    canvas.paste(resized_card2, (900, 100)) 

    # 6. Save with DPI metadata for printing
    canvas.save(deckId+"/"+filename+'.jpg', dpi=(300, 300))

def getBackName(filename, alt):
    path_obj = Path(filename)

    if alt:
        new_name = path_obj.with_name(f"{path_obj.stem}-portrait{path_obj.suffix}")
    else:
        new_name = path_obj.with_name(f"{path_obj.stem}-back{path_obj.suffix}")
    # Create the new name: stem + suffix + extension
    

    return str(new_name)

def download_image(filename, count):
    folder_path = deckId
    filename = filename.replace('~', '')
    imageBaseUrl = "https://swudb.com/cdn-cgi/image/quality=100/images"+filename
    
    splitname = filename.split('/')
    imagename = splitname[-2]+"_"+splitname[-1]
    
    file_path = os.path.join(folder_path, str(count)+"_"+imagename)
    try:
        # 3. Stream the request to handle large files efficiently
        response = requests.get(imageBaseUrl, stream=True)
        response.raise_for_status() # Check for HTTP errors (404, 500, etc.)
        return response.content
        
    except requests.exceptions.RequestException as e:
        print(f"Error downloading image: {e}")
        print("#################")
        return

def getLeader(leader, deckJson):
    leaderfront = download_image(deckJson[leader]['defaultImagePath'], 1)
    leaderBack = download_image(getBackName(deckJson[leader]['defaultImagePath'], False), 1)
    if not leaderBack:
        leaderBack = download_image(getBackName(deckJson[leader]['defaultImagePath'], True), 1)
    printPhoto(leaderfront, leaderBack, True, leader)

def triggerPrint():
    global printArray
    global printCount
    printPhoto(printArray[0], printArray[1], False, str(printCount))
    printArray.clear()
    printCount = printCount + 1

def cleanup():
    global deckId
    shutil.make_archive(deckId, 'zip', deckId)
    shutil.rmtree(deckId)

def getDeck():
    global printArray
    global deckId
    if not os.path.exists(deckId):
        os.makedirs(deckId)
    deck = requests.get("https://swudb.com/api/deck/"+deckId)
    deckJson = deck.json()
    # grab leaders
    print('Getting leaders')
    getLeader('leader', deckJson)
    if deckJson['secondLeader']:
        getLeader('secondLeader', deckJson)
    print('Getting base')
    base = download_image(deckJson['base']['defaultImagePath'], 1)
    printPhoto(base, base, True, "base")
    print('Getting Deck')
    cardCount = 0
    for x in deckJson['shuffledDeck']:
        for i in range(int(x['count'])):
            cardCount = cardCount + 1
            card = download_image(x['card']['defaultImagePath'],i)
            printArray.append(card)
            if len(printArray) == 2:
                triggerPrint()
    print(cardCount)
    cleanup()


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/download', methods=['POST'])
def download():
    global deckId
    deckId = request.form.get('deckId')
    print(deckId)
    getDeck()
    # Logic to generate ZIP
    try:
        filename = os.getcwd()+"/"+deckId+".zip"  # Sanitize the filename
        # file_path = os.path.join(PDF_FOLDER, filename)
        if os.path.isfile(filename):
            print(filename)
            return send_file(filename, as_attachment=True)
        else:
            return make_response(f"File '{filename}' not found.", 404)
    except Exception as e:
        return make_response(f"Error: {str(e)}", 500)
    # zip_buffer = io.BytesIO()
    # with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
    #     # Here you would typically fetch images based on the deck_id
    #     # For now, we create a placeholder text file inside the zip
    #     content = f"Proxy list for Deck ID: {deck_id}\nTarget Size: 6x4 Photo Print"
    #     zip_file.writestr(f"deck_{deck_id}_manifest.txt", content)
    
    # zip_buffer.seek(0)
    
    # return send_file(
    #     zip_buffer,
    #     mimetype='application/zip',
    #     as_attachment=True,
    #     download_name=f"SWU_Proxies_{deck_id}.zip"
    # )

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=5000)