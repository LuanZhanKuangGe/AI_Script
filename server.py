import json
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()


@app.get("/", response_class=HTMLResponse)
def read_root():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>API 控制面板</title>
        <style>
            body { font-family: Arial; padding: 20px; }
            .btn { 
                display: inline-block; 
                padding: 10px 20px; 
                margin: 5px; 
                background: #007bff; 
                color: white; 
                text-decoration: none; 
                border-radius: 5px;
                cursor: pointer;
            }
            .btn:hover { background: #0056b3; }
            #result { margin-top: 20px; padding: 10px; background: #f0f0f0; white-space: pre-wrap; }
        </style>
    </head>
    <body>
        <h1>API 控制面板</h1>
        <div>
            <button class="btn" onclick="callApi('/iwara')">Iwara</button>
            <button class="btn" onclick="callApi('/jav')">JAV</button>
            <button class="btn" onclick="callApi('/rule34')">Rule34</button>
            <button class="btn" onclick="callApi('/manga')">Manga</button>
            <button class="btn" onclick="callApi('/hanime')">Hanime</button>
        </div>
        <div id="result"></div>
        <script>
            async function callApi(url) {
                const resultDiv = document.getElementById('result');
                resultDiv.textContent = '加载中...';
                try {
                    const response = await fetch(url);
                    const data = await response.json();
                    resultDiv.textContent = JSON.stringify(data, null, 2);
                } catch (error) {
                    resultDiv.textContent = '错误: ' + error.message;
                }
            }
        </script>
    </body>
    </html>
    """
    return html
        
@app.get("/iwara")
def api_iwara():
    with open("./data-iwara.json", "r", encoding="utf8") as fp:
        dict = json.load(fp)
        return dict
    
@app.get("/jav")
def api_jav():
    with open("./data-jav.json", "r", encoding="utf8") as fp:
        dict = json.load(fp)
        return dict
    
@app.get("/rule34")
def api_rule34():
    with open("./data-rule34.json", "r", encoding="utf8") as fp:
        dict = json.load(fp)
        return dict
    
@app.get("/manga")
def api_manga():
    with open("./data-manga.json", "r", encoding="utf8") as fp:
        dict = json.load(fp)
        return dict
    
@app.get("/hanime")
def api_hanime():
    with open("./data-hanime.json", "r", encoding="utf8") as fp:
        dict = json.load(fp)
        return dict