"""
utils/csv_handler.py
====================

Wraps Pandas operations behind a clean, defensive API so the Flask
layer never has to deal with raw Pandas exceptions.

**Infinite-rows support**
  - `validate_csv_file` imposes no file-size limit.
  - `get_preview` reads ONLY the first N rows (no full load).
  - `get_dataset_summary` uses chunked streaming reads for files
    larger than 50 MB, keeping memory bounded regardless of file size.
  - `load_columns` loads only the requested columns, so chart
    generation on wide CSVs stays cheap.

Public API:
    CSVHandlerError
    validate_csv_file(path)         -- pre-check (no size limit)
    load_dataset(path)              -- full DataFrame (small files only)
    load_columns(path, cols)        -- only specified columns
    get_preview(path, rows=10)      -- reads only first N rows
    get_dataset_summary(path)       -- chunked, supports huge files
"""

import os
import pandas as pd
import numpy as np


# Files larger than this are processed in chunks to keep memory bounded.
LARGE_FILE_THRESHOLD = 50 * 1024 * 1024  # 50 MB
CHUNK_SIZE = 50_000  # rows per chunk


class CSVHandlerError(Exception):
    """Raised whenever a CSV is missing, empty, corrupted, or unreadable."""


# ------------------------------------------------------------------
# Streaming statistics accumulator
# ------------------------------------------------------------------
class _StreamingStats:
    """Accumulates count / sum / sum_sq / min / max for a numeric
    column across multiple chunks, then derives mean & std at the end.

    Quartiles (25/50/75%) are NOT computed because doing so exactly
    would require holding every value in memory. The dashboard UI
    shows '—' for those slots when running on a large file.
    """

    def __init__(self):
        self.count = 0
        self.sum = 0.0
        self.sum_sq = 0.0
        self.min = float('inf')
        self.max = float('-inf')
        self.missing = 0

    def add(self, series):
        """Add a pandas Series (one column from one chunk)."""
        if not pd.api.types.is_numeric_dtype(series):
            series = pd.to_numeric(series, errors='coerce')
        self.missing += int(series.isnull().sum())
        valid = series.dropna()
        if len(valid) == 0:
            return
        # Cast to float64 to avoid integer overflow on big sums
        valid = valid.astype(np.float64)
        self.count += len(valid)
        self.sum += float(valid.sum())
        self.sum_sq += float((valid * valid).sum())
        self.min = min(self.min, float(valid.min()))
        self.max = max(self.max, float(valid.max()))

    def describe(self):
        if self.count == 0:
            return None
        mean = self.sum / self.count
        if self.count > 1:
            var = (self.sum_sq - (self.sum ** 2) / self.count) / (self.count - 1)
            std = float(np.sqrt(max(var, 0.0)))
        else:
            std = 0.0
        return {
            'count': int(self.count),
            'mean': float(mean),
            'std': float(std),
            'min': float(self.min),
            'max': float(self.max),
        }


# ------------------------------------------------------------------
# Validation & loading
# ------------------------------------------------------------------
def validate_csv_file(path):
    """Raise CSVHandlerError if `path` is not a valid, non-empty CSV.

    No file-size limit is enforced -- the application supports
    arbitrarily large CSVs via chunked reading.
    """
    if not os.path.exists(path):
        raise CSVHandlerError('File does not exist.')

    if os.path.getsize(path) == 0:
        raise CSVHandlerError('The uploaded CSV file is empty.')

    try:
        # Read just the header + first row to fail fast without
        # loading the entire file.
        pd.read_csv(path, nrows=1)
    except pd.errors.EmptyDataError:
        raise CSVHandlerError('The CSV file contains no readable data.')
    except pd.errors.ParserError as e:
        raise CSVHandlerError(f'CSV parsing error: {e}')
    except UnicodeDecodeError:
        raise CSVHandlerError(
            'File encoding is not valid UTF-8. Please re-save the file '
            'as UTF-8 and try again.'
        )
    except Exception as e:
        raise CSVHandlerError(f'Could not read the CSV file: {e}')


def load_dataset(path):
    """Load and return the full DataFrame.

    Use only for small files. For large files prefer `load_columns()`
    or `get_dataset_summary()` which use chunked / column-targeted reads.
    """
    validate_csv_file(path)
    try:
        df = pd.read_csv(path)
    except Exception as e:
        raise CSVHandlerError(f'Failed to load dataset: {e}')

    if df.empty:
        raise CSVHandlerError('The dataset has no rows.')
    if df.shape[1] == 0:
        raise CSVHandlerError('The dataset has no columns.')

    return df


