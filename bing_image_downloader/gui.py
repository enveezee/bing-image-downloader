import sys
import threading
import datetime
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QScrollArea, QGridLayout, QLabel,
    QSplitter, QTextEdit, QFrame, QComboBox, QSpacerItem, QSizePolicy,
    QDateEdit, QMessageBox
)
from PyQt6.QtGui import QPixmap, QPainter, QColor, QBrush
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QObject, QDate

from bing_image_downloader.scraper import BingImageScraper
from bing_image_downloader.downloader import Downloader
from bing_image_downloader.data_model import ImageData

class Communicate(QObject):
    search_finished = pyqtSignal(list)
    load_more_finished = pyqtSignal(list)
    details_finished = pyqtSignal(object)
    error = pyqtSignal(str)

class ImageWidget(QWidget):
    selected_signal = pyqtSignal(ImageData)

    def __init__(self, data: ImageData, parent=None):
        super().__init__(parent)
        self.data = data
        self.is_selected = False
        self.setFixedSize(180, 200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self.pixmap_label = QLabel()
        self.pixmap_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.pixmap_label)

        if data.thumbnail and isinstance(data.thumbnail, bytes):
            try:
                if self.parent().debug:
                    print(f"[DEBUG] Attempting to load thumbnail for {data.title}...")
                pixmap = QPixmap()
                if pixmap.loadFromData(data.thumbnail):
                    self.pixmap_label.setPixmap(pixmap.scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                    if self.parent().debug:
                        print(f"[DEBUG] Thumbnail loaded successfully for {data.title}")
                else:
                    if self.parent().debug:
                        print(f"[DEBUG] QPixmap.loadFromData failed for {data.title}. Data might be corrupted or invalid.")
                    self.pixmap_label.setText("No Image")
            except Exception as e:
                if self.parent().debug:
                    print(f"[DEBUG] Error loading thumbnail for {data.title}: {e}")
                self.pixmap_label.setText("No Image")
        else:
            if self.parent().debug:
                print(f"[DEBUG] No valid thumbnail data for {data.title} (is None or not bytes).")
            self.pixmap_label.setText("No Image")

        title_label = QLabel(data.title or "Untitled")
        title_label.setWordWrap(True)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

    def mousePressEvent(self, event):
        self.is_selected = not self.is_selected
        self.update()
        self.selected_signal.emit(self.data)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        if self.is_selected:
            pen = painter.pen()
            pen.setColor(QColor("lightblue"))
            pen.setWidth(3)
            painter.setPen(pen)
            painter.drawRect(self.rect().adjusted(1, 1, -1, -1))

        if self.data.size:
            painter.setPen(Qt.GlobalColor.white)
            painter.setBrush(QBrush(QColor(0, 0, 0, 128)))
            text_rect = self.pixmap_label.geometry()
            text_rect.setTop(text_rect.bottom() - 20)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f" {self.data.size} ")

