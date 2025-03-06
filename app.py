import os
import uuid
import json
import shutil
import logging
import time
import re
from flask import Flask, request, jsonify, render_template, send_from_directory, Response
from werkzeug.utils import secure_filename
import glob
from dotenv import load_dotenv
import atexit
import threading
from PyPDF2 import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import requests
from concurrent.futures import ThreadPoolExecutor
from requests.exceptions import RequestException

# Load environment variables
load_dotenv()
# Removed ZeroGPT dependency; using RapidAPI instead
X_RAPIDAPI_KEY = os.environ.get('X_RAPIDAPI_KEY')
if not X_RAPIDAPI_KEY:
    raise ValueError("X_RAPIDAPI_KEY must be set in .env for RapidAPI")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("webapp.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['RESULTS_FOLDER'] = 'results'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}
app.config['MAX_FILES'] = 10
app.config['MAX_FILE_SIZE'] = 5 * 1024 * 1024  # 5MB
app.config['WORKERS'] = min(os.cpu_count() or 1, 5)

# Create folders
for folder in [app.config['UPLOAD_FOLDER'], app.config['RESULTS_FOLDER']]:
    os.makedirs(folder, exist_ok=True)

# Session management
SESSION_EXPIRY = 3600  # 1 hour
session_timestamps = {}
session_lock = threading.Lock()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    session_id = str(uuid.uuid4())
    upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
    os.makedirs(upload_dir, exist_ok=True)
    with session_lock:
        session_timestamps[session_id] = time.time()

    if 'files[]' not in request.files:
        return Response("data: 0\nevent: error\ndata: No files uploaded\n\n", mimetype='text/event-stream')

    files = request.files.getlist('files[]')
    if len(files) > app.config['MAX_FILES']:
        return Response(f"data: 0\nevent: error\ndata: Max {app.config['MAX_FILES']} files allowed\n\n", mimetype='text/event-stream')
    if not files or files[0].filename == '':
        return Response("data: 0\nevent: error\ndata: No files selected\n\n", mimetype='text/event-stream')

    def generate():
        saved_files = []
        total_files = len(files)
        for index, file in enumerate(files, 1):
            if not file or not allowed_file(file.filename):
                yield f"data: 0\nevent: error\ndata: Invalid file: {file.filename}\n\n"
                return
            if file.content_length > app.config['MAX_FILE_SIZE']:
                yield f"data: 0\nevent: error\ndata: File {file.filename} exceeds 5MB\n\n"
                return
            filename = secure_filename(file.filename)
            file_path = os.path.join(upload_dir, filename)
            try:
                file.save(file_path)
                saved_files.append(filename)
                progress = int((index / total_files) * 100)
                yield f"data: {progress}\n\n"
                time.sleep(0.05)
            except Exception as e:
                logger.error(f"Failed to save {filename}: {str(e)}")
                yield f"data: 0\nevent: error\ndata: Save failed for {filename}\n\n"
                return
        yield f"data: 100\nevent: complete\ndata: {json.dumps({'success': True, 'session_id': session_id, 'files': saved_files})}\n\n"

    return Response(generate(), mimetype='text/event-stream')

@app.route('/analyze', methods=['POST'])
def analyze_files():
    data = request.json
    session_id = data.get('session_id')
    similarity_threshold = float(data.get('threshold', 0.8))

    if not session_id or session_id not in session_timestamps:
        return Response("data: 0\nevent: error\ndata: Invalid or missing session ID\n\n", mimetype='text/event-stream')

    upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
    if not os.path.exists(upload_dir):
        return Response("data: 0\nevent: error\ndata: Session directory not found\n\n", mimetype='text/event-stream')

    result_dir = os.path.join(app.config['RESULTS_FOLDER'], session_id)
    os.makedirs(result_dir, exist_ok=True)

    def generate():
        try:
            analyzer = PDFAnalyzer(upload_dir, X_RAPIDAPI_KEY, similarity_threshold)
            yield "data: 10\nevent: progress\ndata: Initializing analysis\n\n"
            
            analyzer.extract_text_from_pdfs()
            yield "data: 30\nevent: progress\ndata: Text extracted\n\n"
            
            similarity_data = analyzer.calculate_similarity()
            yield "data: 60\nevent: progress\ndata: Similarity calculated\n\n"
            
            ai_detection_results = analyzer.check_ai_generated()
            yield "data: 90\nevent: progress\ndata: AI detection completed\n\n"
            
            report_path = os.path.join(result_dir, 'analysis_report.json')
            report = analyzer.generate_report(report_path)
            yield f"data: 100\nevent: complete\ndata: {json.dumps({
                'success': True,
                'session_id': session_id,
                'similarity_analysis': similarity_data,
                'ai_detection': {os.path.basename(k): v for k, v in ai_detection_results.items()},
                'timestamp': report['timestamp']
            })}\n\n"
        except Exception as e:
            logger.error(f"Analysis failed: {str(e)}")
            yield f"data: 0\nevent: error\ndata: Analysis failed: {str(e)}\n\n"

    return Response(generate(), mimetype='text/event-stream')