def load_columns(path, cols):
    """Load only the specified columns from the CSV.

    Dramatically reduces memory usage for wide CSVs -- e.g. loading
    2 columns out of 50 from a million-row file uses ~25x less RAM.
    Used by chart generation endpoints.
    """
    validate_csv_file(path)
    # Deduplicate while preserving order
    seen = set()
    unique_cols = []
    for c in cols:
        if c and c not in seen:
            seen.add(c)
            unique_cols.append(c)
    if not unique_cols:
        raise CSVHandlerError('No columns requested.')
    try:
        df = pd.read_csv(path, usecols=unique_cols)
    except ValueError as e:
        raise CSVHandlerError(f'Column not found: {e}')
    except Exception as e:
        raise CSVHandlerError(f'Failed to load columns: {e}')
    return df


# ------------------------------------------------------------------
# Preview -- reads only the first N rows
# ------------------------------------------------------------------
def get_preview(path, rows=10):
    """Read only the first `rows` rows for the preview table.

    Does NOT load the full file into memory. The total row count
    is computed separately via a streaming pass.
    """
    validate_csv_file(path)
    try:
        df = pd.read_csv(path, nrows=rows)
    except Exception as e:
        raise CSVHandlerError(f'Failed to read preview: {e}')

    if df.empty:
        raise CSVHandlerError('The dataset has no rows.')

    # Total row count via streaming (no full load)
    total_rows = _count_rows(path)

    head = df.where(pd.notnull(df), None)
    records = []
    for _, row in head.iterrows():
        rec = {}
        for col, val in row.items():
            if val is None or (isinstance(val, float) and np.isnan(val)):
                rec[col] = None
            elif isinstance(val, (np.integer,)):
                rec[col] = int(val)
            elif isinstance(val, (np.floating,)):
                rec[col] = float(val)
            elif isinstance(val, (np.bool_,)):
                rec[col] = bool(val)
            else:
                rec[col] = str(val)
        records.append(rec)

    return {
        'columns': df.columns.tolist(),
        'dtypes': {c: str(t) for c, t in df.dtypes.items()},
        'rows': records,
        'shown_rows': len(records),
        'total_rows': total_rows,
    }


def _count_rows(path):
    """Count total rows in a CSV without loading it into memory."""
    try:
        count = 0
        # Only read the first column to minimise memory per chunk
        reader = pd.read_csv(path, chunksize=CHUNK_SIZE, usecols=[0])
        for chunk in reader:
            count += len(chunk)
        return count
    except Exception:
        return 0


# ------------------------------------------------------------------
# Summary statistics -- chunked for large files
# ------------------------------------------------------------------
def get_dataset_summary(path):
    """Build the summary dict consumed by the dashboard template.

    Automatically chooses between full-load (small files, with
    quartiles) and chunked streaming (large files, without quartiles)
    based on file size.
    """
    validate_csv_file(path)

    file_size = os.path.getsize(path)
    if file_size > LARGE_FILE_THRESHOLD:
        return _summary_chunked(path, file_size)
    return _summary_full(path, file_size)


def _summary_full(path, file_size):
    """Load the full DataFrame and compute summary. Used for small files."""
    try:
        df = pd.read_csv(path)
    except Exception as e:
        raise CSVHandlerError(f'Failed to load dataset: {e}')

    if df.empty:
        raise CSVHandlerError('The dataset has no rows.')
    if df.shape[1] == 0:
        raise CSVHandlerError('The dataset has no columns.')

    n_rows, n_cols = df.shape

    missing_per_col = df.isnull().sum().to_dict()
    total_missing = int(sum(missing_per_col.values()))

    numeric_df = df.select_dtypes(include='number')
    numeric_cols = numeric_df.columns.tolist()
    categorical_cols = df.select_dtypes(exclude='number').columns.tolist()

    # Descriptive stats for numeric columns (with quartiles)
    if not numeric_df.empty:
        desc = numeric_df.describe().round(4)
        numeric_stats = {
            col: {stat: float(val) if pd.notnull(val) else None
                  for stat, val in desc[col].items()}
            for col in desc.columns
        }
    else:
        numeric_stats = {}

    # Categorical value counts (top 5 per column)
    categorical_stats = {}
    for col in categorical_cols:
        try:
            vc = df[col].astype(str).value_counts().head(5)
            categorical_stats[col] = [
                {'value': k, 'count': int(v)} for k, v in vc.items()
            ]
        except Exception:
            categorical_stats[col] = []

    missing_report = [
        {'column': c, 'missing': int(v)}
        for c, v in sorted(missing_per_col.items(), key=lambda x: -x[1]) if v > 0
    ]

    return {
        'file_rows': int(n_rows),
        'file_columns': int(n_cols),
        'total_missing': total_missing,
        'numeric_count': len(numeric_cols),
        'categorical_count': len(categorical_cols),
        'column_names': df.columns.tolist(),
        'dtypes': {c: str(t) for c, t in df.dtypes.items()},
        'numeric_columns': numeric_cols,
        'categorical_columns': categorical_cols,
        'missing_report': missing_report,
        'numeric_stats': numeric_stats,
        'categorical_stats': categorical_stats,
        'memory_kb': round(df.memory_usage(deep=True).sum() / 1024, 2),
        'file_size_mb': round(file_size / (1024 * 1024), 2),
        'large_file': False,
    }


