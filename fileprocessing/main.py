import argparse
import os
import sys
from processing import convert_to_html, analyze_sentiment
from database import save_sentiment

def main():
    """Main program entry point"""
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(
        description='File Processing Tool - Convert Markdown files to HTML and perform sentiment analysis'
    )
    parser.add_argument(
        'file',
        type=str,
        help='Path to the Markdown file to process (e.g., sample.md)'
    )
    
    args = parser.parse_args()
    input_file = args.file
    
    if not os.path.exists(input_file):
        print(f"[Error] File not found: {input_file}")
        sys.exit(1)
    
    if not (input_file.endswith('.md') or input_file.endswith('.markdown')):
        print(f"[Warning] File does not seem to be in Markdown format (.md/.markdown), but processing will continue")
    
    print("=" * 60)
    print("File Processing Tool")
    print("=" * 60)
    print(f"Processing file: {input_file}")
    print()
    
    print("-" * 60)
    print("Feature 1: Format Conversion (Markdown -> HTML)")
    print("-" * 60)
    try:
        html_file = convert_to_html(input_file)
        print()
    except Exception as e:
        print(f"[Fatal Error] Format conversion failed, program terminated")
        sys.exit(1)

    print("-" * 60)
    print("Feature 2: Sentiment Analysis")
    print("-" * 60)
    try:
        sentiment_data = analyze_sentiment(input_file)
        print()
    except Exception as e:
        print(f"[Fatal Error] Sentiment analysis failed, program terminated")
        sys.exit(1)
    
    # Save sentiment analysis results to database
    print("-" * 60)
    print("Saving results to database")
    print("-" * 60)
    try:
        filename = os.path.basename(input_file)
        save_sentiment(filename, sentiment_data)
        print()
    except Exception as e:
        print(f"[Fatal Error] Failed to save results, program terminated")
        sys.exit(1)
    
    # Complete
    print("=" * 60)
    print("Processing completed!")
    print("=" * 60)
    print(f"HTML File: {html_file}")
    print(f"Sentiment Results: Saved to DynamoDB database")
    print()

if __name__ == '__main__':
    main()