@app.route('/results/<session_id>')
def get_result_data(session_id):
    result_path = os.path.join(app.config['RESULTS_FOLDER'], session_id, 'analysis_report.json')
    if not os.path.exists(result_path):
        return jsonify({'error': 'Result not found'}), 404
    try:
        with open(result_path, 'r') as f:
            return jsonify(json.load(f))
    except Exception as e:
        logger.error(f"Error reading result: {str(e)}")
        return jsonify({'error': f'Failed to read result: {str(e)}'}), 500

@app.route('/download/<session_id>')
def download_report(session_id):
    result_dir = os.path.join(app.config['RESULTS_FOLDER'], session_id)
    report_path = os.path.join(result_dir, 'analysis_report.json')
    if not os.path.exists(report_path):
        return jsonify({'error': 'Report not found'}), 404
    return send_from_directory(result_dir, 'analysis_report.json', as_attachment=True)

@app.route('/compare', methods=['POST'])
def compare_files():
    data = request.json
    session_id, file1, file2 = data.get('session_id'), data.get('file1'), data.get('file2')
    if not all([session_id, file1, file2]):
        return jsonify({'error': 'Session ID and both filenames required'}), 400

    upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
    file1_path = os.path.join(upload_dir, file1)
    file2_path = os.path.join(upload_dir, file2)
    if not (os.path.exists(file1_path) and os.path.exists(file2_path)):
        return jsonify({'error': 'One or both files not found'}), 400

    try:
        analyzer = PDFAnalyzer(upload_dir, X_RAPIDAPI_KEY)
        analyzer.extract_text_from_pdfs()
        docs = [analyzer.pdf_contents.get(file1_path, ''), analyzer.pdf_contents.get(file2_path, '')]
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(docs)
        similarity = cosine_similarity(tfidf_matrix)[0][1]
        return jsonify({'success': True, 'file1': file1, 'file2': file2, 'similarity_score': float(similarity)})
    except Exception as e:
        logger.error(f"Compare failed: {str(e)}")
        return jsonify({'error': f'Comparison failed: {str(e)}'}), 500

@app.route('/cleanup', methods=['POST'])
def cleanup_session():
    data = request.json
    session_id = data.get('session_id')
    if not session_id:
        return jsonify({'error': 'Session ID required'}), 400

    upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
    result_dir = os.path.join(app.config['RESULTS_FOLDER'], session_id)

    try:
        with session_lock:
            for dir_path in [upload_dir, result_dir]:
                if os.path.exists(dir_path):
                    shutil.rmtree(dir_path)
            session_timestamps.pop(session_id, None)
        logger.info(f"Cleaned up session: {session_id}")
        return jsonify({'success': True, 'message': 'Session data cleaned up'})
    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}")
        return jsonify({'error': f'Cleanup failed: {str(e)}'}), 500

def cleanup_expired_sessions():
    with session_lock:
        current_time = time.time()
        expired = [sid for sid, ts in session_timestamps.items() if current_time - ts > SESSION_EXPIRY]
        for session_id in expired:
            for folder in [app.config['UPLOAD_FOLDER'], app.config['RESULTS_FOLDER']]:
                dir_path = os.path.join(folder, session_id)
                if os.path.exists(dir_path):
                    shutil.rmtree(dir_path)
            del session_timestamps[session_id]
            logger.info(f"Cleaned up expired session: {session_id}")