def _summary_chunked(path, file_size):
    """Compute summary statistics using chunked streaming reads.

    Does NOT compute quartiles (25/50/75%) since that would require
    keeping all values in memory. Those slots are returned as None
    and the dashboard renders them as '—'.
    """
    try:
        reader = pd.read_csv(path, chunksize=CHUNK_SIZE, low_memory=False)
        first_chunk = next(reader)
    except Exception as e:
        raise CSVHandlerError(f'Failed to start chunked read: {e}')

    columns = first_chunk.columns.tolist()
    dtypes = {c: str(t) for c, t in first_chunk.dtypes.items()}
    n_cols = len(columns)

    # Infer numeric vs categorical from the first chunk.
    # (Pandas may revise dtype as more chunks arrive, but the first
    # chunk is a reliable approximation for almost all real CSVs.)
    numeric_cols = first_chunk.select_dtypes(include='number').columns.tolist()
    categorical_cols = first_chunk.select_dtypes(exclude='number').columns.tolist()

    # Accumulators
    n_rows = 0
    missing_per_col = {c: 0 for c in columns}
    numeric_stats = {c: _StreamingStats() for c in numeric_cols}
    cat_value_counts = {c: {} for c in categorical_cols}

    def _process_chunk(chunk):
        nonlocal n_rows
        n_rows += len(chunk)
        for c in columns:
            missing_per_col[c] += int(chunk[c].isnull().sum())
        for c in numeric_cols:
            numeric_stats[c].add(chunk[c])
        for c in categorical_cols:
            try:
                vc = chunk[c].astype(str).value_counts()
                for k, v in vc.items():
                    cat_value_counts[c][k] = cat_value_counts[c].get(k, 0) + int(v)
            except Exception:
                pass

    # Process first chunk + the rest
    _process_chunk(first_chunk)
    for chunk in reader:
        _process_chunk(chunk)

    total_missing = int(sum(missing_per_col.values()))

    # Build numeric stats dict (quartiles left as None for large files)
    final_numeric_stats = {}
    for c, s in numeric_stats.items():
        d = s.describe()
        if d is not None:
            final_numeric_stats[c] = {
                'count': d['count'],
                'mean': d['mean'],
                'std': d['std'],
                'min': d['min'],
                '25%': None,  # not computed for large files
                '50%': None,
                '75%': None,
                'max': d['max'],
            }
        else:
            final_numeric_stats[c] = {
                'count': 0, 'mean': None, 'std': None,
                'min': None, '25%': None, '50%': None,
                '75%': None, 'max': None,
            }

    # Build categorical stats (top 5 per column)
    final_categorical_stats = {}
    for c, vc_dict in cat_value_counts.items():
        sorted_items = sorted(vc_dict.items(), key=lambda x: -x[1])[:5]
        final_categorical_stats[c] = [
            {'value': k, 'count': v} for k, v in sorted_items
        ]

    missing_report = [
        {'column': c, 'missing': int(v)}
        for c, v in sorted(missing_per_col.items(), key=lambda x: -x[1]) if v > 0
    ]

    return {
        'file_rows': int(n_rows),
        'file_columns': int(n_cols),
        'total_missing': total_missing,
        'numeric_count': len(numeric_cols),
        'categorical_count': len(categorical_cols),
        'column_names': columns,
        'dtypes': dtypes,
        'numeric_columns': numeric_cols,
        'categorical_columns': categorical_cols,
        'missing_report': missing_report,
        'numeric_stats': final_numeric_stats,
        'categorical_stats': final_categorical_stats,
        'memory_kb': 0,  # not meaningful for chunked reads
        'file_size_mb': round(file_size / (1024 * 1024), 2),
        'large_file': True,
    }
