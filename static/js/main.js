document.addEventListener('DOMContentLoaded', function() {
    const slider = document.getElementById('similarity-slider');
    const thresholdValue = document.getElementById('threshold-value');
    const fileInput = document.getElementById('file-input');
    const fileList = document.getElementById('file-list');
    const uploadContainer = document.getElementById('upload-container');
    const analyzeBtn = document.getElementById('analyze-btn');
    const loadingOverlay = document.getElementById('loading-overlay');
    const alertContainer = document.getElementById('alert-container');
    const resultsContainer = document.getElementById('results-container');
    const progressBarInner = document.getElementById('progress-bar-inner');
    const progressStatus = document.getElementById('progress-status');
    const contrastToggle = document.getElementById('contrast-toggle');
    const converseText = document.getElementById('converse-text');
    const converseBtn = document.getElementById('converse-btn');
    const converseResult = document.getElementById('converse-result');

    let sessionId = null;
    let uploadedFiles = [];

    // Threshold Slider
    slider.addEventListener('input', () => thresholdValue.textContent = `${slider.value}%`);

    // High Contrast Toggle
    contrastToggle.addEventListener('click', () => document.body.classList.toggle('high-contrast'));

    // Drag and Drop Events
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadContainer.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        uploadContainer.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        uploadContainer.addEventListener(eventName, unhighlight, false);
    });

    function highlight() { uploadContainer.classList.add('dragging'); }
    function unhighlight() { uploadContainer.classList.remove('dragging'); }

    uploadContainer.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }

    fileInput.addEventListener('change', function() {
        handleFiles(this.files);
    });

    function handleFiles(files) {
        if (files.length === 0) return;
        if (files.length > 10) {
            showAlert('Maximum 10 files allowed.', 'warning');
            return;
        }
        for (let file of files) {
            if (file.size > 5 * 1024 * 1024) {
                showAlert(`File ${file.name} exceeds 5MB limit.`, 'warning');
                return;
            }
        }

        const formData = new FormData();
        Array.from(files).forEach(file => formData.append('files[]', file));

        loadingOverlay.classList.remove('hidden');
        progressBarInner.style.width = '0%';
        progressBarInner.textContent = '0%';
        progressStatus.textContent = 'Uploading files...';

        const eventSource = new EventSource('/upload');
        fetch('/upload', { method: 'POST', body: formData });
        eventSource.onmessage = function(event) {
            const progress = parseInt(event.data);
            progressBarInner.style.width = `${progress}%`;
            progressBarInner.textContent = `${progress}%`;
        };
        eventSource.addEventListener('progress', function(event) {
            progressStatus.textContent = event.data;
        });
        eventSource.addEventListener('complete', function(event) {
            const data = JSON.parse(event.data);
            eventSource.close();
            loadingOverlay.classList.add('hidden');
            if (data.success) {
                sessionId = data.session_id;
                uploadedFiles = data.files;
                showAlert(`Uploaded ${data.files.length} files.`, 'success');
                updateFileList(data.files);
                analyzeBtn.disabled = false;
                converseBtn.disabled = false;
                progressStatus.textContent = 'Upload complete!';
            }
        });
        eventSource.addEventListener('error', function(event) {
            showAlert(event.data, 'danger');
            eventSource.close();
            loadingOverlay.classList.add('hidden');
        });
    }

    function updateFileList(files) {
        fileList.innerHTML = '';
        files.forEach(filename => {
            const fileItem = document.createElement('div');
            fileItem.className = 'file-item';
            fileItem.innerHTML = `
                <span class="file-item-icon"><i class="fas fa-file-pdf"></i></span>
                <span class="file-item-name">${filename}</span>
                <span class="file-item-preview" data-file="${filename}"><i class="fas fa-eye"></i></span>
                <span class="file-item-remove" data-file="${filename}"><i class="fas fa-times"></i></span>
            `;
            fileList.appendChild(fileItem);
        });
        document.getElementById('file-list-container').classList.toggle('hidden', files.length === 0);
    }

    document.getElementById('clear-all-btn').addEventListener('click', function() {
        uploadedFiles = [];
        updateFileList([]);
        analyzeBtn.disabled = true;
        converseBtn.disabled = true;
        showAlert('All files removed.', 'success');
    });

    analyzeBtn.addEventListener('click', function() {
        if (!sessionId || uploadedFiles.length === 0) {
            showAlert('Please upload files first.', 'warning');
            return;
        }

        const threshold = slider.value / 100;
        loadingOverlay.classList.remove('hidden');
        progressBarInner.style.width = '0%';
        progressBarInner.textContent = '0%';
        progressStatus.textContent = 'Analyzing documents...';

        const eventSource = new EventSource('/analyze');
        fetch('/analyze', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({session_id: sessionId, threshold: threshold})
        });
        eventSource.onmessage = function(event) {
            const progress = parseInt(event.data);
            progressBarInner.style.width = `${progress}%`;
            progressBarInner.textContent = `${progress}%`;
        };
        eventSource.addEventListener('progress', function(event) {
            progressStatus.textContent = event.data;
        });
        eventSource.addEventListener('complete', function(event) {
            const data = JSON.parse(event.data);
            eventSource.close();
            loadingOverlay.classList.add('hidden');
            if (data.success) {
                showAlert('Analysis completed.', 'success');
                displayResults(data);
                progressStatus.textContent = 'Analysis complete!';
            }
        });
        eventSource.addEventListener('error', function(event) {
            showAlert(event.data, 'danger');
            eventSource.close();
            loadingOverlay.classList.add('hidden');
        });
    });

    converseBtn.addEventListener('click', function() {
        if (!sessionId || !converseText.value.trim()) {
            showAlert('Please upload files and enter text first.', 'warning');
            return;
        }

        loadingOverlay.classList.remove('hidden');
        converseResult.textContent = 'Processing...';

        fetch('/converse', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({session_id: sessionId, text: converseText.value})
        })
        .then(response => response.json())
        .then(data => {
            loadingOverlay.classList.add('hidden');
            if (data.success) {
                converseResult.textContent = data.response || 'No meaningful response.';
                showAlert('Conversation completed.', 'success');
            } else {
                converseResult.textContent = 'Error in conversation.';
                showAlert(data.error || 'Conversation failed.', 'danger');
            }
        })
        .catch(error => {
            loadingOverlay.classList.add('hidden');
            converseResult.textContent = 'Error in conversation.';
            showAlert('Network error: ' + error.message, 'danger');
        });
    });

    function displayResults(data) {
        resultsContainer.classList.remove('hidden');
        resultsContainer.innerHTML = '';
        const heading = document.createElement('h2');
        heading.className = 'results-title';
        heading.textContent = 'Analysis Results';
        resultsContainer.appendChild(heading);
        const timestamp = document.createElement('p');
        timestamp.textContent = `Analysis completed on: ${data.timestamp}`;
        resultsContainer.appendChild(timestamp);

        if (data.similarity_analysis && data.similarity_analysis.similarity_matrix) {
            const heatmapContainer = document.createElement('div');
            heatmapContainer.className = 'heatmap-container';
            const table = document.createElement('table');
            table.className = 'heatmap';
            const thead = document.createElement('thead');
            const tbody = document.createElement('tbody');

            const headerRow = document.createElement('tr');
            headerRow.innerHTML = '<th></th>';
            data.similarity_analysis.file_names.forEach(file => {
                const th = document.createElement('th');
                th.textContent = file;
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);
            table.appendChild(thead);

            data.similarity_analysis.file_names.forEach((fileRow, i) => {
                const row = document.createElement('tr');
                const headerCell = document.createElement('th');
                headerCell.textContent = fileRow;
                row.appendChild(headerCell);
                data.similarity_analysis.file_names.forEach((fileCol, j) => {
                    const cell = document.createElement('td');
                    const similarity = data.similarity_analysis.similarity_matrix[i][j] || 0;
                    const hue = (1 - similarity) * 240; // Blue to Red
                    cell.innerHTML = `<div class="heatmap-cell" style="background-color: hsl(${hue}, 70%, 50%)">${(similarity * 100).toFixed(1)}%</div>`;
                    row.appendChild(cell);
                });
                tbody.appendChild(row);
            });
            table.appendChild(tbody);
            heatmapContainer.appendChild(table);
            resultsContainer.appendChild(heatmapContainer);
        }

        if (data.similarity_analysis && data.similarity_analysis.similar_pairs) {
            const similaritySection = document.createElement('div');
            similaritySection.className = 'results-section';
            const similarityTitle = document.createElement('h3');
            similarityTitle.className = 'results-subtitle';
            similarityTitle.textContent = 'Document Similarity Analysis';
            similaritySection.appendChild(similarityTitle);
            const threshold = document.createElement('p');
            threshold.textContent = `Similarity threshold: ${data.similarity_analysis.threshold * 100}%`;
            similaritySection.appendChild(threshold);

            if (data.similarity_analysis.similar_pairs.length > 0) {
                const compareForm = document.createElement('div');
                compareForm.innerHTML = `
                    <select id="compare-file1" class="form-control mt-2" aria-label="Select first file">
                        ${uploadedFiles.map(f => `<option value="${f}">${f}</option>`).join('')}
                    </select>
                    <select id="compare-file2" class="form-control mt-2" aria-label="Select second file">
                        ${uploadedFiles.map(f => `<option value="${f}">${f}</option>`).join('')}
                    </select>
                    <button id="compare-btn" class="btn btn-primary mt-2">Compare</button>
                    <p id="compare-result"></p>
                `;
                similaritySection.appendChild(compareForm);
                document.getElementById('compare-btn').addEventListener('click', function() {
                    const file1 = document.getElementById('compare-file1').value;
                    const file2 = document.getElementById('compare-file2').value;
                    if (file1 === file2) {
                        showAlert('Please select different files.', 'warning');
                        return;
                    }
                    fetch('/compare', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({session_id: sessionId, file1: file1, file2: file2})
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            document.getElementById('compare-result').textContent = 
                                `${data.file1} ↔ ${data.file2}: ${(data.similarity_score * 100).toFixed(1)}%`;
                        } else {
                            showAlert(data.error, 'danger');
                        }
                    })
                    .catch(error => showAlert('Error: ' + error.message, 'danger'));
                });

                data.similarity_analysis.similar_pairs.forEach(pair => {
                    const item = document.createElement('div');
                    item.className = 'results-item';
                    const header = document.createElement('div');
                    header.className = 'results-item-header';
                    header.innerHTML = `
                        <span>${pair.file1} ↔ ${pair.file2}</span>
                        <span class="similarity-score">${(pair.similarity_score * 100).toFixed(1)}%</span>
                    `;
                    item.appendChild(header);
                    similaritySection.appendChild(item);
                });
            } else {
                const noMatches = document.createElement('p');
                noMatches.textContent = 'No similar document pairs found.';
                similaritySection.appendChild(noMatches);
            }
            resultsContainer.appendChild(similaritySection);
        }

        if (data.ai_detection) {
            const aiSection = document.createElement('div');
            aiSection.className = 'results-section';
            const aiTitle = document.createElement('h3');
            aiTitle.className = 'results-subtitle';
            aiTitle.textContent = 'AI Content Detection (RapidAPI Llama)';
            aiSection.appendChild(aiTitle);
            const files = Object.keys(data.ai_detection);
            if (files.length > 0) {
                files.forEach(file => {
                    const result = data.ai_detection[file];
                    const item = document.createElement('div');
                    item.className = 'results-item';
                    const header = document.createElement('div');
                    header.className = 'results-item-header';
                    const scoreClass = result.is_ai_generated ? 'ai-generated' : 'ai-human';
                    const scoreLabel = result.is_ai_generated ? 'AI-Generated' : 'Human-Written';
                    header.innerHTML = `
                        <span>${file}</span>
                        <span class="ai-score ${scoreClass}">${scoreLabel} (${result.ai_probability.toFixed(1)}%)</span>
                    `;
                    item.appendChild(header);
                    aiSection.appendChild(item);
                });
            } else {
                const noResults = document.createElement('p');
                noResults.textContent = 'No AI detection results available.';
                aiSection.appendChild(noResults);
            }
            resultsContainer.appendChild(aiSection);
        }

        const downloadBtn = document.createElement('button');
        downloadBtn.className = 'btn btn-secondary me-2';
        downloadBtn.textContent = 'Download Report';
        downloadBtn.onclick = function() {
            window.location.href = `/download/${sessionId}`;
        };
        resultsContainer.appendChild(downloadBtn);

        const cleanupBtn = document.createElement('button');
        cleanupBtn.className = 'btn btn-secondary';
        cleanupBtn.textContent = 'Clear Session Data';
        cleanupBtn.onclick = function() {
            cleanupSession(sessionId);
        };
        resultsContainer.appendChild(cleanupBtn);
    }

    function cleanupSession(sessionId) {
        if (!sessionId) return;
        fetch('/cleanup', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({session_id: sessionId})
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert('Session data cleaned up successfully.', 'success');
                sessionId = null;
                uploadedFiles = [];
                updateFileList([]);
                analyzeBtn.disabled = true;
                converseBtn.disabled = true;
                resultsContainer.classList.add('hidden');
                resultsContainer.innerHTML = '';
            } else {
                showAlert(data.error || 'Cleanup failed', 'danger');
            }
        })
        .catch(error => {
            showAlert('Error: ' + error.message, 'danger');
        });
    }

    function showAlert(message, type) {
        alertContainer.innerHTML = `
            <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
    }
});