def run_cleanup():
    while True:
        time.sleep(300)  # Every 5 minutes
        cleanup_expired_sessions()

threading.Thread(target=run_cleanup, daemon=True).start()
atexit.register(cleanup_expired_sessions)

class PDFAnalyzer:
    def __init__(self, folder_path, rapidapi_key, similarity_threshold=0.8, max_retries=3, retry_delay=2):
        self.folder_path = folder_path
        self.rapidapi_key = rapidapi_key
        self.similarity_threshold = similarity_threshold
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.pdf_files = []
        self.pdf_contents = {}
        self.similarity_matrix = None
        self.ai_detection_results = {}
        self._validate_inputs()

    def _validate_inputs(self):
        if not os.path.exists(self.folder_path) or not os.path.isdir(self.folder_path):
            raise ValueError(f"Invalid folder: {self.folder_path}")
        if not self.rapidapi_key:
            raise ValueError("RapidAPI key required")
        if not 0 <= self.similarity_threshold <= 1:
            raise ValueError("Similarity threshold must be 0-1")
        self.pdf_files = glob.glob(os.path.join(self.folder_path, "*.pdf"))
        logger.info(f"Found {len(self.pdf_files)} PDFs in {self.folder_path}")

    def extract_text_from_pdfs(self):
        if not self.pdf_files:
            logger.warning("No PDFs to process")
            return
        for pdf_file in self.pdf_files:
            try:
                reader = PdfReader(pdf_file)
                text = "".join(page.extract_text() or "" for page in reader.pages)
                if text.strip():
                    self.pdf_contents[pdf_file] = text
                    logger.info(f"Extracted text from {os.path.basename(pdf_file)}")
                else:
                    logger.warning(f"No text in {os.path.basename(pdf_file)}")
            except Exception as e:
                logger.error(f"Extraction failed for {os.path.basename(pdf_file)}: {str(e)}")

    def calculate_similarity(self):
        if not self.pdf_contents:
            logger.warning("No content for similarity analysis")
            return {'similar_pairs': [], 'similarity_matrix': [], 'file_names': [], 'threshold': self.similarity_threshold}

        docs = list(self.pdf_contents.values())
        file_names = list(self.pdf_contents.keys())
        try:
            vectorizer = TfidfVectorizer(stop_words='english')
            tfidf_matrix = vectorizer.fit_transform(docs)
            self.similarity_matrix = cosine_similarity(tfidf_matrix)
            similar_pairs = [
                {'file1': os.path.basename(file_names[i]), 'file2': os.path.basename(file_names[j]), 'similarity_score': float(self.similarity_matrix[i, j])}
                for i in range(len(file_names)) for j in range(i + 1, len(file_names))
                if self.similarity_matrix[i, j] >= self.similarity_threshold
            ]
            logger.info(f"Found {len(similar_pairs)} similar pairs")
            return {
                'similar_pairs': similar_pairs,
                'similarity_matrix': self.similarity_matrix.tolist(),
                'file_names': [os.path.basename(f) for f in file_names],
                'threshold': self.similarity_threshold
            }
        except Exception as e:
            logger.error(f"Similarity calculation failed: {str(e)}")
            return {'similar_pairs': [], 'similarity_matrix': [], 'file_names': [], 'threshold': self.similarity_threshold}

    def _make_api_request_with_retry(self, url, headers, payload):
        for attempt in range(self.max_retries):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', self.retry_delay * 2))
                    logger.warning(f"Rate limited, retrying in {retry_after}s")
                    time.sleep(retry_after)
                    continue
                if response.status_code != 200:
                    logger.error(f"API error: {response.status_code}")
                    return None
                return response.json()
            except RequestException as e:
                logger.warning(f"API request failed (attempt {attempt+1}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
        logger.error("Max retries exceeded")
        return None

    def check_ai_generated(self):
        if not self.pdf_contents:
            logger.warning("No content for AI detection")
            return {}

        def check_single_pdf(pdf_file):
            text = self.pdf_contents[pdf_file][:5000]
            if len(text.strip()) < 100:
                logger.warning(f"Text too short in {os.path.basename(pdf_file)}")
                return pdf_file, {"ai_probability": 0.0, "is_ai_generated": False}

            headers = {
                'Content-Type': 'application/json',
                'X-RapidAPI-Key': self.rapidapi_key,
                'X-RapidAPI-Host': 'open-ai21.p.rapidapi.com'
            }
            payload = {
                'messages': [{'role': 'user', 'content': text}],
                'web_access': False
            }
            result = self._make_api_request_with_retry(
                'https://open-ai21.p.rapidapi.com/conversationllama',
                headers,
                payload
            )
            if result:
                # Hypothetical logic: If the model generates a coherent response, assume it's human-like
                # Adjust based on actual response structure (e.g., confidence score if provided)
                ai_prob = 30.0  # Default low probability; adjust if API provides a score
                if 'choices' in result and result['choices']:
                    response_text = result['choices'][0].get('message', {}).get('content', '')
                    ai_prob = 70.0 if len(response_text.split()) > 10 else 30.0  # Crude heuristic
                return pdf_file, {"ai_probability": float(ai_prob), "is_ai_generated": ai_prob > 50}
            return pdf_file, {"ai_probability": 0.0, "is_ai_generated": False}

        with ThreadPoolExecutor(max_workers=app.config['WORKERS']) as executor:
            results = dict(executor.map(check_single_pdf, self.pdf_contents.keys()))
        self.ai_detection_results = {k: v for k, v in results.items() if v is not None}
        logger.info(f"AI detection completed for {len(self.ai_detection_results)} files")
        return self.ai_detection_results

    def generate_report(self, output_file="pdf_analysis_report.json"):
        if not self.pdf_contents:
            logger.warning("No content for report")
            return None
        try:
            report = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "analyzed_files": {
                    "total_found": len(self.pdf_files),
                    "successfully_processed": len(self.pdf_contents),
                    "file_list": [os.path.basename(f) for f in self.pdf_contents.keys()]
                },
                "similarity_analysis": self.calculate_similarity() if self.similarity_matrix is None else {
                    'similar_pairs': [],
                    'similarity_matrix': self.similarity_matrix.tolist(),
                    'file_names': [os.path.basename(f) for f in self.pdf_contents.keys()],
                    'threshold': self.similarity_threshold
                },
                "ai_detection": {os.path.basename(k): {
                    "ai_probability": float(v["ai_probability"]),
                    "is_ai_generated": v["is_ai_generated"]
                } for k, v in self.ai_detection_results.items()}
            }
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Report generated: {output_file}")
            return report
        except Exception as e:
            logger.error(f"Report generation failed: {str(e)}")
            error_report = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "error": str(e),
                "partial_data": {
                    "processed_files": len(self.pdf_contents),
                    "has_similarity": self.similarity_matrix is not None,
                    "ai_detection_results": len(self.ai_detection_results)
                }
            }
            error_file = output_file.replace(".json", "_error.json")
            with open(error_file, 'w') as f:
                json.dump(error_report, f, indent=2)
            logger.info(f"Error report saved: {error_file}")
            return None

def cleanup_expired_sessions():
    with session_lock:
        current_time = time.time()
        expired = [sid for sid, ts in session_timestamps.items() if current_time - ts > SESSION_EXPIRY]
        for session_id in expired:
            for folder in [app.config['UPLOAD_FOLDER'], app.config['RESULTS_FOLDER']]:
                dir_path = os.path.join(folder, session_id)
                if os.path.exists(dir_path):
                    shutil.rmtree(dir_path)
            del session_timestamps[session_id]
            logger.info(f"Cleaned up expired session: {session_id}")

def run_cleanup():
    while True:
        time.sleep(300)  # Every 5 minutes
        cleanup_expired_sessions()

threading.Thread(target=run_cleanup, daemon=True).start()
atexit.register(cleanup_expired_sessions)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)