import sys

sys.dont_write_bytecode = True

import boto3
from PIL import Image
import requests
from io import BytesIO
from flask import Flask,Blueprint, request
import os
from flask_cors import CORS
from collections import defaultdict
from dotenv import load_dotenv



load_dotenv()
aws_region_name = os.getenv("aws_region_name")
aws_access_key_id = os.getenv("aws_access_key_id")
aws_secret_access_key = os.getenv("aws_secret_access_key")

app = Flask(__name__)

CORS(app)


@app.route("/textract/tables", methods=["POST"])
def use_textract_tables():
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


@app.route("/textract/forms", methods=["POST"])
def use_textract_forms():
    try:
        data = request.json 
    except:
        return ({"error": "No JSON object received!"}), 400
    
    if 'image_url' not in data:
        return ({"error": "image url is missing!"}), 400

    client = boto3.client('textract', region_name=aws_region_name, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
    response = requests.get(data['image_url'])

    img_bytes = BytesIO(response.content)    

    with BytesIO(response.content) as image:
        img_bytes = bytearray(image.read())
        response = client.analyze_document(
            Document={'Bytes': img_bytes},
            FeatureTypes=["FORMS"],
        )

        blocks = response["Blocks"]

        key_map = {}
        value_map = {}
        block_map = {}
        for block in blocks:
            block_id = block['Id']
            block_map[block_id] = block
            if block['BlockType'] == "KEY_VALUE_SET":
                if 'KEY' in block['EntityTypes']:
                    key_map[block_id] = block
                else:
                    value_map[block_id] = block

        kvs = defaultdict(list)
        for block_id, key_block in key_map.items():
            value_block = find_value_block(key_block, value_map)
            key = get_text(key_block, block_map)
            val = get_text(value_block, block_map)
            kvs[key].append(val)

    return {"form_data": kvs}, 200


def find_value_block(key_block, value_map):
    for relationship in key_block['Relationships']:
        if relationship['Type'] == 'VALUE':
            for value_id in relationship['Ids']:
                value_block = value_map[value_id]
    return value_block


def get_text(result, blocks_map):
    text = ''
    if 'Relationships' in result:
        for relationship in result['Relationships']:
            if relationship['Type'] == 'CHILD':
                for child_id in relationship['Ids']:
                    word = blocks_map[child_id]
                    if word['BlockType'] == 'WORD':
                        text += word['Text'] + ' '
                    if word['BlockType'] == 'SELECTION_ELEMENT':
                        if word['SelectionStatus'] == 'SELECTED':
                            text += 'X '

    return text
            

if __name__ == '__main__':
    app.run(debug=True)