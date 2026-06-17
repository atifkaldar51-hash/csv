import os
import uuid
import traceback
from datetime import datetime

import pandas as pd
from flask import (
    Flask, render_template, request, redirect,
    url_for, jsonify, send_from_directory, session,
    flash
)

# ------------------------------------------------------------------
# App configuration
# ------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
CHART_FOLDER = os.path.join(BASE_DIR, 'static', 'charts')
ALLOWED_EXTENSIONS = {'csv'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CHART_FOLDER'] = CHART_FOLDER
# No MAX_CONTENT_LENGTH -- the app supports arbitrarily large CSVs
# via chunked / column-targeted reads in utils/csv_handler.py.
app.secret_key = 'csv-dashboard-secret-key-2025'

# Ensure required directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CHART_FOLDER, exist_ok=True)

# Local imports (after app/config is ready)
from utils.csv_handler import (
    load_dataset, load_columns, get_dataset_summary, get_preview,
    validate_csv_file, CSVHandlerError
)
from utils.chart_generator import (
    generate_bar_chart, generate_line_chart, generate_pie_chart,
    ChartGenerationError
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def allowed_file(filename):
    """Return True when the filename has a .csv extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _session_dataset_path():
    """Return the path of the CSV currently associated with the session."""
    rel = session.get('current_csv')
    if not rel:
        return None
    return os.path.join(app.config['UPLOAD_FOLDER'], rel)


def _set_current_csv(filename):
    session['current_csv'] = filename
    session['current_csv_name'] = filename.rsplit('_', 1)[-1] if '_' in filename else filename


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------
@app.route('/')
def index():
    """Home page with drag & drop upload zone and feature cards."""
    return render_template(
        'index.html',
        current_file=session.get('current_csv_name')
    )


@app.route('/about')
def about():
    """About page describing the project and tech stack."""
    return render_template('about.html')


@app.route('/dashboard')
def dashboard():
    """Dataset summary cards, preview table, descriptive stats.

    Handles arbitrarily large CSVs: preview reads only the first 10
    rows, and summary statistics use chunked streaming reads so the
    full file is never held in memory.
    """
    csv_path = _session_dataset_path()
    if not csv_path or not os.path.exists(csv_path):
        flash('Please upload a CSV file first to view the dashboard.', 'info')
        return redirect(url_for('index'))

    try:
        # Both functions take a path (not a DataFrame) so they can
        # stream the file instead of loading it all at once.
        summary = get_dataset_summary(csv_path)
        preview = get_preview(csv_path, rows=10)
    except CSVHandlerError as e:
        flash(str(e), 'error')
        return redirect(url_for('index'))
    except Exception as e:
        flash(f'Unexpected error while reading the dataset: {e}', 'error')
        return redirect(url_for('index'))

    return render_template(
        'dashboard.html',
        summary=summary,
        preview=preview,
        file_name=session.get('current_csv_name', 'dataset.csv')
    )


@app.route('/charts', methods=['GET'])
def charts():
    """Charts page - lets user pick columns and generate Bar/Line/Pie charts."""
    csv_path = _session_dataset_path()
    if not csv_path or not os.path.exists(csv_path):
        flash('Please upload a CSV file first to generate charts.', 'info')
        return redirect(url_for('index'))

    # Read only the header + first chunk to discover columns & dtypes.
    # This stays cheap even for multi-GB CSVs.
    try:
        head = pd.read_csv(csv_path, nrows=1)
        numeric_cols = head.select_dtypes(include='number').columns.tolist()
        categorical_cols = head.select_dtypes(exclude='number').columns.tolist()
        all_cols = head.columns.tolist()
    except Exception as e:
        flash(f'Could not read dataset columns: {e}', 'error')
        return redirect(url_for('index'))

    # List previously generated charts (newest first)
    generated = []
    if os.path.exists(app.config['CHART_FOLDER']):
        for fname in sorted(os.listdir(app.config['CHART_FOLDER']), reverse=True):
            if fname.lower().endswith('.png'):
                stat = os.stat(os.path.join(app.config['CHART_FOLDER'], fname))
                generated.append({
                    'name': fname,
                    'url': url_for('static', filename=f'charts/{fname}'),
                    'created': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'size_kb': round(stat.st_size / 1024, 1)
                })

    return render_template(
        'charts.html',
        numeric_cols=numeric_cols,
        categorical_cols=categorical_cols,
        all_cols=all_cols,
        generated=generated,
        file_name=session.get('current_csv_name', 'dataset.csv')
    )


# ------------------------------------------------------------------
# Upload endpoint (form POST)
# ------------------------------------------------------------------
@app.route('/upload', methods=['POST'])
def upload_file():
    """Receive a CSV via form upload, validate, persist, redirect to dashboard."""
    if 'csv_file' not in request.files:
        flash('No file part in the request.', 'error')
        return redirect(url_for('index'))

    file = request.files['csv_file']
    if file.filename == '':
        flash('No file selected. Please choose a CSV file.', 'error')
        return redirect(url_for('index'))

    if not allowed_file(file.filename):
        flash('Invalid file type. Only .csv files are allowed.', 'error')
        return redirect(url_for('index'))

    # Persist with a unique prefix to avoid name collisions
    safe_name = file.filename.replace(' ', '_')
    unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)

    try:
        file.save(save_path)
        # Validate that the saved file is actually a readable CSV
        validate_csv_file(save_path)
    except CSVHandlerError as e:
        # Remove the bad file
        if os.path.exists(save_path):
            os.remove(save_path)
        flash(str(e), 'error')
        return redirect(url_for('index'))
    except Exception as e:
        if os.path.exists(save_path):
            os.remove(save_path)
        flash(f'Upload failed: {e}', 'error')
        return redirect(url_for('index'))

    _set_current_csv(unique_name)
    flash(f'Successfully uploaded "{file.filename}".', 'success')
    return redirect(url_for('dashboard'))


# ------------------------------------------------------------------
# AJAX upload endpoint (used by drag & drop)
# ------------------------------------------------------------------
@app.route('/api/upload', methods=['POST'])
def api_upload():
    """JSON-style upload endpoint for AJAX drag & drop."""
    if 'csv_file' not in request.files:
        return jsonify({'success': False, 'message': 'No file part in the request.'}), 400

    file = request.files['csv_file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected.'}), 400

    if not allowed_file(file.filename):
        return jsonify({'success': False, 'message': 'Invalid file type. Only .csv is allowed.'}), 400

    safe_name = file.filename.replace(' ', '_')
    unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)

    try:
        file.save(save_path)
        validate_csv_file(save_path)
    except CSVHandlerError as e:
        if os.path.exists(save_path):
            os.remove(save_path)
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        if os.path.exists(save_path):
            os.remove(save_path)
        return jsonify({'success': False, 'message': f'Upload failed: {e}'}), 500

    _set_current_csv(unique_name)
    return jsonify({
        'success': True,
        'message': f'Successfully uploaded "{file.filename}".',
        'redirect': url_for('dashboard')
    })


# ------------------------------------------------------------------
# Chart generation endpoints
# ------------------------------------------------------------------
@app.route('/api/chart/bar', methods=['POST'])
def api_chart_bar():
    """Generate a bar chart from selected X / Y columns.

    Only the two needed columns are loaded from disk, so this stays
    fast and memory-light even on very wide CSVs.
    """
    csv_path = _session_dataset_path()
    if not csv_path:
        return jsonify({'success': False, 'message': 'No dataset uploaded.'}), 400

    data = request.get_json(silent=True) or request.form
    x_col = (data.get('x_col') or '').strip()
    y_col = (data.get('y_col') or '').strip()

    try:
        df = load_columns(csv_path, [x_col, y_col])
        url = generate_bar_chart(df, x_col, y_col, app.config['CHART_FOLDER'])
        return jsonify({'success': True, 'chart_url': url})
    except (ChartGenerationError, CSVHandlerError) as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Unexpected error: {e}'}), 500


@app.route('/api/chart/line', methods=['POST'])
def api_chart_line():
    """Generate a line chart from selected X / Y columns.

    Only the two needed columns are loaded; if the resulting series
    is very long, the chart generator downsamples to keep the plot
    readable and fast to render.
    """
    csv_path = _session_dataset_path()
    if not csv_path:
        return jsonify({'success': False, 'message': 'No dataset uploaded.'}), 400

    data = request.get_json(silent=True) or request.form
    x_col = (data.get('x_col') or '').strip()
    y_col = (data.get('y_col') or '').strip()

    try:
        df = load_columns(csv_path, [x_col, y_col])
        url = generate_line_chart(df, x_col, y_col, app.config['CHART_FOLDER'])
        return jsonify({'success': True, 'chart_url': url})
    except (ChartGenerationError, CSVHandlerError) as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Unexpected error: {e}'}), 500


@app.route('/api/chart/pie', methods=['POST'])
def api_chart_pie():
    """Generate a pie chart from a selected category column.

    Only the one needed column is loaded, so this works on very
    wide CSVs without bringing unrelated columns into memory.
    """
    csv_path = _session_dataset_path()
    if not csv_path:
        return jsonify({'success': False, 'message': 'No dataset uploaded.'}), 400

    data = request.get_json(silent=True) or request.form
    cat_col = (data.get('cat_col') or '').strip()

    try:
        df = load_columns(csv_path, [cat_col])
        url = generate_pie_chart(df, cat_col, app.config['CHART_FOLDER'])
        return jsonify({'success': True, 'chart_url': url})
    except (ChartGenerationError, CSVHandlerError) as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Unexpected error: {e}'}), 500


# ------------------------------------------------------------------
# Sample data loader
# ------------------------------------------------------------------
@app.route('/load_sample/<name>')
def load_sample(name):
    """Load one of the bundled sample CSVs into the session."""
    allowed_samples = {
        'sales_data', 'students_data',
        'employees_data', 'products_data'
    }
    if name not in allowed_samples:
        flash('Unknown sample dataset.', 'error')
        return redirect(url_for('index'))

    src = os.path.join(BASE_DIR, 'sample_data', f'{name}.csv')
    if not os.path.exists(src):
        flash('Sample file not found.', 'error')
        return redirect(url_for('index'))

    unique_name = f"{uuid.uuid4().hex[:8]}_{name}.csv"
    dst = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)

    try:
        # Copy & validate
        import shutil
        shutil.copy(src, dst)
        validate_csv_file(dst)
    except Exception as e:
        if os.path.exists(dst):
            os.remove(dst)
        flash(f'Could not load sample dataset: {e}', 'error')
        return redirect(url_for('index'))

    _set_current_csv(unique_name)
    flash(f'Loaded sample dataset "{name}.csv".', 'success')
    return redirect(url_for('dashboard'))


# ------------------------------------------------------------------
# Misc endpoints
# ------------------------------------------------------------------
@app.route('/clear')
def clear_session():
    """Forget the current dataset and go back to the home page."""
    session.pop('current_csv', None)
    session.pop('current_csv_name', None)
    flash('Session cleared.', 'info')
    return redirect(url_for('index'))


@app.route('/download/chart/<filename>')
def download_chart(filename):
    """Trigger a browser download for a generated chart PNG."""
    return send_from_directory(
        app.config['CHART_FOLDER'], filename, as_attachment=True
    )


@app.route('/api/charts')
def api_charts_list():
    """Return a JSON list of all generated chart PNGs (newest first).

    Used by the charts page to refresh just the gallery section via AJAX
    after a new chart is generated, without reloading the whole page
    (which would otherwise wipe the "Latest Chart" preview).
    """
    charts = []
    folder = app.config['CHART_FOLDER']
    if os.path.exists(folder):
        for fname in sorted(os.listdir(folder), reverse=True):
            if fname.lower().endswith('.png'):
                stat = os.stat(os.path.join(folder, fname))
                charts.append({
                    'name': fname,
                    'url': url_for('static', filename=f'charts/{fname}'),
                    'download_url': url_for('download_chart', filename=fname),
                    'created': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'size_kb': round(stat.st_size / 1024, 1)
                })
    return jsonify({'success': True, 'charts': charts, 'count': len(charts)})


# ------------------------------------------------------------------
# Error handlers
# ------------------------------------------------------------------
@app.errorhandler(413)
def too_large(e):
    # No MAX_CONTENT_LENGTH is set, but a reverse proxy might still
    # trigger this -- respond gracefully either way.
    flash('File too large for the server to accept. Contact your administrator.', 'error')
    return redirect(url_for('index')), 413


@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', code=404,
                           message='The page you were looking for does not exist.'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', code=500,
                           message='Something went wrong on our side. Please try again.'), 500


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------
if __name__ == '__main__':
    import os as _os
    print('=' * 60)
    print('  CSV Analytics Dashboard')
    print('  Open http://127.0.0.1:5000 in your browser')
    print('=' * 60)
    # use_reloader=False so the process stays alive under nohup/background
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
