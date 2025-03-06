# PDF Analyzer - Similarity & AI Detection

## Overview

The **PDF Analyzer** is a web application built with Flask that enables users to upload and analyze PDF files. It provides document similarity analysis, AI-generated content detection using the **RapidAPI Llama model**, document comparison, downloadable analysis reports, and a conversational interface for interacting with PDF content. This tool is designed for **researchers, students, and professionals** to ensure document originality and explore content interactively.

## Features

- **Upload PDFs**: Upload up to **10 PDF files** (max **5MB** each).
- **Similarity Analysis**: Compare documents using **cosine similarity** with a customizable threshold.
- **AI Detection**: Identify AI-generated content using the **RapidAPI Llama conversational model**.
- **Document Comparison**: Compare two selected PDFs for similarity.
- **Report Download**: Export analysis results as a **JSON file**.
- **Session Cleanup**: Remove uploaded files and results from the session.
- **Conversational Interaction**: Engage with PDF content using the **RapidAPI conversational AI**.

## Prerequisites

- **Python 3.8+**
- **pip** (Python package manager)

### Required Python Packages

Install the necessary dependencies with:

```bash
pip install flask werkzeug python-dotenv PyPDF2 scikit-learn numpy requests
```

### Additional Requirements

- A **RapidAPI account** with a subscription to **open-ai21.p.rapidapi.com/conversationllama**.
- A `.env` file containing your **RapidAPI key** (see Setup section).

## Setup

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd pdf-analyzer
```

### 2. Create the `.env` File

Create a `.env` file in the project root directory and add your **RapidAPI API key**:

```text
X_RAPIDAPI_KEY=your-rapidapi-key-here
```

🚨 **Note:** Do **not** commit this file to version control. Add it to `.gitignore`:

```text
.env
```

### 3. Project Directory Structure

Ensure the following structure:

```
pdf-analyzer/
├── app.py
├── templates/
│   └── index.html
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js
├── uploads/  (created automatically)
├── results/  (created automatically)
├── .env
└── README.md
```

### 4. Run the Application

Start the Flask server:

```bash
python app.py
```

The application will be accessible at **[http://localhost:5000](http://localhost:5000)**.

## Usage

### Uploading Files

1. Open the app in your browser: **[http://localhost:5000](http://localhost:5000)**
2. Drag and drop up to **10 PDF files** (max **5MB** each) into the upload area or click **"Choose Files"**.
3. Once uploaded, the **"Analyze Files"** and **"Converse"** buttons will be enabled.

### Analyzing Files

1. Click **"Analyze Files"** after uploading.
2. Adjust the **"Similarity Threshold"** slider (**0.1–1.0**) to set the similarity cutoff.
3. The analysis results will display:
   - A **heatmap** of similarity between documents.
   - **Similar document pairs** (if any).
   - **AI detection results** using the RapidAPI Llama model.

### Conversing with PDF

1. Enter text or a question (e.g., **"Summarize the PDF"**) in the **"Converse with PDF"** field.
2. Click **"Converse"** to send the request.
3. The AI-generated response will appear below the button.

### Comparing Files

1. In the **"Document Similarity Analysis"** section, select two PDFs from the dropdown menu.
2. Click **"Compare"** to view their similarity score.

### Downloading Reports

Click **"Download Report"** in the results section to save the analysis as a **JSON file**.

### Clearing Session

Click **"Clear Session Data"** to remove uploaded files and results from the current session.

## Troubleshooting

### 🔹 Buttons Disabled

- Ensure files are **successfully uploaded**.
- Check the **browser console** (**F12** in most browsers) for errors.
- Review **server logs** (`webapp.log`) for issues.

### 🔹 API Errors

- Verify your **X\_RAPIDAPI\_KEY** in `.env`.
- Test the API using:
  ```bash
  curl --request POST \
    --url https://open-ai21.p.rapidapi.com/conversationllama \
    --header 'Content-Type: application/json' \
    --header 'x-rapidapi-host: open-ai21.p.rapidapi.com' \
    --header 'x-rapidapi-key: your-rapidapi-key-here' \
    --data '{"messages":[{"role":"user","content":"hello"}],"web_access":false}'
  ```

### 🔹 No Results

- Ensure the **uploads/** and **results/** directories are **writable**:
  ```bash
  chmod -R 755 uploads results
  ```

### 🔹 Rate Limits

- The **RapidAPI free tier** may impose limits (**e.g., 100 requests/day**). Check your **RapidAPI dashboard**.

## Technologies Used

- **Backend**: Flask (Python web framework)
- **AI Detection**: RapidAPI Llama model (**open-ai21.p.rapidapi.com/conversationllama**)
- **PDF Processing**: PyPDF2
- **Similarity Analysis**: scikit-learn (TF-IDF & Cosine Similarity)
- **Frontend**: HTML, CSS, JavaScript (Bootstrap)
- **Environment Management**: python-dotenv

## Contributing

Contributions are welcome! 🎉 Feel free to:

- **Fork** this repository.
- **Submit issues** or **feature requests**.
- **Create pull requests** to improve the project.

## License

📜 [MIT License]

## Contact

📩 For questions or support, contact **[******[jlfernandez@mmsu.edu.ph](mailto\:jlfernandez@mmsu.edu.ph)******\*\*\*\*]** or open an **issue** in the repository.

