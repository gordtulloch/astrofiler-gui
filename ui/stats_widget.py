import os
import time
import logging
import io
from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QTreeWidget, QTreeWidgetItem, QSplitter,
                               QSizePolicy, QPushButton)
from PySide6.QtGui import QFont, QPixmap

from astrofiler_db import fitsFile as FitsFileModel, fitsSession as FitsSessionModel

logger = logging.getLogger(__name__)

# Try to import matplotlib for charts
try:
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

class StatsWidget(QWidget):
    def __init__(self):
        super().__init__()
        # Initialize cache variables
        self._stats_cache = {}
        self._cache_timestamp = None
        self._cache_validity_seconds = 300  # Cache valid for 5 minutes
        
        self.init_ui()
        self.load_stats_data()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 10)
        layout.setSpacing(5)
        
        # Add refresh button at the top
        controls_layout = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh Statistics")
        self.refresh_button.setStyleSheet("QPushButton { font-size: 11px; }")
        self.refresh_button.clicked.connect(self.force_refresh_stats)
        controls_layout.addWidget(self.refresh_button)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        # Main content area with horizontal splitter for two columns
        splitter = QSplitter(Qt.Horizontal)
        splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Left column
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(5, 0, 5, 5)
        left_layout.setSpacing(0)
        left_layout.setAlignment(Qt.AlignTop)
        
        # Last 10 Objects Observed section
        recent_objects_label = QLabel("Last 10 Objects Observed")
        recent_objects_label.setFont(QFont("Arial", 12, QFont.Bold))
        recent_objects_label.setContentsMargins(0, 0, 0, 2)
        left_layout.addWidget(recent_objects_label)
        
        # Recent objects table
        self.recent_objects_table = QTreeWidget()
        self.recent_objects_table.setMinimumHeight(280)
        self.recent_objects_table.setMaximumHeight(320)
        self.recent_objects_table.setHeaderLabels(["Rank", "Object Name", "Last Observed"])
        self.recent_objects_table.setRootIsDecorated(False)
        self.recent_objects_table.setAlternatingRowColors(True)
        
        # Set column widths for recent objects table
        self.recent_objects_table.setColumnWidth(0, 50)   # Rank
        self.recent_objects_table.setColumnWidth(1, 220)  # Object Name
        self.recent_objects_table.setColumnWidth(2, 120)  # Last Observed
        
        # Set header alignment
        self.recent_objects_table.headerItem().setTextAlignment(0, Qt.AlignCenter)  # Rank
        self.recent_objects_table.headerItem().setTextAlignment(2, Qt.AlignRight)   # Last Observed
        
        left_layout.addWidget(self.recent_objects_table)
        
        # Summary Statistics section
        summary_label = QLabel("Summary Statistics")
        summary_label.setFont(QFont("Arial", 12, QFont.Bold))
        summary_label.setContentsMargins(0, 15, 0, 2)
        left_layout.addWidget(summary_label)
        
        self.summary_table = QTreeWidget()
        self.summary_table.setMinimumHeight(160)
        self.summary_table.setMaximumHeight(200)
        self.summary_table.setHeaderLabels(["Item", "Count"])
        self.summary_table.setRootIsDecorated(False)
        self.summary_table.setAlternatingRowColors(True)
        
        # Set column widths for summary table
        self.summary_table.setColumnWidth(0, 220)  # Item
        self.summary_table.setColumnWidth(1, 100)  # Count
        
        # Set header alignment for "Count" column
        self.summary_table.headerItem().setTextAlignment(1, Qt.AlignRight)
        
        left_layout.addWidget(self.summary_table)
        
        splitter.addWidget(left_widget)
        
        # Right column
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 5, 5)
        right_layout.setSpacing(10)
        right_layout.setAlignment(Qt.AlignTop)
        
        # Top 10 Objects section
        objects_label = QLabel("Top 10 Objects by Total Integration Time")
        objects_label.setFont(QFont("Arial", 12, QFont.Bold))
        objects_label.setContentsMargins(0, 0, 0, 2)
        right_layout.addWidget(objects_label)
        
        # Objects table with columns
        self.objects_table = QTreeWidget()
        self.objects_table.setMinimumHeight(280)
        self.objects_table.setMaximumHeight(350)
        self.objects_table.setHeaderLabels(["Rank", "Object Name", "Total Seconds"])
        self.objects_table.setRootIsDecorated(False)
        self.objects_table.setAlternatingRowColors(True)
        
        # Set column widths
        self.objects_table.setColumnWidth(0, 50)   # Rank
        self.objects_table.setColumnWidth(1, 220)  # Object Name
        self.objects_table.setColumnWidth(2, 120)  # Total Seconds
        
        # Set header alignment for "Total Seconds" column
        self.objects_table.headerItem().setTextAlignment(0, Qt.AlignCenter)  # Rank
        self.objects_table.headerItem().setTextAlignment(2, Qt.AlignRight)   # Total Seconds
        
        right_layout.addWidget(self.objects_table)
        
        # Filter Chart section
        chart_label = QLabel("Total Imaging Time by Filter")
        chart_label.setFont(QFont("Arial", 12, QFont.Bold))
        chart_label.setContentsMargins(0, 15, 0, 2)
        right_layout.addWidget(chart_label)
        
        # Chart area
        self.chart_label = QLabel()
        self.chart_label.setMinimumSize(300, 250)
        self.chart_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.chart_label.setAlignment(Qt.AlignCenter)
        self.chart_label.setStyleSheet("border: 1px solid gray; background-color: white;")
        right_layout.addWidget(self.chart_label)
        
        splitter.addWidget(right_widget)
        
        # Set splitter proportions
        splitter.setSizes([380, 450])
        
        # Add the splitter to the main layout
        layout.addWidget(splitter)
        
        # Add stretch at the bottom to push content to top in fullscreen mode
        layout.addStretch(1)
    
    def _is_cache_valid(self):
        """Check if the stats cache is still valid"""
        if self._cache_timestamp is None:
            return False
        current_time = time.time()
        cache_age = current_time - self._cache_timestamp
        
        return cache_age < self._cache_validity_seconds
    
    def _invalidate_cache(self):
        """Invalidate the stats cache"""
        self._stats_cache.clear()
        self._cache_timestamp = None
        logger.debug("Stats cache invalidated")
    
    def force_refresh_stats(self):
        """Force refresh statistics by clearing cache first"""
        self._invalidate_cache()
        self.load_stats_data()
    
    def invalidate_stats_cache(self):
        """Public method to invalidate stats cache when data changes"""
        self._invalidate_cache()
        logger.debug("Stats cache invalidated due to data changes")
    
    def load_stats_data(self):
        """Load and display statistics data with caching"""
        try:
            # Check if we can use cached data
            if self._is_cache_valid():
                logger.debug("Using cached statistics data")
                return
            
            # Cache is invalid, load fresh data
            logger.debug("Loading fresh statistics data")
            
            # Load last 10 objects observed
            self.load_recent_objects()
            
            # Load summary statistics
            self.load_summary_stats()
            
            # Load top 10 objects by integration time
            self.load_top_objects()
            
            # Load and create pie chart for filters
            self.create_filter_pie_chart()
            
            # Update cache timestamp
            self._cache_timestamp = time.time()
            
            logger.debug("Statistics data loaded and cached")
            
        except Exception as e:
            logging.error(f"Error loading stats data: {str(e)}")
    
    def load_recent_objects(self):
        """Load last 10 objects observed based on most recent sessions"""
        try:
            self.recent_objects_table.clear()
            
            # Query to get the 10 most recent light sessions with their objects and dates
            from peewee import fn
            
            query = (FitsSessionModel
                    .select(FitsSessionModel.fitsSessionObjectName, 
                           fn.MAX(FitsSessionModel.fitsSessionDate).alias('last_observed'))
                    .where(FitsSessionModel.fitsSessionObjectName.is_null(False),
                           FitsSessionModel.fitsSessionObjectName != 'Bias',
                           FitsSessionModel.fitsSessionObjectName != 'Dark',
                           FitsSessionModel.fitsSessionObjectName != 'Flat')
                    .group_by(FitsSessionModel.fitsSessionObjectName)
                    .order_by(fn.MAX(FitsSessionModel.fitsSessionDate).desc())
                    .limit(10))
            
            for i, session in enumerate(query, 1):
                item = QTreeWidgetItem([
                    str(i),
                    session.fitsSessionObjectName,
                    str(session.last_observed) if session.last_observed else "Unknown"
                ])
                item.setTextAlignment(0, Qt.AlignCenter)  # Center rank
                item.setTextAlignment(2, Qt.AlignRight)   # Right-align date
                self.recent_objects_table.addTopLevelItem(item)
                
        except Exception as e:
            logging.error(f"Error loading recent objects: {str(e)}")
    
    def load_summary_stats(self):
        """Load summary statistics for FITS files and sessions"""
        try:
            self.summary_table.clear()
            
            # Count different types of FITS files
            total_lights = FitsFileModel.select().where(FitsFileModel.fitsFileType.contains('Light')).count()
            total_darks = FitsFileModel.select().where(FitsFileModel.fitsFileType.contains('Dark')).count()
            total_biases = FitsFileModel.select().where(FitsFileModel.fitsFileType.contains('Bias')).count()
            total_flats = FitsFileModel.select().where(FitsFileModel.fitsFileType.contains('Flat')).count()
            
            # Count total sessions
            total_sessions = FitsSessionModel.select().count()
            
            # Count unique nights of imaging
            try:
                unique_dates = FitsSessionModel.select(FitsSessionModel.fitsSessionDate).distinct()
                date_list = [session.fitsSessionDate for session in unique_dates if session.fitsSessionDate]
                total_nights = self._count_astronomical_nights(date_list)
            except Exception:
                total_nights = 0
            
            # Create summary items
            summary_items = [
                ("Total Lights", total_lights),
                ("Total Darks", total_darks),
                ("Total Biases", total_biases),
                ("Total Flats", total_flats),
                ("Total Sessions", total_sessions),
                ("Total Nights Imaging", total_nights)
            ]
            
            for item_name, count in summary_items:
                item = QTreeWidgetItem([item_name, str(count)])
                item.setTextAlignment(1, Qt.AlignRight)  # Right-align count
                self.summary_table.addTopLevelItem(item)
                
        except Exception as e:
            logging.error(f"Error loading summary stats: {str(e)}")
    
    def _count_astronomical_nights(self, dates):
        """Count unique astronomical nights from a list of dates"""
        if not dates:
            return 0
        
        # Convert all dates to datetime objects
        datetime_objects = []
        for date in dates:
            if date is None:
                continue
            try:
                if isinstance(date, str):
                    dt = datetime.fromisoformat(date)
                else:
                    dt = date
                datetime_objects.append(dt)
            except (ValueError, TypeError):
                continue
        
        if not datetime_objects:
            return 0
        
        # Sort dates and group into nights
        datetime_objects.sort()
        nights = []
        
        for dt in datetime_objects:
            # Find if this datetime belongs to an existing night
            found_night = False
            for night_group in nights:
                for night_dt in night_group:
                    time_diff = abs((dt - night_dt).total_seconds())
                    if time_diff <= 43200:  # 12 hours
                        night_group.append(dt)
                        found_night = True
                        break
                if found_night:
                    break
            
            # If no existing night found, create a new night
            if not found_night:
                nights.append([dt])
        
        return len(nights)
    
    def load_top_objects(self):
        """Load top 10 objects by total integration time"""
        try:
            self.objects_table.clear()
            
            # Query to get total integration time per object for Light frames only
            from peewee import fn
            
            query = (FitsFileModel
                    .select(FitsFileModel.fitsFileObject, 
                           fn.SUM(FitsFileModel.fitsFileExpTime.cast('float')).alias('total_time'))
                    .where(FitsFileModel.fitsFileType.contains('Light'))
                    .group_by(FitsFileModel.fitsFileObject)
                    .order_by(fn.SUM(FitsFileModel.fitsFileExpTime.cast('float')).desc())
                    .limit(10))
            
            for i, obj in enumerate(query, 1):
                total_seconds = obj.total_time or 0
                item = QTreeWidgetItem([
                    str(i),
                    obj.fitsFileObject or "Unknown",
                    f"{int(total_seconds):,}"
                ])
                item.setTextAlignment(0, Qt.AlignCenter)  # Center rank
                item.setTextAlignment(2, Qt.AlignRight)   # Right-align seconds
                self.objects_table.addTopLevelItem(item)
                
        except Exception as e:
            logging.error(f"Error loading top objects: {str(e)}")
    
    def create_filter_pie_chart(self):
        """Create and display pie chart for filter usage"""
        try:
            if not HAS_MATPLOTLIB:
                self.chart_label.setText("Matplotlib not available for charts\nInstall matplotlib to view charts")
                return
            
            # Query to get total time per filter for Light frames only
            from peewee import fn
            
            query = (FitsFileModel
                    .select(FitsFileModel.fitsFileFilter, 
                           fn.SUM(FitsFileModel.fitsFileExpTime.cast('float')).alias('total_time'))
                    .where(FitsFileModel.fitsFileType.contains('Light'))
                    .group_by(FitsFileModel.fitsFileFilter)
                    .order_by(fn.SUM(FitsFileModel.fitsFileExpTime.cast('float')).desc()))
            
            # ...existing code for chart creation...
            
        except ImportError:
            self.chart_label.setText("Matplotlib not available for charts\nInstall matplotlib to view charts")
            logging.warning("Matplotlib import error")
        except Exception as e:
            logging.error(f"Error creating pie chart: {str(e)}")
            self.chart_label.setText(f"Error creating chart:\n{str(e)}")

    def showEvent(self, event):
        """Handle show events to reload data when widget becomes visible"""
        super().showEvent(event)
        if not self._is_cache_valid():
            self.load_stats_data()
        else:
            logger.debug("Stats widget shown - using cached data")
