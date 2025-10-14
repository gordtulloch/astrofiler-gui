# GitHub Copilot Instructions for AstroFiler Project

## Virtual Environment Requirements

**IMPORTANT**: All Python code execution, package installation, and testing must be performed within a virtual environment (venv).

### Standing Instructions:

1. **Always use the virtual environment**: Before running any Python commands, scripts, or installing packages, ensure you are working within the project's virtual environment located at `.venv/`

2. **Virtual environment activation**: 
   - On Linux/macOS: `source .venv/bin/activate`
   - On Windows: `.venv\Scripts\activate`

3. **Python execution**: Use the virtual environment's Python interpreter:
   - Linux/macOS: `.venv/bin/python`
   - Windows: `.venv\Scripts\python.exe`

4. **Package management**: All pip installations must be done within the activated virtual environment to maintain dependency isolation

5. **Testing and debugging**: All test runs, debugging sessions, and development work should occur within the virtual environment context

6. **Testing limitations**: Do not run functional tests or execute the application to verify changes unless explicitly requested by the user. Only perform syntax checking (e.g., `python -m py_compile`) to verify code correctness.

7. **Change log maintenance**: For every significant change to the application, update CHANGE_LOG.md by adding new features to the current version section. Add only bare minimum content - feature name and brief description. Do not add extra sections or verbose content.

8. **Update change log for all significant changes**: When implementing new features, bug fixes, or UI improvements, always update the change log as part of the standard workflow.

9. **Response style**: Keep responses concise and focused. Avoid lengthy summaries or detailed explanations unless specifically requested by the user.

10. **Always split classes out into separate files**: Each class should be in its own file named after the class. For example, a class named `ImageProcessor` should be in a file named `image_processor.py`. Where a particular part of a program requires multiple classes, group related classes into a single package (directory with `__init__.py`), ensuring each class still resides in its own file within that package. This will keep the codebase organized and maintainable.

### Rationale:
- Ensures consistent dependency versions across development environments
- Prevents conflicts with system-wide Python packages
- Maintains project isolation and reproducibility
- Follows Python best practices for project development

### Example Commands:
```bash
# Activate virtual environment
source .venv/bin/activate

# Run the application
python astrofiler.py

# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest test/
```

**Remember**: Never run Python commands directly with system Python when working on this project. Always ensure the virtual environment is active first.
