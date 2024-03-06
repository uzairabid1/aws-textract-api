import sys

sys.dont_write_bytecode = True

import boto3
from PIL import Image
import requests
from io import BytesIO
from flask import Flask,Blueprint, request
import os
from flask_cors import CORS
from dotenv import load_dotenv



load_dotenv()
aws_region_name = os.getenv("aws_region_name")
aws_access_key_id = os.getenv("aws_access_key_id")
aws_secret_access_key = os.getenv("aws_secret_access_key")

app = Flask(__name__)

CORS(app)


@app.route("/textract", methods=["POST"])
def use_textract():
    try:
        data = request.json 
    except:
        return ({"error": "No JSON object received!"}), 400
    
    if 'image_url' not in data:
        return ({"error": "image url is missing!"}), 400

    client = boto3.client('textract', region_name=aws_region_name, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
    response = requests.get(data['image_url'])
    
    img_bytes = BytesIO(response.content)
    data_list = []

    with BytesIO(response.content) as image:
        img_bytes = bytearray(image.read())
        response = client.analyze_document(
            Document={'Bytes': img_bytes},
            FeatureTypes=["TABLES"],
        )

        for idx, item in enumerate(response["Blocks"]):
            if item["BlockType"] == "LINE":
                data_list.append(item['Text'])

    return {"text_data": data_list}, 200
            

if __name__ == '__main__':
    app.run(debug=True)