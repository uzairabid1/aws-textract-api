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
import time
import PyPDF2

from flask import request


load_dotenv()
aws_region_name = os.getenv("aws_region_name")
aws_access_key_id = os.getenv("aws_access_key_id")
aws_secret_access_key = os.getenv("aws_secret_access_key")

s3_access_key = os.getenv('s3_access_key')
s3_secret_key = os.getenv('s3_secret_key')
s3_bucket_name = os.getenv('s3_bucket_name')
s3_bucket_region = os.getenv('s3_bucket_region')

app = Flask(__name__)

CORS(app)


def get_pdf_num_pages(file_bytes):
    try:
        pdf_reader = PyPDF2.PdfFileReader(file_bytes)
        num_pages = pdf_reader.numPages
        return num_pages
    except:
        return 0 

def upload_pdf_to_s3_2(pdf_content, pdf_file_name):
    s3_client = boto3.client('s3', aws_access_key_id=s3_access_key, aws_secret_access_key=s3_secret_key)
    s3_key = pdf_file_name
    s3_client.put_object(Body=pdf_content, Bucket=s3_bucket_name, Key=s3_key, ContentType='application/pdf')
    s3_url = f'https://{s3_bucket_name}.s3.{aws_region_name}.amazonaws.com/{s3_key}'
    return s3_url

@app.route("/textract/queries", methods=["POST"])
def use_textract_queries():
    try:
        if 'file' not in request.files:
            return {"error": "No file received!"}, 400

        file = request.files['file']
        
        if file.filename == '':
            return {"error": "No file selected!"}, 400

        num_pages = get_pdf_num_pages(file)
        print(num_pages)
        if num_pages == 0:
            return {"error": "Invalid PDF or unable to read the file"}, 400
        
        query_list = []
        client = boto3.client('textract', region_name=aws_region_name, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)


        for key, value in request.form.items():
            query_list.append({
                "Text": value,
                "Alias": value,
                "Pages": [str(num_pages)]
                })
      
        
        response = client.start_document_analysis(
            DocumentLocation={'S3Object': {'Bucket': s3_bucket_name, 'Name': file.filename}},
            FeatureTypes=["QUERIES"],
            QueriesConfig={
                "Queries": query_list
            }
        )

        job_id = response['JobId']
        status = None

        print(job_id)

        while status not in ['SUCCEEDED', 'FAILED']:
            response = client.get_document_analysis(JobId=job_id)
            status = response['JobStatus']
            if status == 'SUCCEEDED':
                break
            elif status == 'FAILED':
                return {"error": "Document analysis failed"}, 500
            time.sleep(2)

        data_list = {}

        for idx, item in enumerate(response["Blocks"]):
            if item["BlockType"] == "QUERY_RESULT":
                data_list[response["Blocks"][response["Blocks"].index(item)-1]['Query']['Alias']] = item["Text"]       

        return data_list, 200

    except Exception as e:
        return {"error": str(e)}, 500



@app.route("/textract/ocr", methods=["POST"])
def use_textract_tables():
    try:
        if 'file' not in request.files:
            return {"error": "No file received!"}, 400

        file = request.files['file']
        
        if file.filename == '':
            return {"error": "No file selected!"}, 400

        file_bytes = file.read()

        s3_url = upload_pdf_to_s3_2(file_bytes, file.filename)

        client = boto3.client('textract', region_name=aws_region_name, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
        response = client.start_document_analysis(
            DocumentLocation={'S3Object': {'Bucket': s3_bucket_name, 'Name': file.filename}},
            FeatureTypes=["TABLES"]
        )

        job_id = response['JobId']
        status = None
        while status not in ['SUCCEEDED', 'FAILED']:
            response = client.get_document_analysis(JobId=job_id)
            status = response['JobStatus']
            if status == 'SUCCEEDED':
                break
            elif status == 'FAILED':
                return {"error": "Document analysis failed"}, 500
            time.sleep(2)


        text_data = []
        for block in response['Blocks']:
            if block['BlockType'] == 'WORD':
                text_data.append(block['Text'])

        return {"text_data": text_data, "s3_url": s3_url}, 200


    except Exception as e:
        return {"error": str(e)}, 500




@app.route("/textract/forms", methods=["POST"])
def use_textract_forms():
    try:
        if 'file' not in request.files:
            return {"error": "No file received!"}, 400

        file = request.files['file']
        
        if file.filename == '':
            return {"error": "No file selected!"}, 400

        file_bytes = file.read()
        s3_url = upload_pdf_to_s3_2(file_bytes, file.filename)

  
        client = boto3.client('textract', region_name=aws_region_name, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
        response = client.start_document_analysis(
            DocumentLocation={'S3Object': {'Bucket': s3_bucket_name, 'Name': file.filename}},
            FeatureTypes=["FORMS"]
        )

        job_id = response['JobId']

        status = None
        while status not in ['SUCCEEDED', 'FAILED']:
            response = client.get_document_analysis(JobId=job_id)
            status = response['JobStatus']
            if status == 'SUCCEEDED':
                break
            elif status == 'FAILED':
                return {"error": "Document analysis failed"}, 500
            time.sleep(2)


        blocks = []
        next_token = None
        while True:
            if next_token:
                response = client.get_document_analysis(JobId=job_id, NextToken=next_token)
            else:
                response = client.get_document_analysis(JobId=job_id)
            
            blocks.extend(response["Blocks"])
            next_token = response.get("NextToken")
            if not next_token:
                break

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

        return {"form_data": dict(kvs), "s3_url": s3_url}, 200

    except Exception as e:
        return {"error": str(e)}, 500

def find_value_block(key_block, value_map):
    for relationship in key_block['Relationships']:
        if relationship['Type'] == 'VALUE':
            for value_id in relationship['Ids']:
                return value_map.get(value_id, None)
    return None

def get_text(result, blocks_map):
    text = ''
    if 'Relationships' in result:
        for relationship in result['Relationships']:
            if relationship['Type'] == 'CHILD':
                for child_id in relationship['Ids']:
                    word = blocks_map[child_id]
                    if word['BlockType'] == 'WORD':
                        text += word['Text'] + ' '
                    elif word['BlockType'] == 'SELECTION_ELEMENT':
                        if word['SelectionStatus'] == 'SELECTED':
                            text += 'X '
    return text
            

if __name__ == '__main__':
    app.run(debug=True)