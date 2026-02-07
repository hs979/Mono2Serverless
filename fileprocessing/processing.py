import os
import markdown
import boto3

def convert_to_html(input_filepath, output_dir='output/html'):
    """
    Convert Markdown file to HTML file
    
    Parameters
    ----------
    input_filepath: str
        Path to the input Markdown file
    output_dir: str
        Directory for output HTML files, default is 'output/html'
    
    Returns
    -------
    str
        Path to the generated HTML file
    """
    try:
        os.makedirs(output_dir, exist_ok=True)

        with open(input_filepath, 'r', encoding='utf-8') as f:
            markdown_text = f.read()

        html_content = markdown.markdown(markdown_text)

        filename = os.path.basename(input_filepath)
        html_filename = os.path.splitext(filename)[0] + '.html'
        output_filepath = os.path.join(output_dir, html_filename)

        with open(output_filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"[Format Conversion] Conversion successful: {filename} -> {html_filename}")
        print(f"[Format Conversion] HTML file saved to: {output_filepath}")
        
        return output_filepath
    
    except FileNotFoundError:
        print(f"[Format Conversion Error] File not found: {input_filepath}")
        raise
    except Exception as e:
        print(f"[Format Conversion Error] Conversion failed: {e}")
        raise

def analyze_sentiment(input_filepath):
    """
    Analyze text file sentiment using AWS Comprehend
    
    Parameters
    ----------
    input_filepath: str
        Path to the input text file
    
    Returns
    -------
    dict
        Dictionary containing sentiment analysis results, including:
        - Sentiment: Overall sentiment (POSITIVE/NEGATIVE/NEUTRAL/MIXED)
        - SentimentScore: Confidence scores for each sentiment
            - Positive: Positive sentiment score (between 0 and 1)
            - Negative: Negative sentiment score (between 0 and 1)
            - Neutral: Neutral sentiment score (between 0 and 1)
            - Mixed: Mixed sentiment score (between 0 and 1)
    """
    try:
        with open(input_filepath, 'r', encoding='utf-8') as f:
            text = f.read()

        if len(text.encode('utf-8')) > 5000:
            print(f"[Sentiment Analysis Warning] Text too long, truncating to first 5000 bytes")
            while len(text.encode('utf-8')) > 5000:
                text = text[:-100]
        
        aws_region = os.getenv('AWS_REGION', 'us-east-1')
        comprehend_client = boto3.client('comprehend', region_name=aws_region)
        
        # Use AWS Comprehend for sentiment analysis
        response = comprehend_client.detect_sentiment(
            Text=text,
            LanguageCode='en'
        )
        
        overall_sentiment = response['Sentiment']
        sentiment_score = response['SentimentScore']
        
        sentiment_data = {
            'Sentiment': overall_sentiment,
            'SentimentScore': sentiment_score
        }
        
        print(f"[Sentiment Analysis] Analysis completed")
        print(f"[Sentiment Analysis] Overall Sentiment: {overall_sentiment}")
        print(f"[Sentiment Analysis] Sentiment Scores: Positive={sentiment_score['Positive']:.3f}, "
              f"Negative={sentiment_score['Negative']:.3f}, "
              f"Neutral={sentiment_score['Neutral']:.3f}, "
              f"Mixed={sentiment_score['Mixed']:.3f}")
        
        return sentiment_data
    
    except FileNotFoundError:
        print(f"[Sentiment Analysis Error] File not found: {input_filepath}")
        raise
    except Exception as e:
        print(f"[Sentiment Analysis Error] Analysis failed: {e}")
        raise