class ImageSearchGUI(QMainWindow):
    def __init__(self, debug=False):
        super().__init__()
        self.debug = debug
        self.setWindowTitle("Bing Image Search")
        self.setGeometry(100, 100, 1400, 900)
        self.signals = Communicate()
        self.signals.search_finished.connect(self.on_search_finished)
        self.signals.load_more_finished.connect(self.on_load_more_finished)
        self.signals.details_finished.connect(self.on_details_finished)
        self.signals.error.connect(self.on_error)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter your search query and press Enter...")
        self.search_input.returnPressed.connect(self.start_search)
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.start_search)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)
        self.layout.addLayout(search_layout)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.layout.addWidget(self.splitter)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        self.results_widget = QWidget()
        self.results_layout = QGridLayout(self.results_widget)
        scroll_area.setWidget(self.results_widget)
        self.splitter.addWidget(scroll_area)

        self.splitter.setSizes([1100, 300])
        self.layout.setStretchFactor(self.splitter, 1)

        self.setup_sidebar()
        self.setup_filter_bar()

        bottom_layout = QHBoxLayout()
        self.load_more_button = QPushButton("Load More")
        self.load_more_button.clicked.connect(self.load_more)
        self.download_button = QPushButton("Download Selected")
        self.download_button.clicked.connect(self.download_selected)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.load_more_button)
        bottom_layout.addWidget(self.download_button)
        self.layout.addLayout(bottom_layout)

        self.scraper = BingImageScraper(debug=self.debug)
        self.downloader = Downloader("downloads")
        self.image_data_store = []
        self.active_filters = []
        self.selected_widgets = []
        self.sidebar.setVisible(False)

    def setup_filter_bar(self):
        filter_bar_layout = QHBoxLayout()
        self.active_filters_widget = QWidget()
        self.active_filters_layout = QHBoxLayout(self.active_filters_widget)
        self.active_filters_layout.setContentsMargins(0,0,0,0)

        self.filter_criterion_combo = QComboBox()
        self.filter_criterion_combo.addItems(["Source", "Title", "Size (px)", "Date", "Age"])
        self.filter_criterion_combo.currentTextChanged.connect(self.update_filter_inputs)

        self.filter_operator_combo = QComboBox()
        self.filter_value_input = QLineEdit()
        self.filter_date_input = QDateEdit(calendarPopup=True)
        self.filter_date_input.setDate(QDate.currentDate())
        self.filter_date_input.hide()

        self.add_filter_button = QPushButton("Add Filter")
        self.add_filter_button.clicked.connect(self.add_filter)

        filter_bar_layout.addWidget(self.filter_criterion_combo)
        filter_bar_layout.addWidget(self.filter_operator_combo)
        filter_bar_layout.addWidget(self.filter_value_input)
        filter_bar_layout.addWidget(self.filter_date_input)
        filter_bar_layout.addWidget(self.add_filter_button)
        filter_bar_layout.addStretch(1)

        main_filter_layout = QVBoxLayout()
        main_filter_layout.addLayout(filter_bar_layout)
        main_filter_layout.addWidget(self.active_filters_widget)
        self.layout.insertLayout(1, main_filter_layout)
        self.update_filter_inputs()

    def update_filter_inputs(self):
        criterion = self.filter_criterion_combo.currentText()
        self.filter_operator_combo.clear()
        self.filter_value_input.show()
        self.filter_date_input.hide()

        if criterion in ["Source", "Title"]:
            self.filter_operator_combo.addItems(["contains", "does not contain"])
        elif criterion == "Size (px)":
            self.filter_operator_combo.addItems(["is greater than", "is less than"])
        elif criterion == "Date":
            self.filter_operator_combo.addItems(["is after", "is before", "is on"])
            self.filter_value_input.hide()
            self.filter_date_input.show()
        elif criterion == "Age":
            self.filter_operator_combo.addItems(["older than (days)", "newer than (days)"])
            self.filter_date_input.hide()
            self.filter_value_input.show()

    def add_filter(self):
        criterion = self.filter_criterion_combo.currentText()
        operator = self.filter_operator_combo.currentText()
        
        if criterion == "Date":
            value = self.filter_date_input.date().toPyDate()
        else:
            value = self.filter_value_input.text()

        if not value:
            return

        filter_id = time.time()
        self.active_filters.append({"id": filter_id, "criterion": criterion, "operator": operator, "value": value})
        self.create_filter_tag_widget(criterion, operator, value, filter_id)
        self.apply_filters()

    def create_filter_tag_widget(self, criterion, operator, value, filter_id):
        tag_widget = QFrame()
        tag_widget.setStyleSheet("QFrame { border: 1px solid #777; border-radius: 5px; }")
        tag_layout = QHBoxLayout(tag_widget)
        tag_layout.setContentsMargins(5, 2, 5, 2)
        
        value_str = value.strftime('%Y-%m-%d') if isinstance(value, datetime.date) else str(value)
        label_text = f"{criterion} {operator} '{value_str}'"
        tag_label = QLabel(label_text)
        
        remove_button = QPushButton("x")
        remove_button.setFixedSize(20, 20)
        remove_button.setStyleSheet("QPushButton { border: none; background-color: transparent; }")
        remove_button.clicked.connect(lambda: self.remove_filter(filter_id, tag_widget))
        
        tag_layout.addWidget(tag_label)
        tag_layout.addWidget(remove_button)
        self.active_filters_layout.addWidget(tag_widget)

    def remove_filter(self, filter_id, tag_widget):
        self.active_filters = [f for f in self.active_filters if f["id"] != filter_id]
        tag_widget.deleteLater()
        self.apply_filters()

    def setup_sidebar(self):
        self.sidebar = QWidget()
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(5, 5, 5, 5)
        close_button = QPushButton("✕")
        close_button.setFixedSize(24, 24)
        close_button.clicked.connect(self.close_sidebar)
        sidebar_top_layout = QHBoxLayout()
        sidebar_top_layout.addStretch()
        sidebar_top_layout.addWidget(close_button)
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        sidebar_layout.addLayout(sidebar_top_layout)
        sidebar_layout.addWidget(self.info_text)
        self.splitter.addWidget(self.sidebar)

    def clear_grid(self):
        while self.results_layout.count():
            child = self.results_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.image_data_store = []
        self.selected_widgets = []
        self.sidebar.setVisible(False)

    def start_search(self):
        query = self.search_input.text()
        if query:
            self.clear_grid()
            self.search_button.setEnabled(False)
            self.search_button.setText("Searching...")
            threading.Thread(target=self.run_search, args=(query,), daemon=True).start()

    def run_search(self, query):
        try:
            if self.debug:
                print(f"[DEBUG] Starting search for query: {query}")
            self.scraper.search(query)
            if self.debug:
                print("[DEBUG] Scraper search completed. Getting image data...")
            images = self.scraper.get_image_data(max_images=20)
            if self.debug:
                print(f"[DEBUG] Retrieved {len(images)} images. Emitting search_finished signal.")
            self.signals.search_finished.emit(images)
        except Exception as e:
            if self.debug:
                print(f"[DEBUG] Error during search: {e}")
            self.signals.error.emit(str(e))

    def on_search_finished(self, images):
        if self.debug:
            print(f"[DEBUG] on_search_finished called with {len(images)} images.")
        self.image_data_store = images
        self.apply_filters()
        self.search_button.setEnabled(True)
        self.search_button.setText("Search")
        if self.debug:
            print("[DEBUG] on_search_finished completed.")

    def load_more(self):
        self.load_more_button.setEnabled(False)
        self.load_more_button.setText("Loading...")
        threading.Thread(target=self.run_load_more, daemon=True).start()

    def run_load_more(self):
        try:
            new_data = self.scraper.get_image_data(max_images=len(self.image_data_store) + 20)
            self.signals.load_more_finished.emit(new_data)
        except Exception as e:
            self.signals.error.emit(str(e))

    def on_load_more_finished(self, new_images):
        if self.debug:
            print(f"[DEBUG] Load more finished, received {len(new_images)} new images.")
        existing_urls = {img.image_source_url for img in self.image_data_store}
        self.image_data_store.extend([d for d in new_images if d.image_source_url not in existing_urls])
        self.apply_filters()
        self.load_more_button.setEnabled(True)
        self.load_more_button.setText("Load More")

    def apply_filters(self):
        if not self.active_filters:
            self.update_grid(self.image_data_store)
            return

        filtered_images = self.image_data_store
        for f in self.active_filters:
            filtered_images = self._filter_data(filtered_images, f["criterion"], f["operator"], f["value"])
        
        self.update_grid(filtered_images)

    def _filter_data(self, data, criterion, operator, value):
        filtered_data = []
        for item in data:
            try:
                if criterion == "Title":
                    if operator == "contains" and value.lower() in (item.title or "").lower():
                        filtered_data.append(item)
                    elif operator == "does not contain" and value.lower() not in (item.title or "").lower():
                        filtered_data.append(item)
                elif criterion == "Source":
                    if operator == "contains" and value.lower() in (item.site_source or "").lower():
                        filtered_data.append(item)
                    elif operator == "does not contain" and value.lower() not in (item.site_source or "").lower():
                        filtered_data.append(item)
                elif criterion == "Size (px)":
                    if not item.size: continue
                    width, height = map(int, item.size.split(' x '))
                    pixel_count = width * height
                    if operator == "is greater than" and pixel_count > int(value):
                        filtered_data.append(item)
                    elif operator == "is less than" and pixel_count < int(value):
                        filtered_data.append(item)
                elif criterion == "Date":
                    if not item.parsed_date: continue
                    if operator == "is after" and item.parsed_date > value:
                        filtered_data.append(item)
                    elif operator == "is before" and item.parsed_date < value:
                        filtered_data.append(item)
                    elif operator == "is on" and item.parsed_date == value:
                        filtered_data.append(item)
                elif criterion == "Age":
                    if not item.parsed_age: continue
                    if operator == "older than (days)" and item.parsed_age > int(value):
                        filtered_data.append(item)
                    elif operator == "newer than (days)" and item.parsed_age < int(value):
                        filtered_data.append(item)
            except (ValueError, AttributeError, TypeError) as e:
                print(f"Could not apply filter for item {item.data_idx}: {e}")
                continue
        return filtered_data

    def update_grid(self, images):
        if self.debug:
            print(f"[DEBUG] update_grid called with {len(images)} images.")
        while self.results_layout.count():
            child = self.results_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        row, col = 0, 0
        for i, image_data in enumerate(images):
            if self.debug:
                print(f"[DEBUG] Adding image {i+1}/{len(images)} to grid: {image_data.title}")
            widget = ImageWidget(image_data, parent=self)
            widget.selected_signal.connect(self.on_image_selected)
            self.results_layout.addWidget(widget, row, col)
            col += 1
            if col == 6:
                col = 0
                row += 1
        if self.debug:
            print("[DEBUG] update_grid completed.")

    def on_image_selected(self, image_data):
        if self.debug:
            print(f"[DEBUG] Image selected: {image_data.title}")

        # Find the widget associated with the image data
        selected_widget = None
        for i in range(self.results_layout.count()):
            widget = self.results_layout.itemAt(i).widget()
            if widget and widget.data == image_data:
                selected_widget = widget
                break

        if selected_widget:
            if selected_widget.is_selected:
                if selected_widget not in self.selected_widgets:
                    self.selected_widgets.append(selected_widget)
            else:
                if selected_widget in self.selected_widgets:
                    self.selected_widgets.remove(selected_widget)

        if self.debug:
            print(f"[DEBUG] Selected widgets: {self.selected_widgets}")

        if self.selected_widgets:
            last_selected = self.selected_widgets[-1]
            if self.debug:
                print(f"[DEBUG] Last selected image data: {last_selected.data}")
            try:
                self.info_text.setText(
                    f"<b>Title:</b> {last_selected.data.title or 'N/A'}<br>"
                    f"<b>Size:</b> {last_selected.data.size or 'N/A'}<br>"
                    f"<b>Type:</b> {last_selected.data.file_type or 'N/A'}<br>"
                    f"<b>Date:</b> {last_selected.data.date or 'N/A'}<br>"
                    f"<b>Age:</b> {last_selected.data.ago or 'N/A'}<br>"
                    f"<b>Source:</b> {last_selected.data.site_source or 'N/A'}<br>"
                    f"<a href='{last_selected.data.image_source_url or '#'}'>Image Link</a>"
                )
                if self.debug:
                    print("[DEBUG] Sidebar info text set successfully.")
            except Exception as e:
                if self.debug:
                    print(f"[DEBUG] Error setting sidebar info text: {e}")
                self.signals.error.emit(f"Error displaying image details: {e}")
            self.sidebar.setVisible(True)
        else:
            self.sidebar.setVisible(False)

    def close_sidebar(self):
        self.sidebar.setVisible(False)
        for widget in self.selected_widgets:
            widget.is_selected = False
            widget.update()
        self.selected_widgets = []

    def download_selected(self):
        if not self.selected_widgets:
            QMessageBox.information(self, "No Images Selected", "Please select images to download.")
            return

        if self.debug:
            print(f"[DEBUG] Attempting to download {len(self.selected_widgets)} selected images.")

        if self.debug:
            print("[DEBUG] Entering download_selected method.")
        if not self.selected_widgets:
            QMessageBox.information(self, "No Images Selected", "Please select images to download.")
            if self.debug:
                print("[DEBUG] No images selected. Exiting download_selected.")
            return

        successful_downloads = 0
        failed_downloads = []

        if self.debug:
            print(f"[DEBUG] Attempting to download {len(self.selected_widgets)} selected images.")

        for widget in self.selected_widgets:
            if self.debug:
                print(f"[DEBUG] Downloading image: {widget.data.title}")
            try:
                self.downloader.download(widget.data)
                successful_downloads += 1
            except Exception as e:
                failed_downloads.append(f"{widget.data.title}: {e}")
                if self.debug:
                    print(f"[DEBUG] Download failed for {widget.data.title}: {e}")

        if self.debug:
            print("[DEBUG] All download attempts completed.")

        if successful_downloads > 0 and not failed_downloads:
            if self.debug:
                print(f"[DEBUG] About to show success QMessageBox for {successful_downloads} downloads.")
            QMessageBox.information(self, "Download Complete", f"Downloaded {successful_downloads} images.")
            if self.debug:
                print("[DEBUG] Success QMessageBox displayed and dismissed.")
        elif successful_downloads > 0 and failed_downloads:
            if self.debug:
                print(f"[DEBUG] About to show partial success QMessageBox for {successful_downloads} successful and {len(failed_downloads)} failed downloads.")
            QMessageBox.warning(self, "Download Partially Complete", 
                                f"Downloaded {successful_downloads} images. "
                                f"Failed to download {len(failed_downloads)} images:\n" +
                                "\n".join(failed_downloads))
            if self.debug:
                print("[DEBUG] Partial success QMessageBox displayed and dismissed.")
        else:
            if self.debug:
                print(f"[DEBUG] About to show total failure QMessageBox for {len(failed_downloads)} failed downloads.")
            QMessageBox.critical(self, "Download Failed", 
                                 f"Failed to download all selected images:\n" +
                                 "\n".join(failed_downloads))
            if self.debug:
                print("[DEBUG] Total failure QMessageBox displayed and dismissed.")
        
        if self.debug:
            print("[DEBUG] About to call close_sidebar.")
        self.close_sidebar()
        if self.debug:
            print("[DEBUG] close_sidebar called. Exiting download_selected method.")

    def on_details_finished(self, data):
        pass

    def on_error(self, error_message):
        QMessageBox.critical(self, "Error", error_message)
        self.search_button.setEnabled(True)
        self.search_button.setText("Search")
        self.load_more_button.setEnabled(True)
        self.load_more_button.setText("Load More")

def main():
    try:
        debug = "--debug" in sys.argv
        app = QApplication(sys.argv)
        app.setStyleSheet("""
            QWidget { background-color: #333; color: #EEE; }
            QPushButton { background-color: #555; border: 1px solid #777; padding: 5px; border-radius: 3px; }
            QPushButton:hover { background-color: #666; }
            QPushButton:pressed { background-color: #444; }
            QLineEdit, QComboBox, QDateEdit { background-color: #444; border: 1px solid #666; padding: 5px; border-radius: 3px; }
            QTextEdit, QScrollArea { background-color: #222; border: 1px solid #444; }
            QComboBox::drop-down { border: 0px; }
            QComboBox::down-arrow { image: url(no_arrow.png); }
        """)
        window = ImageSearchGUI(debug=debug)
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"[FATAL] An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
