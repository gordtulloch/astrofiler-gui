## 🤝 Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

If you wish to make a cash contribution to assist the author in continuing to produce quality open source software please feel free to make a Paypal contribution to gord.tulloch@gmail.com.

## 🏗️ Code Structure

### Main Components

- **`astrofiler.py`**: Application entry point
- **`astrofiler_gui.py`**: Main GUI implementation with all tabs
- **`astrofiler_file.py`**: FITS file processing and session management
- **`astrofiler_db.py`**: Database models and migration functions

### Key Features Implementation

#### Merge/Rename Functionality (`astrofiler_gui.py`)

The **MergeTab** class implements object merging with the following capabilities:

**Core Functions:**
- `execute_merge()`: Main merge operation coordinating database and file updates
- Handles both database-only and file-renaming operations
- Integrates FITS header updates when files are physically renamed

**FITS Header Management:**
- Uses `astropy.fits` in `mode='update'` for safe header modifications
- Updates OBJECT header field to match new object names
- Adds audit trail comments showing change history
- Only modifies headers when files are actually renamed on disk

**Error Handling:**
- Comprehensive try-catch blocks for file operations
- Individual error tracking with detailed logging
- Graceful failure handling that doesn't stop batch operations
- User-friendly error reporting with guidance

**Progress Tracking:**
- Real-time progress updates during long operations
- Detailed operation summaries with counts and statistics
- Cancellation support for user-initiated stops

#### Database Integration

**Session-Level Metadata:**
Recent enhancements add equipment and acquisition settings to session records for improved calibration matching.

#### Best Practices for Contributors

**FITS File Operations:**
- Always use `mode='update'` when modifying FITS files
- Include proper error handling for corrupted files
- Preserve original data and add audit trail comments
- Use `hdul.flush()` to ensure changes are written

**Database Operations:**
- Use transactions for multi-step database operations
- Handle integrity errors gracefully
- Provide detailed logging for debugging
- Test with both small and large datasets

**UI Development:**
- Follow the existing tab-based structure
- Include progress dialogs for long operations
- Provide clear user feedback and confirmation dialogs
- Implement cancellation support where appropriate

**Testing:**
- Test with various FITS file formats and headers
- Verify error handling with corrupted or missing files
- Test database migrations with existing data
- Validate file operations don't corrupt FITS files

