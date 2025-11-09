#!/usr/bin/env python3
"""
Auto-Calibration Workflow Dialog

This dialog allows users to select which auto-calibration operations to run
with checkboxes for each workflow stage.
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, 
                            QPushButton, QLabel, QGroupBox, QTextEdit,
                            QProgressBar, QMessageBox)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
import logging


class AutoCalibrationWorker(QThread):
    """Worker thread for running auto-calibration workflow."""
    
    progress_updated = Signal(int, str)  # percentage, message
    finished = Signal(dict)  # results
    error = Signal(str)  # error message
    
    def __init__(self, operations):
        super().__init__()
        self.operations = operations
        self.cancelled = False
    
    def run(self):
        """Run the auto-calibration workflow."""
        try:
            from src.astrofiler.core import fitsProcessing
            
            def progress_callback(percentage, message):
                if not self.cancelled:
                    self.progress_updated.emit(percentage, message)
            
            fits_processor = fitsProcessing()
            results = fits_processor.runAutoCalibrationWorkflow(
                progress_callback=progress_callback,
                operations=self.operations
            )
            
            if not self.cancelled:
                self.finished.emit(results)
                
        except Exception as e:
            if not self.cancelled:
                self.error.emit(str(e))
    
    def cancel(self):
        """Cancel the operation."""
        self.cancelled = True
        self.terminate()


class AutoCalibrationDialog(QDialog):
    """Dialog for selecting and running auto-calibration workflow operations."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Auto-Calibration Workflow")
        self.setModal(True)
        self.resize(600, 500)
        
        self.worker = None
        self.setupUI()
    
    def setupUI(self):
        """Set up the user interface."""
        layout = QVBoxLayout()
        
        # Title and description
        title_label = QLabel("Auto-Calibration Workflow")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        desc_label = QLabel("Select which calibration operations to perform:")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # Operations selection group
        operations_group = QGroupBox("Workflow Operations")
        operations_layout = QVBoxLayout()
        
        # Analyze operation
        self.analyze_checkbox = QCheckBox("Analyze Sessions")
        self.analyze_checkbox.setChecked(True)
        self.analyze_checkbox.setToolTip("Scan all sessions to identify calibration opportunities\n"
                                        "and check current master frame status")
        operations_layout.addWidget(self.analyze_checkbox)
        
        analyze_desc = QLabel("  • Identifies calibration opportunities")
        analyze_desc.setStyleSheet("color: gray; margin-left: 20px;")
        operations_layout.addWidget(analyze_desc)
        
        # Masters operation
        self.masters_checkbox = QCheckBox("Create Master Frames")
        self.masters_checkbox.setChecked(True)
        self.masters_checkbox.setToolTip("Create master bias, dark, and flat frames from\n"
                                       "calibration sessions with sufficient frames")
        operations_layout.addWidget(self.masters_checkbox)
        
        masters_desc = QLabel("  • Creates bias, dark, and flat master frames")
        masters_desc.setStyleSheet("color: gray; margin-left: 20px;")
        operations_layout.addWidget(masters_desc)
        
        # Calibrate operation
        self.calibrate_checkbox = QCheckBox("Calibrate Light Frames")
        self.calibrate_checkbox.setChecked(True)
        self.calibrate_checkbox.setToolTip("Apply master calibration frames to light frames\n"
                                         "for bias, dark, and flat field correction")
        operations_layout.addWidget(self.calibrate_checkbox)
        
        calibrate_desc = QLabel("  • Applies master frames to light sessions")
        calibrate_desc.setStyleSheet("color: gray; margin-left: 20px;")
        operations_layout.addWidget(calibrate_desc)
        
        # Quality operation
        self.quality_checkbox = QCheckBox("Quality Assessment")
        self.quality_checkbox.setChecked(False)  # Optional by default
        self.quality_checkbox.setToolTip("Perform quality analysis including FWHM, uniformity,\n"
                                       "noise metrics, and overall quality scoring")
        operations_layout.addWidget(self.quality_checkbox)
        
        quality_desc = QLabel("  • Analyzes frame quality and provides recommendations")
        quality_desc.setStyleSheet("color: gray; margin-left: 20px;")
        operations_layout.addWidget(quality_desc)
        
        operations_group.setLayout(operations_layout)
        layout.addWidget(operations_group)
        
        # Selection helpers
        helper_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.selectAll)
        helper_layout.addWidget(self.select_all_btn)
        
        self.select_none_btn = QPushButton("Select None")
        self.select_none_btn.clicked.connect(self.selectNone)
        helper_layout.addWidget(self.select_none_btn)
        
        self.select_essential_btn = QPushButton("Essential Only")
        self.select_essential_btn.clicked.connect(self.selectEssential)
        self.select_essential_btn.setToolTip("Select only analyze and masters operations")
        helper_layout.addWidget(self.select_essential_btn)
        
        helper_layout.addStretch()
        layout.addLayout(helper_layout)
        
        # Progress bar (initially hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel()
        self.progress_label.setVisible(False)
        layout.addWidget(self.progress_label)
        
        # Results area (initially hidden)
        self.results_group = QGroupBox("Results")
        self.results_group.setVisible(False)
        results_layout = QVBoxLayout()
        
        self.results_text = QTextEdit()
        self.results_text.setMaximumHeight(150)
        self.results_text.setReadOnly(True)
        results_layout.addWidget(self.results_text)
        
        self.results_group.setLayout(results_layout)
        layout.addWidget(self.results_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.run_button = QPushButton("Run Workflow")
        self.run_button.clicked.connect(self.runWorkflow)
        self.run_button.setDefault(True)
        button_layout.addWidget(self.run_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancelWorkflow)
        button_layout.addWidget(self.cancel_button)
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        self.close_button.setVisible(False)
        button_layout.addWidget(self.close_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def selectAll(self):
        """Select all operations."""
        self.analyze_checkbox.setChecked(True)
        self.masters_checkbox.setChecked(True)
        self.calibrate_checkbox.setChecked(True)
        self.quality_checkbox.setChecked(True)
    
    def selectNone(self):
        """Deselect all operations."""
        self.analyze_checkbox.setChecked(False)
        self.masters_checkbox.setChecked(False)
        self.calibrate_checkbox.setChecked(False)
        self.quality_checkbox.setChecked(False)
    
    def selectEssential(self):
        """Select only essential operations (analyze and masters)."""
        self.analyze_checkbox.setChecked(True)
        self.masters_checkbox.setChecked(True)
        self.calibrate_checkbox.setChecked(False)
        self.quality_checkbox.setChecked(False)
    
    def getSelectedOperations(self):
        """Get list of selected operations."""
        operations = []
        
        if self.analyze_checkbox.isChecked():
            operations.append('analyze')
        if self.masters_checkbox.isChecked():
            operations.append('masters')
        if self.calibrate_checkbox.isChecked():
            operations.append('calibrate')
        if self.quality_checkbox.isChecked():
            operations.append('quality')
        
        return operations
    
    def runWorkflow(self):
        """Run the selected workflow operations."""
        operations = self.getSelectedOperations()
        
        if not operations:
            QMessageBox.warning(self, "No Operations Selected", 
                              "Please select at least one operation to run.")
            return
        
        # Show progress UI
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Preparing workflow...")
        
        # Disable run button, enable cancel
        self.run_button.setEnabled(False)
        self.cancel_button.setText("Cancel")
        
        # Hide results if previously shown
        self.results_group.setVisible(False)
        
        # Start worker thread
        self.worker = AutoCalibrationWorker(operations)
        self.worker.progress_updated.connect(self.updateProgress)
        self.worker.finished.connect(self.workflowFinished)
        self.worker.error.connect(self.workflowError)
        self.worker.start()
    
    def cancelWorkflow(self):
        """Cancel the running workflow."""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.progress_label.setText("Cancelling...")
        else:
            self.close()
    
    def updateProgress(self, percentage, message):
        """Update progress bar and message."""
        self.progress_bar.setValue(percentage)
        self.progress_label.setText(message)
    
    def workflowFinished(self, results):
        """Handle workflow completion."""
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        
        # Show results
        self.showResults(results)
        
        # Update buttons
        self.run_button.setEnabled(True)
        self.cancel_button.setText("Close")
        self.close_button.setVisible(True)
        
        self.worker = None
    
    def workflowError(self, error_message):
        """Handle workflow error."""
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        
        QMessageBox.critical(self, "Workflow Error", 
                           f"Auto-calibration workflow failed:\n\n{error_message}")
        
        # Reset buttons
        self.run_button.setEnabled(True)
        self.cancel_button.setText("Close")
        
        self.worker = None
    
    def showResults(self, results):
        """Show workflow results."""
        self.results_group.setVisible(True)
        
        status = results.get('status', 'unknown')
        sessions_analyzed = results.get('sessions_analyzed', 0)
        masters_created = results.get('masters_created', 0)
        opportunities = results.get('calibration_opportunities', 0)
        light_sessions = results.get('light_frames_calibrated', 0)
        errors = results.get('errors', [])
        
        # Format results text
        result_text = f"Auto-calibration workflow completed ({status})!\n\n"
        
        if self.analyze_checkbox.isChecked():
            result_text += f"📊 Sessions analyzed: {sessions_analyzed}\n"
            result_text += f"🎯 Calibration opportunities found: {opportunities}\n"
        
        if self.masters_checkbox.isChecked():
            result_text += f"🔧 Master frames created: {masters_created}\n"
        
        if self.calibrate_checkbox.isChecked():
            result_text += f"✨ Light sessions calibrated: {light_sessions}\n"
        
        if errors:
            result_text += f"\n⚠️ Warnings/Errors ({len(errors)}):\n"
            for i, error in enumerate(errors[:3]):  # Show first 3 errors
                result_text += f"  {i+1}. {error}\n"
            if len(errors) > 3:
                result_text += f"  ... and {len(errors)-3} more issues\n"
        
        if status == 'success':
            result_text += "\n✅ Workflow completed successfully!"
        elif status == 'error':
            result_text += f"\n❌ Workflow failed: {results.get('message', 'Unknown error')}"
        
        self.results_text.setPlainText(result_text)
    
    def closeEvent(self, event):
        """Handle dialog close event."""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(self, "Workflow Running", 
                                       "Auto-calibration workflow is still running. Cancel it?",
                                       QMessageBox.Yes | QMessageBox.No,
                                       QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                self.worker.cancel()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()