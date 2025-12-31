# SOLID Principles Analysis and Refactoring Plan

## Current Architecture Analysis

### 📊 SOLID Principles Violations Identified

#### 1. **Single Responsibility Principle (SRP) Violations**

##### FileProcessor Class (Major Violation)
**Current Responsibilities:**
- File hash calculation
- ZIP file extraction  
- XISF file conversion
- Master file detection and registration
- FITS file registration
- Database operations
- Header processing
- Configuration management

**Problem:** One class handling 8+ distinct responsibilities

##### MasterFrameManager Class (Minor Violation)
**Current Responsibilities:**
- Master frame creation via Siril
- Master frame validation
- Cleanup operations
- Configuration management
- Statistics generation

#### 2. **Open/Closed Principle (OCP) Violations**

##### File Format Support
**Problem:** Adding new file formats (e.g., TIFF, CR2) requires modifying FileProcessor class directly
**Current Pattern:**
```python
if file_extension.lower() in ['.zip']:
    # Handle ZIP
elif file_extension.lower() in ['.xisf']:
    # Handle XISF
# Need to modify this method for new formats
```

##### Master Frame Types
**Problem:** Adding new calibration frame types requires modifying multiple methods
**Current Pattern:** Hard-coded support for 'bias', 'dark', 'flat'

#### 3. **Interface Segregation Principle (ISP) Violations**

##### UI Widget Dependencies
**Problem:** Large UI classes with many unrelated methods
**Example:** Main window knows about all specific widget implementations

#### 4. **Dependency Inversion Principle (DIP) Violations**

##### Direct Database Dependencies
**Problem:** Core classes directly import and use specific database models
```python
from ..models import fitsFile as FitsFileModel  # Concrete dependency
```

##### Configuration Coupling
**Problem:** Classes directly read from astrofiler.ini file instead of using abstraction

## 🛠️ Refactoring Strategy

### Phase 1: Single Responsibility Principle (SRP) Fixes

#### 1.1 Extract File Format Handlers
```python
# New abstraction
class FileFormatHandler(Protocol):
    def can_handle(self, file_path: str) -> bool:
    def process_file(self, file_path: str) -> str:

class ZipFileHandler(FileFormatHandler):
    def can_handle(self, file_path: str) -> bool:
        return file_path.lower().endswith('.zip')
    
    def process_file(self, file_path: str) -> str:
        # ZIP extraction logic

class XisfFileHandler(FileFormatHandler):
    def can_handle(self, file_path: str) -> bool:
        return file_path.lower().endswith('.xisf')
    
    def process_file(self, file_path: str) -> str:
        # XISF conversion logic
```

#### 1.2 Extract Hash Calculator Service
```python
class FileHashCalculator:
    """Single responsibility: Calculate file hashes"""
    
    def calculate_sha256(self, file_path: str) -> str:
        # Hash calculation logic
        
    def calculate_md5(self, file_path: str) -> str:
        # Alternative hash algorithm
```

#### 1.3 Extract Database Operations
```python
class FitsFileRepository:
    """Single responsibility: FITS file database operations"""
    
    def save_fits_file(self, fits_data: FitsFileData) -> str:
    def find_by_hash(self, file_hash: str) -> Optional[FitsFileData]:
    def check_duplicate(self, file_hash: str) -> bool:
```

### Phase 2: Open/Closed Principle (OCP) Fixes

#### 2.1 File Format Strategy Pattern
```python
class FileFormatProcessor:
    def __init__(self):
        self._handlers: List[FileFormatHandler] = [
            ZipFileHandler(),
            XisfFileHandler(),
            FitsFileHandler()
        ]
    
    def register_handler(self, handler: FileFormatHandler):
        """Extend functionality without modifying existing code"""
        self._handlers.append(handler)
    
    def process_file(self, file_path: str) -> str:
        for handler in self._handlers:
            if handler.can_handle(file_path):
                return handler.process_file(file_path)
        raise UnsupportedFileFormatError(file_path)
```

#### 2.2 Master Frame Type Strategy
```python
class MasterFrameStrategy(Protocol):
    def get_frame_type(self) -> str:
    def validate_session_data(self, session_data: Dict) -> bool:
    def create_master(self, files: List[str], output_path: str) -> bool:

class BiasMasterStrategy(MasterFrameStrategy):
    def get_frame_type(self) -> str:
        return "bias"
    
    def validate_session_data(self, session_data: Dict) -> bool:
        # Bias-specific validation
        
class DarkMasterStrategy(MasterFrameStrategy):
    def get_frame_type(self) -> str:
        return "dark"
    
    def validate_session_data(self, session_data: Dict) -> bool:
        # Dark-specific validation (exposure time matching)
```

