# CSV Analytics Dashboard

A modern, Apple-inspired web application to **upload, analyse, and visualise CSV files** — built with Python, Flask, Pandas, NumPy, Matplotlib, Bootstrap 5, and vanilla JavaScript.

> Drag & drop a CSV → preview rows → view dataset statistics → generate Bar / Line / Pie charts → download PNGs. All in a clean, glassmorphism-flavoured light UI.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Folder Structure](#folder-structure)
- [Installation](#installation)
- [Running the Application](#running-the-application)
- [Usage Guide](#usage-guide)
- [Sample Datasets](#sample-datasets)
- [Error Handling](#error-handling)
- [Screenshots](#screenshots)
- [Future Enhancements](#future-enhancements)
- [License](#license)

---

## Project Overview

**CSV Analytics Dashboard** is a lightweight yet production-ready web application designed to make CSV data exploration effortless. Upload a CSV file (or pick one of the bundled sample datasets) and the app instantly shows:

- A clean preview of the first 10 rows
- Column names and Pandas-inferred data types
- A summary dashboard with row/column counts, missing values, numeric vs categorical column breakdown, and memory usage
- A descriptive-statistics table (count, mean, std, min, quartiles, max)
- A categorical value-counts panel
- One-click Bar, Line, and Pie chart generation
- A chart gallery where every chart can be downloaded as a PNG

The UI is deliberately minimal — Apple-inspired light mode with glassmorphism cards, soft shadows, rounded corners (12–20px), and the signature **#007AFF** blue accent.

---

## Features

### Upload
- Drag & drop CSV upload with AJAX (no full page reload)
- Click-to-browse fallback
- Strict `.csv` extension validation
- **No file-size limit** -- the app supports arbitrarily large CSVs
- Empty / corrupted / non-UTF-8 detection with friendly error messages
- **Large files (> 50 MB) are processed via chunked streaming reads**, so memory stays bounded regardless of file size

### Preview
- First 10 rows rendered as a clean table
- Data types shown as small chips next to column names
- Row index column for easy reference
- NULL / NaN cells rendered as `—`

### Analytics Dashboard
- Summary cards: total rows, total columns, missing values, numeric columns, categorical columns, memory usage
- Column chips with data types
- Missing-values report with horizontal bars (proportion of missing per column)
- Descriptive statistics table for numeric columns
- Top-5 categorical value distribution per categorical column

### Charts
- **Bar chart** — pick X (category) and Y (numeric) columns
- **Line chart** — pick X and Y columns; values are sorted along X for a clean curve
- **Pie chart** — pick a category column; top 8 slices, smaller slices grouped into "Other", rendered as a donut
- Each generated chart is saved to `static/charts/` and listed in the gallery
- One-click PNG download for every chart

### UX
- Fully responsive (mobile-friendly)
- Apple-inspired glassmorphism light theme
- Smooth animations, hover effects, and floating icons
- Toast notifications for upload / chart events
- Friendly 404 / 500 error pages

---

## Technology Stack

### Backend
| Library        | Purpose                                              |
|----------------|------------------------------------------------------|
| Flask 3.0      | Web framework, routing, request handling             |
| Pandas 2.2     | DataFrame loading, preview, statistics               |
| NumPy 1.26     | Numeric backbone for descriptive stats               |
| Matplotlib 3.8 | Server-side chart rendering (Bar / Line / Pie)       |
| Werkzeug 3.0   | WSGI utilities, secure filename handling             |

### Frontend
| Technology        | Purpose                                              |
|-------------------|------------------------------------------------------|
| HTML5             | Semantic page structure                              |
| CSS3              | Custom Apple-inspired glassmorphism theme            |
| JavaScript (ES5)  | Drag & drop, AJAX chart generation, toasts           |
| Bootstrap 5.3     | Responsive grid, navbar, forms, utilities            |
| Bootstrap Icons   | Modern icon set                                      |
| Google Fonts      | Inter typeface for clean typography                  |

---

## Folder Structure

```
csv-dashboard/
│
├── app.py                         # Flask application entry point
├── requirements.txt               # Python dependencies
├── README.md                      # This file
│
├── static/
│   ├── css/
│   │   └── style.css              # Apple-inspired glassmorphism theme
│   ├── js/
│   │   └── script.js              # Drag & drop + chart builder AJAX
│   ├── uploads/                   # Uploaded CSV files (runtime)
│   └── charts/                    # Generated chart PNGs (runtime)
│
├── templates/
│   ├── base.html                  # Layout: navbar, footer, flash messages
│   ├── index.html                 # Home: hero + upload + samples + features
│   ├── dashboard.html             # Summary cards + preview + stats
│   ├── charts.html                # Chart builders + latest preview + gallery
│   ├── about.html                 # Project info + tech stack + roadmap
│   └── error.html                 # 404 / 500 friendly page
│
├── sample_data/
│   ├── sales_data.csv             # Month, Sales (12 rows)
│   ├── students_data.csv          # Name, Marks (10 rows)
│   ├── employees_data.csv         # Department, Employees (8 rows)
│   └── products_data.csv          # Product, Quantity (8 rows)
│
└── utils/
    ├── __init__.py
    ├── csv_handler.py             # Pandas wrappers: validate, load, preview, summary
    └── chart_generator.py         # Matplotlib wrappers: bar / line / pie
```

---

## Installation

### Prerequisites
- Python **3.9+** (tested on 3.10 / 3.11 / 3.12)
- `pip` package manager
- (Recommended) a virtual environment

### Steps

1. **Clone or unzip the project**

   ```bash
   # If you received a zip:
   unzip csv-dashboard.zip
   cd csv-dashboard

   # If cloning from git:
   git clone <your-repo-url>
   cd csv-dashboard
   ```

2. **(Recommended) create a virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate          # macOS / Linux
   # venv\Scripts\activate           # Windows
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

   This installs Flask, Pandas, NumPy, Matplotlib, and Werkzeug.

---

## Running the Application

```bash
python app.py
```

You should see:

```
============================================================
  CSV Analytics Dashboard
  Open http://127.0.0.1:5000 in your browser
============================================================
 * Serving Flask app 'app'
 * Debug mode: on
 * Running on http://127.0.0.1:5000
```

Open <http://127.0.0.1:5000> in your browser.

> **Note:** Debug mode is enabled by default. Disable it in production by setting `debug=False` in `app.py`.

---

## Usage Guide

### 1. Upload a CSV
- Drag & drop a `.csv` file onto the upload zone on the home page, or click **Choose CSV File**.
- Alternatively, click one of the four **sample dataset** cards to load bundled data.

### 2. Explore the Dashboard
After a successful upload, you are redirected to the **Dashboard** page:
- Summary cards at the top show row/column counts, missing values, numeric vs categorical breakdown, and memory usage.
- The **Data Preview** table shows the first 10 rows.
- The **Columns** section lists every column with its Pandas-inferred dtype.
- The **Missing Values Report** shows a horizontal bar per column with missing entries.
- The **Descriptive Statistics** table covers count / mean / std / min / quartiles / max for every numeric column.
- The **Categorical Distributions** panel shows the top 5 values for every categorical column.

### 3. Generate Charts
Navigate to the **Charts** page (top nav bar):
- **Bar chart:** select an X (category) and a Y (numeric) column, then click **Generate Bar Chart**.
- **Line chart:** select an X and a Y column; values are auto-sorted along X.
- **Pie chart:** select a category column; the top 7 slices are shown, with smaller categories grouped as "Other".

The latest chart appears in the **Latest Chart** panel; all previously generated charts are listed in the **Chart Gallery** below. Click the download icon next to any chart to save it as a PNG.

### 4. Clear & Start Over
Click **Clear** in the navbar to forget the current dataset and return to the home page.

---

## Sample Datasets

The project ships with four small CSV files inside `sample_data/`. They can be loaded directly from the home page:

| File                  | Columns              | Rows | Use case                          |
|-----------------------|----------------------|------|-----------------------------------|
| `sales_data.csv`      | `Month, Sales`       | 12   | Line chart of monthly sales       |
| `students_data.csv`   | `Name, Marks`        | 10   | Bar chart of student marks        |
| `employees_data.csv`  | `Department, Employees` | 8 | Pie chart of department headcount |
| `products_data.csv`   | `Product, Quantity`  | 8    | Bar / pie of product inventory    |

---

## Error Handling

The application gracefully handles the following scenarios with friendly messages:

| Scenario                              | Handling                                                            |
|---------------------------------------|---------------------------------------------------------------------|
| No file selected                      | Flash message: *“No file selected. Please choose a CSV file.”*      |
| Wrong file extension (not `.csv`)     | Flash message: *“Invalid file type. Only .csv files are allowed.”*  |
| File larger than 16 MB                | No longer enforced -- app supports arbitrarily large files via chunked streaming |
| Empty CSV file (0 bytes)              | `CSVHandlerError` — *“The uploaded CSV file is empty.”*            |
| Corrupted / malformed CSV             | `CSVHandlerError` with parser details                               |
| Non-UTF-8 encoding                    | `CSVHandlerError` — *“File encoding is not valid UTF-8.”*          |
| Dataset with no rows                  | `CSVHandlerError` — *“The dataset has no rows.”*                    |
| Dataset with no columns               | `CSVHandlerError` — *“The dataset has no columns.”*                 |
| Missing chart selection (X / Y / cat) | `ChartGenerationError` — *“Please select …”*                       |
| Non-numeric Y column for bar / line   | `ChartGenerationError` — *“Y column must be numeric …”*            |
| Unknown URL                           | Custom 404 page                                                     |
| Server-side crash                     | Custom 500 page                                                     |

---

## Screenshots

> Add the following screenshots after running the app locally (save them under `docs/screenshots/`):

| File             | Caption                                  | Suggested filename           |
|------------------|------------------------------------------|------------------------------|
| Home page        | Hero + drag & drop + sample cards        | `screenshots/home.png`       |
| Dashboard        | Summary cards + preview table            | `screenshots/dashboard.png`  |
| Statistics       | Missing values + descriptive stats       | `screenshots/stats.png`      |
| Chart builder    | Bar / Line / Pie builder cards           | `screenshots/chart-build.png`|
| Chart gallery    | Generated chart cards with download btns | `screenshots/gallery.png`    |
| About            | Tech stack + features                    | `screenshots/about.png`      |

---

## Future Enhancements

- [ ] Export analytics summary as PDF or Excel
- [ ] Interactive Chart.js previews in addition to Matplotlib PNGs
- [ ] User accounts with persistent upload history
- [ ] Advanced charts: scatter, heatmap, histogram, boxplot
- [ ] API token authentication for programmatic uploads
- [ ] Light / Dark mode toggle
- [ ] Multi-file upload and side-by-side comparison
- [ ] CSV column type overrides (force numeric / datetime / categorical)
- [ ] Direct database connectors (SQLite / PostgreSQL)
- [ ] Scheduled / cron-based CSV ingestion

---

## Infinite Rows Support

The application is designed to handle **arbitrarily large CSV files** without running out of memory.

### How it works

| Operation         | Strategy                                                         |
|-------------------|------------------------------------------------------------------|
| File upload       | No `MAX_CONTENT_LENGTH` enforced; Flask streams to disk          |
| Preview           | `pd.read_csv(path, nrows=10)` -- reads only the first 10 rows    |
| Total row count   | Streaming pass with `chunksize=50_000`, only column 0 loaded    |
| Summary stats     | Files < 50 MB: full load with `describe()` (includes quartiles) |
|                   | Files >= 50 MB: chunked streaming with incremental accumulators |
|                   | (count / mean / std / min / max; quartiles skipped)             |
| Missing values    | Accumulated per chunk across the whole file                     |
| Categorical dist  | Per-chunk `value_counts()` merged into a single dict            |
| Chart generation  | Only the requested columns are loaded via `usecols=[...]`        |
| Line chart        | Auto-downsamples to 5,000 points if the series is longer         |

### Practical limits

There is no hard row limit. Practical limits are:

- **Disk space** for the upload (typically not a concern)
- **Processing time** -- a 1 GB CSV takes ~30-60 seconds for the dashboard to render
- **Categorical cardinality** -- if a categorical column has millions of unique values, the value-counts dict may grow large

### Verifying with a large file

You can generate a test CSV with one million rows like this:

```python
import pandas as pd
df = pd.DataFrame({
    'id':       range(1, 1_000_001),
    'value':    [i * 1.5 for i in range(1_000_000)],
    'category': [f'cat_{i % 20}' for i in range(1_000_000)],
})
df.to_csv('large_test.csv', index=False)
```

Upload `large_test.csv` through the dashboard and you should see:

- Total Rows: 1,000,000
- Total Columns: 3
- A "Large file (streamed)" badge in the dashboard header
- "Quartiles skipped (large file)" note next to the descriptive stats table
- Charts generate quickly because only the needed columns are loaded

---

## License

This project is released under the **MIT License**. You are free to use, modify, and distribute it for personal or commercial purposes.

---

### Crafted with care using Flask, Pandas, Matplotlib & Bootstrap 5.
