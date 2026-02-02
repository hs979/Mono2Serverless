import json
import os
import markdown
import boto3
import base64

def lambda_handler(event, context):
    """
    Converts markdown content to HTML
    """
    try:
        # Determine input source
        if 'body' in event:
            # API Gateway trigger
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
            markdown_text = body.get('content', '')
            filename = body.get('filename', 'unknown.md')
        elif 'Records' in event:
            # S3 Event trigger
            record = event['Records'][0]
            s3_info = record['s3']
            bucket = s3_info['bucket']['name']
            key = s3_info['object']['key']
            
            s3_client = boto3.client('s3')
            response = s3_client.get_object(Bucket=bucket, Key=key)
            markdown_text = response['Body'].read().decode('utf-8')
            filename = key
        else:
            # Direct invocation
            markdown_text = event.get('content', '')
            filename = event.get('filename', 'unknown.md')
        
        # Convert markdown to HTML
        html_content = markdown.markdown(markdown_text)
        
        # Prepare response
        result = {
            'filename': filename,
            'html_content': html_content,
            'original_content_length': len(markdown_text)
        }
        
        return {
            'statusCode': 200,
            'body': json.dumps(result),
            'headers': {
                'Content-Type': 'application/json'
            }
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)}),
            'headers': {
                'Content-Type': 'application/json'
            }
        }