### Phase 3: Interface Segregation Principle (ISP) Fixes

#### 3.1 Specific Interfaces for UI Components
```python
class FileDisplayInterface(Protocol):
    def display_files(self, files: List[FitsFileData]) -> None:
    def refresh_display(self) -> None:

class FileSelectionInterface(Protocol):
    def get_selected_files(self) -> List[str]:
    def clear_selection(self) -> None:

class ProgressInterface(Protocol):
    def update_progress(self, percentage: int, message: str) -> None:
    def show_progress(self) -> None:
    def hide_progress(self) -> None:
```

#### 3.2 Segregated Database Interfaces
```python
class FitsFileReader(Protocol):
    def get_by_id(self, file_id: str) -> Optional[FitsFileData]:
    def find_by_criteria(self, criteria: Dict) -> List[FitsFileData]:

class FitsFileWriter(Protocol):
    def save(self, fits_file: FitsFileData) -> str:
    def update(self, file_id: str, updates: Dict) -> bool:

class FitsFileDeleter(Protocol):
    def delete(self, file_id: str) -> bool:
    def bulk_delete(self, file_ids: List[str]) -> int:
```

### Phase 4: Dependency Inversion Principle (DIP) Fixes

#### 4.1 Abstract Configuration Service
```python
class ConfigurationService(Protocol):
    def get_source_folder(self) -> str:
    def get_repo_folder(self) -> str:
    def get_masters_folder(self) -> str:
    def get_boolean_setting(self, key: str, default: bool = False) -> bool:

class IniConfigurationService(ConfigurationService):
    def __init__(self, config_file: str = 'astrofiler.ini'):
        self._config_file = config_file
        
    def get_source_folder(self) -> str:
        config = configparser.ConfigParser()
        config.read(self._config_file)
        return config.get('DEFAULT', 'source', fallback='.')
```

#### 4.2 Abstract Database Repository
```python
class DatabaseRepository(Protocol):
    def connect(self) -> None:
    def disconnect(self) -> None:
    def begin_transaction(self) -> None:
    def commit_transaction(self) -> None:
    def rollback_transaction(self) -> None:

class PeeweeDatabaseRepository(DatabaseRepository):
    # Concrete implementation for Peewee ORM
```

## 🎯 Implementation Priority

### High Priority (Immediate Benefits)
1. **Extract FileFormatProcessor** - Enables easy addition of new file formats
2. **Extract FileHashCalculator** - Simple, clear responsibility separation
3. **Extract ConfigurationService** - Improves testability and flexibility

### Medium Priority (Architecture Improvement)
4. **Extract Database Repositories** - Better abstraction and testability
5. **Implement Master Frame Strategies** - Easier to add new frame types
6. **Segregate UI Interfaces** - Better component isolation

### Low Priority (Future Extensibility)
7. **Advanced Strategy Patterns** - For complex processing workflows
8. **Event-Driven Architecture** - For loose coupling between components
9. **Plugin Architecture** - For third-party extensions

## 📈 Expected Benefits

### Code Quality
- **Cleaner Separation** - Each class has a single, clear purpose
- **Easier Testing** - Isolated responsibilities are easier to unit test
- **Better Documentation** - Clear interfaces and contracts

### Maintainability
- **Reduced Coupling** - Changes in one area don't affect unrelated areas
- **Easier Refactoring** - Well-defined boundaries make changes safer
- **Clear Dependencies** - Abstract interfaces make relationships explicit

### Extensibility
- **New File Formats** - Add without modifying existing code
- **New Master Types** - Plugin new calibration frame types
- **New Data Sources** - Swap database or configuration implementations
- **Third-Party Integration** - Well-defined interfaces for extensions

## 🧪 Validation Strategy

### Automated Testing
- **Unit Tests** - Test each extracted class in isolation
- **Integration Tests** - Verify interfaces work correctly together
- **Regression Tests** - Ensure existing functionality remains intact

### Code Quality Metrics
- **Cyclomatic Complexity** - Should decrease with responsibility separation
- **Coupling Metrics** - Lower coupling between unrelated components
- **Cohesion Metrics** - Higher cohesion within each component

### Performance Validation
- **Benchmark Current Implementation** - Establish baseline performance
- **Test Refactored Implementation** - Ensure no performance degradation
- **Memory Usage Analysis** - Verify abstractions don't increase memory overhead significantly

## Next Steps

1. **Start with FileFormatProcessor extraction** - Most straightforward refactoring
2. **Implement comprehensive test suite** - Ensure safety net for refactoring
3. **Gradual migration** - Move functionality piece by piece
4. **Continuous validation** - Test at each step to ensure stability